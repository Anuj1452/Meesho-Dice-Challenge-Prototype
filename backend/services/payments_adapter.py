"""Payments adapter and mock webhook handling (§7.2).
Handles COD to online payment conversion, payment link lifecycle,
and idempotent webhook processing with live manifest updates.
"""

import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.models.database import Order, PaymentLink, TrackingEvent, Ticket
from backend.models.enums import OrderState


class PaymentsAdapter:
    @staticmethod
    def create_payment_link(db: Session, order: Order) -> Dict[str, Any]:
        """Generate a 30-minute payment link (§7.2, §5.1).
        Amount is pulled directly from the order record, NEVER from chat text.
        """
        now = datetime.now(timezone.utc)
        link_id = f"pay_{uuid.uuid4().hex[:12]}"
        expiry = now + timedelta(minutes=30)

        # Check existing active link
        existing = db.query(PaymentLink).filter(
            PaymentLink.order_id == order.order_id,
            PaymentLink.status == "created",
            PaymentLink.expires_at > now,
        ).first()

        if existing:
            return {
                "link_id": existing.link_id,
                "payment_url": f"https://pay.valmo.sim/{existing.link_id}",
                "amount": existing.amount,
                "expires_at": existing.expires_at.isoformat(),
                "is_new": False,
            }

        amount = order.amount_due if order.amount_due is not None else order.amount

        # Optional prototype discount (e.g. ₹10 online pay incentive)
        discount_rs = 10.0
        final_amount = max(amount - discount_rs, 1.0)

        link_record = PaymentLink(
            link_id=link_id,
            order_id=order.order_id,
            amount=final_amount,
            status="created",
            created_at=now,
            expires_at=expiry,
        )
        db.add(link_record)

        order.payment_link_id = link_id
        order.payment_link_expiry = expiry
        db.commit()

        return {
            "link_id": link_id,
            "payment_url": f"https://pay.valmo.sim/{link_id}",
            "amount": final_amount,
            "discount_applied": discount_rs,
            "expires_at": expiry.isoformat(),
            "is_new": True,
            "label": "SIMULATED",
        }

    @staticmethod
    def process_webhook(
        db: Session,
        link_id: str,
        payment_ref: str,
        amount_paid: float,
        signature: Optional[str] = "valid_sim_sig",
    ) -> Dict[str, Any]:
        """Process verified payment webhook idempotently (§7.2).
        Flips manifest from COD to PREPAID instantly.
        """
        link = db.query(PaymentLink).filter(PaymentLink.link_id == link_id).first()
        if not link:
            return {"success": False, "error": f"Payment link {link_id} not found"}

        order = db.query(Order).filter(Order.order_id == link.order_id).first()
        if not order:
            return {"success": False, "error": f"Order {link.order_id} not found"}

        now = datetime.now(timezone.utc)

        # Idempotency check (§7.2 rule 5)
        if link.status == "paid" and order.payment_verified:
            return {
                "success": True,
                "order_id": order.order_id,
                "idempotent": True,
                "message": "Payment already processed previously. No duplicate action taken.",
            }

        # Check edge case: payment after delivery
        if order.status == OrderState.DELIVERED.value:
            # Create ops ticket for post-delivery reconciliation
            ticket = Ticket(
                ticket_id=f"TCK-POSTPAY-{order.order_id[-5:]}",
                order_id=order.order_id,
                category="payment_issue",
                severity="P1",
                status="open",
                summary=f"Online payment received after order was already marked delivered (Ref: {payment_ref})",
                created_at=now,
                updated_at=now,
            )
            db.add(ticket)

        # Update link and order
        link.status = "paid"
        link.payment_ref = payment_ref
        link.paid_at = now

        order.is_cod = False
        order.payment_mode = "prepaid"
        order.amount_due = 0.0
        order.payment_verified = True
        order.updated_at = now

        # Add tracking event
        tracking = TrackingEvent(
            order_id=order.order_id,
            status=order.status,
            location="Online Payment Gateway",
            description=f"[SIMULATED] Online payment confirmed via UPI/Card (Ref: {payment_ref}). Cash collection removed.",
            timestamp=now,
        )
        db.add(tracking)
        db.commit()

        return {
            "success": True,
            "order_id": order.order_id,
            "status": "paid",
            "amount_paid": amount_paid,
            "payment_ref": payment_ref,
            "rider_manifest_update": "PREPAID - ₹0 cash to collect",
            "receipt": {
                "order_id": order.order_id,
                "product": order.product_name,
                "amount": f"₹{amount_paid:.0f}",
                "mode": "Online Prepaid",
                "timestamp": now.strftime("%d %b %Y, %I:%M %p"),
            },
            "label": "SIMULATED",
        }
