from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False) # Roles: 'Admin' or 'User'

class Rate(db.Model):
    __tablename__ = 'rates'
    id = db.Column(db.Integer, primary_key=True)
    carrier = db.Column(db.String(100), nullable=False)
    origin_port = db.Column(db.String(100), nullable=False)
    destination_port = db.Column(db.String(100), nullable=False)
    container_type = db.Column(db.String(20), nullable=False)
    rate_usd = db.Column(db.Float, nullable=False)
    transit_days = db.Column(db.Integer, nullable=True) # Now allows None for unprovided transit times

class Shipment(db.Model):
    __tablename__ = 'shipments'
    id = db.Column(db.Integer, primary_key=True)
    shipment_id = db.Column(db.String(50), unique=True, nullable=False)
    carrier = db.Column(db.String(100), nullable=False)
    origin_port = db.Column(db.String(100), nullable=False)
    destination_port = db.Column(db.String(100), nullable=False)
    container_type = db.Column(db.String(20), nullable=False)
    departure_date = db.Column(db.Date, nullable=True)
    expected_arrival = db.Column(db.Date, nullable=True)
    delivered_date = db.Column(db.Date, nullable=True)
    invoice_amount_usd = db.Column(db.Float, nullable=False)

    @property
    def status(self):
        """
        Dynamically calculates status avoiding static database staleness.
        Rules:
        - Delivered if delivered_date exists.
        - Delayed if delivered_date is empty AND today's date is after expected_arrival.
        - Otherwise In Transit.
        """
        if self.delivered_date is not None:
            return "Delivered"
        
        if self.expected_arrival is not None:
            if date.today() > self.expected_arrival and self.delivered_date is None:
                return "Delayed"
                
        return "In Transit"

class EmailLog(db.Model):
    __tablename__ = 'email_logs'
    id = db.Column(db.Integer, primary_key=True)
    email_content = db.Column(db.Text, nullable=False)
    classification = db.Column(db.String(50), nullable=False)
    result = db.Column(db.String(50), nullable=False)
    reason = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)