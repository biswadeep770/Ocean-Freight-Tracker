from services import Rate

def search_rates(origin, destination, container_type):
    """
    Query the Rate database for matching lanes and equipment.
    Results are strictly sorted by lowest rate_usd first to highlight cheapest option.
    """
    return Rate.query.filter_by(
        origin_port=origin,
        destination_port=destination,
        container_type=container_type
    ).order_by(Rate.rate_usd.asc()).all()