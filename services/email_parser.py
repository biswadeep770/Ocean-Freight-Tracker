import os
import re
from datetime import datetime
from services import db, Rate, Shipment, EmailLog


def _parse_date(text):
    """Parse the date formats used in the supplied sample emails."""
    patterns = [
        (r"\b(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})\b", "%d %b %Y"),
        (r"\b(\d{1,2}\s+[A-Za-z]+\s+\d{4})\b", "%d %B %Y"),
        (r"\b(\d{4}-\d{2}-\d{2})\b", "%Y-%m-%d"),
    ]

    for pattern, date_format in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                return datetime.strptime(match.group(1), date_format).date()
            except ValueError:
                pass

    return None


def _extract_shipment_id(text):
    """Only accept real shipment IDs such as SHP1007."""
    match = re.search(r"\bSHP\d{4,}\b", text, re.IGNORECASE)
    return match.group(0).upper() if match else None


def _extract_carrier(text):
    """Match carriers against the carriers already loaded in the database."""
    carriers = [
        row[0]
        for row in db.session.query(Rate.carrier).distinct().all()
    ]

    text_lower = text.lower()

    for carrier in sorted(carriers, key=len, reverse=True):
        if carrier.lower() in text_lower:
            return carrier

    # Useful aliases for the supplied sample emails.
    aliases = {
        "oceanlink": "OceanLink Lines",
        "bluewave": "BlueWave Shipping",
        "globalmariner": "GlobalMariner",
        "pacificstar": "PacificStar Line",
        "atlassea": "AtlasSea Carriers",
    }

    for alias, carrier in aliases.items():
        if alias in text_lower:
            return carrier

    return None


def _extract_route(text):
    """
    Find the first origin port and first destination port mentioned
    in the sample email.
    """
    origins = [
        row[0]
        for row in db.session.query(Rate.origin_port).distinct().all()
    ]

    destinations = [
        row[0]
        for row in db.session.query(Rate.destination_port).distinct().all()
    ]

    origin_matches = []
    destination_matches = []

    text_lower = text.lower()

    for port in origins:
        pos = text_lower.find(port.lower())
        if pos >= 0:
            origin_matches.append((pos, port))

    for port in destinations:
        pos = text_lower.find(port.lower())
        if pos >= 0:
            destination_matches.append((pos, port))

    origin = min(origin_matches, key=lambda x: x[0])[1] if origin_matches else None
    destination = (
        min(destination_matches, key=lambda x: x[0])[1]
        if destination_matches
        else None
    )

    return origin, destination


def _extract_container_type(text):
    match = re.search(r"\b(20ft|40ft)\b", text, re.IGNORECASE)
    return match.group(1).lower() if match else None


def _extract_rate(text):
    match = re.search(
        r"(?:USD|\$)\s*([0-9]+(?:\.[0-9]+)?)",
        text,
        re.IGNORECASE
    )
    return float(match.group(1)) if match else None


def parse_inbox_emails(filepath):
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # The supplied sample uses a line of dashes between emails.
    # Discard the introductory text before the first actual email.
    chunks = re.split(r"(?m)^\s*-{10,}\s*$", content)

    emails = [
        chunk.strip()
        for chunk in chunks
        if re.search(r"(?m)^From:\s*", chunk)
    ]

    # Each processing run represents one fresh inbox batch.
    # This prevents duplicate log rows when the demo button is clicked again.
    EmailLog.query.delete()
    db.session.commit()

    for email_text in emails:
        email_text = email_text.strip()

        if not email_text:
            continue

        text_lower = email_text.lower()
        log_preview = (
            email_text[:150] + "..."
            if len(email_text) > 150
            else email_text
        )

        try:
            # ---------------------------------------------------------
            # RATE EMAIL
            # ---------------------------------------------------------
            rate_signal = bool(
                re.search(
                    r"\b(rate|tariff|quote)\b",
                    text_lower,
                    re.IGNORECASE
                )
            )

            if rate_signal:
                carrier = _extract_carrier(email_text)
                origin, destination = _extract_route(email_text)
                container_type = _extract_container_type(email_text)
                rate_value = _extract_rate(email_text)

                # A rate email without complete rate data is safely skipped.
                if not (
                    carrier
                    and origin
                    and destination
                    and container_type
                    and rate_value is not None
                ):
                    log = EmailLog(
                        email_content=log_preview,
                        classification="Skipped",
                        result="Skipped",
                        reason="Incomplete rate email; required rate fields were not available."
                    )
                    db.session.add(log)
                    continue

                rate = Rate.query.filter_by(
                    carrier=carrier,
                    origin_port=origin,
                    destination_port=destination,
                    container_type=container_type
                ).first()

                if rate:
                    rate.rate_usd = rate_value
                    action = f"Updated contracted rate to USD {rate_value:.2f}"
                else:
                    rate = Rate(
                        carrier=carrier,
                        origin_port=origin,
                        destination_port=destination,
                        container_type=container_type,
                        rate_usd=rate_value,
                        transit_days=None
                    )
                    db.session.add(rate)
                    action = f"Inserted new contracted rate USD {rate_value:.2f}"

                db.session.add(
                    EmailLog(
                        email_content=log_preview,
                        classification="Rate Update",
                        result="Success",
                        reason=action
                    )
                )
                continue

            # ---------------------------------------------------------
            # SHIPMENT EMAIL
            # ---------------------------------------------------------
            shipment_signal = bool(
                re.search(
                    r"\bshipment\b|\bdelivered\b|\bdelayed\b|\bin transit\b",
                    text_lower,
                    re.IGNORECASE
                )
            )

            if shipment_signal:
                shipment_id = _extract_shipment_id(email_text)

                if not shipment_id:
                    db.session.add(
                        EmailLog(
                            email_content=log_preview,
                            classification="Skipped",
                            result="Skipped",
                            reason="Shipment email did not contain a valid shipment ID."
                        )
                    )
                    continue

                shipment = Shipment.query.filter_by(
                    shipment_id=shipment_id
                ).first()

                if not shipment:
                    db.session.add(
                        EmailLog(
                            email_content=log_preview,
                            classification="Skipped",
                            result="Skipped",
                            reason=f"Shipment {shipment_id} was not found in the tracker."
                        )
                    )
                    continue

                event_date = _parse_date(email_text)

                # Delivered email: store the actual delivery date.
                if re.search(r"\bdelivered\b", text_lower):
                    if event_date:
                        shipment.delivered_date = event_date

                    reason = (
                        f"Shipment {shipment_id} marked Delivered"
                        + (f" on {event_date}" if event_date else "")
                    )

                # Delayed email: record the operational update.
                # The dashboard's formal Delayed status still follows
                # the assignment rule based on expected_arrival.
                elif re.search(r"\bdelayed\b|\bdelay\b", text_lower):
                    reason = f"Shipment {shipment_id} delayed update received"

                # In-transit email: record the operational update.
                elif re.search(r"\bin transit\b", text_lower):
                    reason = f"Shipment {shipment_id} in-transit update received"

                else:
                    db.session.add(
                        EmailLog(
                            email_content=log_preview,
                            classification="Skipped",
                            result="Skipped",
                            reason="No supported shipment status was detected."
                        )
                    )
                    continue

                db.session.add(
                    EmailLog(
                        email_content=log_preview,
                        classification="Shipment Update",
                        result="Success",
                        reason=reason
                    )
                )
                continue

            # ---------------------------------------------------------
            # IRRELEVANT EMAIL
            # ---------------------------------------------------------
            db.session.add(
                EmailLog(
                    email_content=log_preview,
                    classification="Irrelevant",
                    result="Skipped",
                    reason="No actionable logistics information detected."
                )
            )

        except Exception as exc:
            # Roll back the current transaction so one malformed email
            # cannot poison the entire batch.
            db.session.rollback()

            db.session.add(
                EmailLog(
                    email_content=log_preview,
                    classification="Error",
                    result="Skipped",
                    reason=f"Unexpected parser exception: {exc}"
                )
            )

    db.session.commit()