from services import Shipment

def get_all_shipments():
    """
    Returns a list of all shipments, descending by departure date.
    """
    return Shipment.query.order_by(Shipment.departure_date.desc()).all()

def get_dashboard_stats():
    """
    Calculates aggregated statistics for the global visibility dashboard.
    """
    shipments = get_all_shipments()
    total = len(shipments)
    in_transit = len([s for s in shipments if s.status == "In Transit"])
    delivered = len([s for s in shipments if s.status == "Delivered"])
    delayed = len([s for s in shipments if s.status == "Delayed"])
    
    return {
        "total": total,
        "in_transit": in_transit,
        "delivered": delivered,
        "delayed": delayed
    }