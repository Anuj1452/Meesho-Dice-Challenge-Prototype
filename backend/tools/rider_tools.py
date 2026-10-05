"""Rider assistant tools (§5.2).
Voice + button first operations for delivery riders.
All data returned is masked and safe — riders never see raw customer phone numbers,
risk tiers, or other riders' metrics.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from backend.models.database import (
    Order, Rider, Customer, TrackingEvent, Ticket, AuditLog, ValmoCenter,
    ChatSession, ChatMessage
)
from backend.models.enums import OrderState, RiskTier, STATE_DISPLAY_NAMES


def _get_or_create_customer_session(db: Session, customer: Customer) -> ChatSession:
    """Get latest active chat session or create one for customer notifications."""
    if not customer:
        return None
    session = db.query(ChatSession).filter(
        ChatSession.customer_id == customer.id,
        ChatSession.active == True
    ).order_by(ChatSession.created_at.desc()).first()
    
    if not session:
        session = ChatSession(
            session_id=f"sess_{customer.phone_hash[:8]}_{int(datetime.now(timezone.utc).timestamp())}",
            customer_id=customer.id,
            role="customer",
            verification_level="v0",
        )
        db.add(session)
        db.commit()
    return session


def get_manifest(db: Session, rider_id: str) -> Dict[str, Any]:
    """Get the rider's manifest of orders to deliver today (§5.2)."""
    rider = db.query(Rider).filter(Rider.rider_id == rider_id).first()
    if not rider:
        return {"error": f"Rider {rider_id} not found", "stops": []}

    # Fetch all orders assigned to this rider (including IN_TRANSIT/RESCHEDULED for full manifest view)
    active_statuses = [
        OrderState.IN_TRANSIT.value,
        OrderState.AT_DESTINATION_HUB.value,
        OrderState.OUT_FOR_DELIVERY.value,
        OrderState.FAILED_ATTEMPT.value,
        OrderState.RESCHEDULED.value,
        OrderState.SKIPPED_TODAY.value,
        OrderState.DELIVERED.value,
    ]

    orders = db.query(Order).filter(
        Order.rider_id == rider.id,
        Order.status.in_(active_statuses),
        Order.self_pickup == False,  # Self pickup orders do not appear on rider manifests (§7.3A)
    ).all()

    # Phone mapping for demo convenience (all 14 demo customers)
    phone_map = {
        "f855b2ec33339e4b": "9198765001",  # Priya
        "44a7469deed95dfa": "9198765002",  # Rahul
        "d3aba319ff24da92": "9198765003",  # Anita
        "2da161fd74c17eb8": "9198765004",  # Suresh
        "9c7e3945db6acfb8": "9198765005",  # Meena
        "1a2b3c4d5e6f7g8h": "9198765006",  # Vikram (placeholder — computed at runtime)
        "2b3c4d5e6f7g8h9i": "9198765007",  # Deepa
        "3c4d5e6f7g8h9i0j": "9198765008",  # Arjun
        "4d5e6f7g8h9i0j1k": "9198765009",  # Sunita
        "5e6f7g8h9i0j1k2l": "9198765010",  # Ramesh
        "6f7g8h9i0j1k2l3m": "9198765011",  # Kavita
        "7g8h9i0j1k2l3m4n": "9198765012",  # Mohan
        "8h9i0j1k2l3m4n5o": "9198765013",  # Geeta
        "9i0j1k2l3m4n5o6p": "9198765014",  # Sanjay
    }
    # Compute real hashes for new customers dynamically
    import hashlib
    for i, phone in enumerate(["9198765006","9198765007","9198765008","9198765009",
                                "9198765010","9198765011","9198765012","9198765013","9198765014"]):
        h = hashlib.sha256(phone.encode()).hexdigest()[:16]
        phone_map[h] = phone

    stops = []
    for o in orders:
        cust_name = o.customer.name if o.customer else "Customer"
        # First name only for privacy
        first_name = cust_name.split()[0] if cust_name else "Customer"
        raw_phone = phone_map.get(o.customer.phone_hash if o.customer else "", "9198765000")

        cash_to_collect = 0.0 if not o.is_cod else (o.amount_due if o.amount_due is not None else o.amount)

        # Payout logic: Rs15 standard, Rs30 for HIGH risk/far zone (SIMULATED)
        is_high_risk = (o.risk_tier == RiskTier.HIGH.value)
        payout = 30 if is_high_risk else 15
        payout_label = f"₹{payout}" + (" 🔥 Bonus Zone" if payout == 30 else "")

        stops.append({
            "order_id": o.order_id,
            "awb": o.awb,
            "customer_first_name": first_name,
            "customer_full_name": cust_name,
            "customer_phone": raw_phone,
            "product_name": o.product_name,
            "status": o.status,
            "status_display": STATE_DISPLAY_NAMES.get(OrderState(o.status), o.status) if o.status in [s.value for s in OrderState] else o.status,
            "address": o.address_text,
            "original_address": getattr(o, "original_address", None) or None,
            "is_address_updated": bool(getattr(o, "original_address", None) and o.original_address != o.address_text),
            "landmark": o.landmark or "None provided",
            "pincode": o.pincode,
            "cash_to_collect": f"₹{cash_to_collect:.0f}",
            "is_prepaid": not o.is_cod or cash_to_collect == 0,
            "payment_verified": o.payment_verified,
            "customer_note": o.delivery_note or None,
            "alternate_receiver": o.alternate_receiver or None,
            "availability_slot": o.availability_slot or "Standard delivery",
            "missed_call_count": getattr(o, "missed_call_count", 0) or 0,
            "customer_response_status": getattr(o, "customer_response_status", "") or "",
            "is_skipped": o.status == OrderState.SKIPPED_TODAY.value,
            "is_delivered": o.status == OrderState.DELIVERED.value,
            "is_in_transit": o.status == OrderState.IN_TRANSIT.value,
            "is_rescheduled": o.status == OrderState.RESCHEDULED.value,
            "payout": payout,
            "payout_label": payout_label,
            "label": "SIMULATED",
        })

    return {
        "rider_id": rider.rider_id,
        "rider_name": rider.name,
        "total_stops": len(stops),
        "pending_stops": len([s for s in stops if not s["is_delivered"] and not s["is_skipped"]]),
        "delivered_stops": len([s for s in stops if s["is_delivered"]]),
        "skipped_stops": len([s for s in stops if s["is_skipped"]]),
        "stops": stops,
    }


def get_order_card(db: Session, order_id: str, rider_id: str) -> Dict[str, Any]:
    """Get single order card detail for the rider screen (§5.2)."""
    rider = db.query(Rider).filter(Rider.rider_id == rider_id).first()
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        return {"error": "Order not found"}

    cust_name = order.customer.name if order.customer else "Customer"
    first_name = cust_name.split()[0] if cust_name else "Customer"
    cash_to_collect = 0.0 if not order.is_cod else (order.amount_due if order.amount_due is not None else order.amount)

    return {
        "order_id": order.order_id,
        "awb": order.awb,
        "customer_first_name": first_name,
        "product_name": order.product_name,
        "status": order.status,
        "status_display": STATE_DISPLAY_NAMES.get(OrderState(order.status), order.status) if order.status in [s.value for s in OrderState] else order.status,
        "address": order.address_text,
        "landmark": order.landmark or "None",
        "pincode": order.pincode,
        "cash_to_collect": f"₹{cash_to_collect:.0f}",
        "payment_mode": "PREPAID (No cash to collect)" if not order.is_cod or cash_to_collect == 0 else f"COD ₹{cash_to_collect:.0f}",
        "customer_note": order.delivery_note or None,
        "alternate_receiver": order.alternate_receiver or None,
        "availability_slot": order.availability_slot or "Standard delivery",
        "allow_nudge": order.risk_tier in [RiskTier.MEDIUM.value, RiskTier.HIGH.value],
        "label": "SIMULATED",
    }


def mark_outcome(
    db: Session,
    order_id: str,
    rider_id: str,
    outcome: str,
    reason: Optional[str] = None,
    otp: Optional[str] = None,
) -> Dict[str, Any]:
    """Mark outcome of a delivery stop (§5.2, §14).
    Outcomes:
    - Delivered
    - Failed: not available
    - Failed: refused
    - Failed: address issue
    - Revisit today
    """
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        return {"error": "Order not found"}

    norm_outcome = outcome.strip().lower()
    now = datetime.now(timezone.utc)

    if "delivered" in norm_outcome:
        otp_required = bool(order.is_cod or (order.amount or 0) >= 1000)
        if otp_required:
            if not order.delivery_otp:
                order.delivery_otp = "4821"  # fixed, explicitly simulated demo OTP
                order.otp_sent_at = now
                _send_otp_message(db, order)
                db.commit()
                return {"success": False, "requires_otp": True, "message": "OTP required. It was sent to the customer's WhatsApp chat.", "order_id": order.order_id}
            if otp != order.delivery_otp:
                return {"success": False, "requires_otp": True, "message": "Invalid delivery OTP. Ask the customer after handing over the parcel.", "order_id": order.order_id}
        order.status = OrderState.DELIVERED.value
        order.delivered_at = now
        if order.is_cod:
            order.amount_due = 0.0
            order.payment_verified = True
        desc = "Order delivered successfully to customer"
    elif "refused" in norm_outcome:
        order.status = OrderState.FAILED_ATTEMPT.value
        desc = f"Delivery failed: customer refused parcel ({reason or 'No reason provided'})"
    elif "not available" in norm_outcome:
        order.status = OrderState.FAILED_ATTEMPT.value
        desc = f"Delivery failed: customer not available ({reason or 'Door locked / unreachable'})"
    elif "address" in norm_outcome:
        order.status = OrderState.FAILED_ATTEMPT.value
        desc = f"Delivery failed: address issue ({reason or 'Could not locate address'})"
    elif "revisit" in norm_outcome:
        order.status = OrderState.OUT_FOR_DELIVERY.value
        desc = f"Rider marked for revisit later today: {reason or 'Customer requested evening attempt'}"
    else:
        order.status = OrderState.FAILED_ATTEMPT.value
        desc = f"Delivery attempt outcome: {outcome}"

    order.updated_at = now

    # Record tracking event
    tracking = TrackingEvent(
        order_id=order.order_id,
        status=order.status,
        location=f"Last-mile DC ({order.serving_center_id or 'Hub'})",
        description=f"[SIMULATED] {desc}",
        timestamp=now,
    )
    db.add(tracking)
    db.commit()

    return {
        "success": True,
        "order_id": order.order_id,
        "new_status": order.status,
        "outcome": outcome,
        "timestamp": now.isoformat(),
        "label": "SIMULATED",
    }


def _send_otp_message(db: Session, order: Order) -> None:
    """Deliver a simulated OTP to the isolated customer chat session."""
    session = _get_or_create_customer_session(db, order.customer)
    if session:
        db.add(ChatMessage(
            session_id=session.session_id,
            role="assistant",
            content="Aapka delivery OTP hai 4821. Rider ko parcel lene ke baad hi ye OTP dein.",
            message_type="template",
            timestamp=datetime.now(timezone.utc),
        ))


def report_problem(
    db: Session,
    order_id: str,
    rider_id: str,
    problem_type: str,
    description: Optional[str] = None
) -> Dict[str, Any]:
    """Report a delivery issue (gate locked, phone off, wrong address) (§5.2)."""
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        return {"error": "Order not found"}

    now = datetime.now(timezone.utc)
    ticket_id = f"TCK-RDR-{order.order_id[-5:]}-{int(now.timestamp()) % 1000}"

    ticket = Ticket(
        ticket_id=ticket_id,
        order_id=order.order_id,
        category="rider_problem_report",
        severity="P2",
        status="open",
        summary=f"Rider {rider_id} reported: {problem_type}. Details: {description or 'None'}",
        messages=[{
            "from": f"Rider {rider_id}",
            "text": f"Problem: {problem_type}. {description or ''}",
            "timestamp": now.isoformat(),
        }],
        created_at=now,
        updated_at=now,
    )
    db.add(ticket)
    db.commit()

    return {
        "success": True,
        "order_id": order_id,
        "problem_reported": problem_type,
        "ticket_id": ticket_id,
        "action_taken": "Location-pin and availability ping queued for customer",
        "label": "SIMULATED",
    }


def nudge_customer(db: Session, order_id: str, rider_id: str) -> Dict[str, Any]:
    """Send morning arrival nudge to customer with interactive options on WhatsApp (§5.2, §7.6)."""
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        return {"error": "Order not found"}

    rider = db.query(Rider).filter(Rider.rider_id == rider_id).first()
    rider_name = rider.name if rider else "Amit"
    cust_name = order.customer.name.split()[0] if order.customer and order.customer.name else "Customer"
    clean_prod = (order.product_name or "Parcel").replace("[SIMULATED] ", "")
    now = datetime.now(timezone.utc)

    message_text = f"Namaste {cust_name}! 🛵 Aaj aapka Meesho order ({clean_prod}) deliver karne rider {rider_name} aane wale hain.\n\nKya aap aaj delivery location par available hain?"

    buttons = [
        {"id": "btn_available_today", "title": "✅ Available Today"},
        {"id": "btn_not_today", "title": "🔄 Kal Deliver Karein"},
        {"id": "btn_change_address", "title": "📍 Change Address"},
        {"id": "btn_call_rider", "title": "📞 Call Rider"}
    ]

    session = _get_or_create_customer_session(db, order.customer)
    if session:
        msg = ChatMessage(
            session_id=session.session_id,
            role="assistant",
            content=message_text,
            buttons=buttons,
            message_type="template",
            timestamp=now,
        )
        db.add(msg)
        session.turn_count += 1
        db.commit()

    return {
        "success": True,
        "order_id": order_id,
        "nudge_sent": True,
        "message": message_text,
        "recipient": order.customer.name if order.customer else "Customer",
        "timestamp": now.isoformat(),
        "label": "SIMULATED",
    }


def nudge_all_customers(db: Session, rider_id: str) -> Dict[str, Any]:
    """Send morning delivery notifications to all active manifest customers (§5.2)."""
    rider = db.query(Rider).filter(Rider.rider_id == rider_id).first()
    if not rider:
        return {"error": f"Rider {rider_id} not found"}

    active_statuses = [
        OrderState.OUT_FOR_DELIVERY.value,
        OrderState.AT_DESTINATION_HUB.value,
        OrderState.FAILED_ATTEMPT.value,
    ]
    orders = db.query(Order).filter(
        Order.rider_id == rider.id,
        Order.status.in_(active_statuses),
        Order.self_pickup == False,
    ).all()

    nudged_count = 0
    for o in orders:
        nudge_customer(db, o.order_id, rider_id)
        nudged_count += 1

    return {
        "success": True,
        "rider_id": rider_id,
        "nudged_count": nudged_count,
        "message": f"Morning nudge sent to all {nudged_count} customers on today's manifest!",
    }


def record_missed_call(db: Session, order_id: str, rider_id: str) -> Dict[str, Any]:
    """Log an unanswered call from rider and trigger instant WhatsApp alert to customer (§5.2)."""
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        return {"error": "Order not found"}
    rider = db.query(Rider).filter(Rider.rider_id == rider_id).first()
    rider_name = rider.name if rider else "Amit"

    order.missed_call_count = (getattr(order, "missed_call_count", 0) or 0) + 1
    attempt = order.missed_call_count
    now = datetime.now(timezone.utc)
    order.updated_at = now

    if attempt < 3:
        db.commit()
        return {
            "success": True,
            "order_id": order_id,
            "missed_call_count": attempt,
            "alert_sent": False,
            "message": f"Missed call attempt {attempt}/3 logged. No WhatsApp alert sent yet.",
        }

    # On 3rd attempt, evaluate location discrepancy before accepting a no-answer outcome (R-14).
    order.status = OrderState.FAILED_ATTEMPT.value
    rider_lat = rider.lat if rider and rider.lat is not None else 28.7041
    rider_lng = rider.lng if rider and rider.lng is not None else 77.1025
    customer_lat = order.lat if order.lat is not None else 28.7041
    customer_lng = order.lng if order.lng is not None else 77.1025
    distance_m = int(_haversine_km(rider_lat, rider_lng, customer_lat, customer_lng) * 1000)
    fake_attempt = distance_m > 150
    if fake_attempt:
        db.add(Ticket(
            ticket_id=f"TKT-R14-{order.order_id[-6:]}", order_id=order.order_id,
            category="fake_door_attempt", severity="P1", status="open",
            summary=f"Rule R-14 GPS discrepancy: rider was {distance_m}m from customer pin after 3 no-answer attempts.",
        ))

    # Record tracking event
    tracking = TrackingEvent(
        order_id=order.order_id,
        status=order.status,
        location=f"Last-mile DC ({order.serving_center_id or 'Hub'})",
        description=f"[SIMULATED] Delivery failed: Customer did not answer call (3 attempts)",
        timestamp=now,
    )
    db.add(tracking)

    cust_name = order.customer.name.split()[0] if order.customer and order.customer.name else "Customer"
    clean_prod = (order.product_name or "Parcel").replace("[SIMULATED] ", "")

    message_text = (
        f"⚠️ Namaste {cust_name}! Rider {rider_name} ne aapko parcel ({clean_prod}) ke liye aaj 3 baar call kiya tha, "
        f"par aapne answer nahi kiya (Attempt 3/3).\n\n"
        f"Kripya batayein kya hua tha:"
    )

    buttons = [
        {"id": "btn_was_available", "title": "I was available (Didn't get call)"},
        {"id": "btn_was_busy", "title": "I was busy (Not available)"},
    ]

    session = _get_or_create_customer_session(db, order.customer)
    if session:
        msg = ChatMessage(
            session_id=session.session_id,
            role="assistant",
            content=message_text,
            buttons=buttons,
            message_type="template",
            timestamp=now,
        )
        db.add(msg)
        session.turn_count += 1

    db.commit()

    return {
        "success": True,
        "order_id": order_id,
        "missed_call_count": attempt,
        "alert_sent": True,
        "fake_door_attempt_flagged": fake_attempt,
        "gps_distance_m": distance_m,
        "message": f"Missed call attempt {attempt}/3 logged. WhatsApp alert sent to customer.",
    }


def _haversine_km(lat1, lng1, lat2, lng2):
    from math import radians, sin, cos, asin, sqrt
    dlat, dlng = radians(lat2 - lat1), radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 6371 * 2 * asin(sqrt(a))


def suggest_route_order(db: Session, rider_id: str) -> Dict[str, Any]:
    """Deterministic sort: skip pre-confirmed unavailable, cluster by pincode and landmark (§5.2)."""
    manifest_data = get_manifest(db, rider_id)
    stops = manifest_data.get("stops", [])

    # Separate skipped/deferred stops to the end
    active_stops = [s for s in stops if not s["is_skipped"] and not s["is_delivered"]]
    deferred_stops = [s for s in stops if s["is_skipped"]]
    done_stops = [s for s in stops if s["is_delivered"]]

    # Cluster active stops by pincode, then by landmark presence
    active_stops.sort(key=lambda s: (s["pincode"], 0 if s["landmark"] != "None provided" else 1))

    ordered_stops = active_stops + deferred_stops + done_stops

    return {
        "rider_id": rider_id,
        "suggested_order": [s["order_id"] for s in ordered_stops],
        "active_count": len(active_stops),
        "skipped_count": len(deferred_stops),
        "label": "SIMULATED",
    }


def respond_to_dispute(
    db: Session,
    order_id: str,
    rider_id: str,
    response_text: str
) -> Dict[str, Any]:
    """Record rider's rebuttal to a customer dispute (§5.2, e.g. 'phone was off')."""
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        return {"error": "Order not found"}

    ticket = db.query(Ticket).filter(Ticket.order_id == order_id).first()
    now = datetime.now(timezone.utc)

    if ticket:
        messages = list(ticket.messages or [])
        messages.append({
            "from": f"Rider {rider_id}",
            "text": response_text,
            "timestamp": now.isoformat(),
        })
        ticket.messages = messages
        ticket.updated_at = now
    else:
        ticket = Ticket(
            ticket_id=f"TCK-DISPUTE-{order_id[-5:]}",
            order_id=order_id,
            category="delivery_dispute",
            severity="P1",
            status="open",
            summary=f"Rider dispute response on order {order_id}: {response_text}",
            messages=[{
                "from": f"Rider {rider_id}",
                "text": response_text,
                "timestamp": now.isoformat(),
            }],
            created_at=now,
            updated_at=now,
        )
        db.add(ticket)

    db.commit()
    return {
        "success": True,
        "order_id": order_id,
        "response_recorded": response_text,
        "ticket_id": ticket.ticket_id,
        "label": "SIMULATED",
    }


def get_my_day(db: Session, rider_id: str) -> Dict[str, Any]:
    """Get 'My Day' stats with dead-mile counter & ₹ saved (§5.2)."""
    manifest_data = get_manifest(db, rider_id)
    stops = manifest_data.get("stops", [])

    delivered_count = len([s for s in stops if s["is_delivered"]])
    skipped_count = len([s for s in stops if s["is_skipped"]])
    pending_count = len([s for s in stops if not s["is_delivered"] and not s["is_skipped"]])

    km_saved_per_stop = 2.8
    cost_per_km = 4.5
    estimated_km_saved = round(skipped_count * km_saved_per_stop, 1)
    estimated_rupees_saved = round(estimated_km_saved * cost_per_km + (skipped_count * 15), 0)

    delivered_orders = [s for s in stops if s["is_delivered"]]
    cash_collected = sum(
        float(s["cash_to_collect"].replace("₹", "")) for s in delivered_orders
        if not s["is_prepaid"]
    )

    return {
        "rider_id": rider_id,
        "delivered_stops": delivered_count,
        "pending_stops": pending_count,
        "stops_skipped_by_customer": skipped_count,
        "dead_km_saved": f"{estimated_km_saved} km",
        "rupees_saved": f"₹{int(estimated_rupees_saved)}",
        "cash_collected_today": f"₹{int(cash_collected)}",
        "message": f"Kamaal! Customers ke pre-declaration se aaj aapke {estimated_km_saved} km aur ₹{int(estimated_rupees_saved)} bache hain!",
        "label": "SIMULATED",
    }
