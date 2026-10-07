from services import Rate, Shipment

def verify_invoice(shipment_id, user_invoice_amount):
    """
    Validates a manually provided invoice amount against the active contracted rate.
    Checks exact matches for carrier, origin, destination, and container_type.
    """
    shipment = Shipment.query.filter_by(shipment_id=shipment_id).first()
    if not shipment:
        return {"error": "Shipment not found."}
        
    rate = Rate.query.filter_by(
        carrier=shipment.carrier,
        origin_port=shipment.origin_port,
        destination_port=shipment.destination_port,
        container_type=shipment.container_type
    ).first()
    
    if not rate:
        return {
            "error": "No matching contracted rate found for this shipment's parameters."
        }
        
    diff = user_invoice_amount - rate.rate_usd
    
    if diff <= 0:
        return {
            "status": "Correct",
            "contracted": rate.rate_usd,
            "invoice": user_invoice_amount,
            "difference": 0
        }
    else:
        return {
            "status": "Overcharged",
            "contracted": rate.rate_usd,
            "invoice": user_invoice_amount,
            "difference": diff
        }