import os
import csv
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
from services import db, User, Rate, Shipment, EmailLog
from services.rate_service import search_rates
from services.shipment_service import get_all_shipments, get_dashboard_stats
from services.invoice_service import verify_invoice
from services.email_parser import parse_inbox_emails

app = Flask(__name__)
app.config.from_object(Config)

# Initialize database mapping
db.init_app(app)

# --- AUTHENTICATION DECORATORS ---

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access the system.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'Admin':
            flash("Unauthorized access. Admin privileges required.", "error")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# --- DATABASE INITIALIZATION & SEEDING ---

def initialize_database():
    """
    Executes within the application context to safely create tables
    and ingest static CSV data only if the tables are empty.
    """
    with app.app_context():
        db.create_all()
        
        # Seed Demo Users securely if the table is empty
        if not User.query.first():
            admin_user = User(
                username='admin',
                password_hash=generate_password_hash('adminpass'),
                role='Admin'
            )
            standard_user = User(
                username='user',
                password_hash=generate_password_hash('userpass'),
                role='User'
            )
            db.session.add_all([admin_user, standard_user])
            db.session.commit()

        # Seed Carrier Rates
        if not Rate.query.first() and os.path.exists('data/carrier_rates.csv'):
            with open('data/carrier_rates.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    transit_val = int(row['transit_days']) if row['transit_days'].strip() else None
                    rate = Rate(
                        carrier=row['carrier'].strip(),
                        origin_port=row['origin_port'].strip(),
                        destination_port=row['destination_port'].strip(),
                        container_type=row['container_type'].strip(),
                        rate_usd=float(row['rate_usd']),
                        transit_days=transit_val
                    )
                    db.session.add(rate)
            db.session.commit()

        # Seed Sample Shipments
        if not Shipment.query.first() and os.path.exists('data/sample_shipments.csv'):
            with open('data/sample_shipments.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    dept_date = datetime.strptime(row['departure_date'].strip(), '%Y-%m-%d').date() if row.get('departure_date') else None
                    arr_date = datetime.strptime(row['expected_arrival'].strip(), '%Y-%m-%d').date() if row.get('expected_arrival') else None
                    deliv_date = datetime.strptime(row['delivered_date'].strip(), '%Y-%m-%d').date() if row.get('delivered_date') else None
                    
                    shipment = Shipment(
                        shipment_id=row['shipment_id'].strip(),
                        carrier=row['carrier'].strip(),
                        origin_port=row['origin_port'].strip(),
                        destination_port=row['destination_port'].strip(),
                        container_type=row['container_type'].strip(),
                        departure_date=dept_date,
                        expected_arrival=arr_date,
                        delivered_date=deliv_date,
                        invoice_amount_usd=float(row['invoice_amount_usd'])
                    )
                    db.session.add(shipment)
            db.session.commit()

with app.app_context():
    initialize_database()

# --- TEMPLATE FILTERS & CONTEXT ---

@app.template_filter('currency')
def format_currency(value):
    """Jinja filter to standardize USD formatting."""
    try:
        return f"${float(value):,.2f}"
    except (ValueError, TypeError):
        return ""

@app.context_processor
def inject_user():
    """Injects user role into all templates for frontend rendering logic."""
    return dict(current_role=session.get('role'), current_user=session.get('username'))

# --- APPLICATION ROUTES ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid credentials.", "error")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    stats = get_dashboard_stats()
    recent_rates = Rate.query.order_by(Rate.id.desc()).limit(5).all()
    delayed_shipments = [s for s in get_all_shipments() if s.status == 'Delayed'][:5]
    
    return render_template('dashboard.html', stats=stats, recent_rates=recent_rates, delayed=delayed_shipments)

@app.route('/rates', methods=['GET'])
@login_required
def rates():
    origins = [r.origin_port for r in db.session.query(Rate.origin_port).distinct()]
    destinations = [r.destination_port for r in db.session.query(Rate.destination_port).distinct()]
    
    origin_query = request.args.get('origin_port', '')
    dest_query = request.args.get('destination_port', '')
    container_query = request.args.get('container_type', '')
    
    results = []
    if origin_query and dest_query and container_query:
        results = search_rates(origin_query, dest_query, container_query)
        
    return render_template('rates.html', 
                           origins=origins, 
                           destinations=destinations, 
                           results=results,
                           query={'origin': origin_query, 'dest': dest_query, 'container': container_query})

@app.route('/shipments', methods=['GET', 'POST'])
@login_required
def shipments():
    if request.method == 'POST':
        shipment_id = request.form.get('shipment_id', '').strip()
        carrier = request.form.get('carrier', '').strip()
        origin = request.form.get('origin_port', '').strip()
        dest = request.form.get('destination_port', '').strip()
        container = request.form.get('container_type', '').strip()
        dept_date_str = request.form.get('departure_date', '').strip()
        arr_date_str = request.form.get('expected_arrival', '').strip()
        deliv_date_str = request.form.get('delivered_date', '').strip()
        invoice_amt = request.form.get('invoice_amount_usd', '0').strip()

        if Shipment.query.filter_by(shipment_id=shipment_id).first():
            flash(f"Shipment ID {shipment_id} already exists.", "error")
        else:
            try:
                dept_date = datetime.strptime(dept_date_str, '%Y-%m-%d').date() if dept_date_str else None
                arr_date = datetime.strptime(arr_date_str, '%Y-%m-%d').date() if arr_date_str else None
                deliv_date = datetime.strptime(deliv_date_str, '%Y-%m-%d').date() if deliv_date_str else None

                new_shp = Shipment(
                    shipment_id=shipment_id,
                    carrier=carrier,
                    origin_port=origin,
                    destination_port=dest,
                    container_type=container,
                    departure_date=dept_date,
                    expected_arrival=arr_date,
                    delivered_date=deliv_date,
                    invoice_amount_usd=float(invoice_amt)
                )
                db.session.add(new_shp)
                db.session.commit()
                flash(f"Shipment {shipment_id} added successfully.", "success")
            except Exception as e:
                flash(f"Error adding shipment: {str(e)}", "error")
        
        return redirect(url_for('shipments'))

    all_shipments = get_all_shipments()
    search = request.args.get('search', '').lower()
    
    if search:
        all_shipments = [s for s in all_shipments if search in s.shipment_id.lower() or search in s.carrier.lower()]
        
    return render_template('shipments.html', shipments=all_shipments, search=search)

@app.route('/invoices', methods=['GET', 'POST'])
@login_required
def invoices():
    shipment_list = Shipment.query.all()
    result = None
    selected_shp = None
    
    if request.method == 'POST':
        shipment_id = request.form.get('shipment_id')
        user_invoice_amt = request.form.get('invoice_amount')
        
        if shipment_id and user_invoice_amt:
            try:
                amt = float(user_invoice_amt)
                result = verify_invoice(shipment_id, amt)
                selected_shp = Shipment.query.filter_by(shipment_id=shipment_id).first()
            except ValueError:
                flash("Invalid numeric format for invoice amount.", "error")
            
    return render_template('invoices.html', shipments=shipment_list, result=result, selected_shp=selected_shp)

@app.route('/emails', methods=['GET'])
@admin_required
def emails():
    logs = EmailLog.query.order_by(EmailLog.timestamp.desc()).all()
    
    stats = {
        'processed': len(logs),
        'updated': len([L for L in logs if L.result == 'Success']),
        'skipped': len([L for L in logs if L.result == 'Skipped']),
        'errors': len([L for L in logs if L.classification == 'Error'])
    }
    
    return render_template('emails.html', logs=logs, stats=stats)

@app.route('/emails/process', methods=['POST'])
@admin_required
def process_emails():
    # Trigger the automated parser
    file_path = os.path.join(app.root_path, 'data', 'sample_emails.txt')
    parse_inbox_emails(file_path)
    flash("Email processing batch complete.", "success")
    return redirect(url_for('emails'))

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)