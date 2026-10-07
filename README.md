# Ocean Freight Rate & Shipment Tracker

A Flask-based logistics management prototype for searching ocean freight rates, tracking shipments, checking invoices against contracted rates, and automatically processing operational updates received through sample emails.

## 1. Project Overview

The Ocean Freight Rate & Shipment Tracker provides four core capabilities:

1. **Rate Search**
   - Search freight rates by origin, destination, and container type.
   - Compare multiple carriers.
   - Sort results by price.
   - Display transit time.
   - Highlight the cheapest available option.

2. **Shipment Tracker**
   - View shipment records and operational status.
   - Add new shipments manually.
   - Automatically classify shipments as:
     - In Transit
     - Delivered
     - Delayed
   - Delayed status is determined when today's date is later than the expected arrival date and the shipment has not been delivered.

3. **Invoice Checker**
   - Select a shipment.
   - Enter the final invoice amount.
   - Compare it against the current contracted carrier rate.
   - Report:
     - Correct
     - Overcharged by USD X

4. **Email-Based Rate & Shipment Updates**
   - Process the supplied sample email batch.
   - Extract rate updates from operational emails.
   - Extract shipment IDs and shipment status updates.
   - Update the rate and shipment database.
   - Safely skip irrelevant or incomplete emails.
   - Maintain an auditable processing log.

## 2. Technology Stack

- Python 3
- Flask
- Flask-SQLAlchemy
- SQLite
- Jinja2
- HTML5
- CSS3
- JavaScript
- Werkzeug password hashing

## 3. Project Structure

```text
Ocean-Freight-Tracker/
│
├── app.py
├── config.py
├── requirements.txt
├── README.md
├── .gitignore
│
├── data/
│   ├── carrier_rates.csv
│   ├── sample_shipments.csv
│   └── sample_emails.txt
│
├── database/
│   └── ocean_freight.db
│
├── services/
│   ├── __init__.py
│   ├── rate_service.py
│   ├── shipment_service.py
│   ├── invoice_service.py
│   └── email_parser.py
│
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── rates.html
│   ├── shipments.html
│   ├── invoices.html
│   └── emails.html
│
└── static/
    ├── css/
    │   └── app.css
    └── js/
        └── app.js