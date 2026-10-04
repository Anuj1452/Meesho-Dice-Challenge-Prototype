"""Ops copilot tools (§5.3).
Control Tower tools for Meesho Valmo operations team.
The copilot NEVER executes consequential actions (cannot ban riders, issue refunds, or cancel orders).
It proposes, and a human clicks/approves (§5.3, §14).
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models.database import (
    Order, Rider, Customer, TrackingEvent, Ticket, ScheduledCallback,
    AuditLog, ValmoCenter
)
from backend.models.enums import OrderState, RiskTier, TicketCategory, TicketSeverity


# In-memory storage for pending actions in the prototype (§5.3)
_PENDING_ACTIONS = []


def get_case_bundle(db: Session, order_id: str) -> Dict[str, Any]:
    """Get complete case bundle for an order: timeline, verdicts, tickets, audits (§5.3)."""
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        return {"error": "Order not found"}

    # Tracking timeline
    tracking_events = db.query(TrackingEvent).filter(
        TrackingEvent.order_id == order_id
    ).order_by(TrackingEvent.timestamp.asc()).all()

    # Tickets
    tickets = db.query(Ticket).filter(Ticket.order_id == order_id).all()

    # Audit logs for this order
    audits = db.query(AuditLog).filter(
        AuditLog.arguments.like(f"%{order_id}%")
    ).order_by(AuditLog.timestamp.desc()).all()

    timeline = []
    for t in tracking_events:
        timeline.append({
            "status": t.status,
            "location": t.location,
            "description": t.description,
            "timestamp": t.timestamp.isoformat(),
        })

    ticket_summaries = []
    for t in tickets:
        ticket_summaries.append({
            "ticket_id": t.ticket_id,
            "category": t.category,
            "severity": t.severity,
            "status": t.status,
            "summary": t.summary,
            "messages": t.messages,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        })

    # Call log / Customer interaction summary
    cust_name = order.customer.name if order.customer else "Unknown"
    phone_hash = order.customer.phone_hash if order.customer else ""

    return {
        "order_id": order.order_id,
        "awb": order.awb,
        "customer": {
            "name": cust_name,
            "phone_hash": phone_hash,
            "language": order.customer.language if order.customer else "hinglish",
        },
        "order_details": {
            "product": order.product_name,
            "amount": f"₹{order.amount:.0f}",
            "payment_mode": "COD" if order.is_cod else "Prepaid",
            "current_status": order.status,
            "risk_tier": order.risk_tier,
            "address": order.address_text,
            "pincode": order.pincode,
            "city": order.city,
            "hub_id": order.serving_center_id,
            "deferral_count": order.deferral_count,
            "address_edit_count": order.address_edit_count,
        },
        "timeline": timeline,
        "tickets": ticket_summaries,
        "audit_count": len(audits),
        "label": "SIMULATED",
    }


def get_hub_metrics(db: Session, hub_id: str, window_days: int = 7) -> Dict[str, Any]:
    """Get predefined hub metrics (§5.3).
    Predefined metrics only, never free SQL!
    Calculates RTO %, attempts per delivery, reply rate, and dispute rate.
    """
    center = db.query(ValmoCenter).filter(ValmoCenter.center_id == hub_id).first()
    hub_name = center.name if center else f"Hub {hub_id}"

    # Orders at this hub
    orders = db.query(Order).filter(Order.serving_center_id == hub_id).all()
    total_orders = len(orders) or 240  # fallback to baseline sample

    # Metric calculations (calibrated to realistic Valmo last-mile benchmarks)
    if hub_id == "VMC-DEL-01":
        rto_pct = 8.4
        attempts_per_del = 1.18
        customer_reply_rate = 74.2
        dispute_rate = 1.2
        active_riders = 14
        daily_deliveries = 312
    elif hub_id == "VMC-DEL-02":
        rto_pct = 9.1
        attempts_per_del = 1.22
        customer_reply_rate = 68.5
        dispute_rate = 1.6
        active_riders = 11
        daily_deliveries = 245
    elif hub_id == "VMC-MUM-01":
        rto_pct = 7.6
        attempts_per_del = 1.14
        customer_reply_rate = 79.1
        dispute_rate = 0.9
        active_riders = 18
        daily_deliveries = 410
    elif hub_id == "VMC-PAT-01":
        rto_pct = 14.8  # elevated RTO hub for demo
        attempts_per_del = 1.45
        customer_reply_rate = 52.0
        dispute_rate = 3.8
        active_riders = 8
        daily_deliveries = 180
    else:
        rto_pct = 9.5
        attempts_per_del = 1.21
        customer_reply_rate = 66.0
        dispute_rate = 1.5
        active_riders = 10
        daily_deliveries = 220

    return {
        "hub_id": hub_id,
        "hub_name": hub_name,
        "window_days": window_days,
        "metrics": {
            "rto_percentage": f"{rto_pct}%",
            "attempts_per_delivery": round(attempts_per_del, 2),
            "customer_reply_rate": f"{customer_reply_rate}%",
            "dispute_rate": f"{dispute_rate}%",
            "active_riders": active_riders,
            "daily_volume": daily_deliveries,
            "self_pickup_share": "4.2%",
        },
        "flags": [
            "High COD share (>78%)" if rto_pct > 12 else "Normal operational band",
            "Elevated fake-attempt disputes" if dispute_rate > 2.5 else "Clean rider audit status",
        ],
        "label": "SIMULATED",
    }


def list_review_queue(db: Session, hub_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """List flagged riders and orders in the ops review queue (§5.3)."""
    # Sample items in ops review queue
    queue = [
        {
            "case_id": "REV-2026-081",
            "order_id": "MS100200300",
            "hub_id": "VMC-PAT-01",
            "rider_id": "RDR-007",
            "rider_name": "Raju",
            "flag_reason": "Customer marked 'I was home' after rider reported 'Gate locked'",
            "evidence": {
                "rider_gps_distance_m": 420,
                "attempt_time": "14:12 IST",
                "customer_reply_time": "14:14 IST",
                "dispute_match": "High discrepancy — rider was 420m away from pin",
            },
            "severity": "P1",
            "suggested_action": "hub_rider_inquiry",
            "status": "pending_ops_review",
        },
        {
            "case_id": "REV-2026-082",
            "order_id": "MS987654321",
            "hub_id": "VMC-DEL-01",
            "rider_id": "RDR-001",
            "rider_name": "Amit",
            "flag_reason": "Declared pincode vs WhatsApp pin mismatch (8.4 km away)",
            "evidence": {
                "order_pincode": "110085",
                "pin_pincode": "110089",
                "distance_from_dc_km": 6.8,
            },
            "severity": "P2",
            "suggested_action": "address_clarification",
            "status": "pending_ops_review",
        },
        {
            "case_id": "REV-2026-083",
            "order_id": "MS456123789",
            "hub_id": "VMC-LKO-01",
            "rider_id": "RDR-005",
            "rider_name": "Pappu",
            "flag_reason": "Second deferral limit reached by customer",
            "evidence": {
                "deferral_count": 2,
                "ordered_days_ago": 3,
                "auto_rto_risk": "Imminent at next deferral",
            },
            "severity": "P2",
            "suggested_action": "self_pickup_or_urgent_delivery",
            "status": "pending_ops_review",
        },
    ]

    if hub_id:
        queue = [q for q in queue if q["hub_id"] == hub_id]

    return queue


def explain_score(db: Session, order_id: str) -> Dict[str, Any]:
    """Explain in plain words why an order has its risk tier (§5.3)."""
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        return {"error": "Order not found"}

    tier = order.risk_tier
    reasons = []

    if order.is_cod:
        reasons.append("Payment mode is COD (historical COD refusal rate is 3.4x higher than prepaid)")
    else:
        reasons.append("Payment is Prepaid (very low risk factor)")

    if order.deferral_count > 0:
        reasons.append(f"Customer has rescheduled/deferred delivery {order.deferral_count} time(s)")

    if order.lane_class == "remote":
        reasons.append("Delivery lane is classified as remote / long-tail pincode")

    if order.amount > 1000:
        reasons.append(f"High ticket value (₹{order.amount:.0f})")

    # Plain language explanation
    if tier == "high":
        summary = (
            f"Order {order_id} is marked HIGH RISK because it is a COD shipment with prior deferrals. "
            "Recommended action: send morning availability verification and offer ₹10 online payment discount link."
        )
    elif tier == "medium":
        summary = (
            f"Order {order_id} has MEDIUM RISK due to standard COD delivery parameters in a semi-urban cluster. "
            "Doorbell verification template recommended."
        )
    else:
        summary = (
            f"Order {order_id} has LOW RISK: address matches verified cluster and customer has positive delivery history."
        )

    return {
        "order_id": order_id,
        "risk_tier": tier,
        "summary": summary,
        "risk_factors": reasons,
        "label": "SIMULATED",
    }


def search_tickets(
    db: Session,
    order_id: Optional[str] = None,
    hub_id: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Search tickets by order, hub, category, status (§5.3)."""
    query = db.query(Ticket)
    if order_id:
        query = query.filter(Ticket.order_id == order_id)
    if category:
        query = query.filter(Ticket.category == category)
    if status:
        query = query.filter(Ticket.status == status)

    tickets = query.order_by(Ticket.created_at.desc()).limit(20).all()

    return [
        {
            "ticket_id": t.ticket_id,
            "order_id": t.order_id,
            "category": t.category,
            "severity": t.severity,
            "status": t.status,
            "summary": t.summary,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "label": "SIMULATED",
        }
        for t in tickets
    ]


def propose_action(
    db: Session,
    order_id: str,
    action_type: str,
    rationale: str,
    suggested_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Propose an action for human ops approval (§5.3).
    The copilot NEVER executes consequential actions directly.
    Allowed action_types: 'hub_review', 'callback', 'address_correction', 'goodwill_coupon', 'self_pickup_offer'
    """
    now = datetime.now(timezone.utc)
    proposal_id = f"PROP-{int(now.timestamp()) % 100000}"

    proposal = {
        "proposal_id": proposal_id,
        "order_id": order_id,
        "action_type": action_type,
        "rationale": rationale[:200],
        "payload": suggested_payload or {},
        "status": "pending_human_approval",
        "created_at": now.isoformat(),
        "requires_role": "Ops Lead",
        "label": "SIMULATED",
    }

    _PENDING_ACTIONS.append(proposal)

    return {
        "success": True,
        "proposal_id": proposal_id,
        "status": "pending_human_approval",
        "message": f"Action '{action_type}' proposed. Awaiting Ops Manager approval in Control Tower.",
        "proposal": proposal,
    }


def list_pending_actions() -> List[Dict[str, Any]]:
    """List pending actions waiting for Ops approval."""
    return [p for p in _PENDING_ACTIONS if p["status"] == "pending_human_approval"]


def resolve_action(proposal_id: str, approved: bool, reviewer: str = "Ops Lead") -> Dict[str, Any]:
    """Human approval or rejection of a copilot proposal (§5.3)."""
    for p in _PENDING_ACTIONS:
        if p["proposal_id"] == proposal_id:
            p["status"] = "approved" if approved else "rejected"
            p["reviewed_by"] = reviewer
            p["reviewed_at"] = datetime.now(timezone.utc).isoformat()
            return {"success": True, "proposal_id": proposal_id, "new_status": p["status"]}

    return {"error": f"Proposal {proposal_id} not found"}


def draft_message(
    db: Session,
    recipient_type: str,
    target_id: str,
    tone: str,
    key_points: str,
) -> Dict[str, Any]:
    """Draft a note to a hub entrepreneur or customer for human review (§5.3)."""
    if recipient_type == "hub_entrepreneur":
        draft = (
            f"Dear Hub Lead ({target_id}),\n"
            f"Regarding recent delivery exception patterns: {key_points}. "
            "Please audit the listed attempts with your rider fleet and share route feedback by 18:00 IST."
        )
    elif recipient_type == "customer":
        draft = (
            f"Namaste, Meesho Valmo delivery team ki taraf se update. "
            f"{key_points}. Aapki suvidha ke anusaar delivery ensure karne ke liye hum committed hain."
        )
    else:
        draft = f"Operational Note ({target_id}): {key_points}"

    return {
        "recipient_type": recipient_type,
        "target_id": target_id,
        "draft_text": draft,
        "requires_human_approval": True,
        "label": "SIMULATED",
    }
