import re
"""Customer agent tools (§5.1).
Each tool is a function that reads from or writes to the database.
The gateway authorises every call before it reaches here.
"""

import uuid
import random
import string
import math
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from backend.models.database import (
    Order, Customer, TrackingEvent, Ticket, ScheduledCallback,
    PaymentLink, ValmoCenter, ChatMessage,
)
from backend.models.enums import (
    OrderState, TicketCategory, TicketSeverity,
    ADDRESS_EDIT_ALLOWED_STATES, SELF_PICKUP_ALLOWED_STATES,
    STATE_DISPLAY_NAMES, DistanceBand,
)
from backend.services.eta_engine import compute_eta


def get_orders(db: Session, phone_hash: str) -> dict:
    """List open orders and the last 5 delivered (§5.1)."""
    customer = db.query(Customer).filter(Customer.phone_hash == phone_hash).first()
    if not customer:
        return {"orders": [], "message": "No orders found for this phone number."}

    # Open orders
    terminal = {OrderState.DELIVERED.value, OrderState.PICKED_UP.value,
                OrderState.RETURNED.value}
    all_orders = db.query(Order).filter(Order.customer_id == customer.id).all()

    open_orders = [o for o in all_orders if o.status not in terminal]
    delivered = [o for o in all_orders if o.status in terminal]
    delivered.sort(key=lambda x: x.delivered_at or x.updated_at or x.ordered_at, reverse=True)

    def _order_snapshot(o: Order) -> dict:
        return {
            "order_id": o.order_id,
            "product": o.product_name,
            "amount": f"₹{o.amount:.0f}",
            "status": o.status,
            "status_display": STATE_DISPLAY_NAMES.get(OrderState(o.status), o.status),
            "payment": "COD" if o.is_cod else "Prepaid",
            "address": o.address_text or "",
            "pincode": o.pincode,
            "city": o.city,
            "landmark": o.landmark or "",
            "ordered_at": o.ordered_at.isoformat() if o.ordered_at else None,
            "is_simulated": o.is_simulated,
        }

    return {
        "open_orders": [_order_snapshot(o) for o in open_orders[:3]],
        "recent_delivered": [_order_snapshot(o) for o in delivered[:5]],
        "total_open": len(open_orders),
    }


def get_order(db: Session, order_id: str) -> dict:
    """Get detailed order info (§5.1)."""
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        return {"error": "Order not found."}

    return {
        "order_id": order.order_id,
        "product": order.product_name,
        "category": order.product_category,
        "quantity": order.quantity,
        "amount": f"₹{order.amount:.0f}",
        "amount_due": f"₹{order.amount_due:.0f}" if order.amount_due else "₹0",
        "payment_mode": "COD" if order.is_cod else "Prepaid",
        "status": order.status,
        "status_display": STATE_DISPLAY_NAMES.get(OrderState(order.status), order.status),
        "address": order.address_text,
        "pincode": order.pincode,
        "city": order.city,
        "landmark": order.landmark or "",
        "delivery_note": order.delivery_note or "",
        "alternate_receiver": order.alternate_receiver or "",
        "availability_slot": order.availability_slot or "",
        "deferral_count": order.deferral_count,
        "address_edit_count": order.address_edit_count,
        "self_pickup": order.self_pickup,
        "ordered_at": order.ordered_at.isoformat() if order.ordered_at else None,
        "is_simulated": order.is_simulated,
    }


def get_tracking(db: Session, order_id: str) -> dict:
    """Get tracking timeline (§5.1)."""
    events = db.query(TrackingEvent).filter(
        TrackingEvent.order_id == order_id
    ).order_by(TrackingEvent.timestamp.desc()).all()

    return {
        "order_id": order_id,
        "events": [
            {
                "status": e.status,
                "status_display": STATE_DISPLAY_NAMES.get(OrderState(e.status), e.status) if e.status in [s.value for s in OrderState] else e.status,
                "location": e.location,
                "description": e.description,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in events
        ],
    }


def get_eta(db: Session, order_id: str) -> dict:
    """Get ETA from the deterministic engine (§8)."""
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        return {"error": "Order not found."}

    eta = compute_eta(
        order_status=order.status,
        lane_class=order.lane_class,
        deferral_count=order.deferral_count,
        ordered_at=order.ordered_at,
    )

    return {
        "order_id": order_id,
        "eta_range": f"{eta['eta_low_display']} - {eta['eta_high_display']}",
        "confidence": eta["confidence"],
        "delayed": eta["delayed"],
        "label": "SIMULATED",
    }


def get_policy(topic: str) -> dict:
    """Return a policy snippet by topic (§5.1). Static facts, no vector DB."""
    policies = {
        "cancellation": {
            "topic": "Cancellation",
            "text": "Order cancel karne ke liye Meesho app mein My Orders → ye order → Cancel option use karein. Chat se cancel nahi hota.",
        },
        "return": {
            "topic": "Return",
            "text": "Return ke liye Meesho app mein My Orders → ye order → Return/Exchange option use karein. Delivery ke 7 din ke andar available hai (eligible items ke liye).",
        },
        "refund": {
            "topic": "Refund",
            "text": "Refund return approve hone ke baad process hota hai. Prepaid orders mein 5-7 working days lagti hain.",
        },
        "payment": {
            "topic": "Payment",
            "text": "COD order ke liye exact change rakhein. Online payment ke liye hum payment link bhej sakte hain.",
        },
        "delivery": {
            "topic": "Delivery",
            "text": "Delivery time location aur product availability pe depend karta hai. Estimated time tool se milta hai.",
        },
        "address_change": {
            "topic": "Address Change",
            "text": "Address same pincode mein change ho sakta hai. City, state ya pincode change nahi hota. Max 2 edits per order.",
        },
        "self_pickup": {
            "topic": "Self Pickup",
            "text": "Apne area ke Valmo center se order khud utha sakte hain. Center pe pahunchne pe pickup code dikhana hoga.",
        },
    }

    result = policies.get(topic.lower().strip())
    if not result:
        # Try fuzzy match
        for key, val in policies.items():
            if topic.lower() in key or key in topic.lower():
                return val
        return {"topic": topic, "text": "Is topic ke baare mein specific information nahi hai. Kya aap aur detail bata sakte hain?"}
    return result


def _resolve_order(db: Session, order_id: str = None, phone_hash: str = None) -> Optional[Order]:
    """Resolve an order by ID or fallback to customer's active open order."""
    if order_id:
        o = db.query(Order).filter(Order.order_id == order_id).first()
        if o:
            return o
    if phone_hash:
        cust = db.query(Customer).filter(Customer.phone_hash == phone_hash).first()
        if cust:
            return db.query(Order).filter(
                Order.customer_id == cust.id,
                Order.status.notin_([OrderState.DELIVERED.value, OrderState.RETURNED.value])
            ).order_by(Order.ordered_at.desc()).first()
    return None


def set_availability(db: Session, order_id: str = None, slot: str = "today", phone_hash: str = None) -> dict:
    """Set delivery availability slot. Notifies rider via tracking event when rescheduled."""
    order = _resolve_order(db, order_id, phone_hash)
    if not order:
        return {"error": "Order not found."}

    now = datetime.now(timezone.utc)
    order.availability_slot = slot
    slot_lower = slot.lower()

    if "today" in slot_lower or "aaj" in slot_lower or "available" in slot_lower:
        order.customer_response_status = "available_today"
        event = TrackingEvent(
            order_id=order.order_id,
            status=order.status,
            location=order.serving_center_id or "Hub",
            description="[SIMULATED] Customer confirmed: Available today for delivery",
            timestamp=now,
        )
        db.add(event)
    else:
        order.customer_response_status = "rescheduled_tomorrow"
        order.status = OrderState.SKIPPED_TODAY.value
        order.deferral_count = (order.deferral_count or 0) + 1
        tomorrow_date = (now + timedelta(days=1)).strftime("%d %b")
        cust_name = order.customer.name.split()[0] if order.customer and order.customer.name else "Customer"
        event = TrackingEvent(
            order_id=order.order_id,
            status=OrderState.SKIPPED_TODAY.value,
            location=order.serving_center_id or "Hub",
            description=f"[SIMULATED] Rider Alert: {cust_name} NOT available today. Deliver tomorrow ({tomorrow_date}). Skip this stop.",
            timestamp=now,
        )
        db.add(event)

    order.updated_at = now
    db.commit()

    warning = None
    if order.deferral_count and order.deferral_count >= 2:
        warning = "Ye aakhri baar reschedule ho sakta hai. Teesri baar defer karne pe order 4th day auto-return ho jayega."

    tomorrow_str = (now + timedelta(days=1)).strftime("%d %b")
    is_tomorrow = not ("today" in slot_lower or "aaj" in slot_lower or "available" in slot_lower)
    return {
        "success": True,
        "order_id": order.order_id,
        "slot": slot,
        "deferral_count": order.deferral_count,
        "scheduled_for": tomorrow_str if is_tomorrow else "today",
        "rider_notified": True,
        "rider_message": f"Customer not available today. Delivery rescheduled to {tomorrow_str}. Stop skipped on manifest.",
        "warning": warning,
    }

def add_delivery_note(db: Session, order_id: str = None, note: str = "", phone_hash: str = None) -> dict:
    """Add structured note for the rider (§5.1)."""
    order = _resolve_order(db, order_id, phone_hash)
    if not order:
        return {"error": "Order not found."}

    order.delivery_note = note[:120]
    order.customer_response_status = "note_added"
    order.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {"success": True, "order_id": order.order_id, "note": note[:120]}


def set_alternate_receiver(db: Session, order_id: str = None, name: str = "", contact_phone: str = "", phone_hash: str = None) -> dict:
    """Save an alternate receiver as structured name/contact data."""
    order = _resolve_order(db, order_id, phone_hash)
    if not order:
        return {"error": "Order not found."}

    clean_name = " ".join(name.split())
    phone_digits = re.sub(r"\D", "", contact_phone)
    if len(clean_name) < 2 or not re.fullmatch(r"[6-9]\d{9}", phone_digits):
        return {"error": "Alternate receiver ke liye unka naam aur valid 10-digit mobile number chahiye."}

    order.alternate_receiver = f"{clean_name} ({phone_digits})"
    order.customer_response_status = "alt_receiver_added"
    order.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {"success": True, "order_id": order.order_id, "alternate_receiver": clean_name, "contact_last4": phone_digits[-4:]}


def update_address(db: Session, order_id: str = None, address_text: str = "", landmark: str = None, receiver_name: str = None, receiver_phone: str = None, phone_hash: str = None) -> dict:
    """Update address within same pincode (§7.3). Validates pincode and address validity."""
    order = _resolve_order(db, order_id, phone_hash)
    if not order:
        return {"error": "Order not found."}

    clean_text = address_text.strip()
    lower_text = clean_text.lower()

    # Reject intent questions or non-address text
    invalid_patterns = [
        "change", "badal", "kese", "kaise", "krna", "karna", "update",
        "hai", "hoga", "karo", "bhejo", "batao", "madad", "help"
    ]
    words = re.findall(r"\w+", lower_text)
    if len(words) <= 3 and any(w in words for w in ["change", "badal", "kese", "kaise", "krna", "karna", "update", "address"]):
        return {"error": "Ye address nahi hai. Kripya apna pura naya delivery address batayein (Flat/House No., Gali, Landmark)."}

    # A landmark alone is not routable. Do this in the tool as well as NLU so a
    # provider cannot bypass the delivery-quality rule.
    has_house_identifier = bool(re.search(r"\b(?:flat|house|h\.?(?:\s*no)?|plot|building|block|floor|door)\s*[-#:]?\s*\d", lower_text))
    has_street_detail = any(token in lower_text for token in ("gali", "street", "road", "sector", "colony", "nagar", "marg", "residency", "apartment", "pocket"))
    if len(words) < 4 or not has_house_identifier or not has_street_detail:
        return {"error": "Kripya house/flat number aur street details bhi batayein taaki rider ko parcel deliver karne mein pareshani na ho 📍", "needs_address_details": True}

    # Pincode validation: same pincode check (§7.3)
    pincode_match = re.search(r"\b\d{6}\b", clean_text)
    if pincode_match:
        extracted_pincode = pincode_match.group(0)
        if order.pincode and extracted_pincode != order.pincode:
            return {
                "error": f"Address sirf same pincode ({order.pincode}) mein change ho sakta hai. Naya pincode ({extracted_pincode}) allowed nahi hai. Dusre pincode ke liye Meesho app se order karein.",
                "allowed_pincode": order.pincode,
                "requested_pincode": extracted_pincode
            }

    # Max edit limit (§7.3: max 2 edits)
    if order.address_edit_count and order.address_edit_count >= 2:
        return {"error": "Aap is order ke liye maximum 2 baar address update kar chuke hain. Aur edits allowed nahi hain."}

    # Preserve initial address before first update
    if not order.original_address:
        order.original_address = order.address_text

    order.address_text = clean_text
    if landmark:
        order.landmark = landmark
    if receiver_name:
        receiver_info = receiver_name
        if receiver_phone:
            receiver_info += f" ({receiver_phone})"
        order.alternate_receiver = receiver_info
    
    order.customer_response_status = "address_updated"
    order.address_edit_count = (order.address_edit_count or 0) + 1
    order.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "success": True,
        "order_id": order.order_id,
        "original_address": order.original_address,
        "new_address": clean_text,
        "landmark": order.landmark or "",
        "alternate_receiver": order.alternate_receiver or "",
        "pincode": order.pincode,
        "edits_remaining": max(0, 2 - order.address_edit_count),
    }




def get_pickup_options(db: Session, order_id: str) -> dict:
    """Get serving Valmo center info for self pickup (§5.1, §7.3A)."""
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        return {"error": "Order not found."}

    center = db.query(ValmoCenter).filter(
        ValmoCenter.center_id == order.serving_center_id,
        ValmoCenter.type == "last_mile_dc",  # R-31: only last_mile_dc
    ).first()

    if not center:
        return {"error": "No self-pickup center available for this order."}

    # Calculate approximate distance band
    if order.lat and order.lng and center.lat and center.lng:
        dist = _haversine(order.lat, order.lng, center.lat, center.lng)
    else:
        dist = 5.0  # Default assumption

    if dist <= 2:
        distance_band = DistanceBand.NEAR_2KM.value
    elif dist <= 5:
        distance_band = DistanceBand.MEDIUM_5KM.value
    else:
        distance_band = DistanceBand.FAR_10KM.value

    return {
        "center_name": center.name,
        "address": center.address,
        "hours": center.hours_json,
        "weekly_off": center.weekly_off,
        "holidays": center.holidays,
        "accepts_self_pickup": center.accepts_self_pickup,
        "distance_band": distance_band,
        "distance_km": round(dist, 1),
        "label": "SIMULATED",
    }


def set_self_pickup(db: Session, order_id: str, center_id: str = None) -> dict:
    """Switch order to self pickup (§7.3A)."""
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        return {"error": "Order not found."}

    cid = center_id or order.serving_center_id
    order.self_pickup = True
    order.status = OrderState.SELF_PICKUP_PENDING.value
    order.rider_id = None  # Remove from rider manifest
    order.pickup_code = ''.join(random.choices(string.digits, k=6))
    order.pickup_hold_expires = datetime.now(timezone.utc) + timedelta(days=3)
    order.updated_at = datetime.now(timezone.utc)

    # Add tracking event
    event = TrackingEvent(
        order_id=order_id,
        status=OrderState.SELF_PICKUP_PENDING.value,
        location=cid,
        description="[SIMULATED] Self pickup requested at Valmo center",
    )
    db.add(event)
    db.commit()

    return {
        "success": True,
        "order_id": order_id,
        "center_id": cid,
        "pickup_code": order.pickup_code,
        "hold_expires": order.pickup_hold_expires.isoformat(),
    }


def create_payment_link(db: Session, order_id: str) -> dict:
    """Create COD-to-online payment link (§7.2)."""
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        return {"error": "Order not found."}

    link_id = f"PAY-{uuid.uuid4().hex[:8].upper()}"
    expires = datetime.now(timezone.utc) + timedelta(minutes=30)

    link = PaymentLink(
        link_id=link_id,
        order_id=order_id,
        amount=order.amount,
        payment_url=f"https://pay.valmo.in/{link_id}",
        expires_at=expires,
    )
    order.payment_link_id = link_id
    order.payment_link_expiry = expires

    db.add(link)
    db.commit()

    return {
        "success": True,
        "order_id": order_id,
        "link_id": link_id,
        "amount": f"₹{order.amount:.0f}",
        "payment_url": link.payment_url,
        "expires_in": "30 minutes",
        "label": "SIMULATED",
    }


def create_ticket(db: Session, order_id: str, category: str, summary: str, photos: list = None) -> dict:
    """Create a complaint ticket (§7.4)."""
    # Check existing open ticket
    existing = db.query(Ticket).filter(
        Ticket.order_id == order_id,
        Ticket.category == category,
        Ticket.status.in_(["open", "in_progress"]),
    ).first()

    if existing:
        # Append to existing
        msgs = existing.messages or []
        msgs.append({"text": summary, "timestamp": datetime.now(timezone.utc).isoformat()})
        existing.messages = msgs
        if photos:
            existing_photos = existing.photos or []
            existing_photos.extend(photos[:3])
            existing.photos = existing_photos[:3]
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        return {
            "success": True,
            "ticket_id": existing.ticket_id,
            "message": "Your earlier complaint has been updated with the new information.",
            "status": existing.status,
        }

    # Severity mapping
    severity_map = {
        TicketCategory.NOT_RECEIVED.value: TicketSeverity.P1.value,
        TicketCategory.RIDER_BEHAVIOUR.value: TicketSeverity.P1.value,
        TicketCategory.PAYMENT_CHARGE.value: TicketSeverity.P1.value,
        TicketCategory.DAMAGED_WRONG.value: TicketSeverity.P1.value,
        TicketCategory.LATE_DELIVERY.value: TicketSeverity.P2.value,
        TicketCategory.ADDRESS_ISSUE.value: TicketSeverity.P3.value,
        TicketCategory.PRODUCT_QUALITY.value: TicketSeverity.P3.value,
    }

    ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"
    ticket = Ticket(
        ticket_id=ticket_id,
        order_id=order_id,
        category=category,
        severity=severity_map.get(category, TicketSeverity.P3.value),
        summary=summary,
        photos=photos[:3] if photos else [],
    )
    db.add(ticket)
    db.commit()

    return {
        "success": True,
        "ticket_id": ticket_id,
        "category": category,
        "severity": ticket.severity,
        "message": "Complaint registered. Our team will review it.",
    }


def schedule_callback(db: Session, customer_id: int, order_id: str, time_str: str, reason: str = "") -> dict:
    """Schedule a human callback (§5.1)."""
    # Check open callbacks
    open_cbs = db.query(ScheduledCallback).filter(
        ScheduledCallback.customer_id == customer_id,
        ScheduledCallback.status == "pending",
    ).count()

    if open_cbs >= 2:
        return {"error": "Maximum 2 open callbacks allowed. Please wait for a callback before scheduling a new one."}

    # Parse time (simplified for prototype)
    now = datetime.now(timezone.utc)
    callback_time = now + timedelta(hours=2)  # Default: 2 hours from now

    cb = ScheduledCallback(
        customer_id=customer_id,
        order_id=order_id,
        scheduled_time=callback_time,
        reason=reason,
    )
    db.add(cb)
    db.commit()

    return {
        "success": True,
        "callback_time": callback_time.isoformat(),
        "message": "Callback scheduled. Our team will call you.",
    }


def request_rider_call(db: Session, order_id: str) -> dict:
    """Ask rider to call through masked number (§5.1)."""
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        return {"error": "Order not found."}

    return {
        "success": True,
        "order_id": order_id,
        "message": "Rider ko call karne ka request bhej diya hai. Wo masked number se call karenge.",
    }


def set_language(db: Session, phone_hash: str, language: str) -> dict:
    """Set language preference (§5.1)."""
    customer = db.query(Customer).filter(Customer.phone_hash == phone_hash).first()
    if not customer:
        return {"error": "Customer not found."}

    customer.language = language
    db.commit()
    return {"success": True, "language": language}


def escalate_to_human(db: Session, order_id: str, summary: str) -> dict:
    """Immediate handoff to human (R-20)."""
    return {
        "success": True,
        "order_id": order_id,
        "message": "Aapko ek human agent se connect kar rahe hain. Callback 4 business hours mein milega.",
        "summary": summary,
    }


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in km between two lat/lng points."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))
