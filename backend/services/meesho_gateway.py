"""Meesho Gateway (§10.1).
Abstracts integration with Meesho core systems.
MOCK reads seeded SQLite tables. REAL is a stub that raises NotConfigured (§10.1).
Switch with MEESHO_GATEWAY=mock|real.
"""

import os
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from backend.models.database import Order, Customer, TrackingEvent, ValmoCenter
from backend.models.enums import OrderState


class NotConfigured(Exception):
    """Raised when REAL Meesho Gateway is called without production credentials."""
    pass


class BaseMeeshoGateway:
    def get_orders_by_phone(self, db: Session, phone_hash: str) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def get_order(self, db: Session, order_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def get_tracking(self, db: Session, order_id: str) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def update_address(self, db: Session, order_id: str, address_text: str) -> Dict[str, Any]:
        # Pincode, city and hub are NEVER parameters (§10.1)
        raise NotImplementedError

    def get_center_for_pincode(self, db: Session, pincode: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def get_center(self, db: Session, center_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def set_self_pickup(self, db: Session, order_id: str, center_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def set_payment_mode(self, db: Session, order_id: str, mode: str, ref: str) -> Dict[str, Any]:
        raise NotImplementedError

    def get_payment_status(self, db: Session, order_id: str) -> Dict[str, Any]:
        raise NotImplementedError


class MockMeeshoGateway(BaseMeeshoGateway):
    """Mock implementation reading/writing local SQLite database (§10.1)."""

    def get_orders_by_phone(self, db: Session, phone_hash: str) -> List[Dict[str, Any]]:
        customer = db.query(Customer).filter(Customer.phone_hash == phone_hash).first()
        if not customer:
            return []
        orders = db.query(Order).filter(Order.customer_id == customer.id).all()
        return [
            {
                "order_id": o.order_id,
                "awb": o.awb,
                "product_name": o.product_name,
                "amount": o.amount,
                "is_cod": o.is_cod,
                "amount_due": o.amount_due,
                "status": o.status,
                "pincode": o.pincode,
                "city": o.city,
                "state": o.state,
                "address_text": o.address_text,
                "serving_center_id": o.serving_center_id,
                "is_simulated": True,
            }
            for o in orders
        ]

    def get_order(self, db: Session, order_id: str) -> Optional[Dict[str, Any]]:
        o = db.query(Order).filter(Order.order_id == order_id).first()
        if not o:
            return None
        return {
            "order_id": o.order_id,
            "awb": o.awb,
            "product_name": o.product_name,
            "amount": o.amount,
            "is_cod": o.is_cod,
            "amount_due": o.amount_due,
            "status": o.status,
            "pincode": o.pincode,
            "city": o.city,
            "state": o.state,
            "address_text": o.address_text,
            "landmark": o.landmark,
            "serving_center_id": o.serving_center_id,
            "self_pickup": o.self_pickup,
            "pickup_code": o.pickup_code,
            "is_simulated": True,
        }

    def get_tracking(self, db: Session, order_id: str) -> List[Dict[str, Any]]:
        events = db.query(TrackingEvent).filter(
            TrackingEvent.order_id == order_id
        ).order_by(TrackingEvent.timestamp.asc()).all()
        return [
            {
                "status": e.status,
                "location": e.location,
                "description": e.description,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in events
        ]

    def update_address(self, db: Session, order_id: str, address_text: str) -> Dict[str, Any]:
        # Pincode, city and hub are intentionally NOT accepted here (§10.1, §7.3)
        order = db.query(Order).filter(Order.order_id == order_id).first()
        if not order:
            return {"success": False, "error": "Order not found"}
        order.address_text = address_text
        order.address_edit_count += 1
        order.updated_at = datetime.now(timezone.utc)
        db.commit()
        return {"success": True, "order_id": order_id, "new_address": address_text}

    def get_center_for_pincode(self, db: Session, pincode: str) -> Optional[Dict[str, Any]]:
        centers = db.query(ValmoCenter).filter(ValmoCenter.type == "last_mile_dc").all()
        for c in centers:
            served = c.pincodes_served or []
            if pincode in served:
                return {
                    "center_id": c.center_id,
                    "name": c.name,
                    "city": c.city,
                    "state": c.state,
                    "address": c.address,
                    "hours_json": c.hours_json,
                    "weekly_off": c.weekly_off,
                    "accepts_self_pickup": c.accepts_self_pickup,
                    "status": c.status,
                }
        return None

    def get_center(self, db: Session, center_id: str) -> Optional[Dict[str, Any]]:
        c = db.query(ValmoCenter).filter(ValmoCenter.center_id == center_id).first()
        if not c:
            return None
        return {
            "center_id": c.center_id,
            "name": c.name,
            "type": c.type,
            "city": c.city,
            "address": c.address,
            "hours_json": c.hours_json,
            "weekly_off": c.weekly_off,
            "accepts_self_pickup": c.accepts_self_pickup,
            "status": c.status,
        }

    def set_self_pickup(self, db: Session, order_id: str, center_id: str) -> Dict[str, Any]:
        order = db.query(Order).filter(Order.order_id == order_id).first()
        if not order:
            return {"success": False, "error": "Order not found"}
        order.self_pickup = True
        order.serving_center_id = center_id
        order.status = OrderState.SELF_PICKUP_PENDING.value
        order.updated_at = datetime.now(timezone.utc)
        db.commit()
        return {"success": True, "order_id": order_id, "status": order.status}

    def set_payment_mode(self, db: Session, order_id: str, mode: str, ref: str) -> Dict[str, Any]:
        order = db.query(Order).filter(Order.order_id == order_id).first()
        if not order:
            return {"success": False, "error": "Order not found"}
        order.payment_mode = mode
        if mode == "prepaid":
            order.is_cod = False
            order.amount_due = 0.0
            order.payment_verified = True
        order.updated_at = datetime.now(timezone.utc)
        db.commit()
        return {"success": True, "order_id": order_id, "payment_mode": mode}

    def get_payment_status(self, db: Session, order_id: str) -> Dict[str, Any]:
        order = db.query(Order).filter(Order.order_id == order_id).first()
        if not order:
            return {"error": "Order not found"}
        return {
            "order_id": order_id,
            "payment_mode": order.payment_mode,
            "is_cod": order.is_cod,
            "amount_due": order.amount_due,
            "payment_verified": order.payment_verified,
        }


class RealMeeshoGateway(BaseMeeshoGateway):
    """Production stub — raises NotConfigured (§10.1)."""

    def get_orders_by_phone(self, db: Session, phone_hash: str) -> List[Dict[str, Any]]:
        raise NotConfigured("Production Meesho Gateway is not configured. Use MEESHO_GATEWAY=mock.")

    def get_order(self, db: Session, order_id: str) -> Optional[Dict[str, Any]]:
        raise NotConfigured("Production Meesho Gateway is not configured. Use MEESHO_GATEWAY=mock.")

    def get_tracking(self, db: Session, order_id: str) -> List[Dict[str, Any]]:
        raise NotConfigured("Production Meesho Gateway is not configured. Use MEESHO_GATEWAY=mock.")

    def update_address(self, db: Session, order_id: str, address_text: str) -> Dict[str, Any]:
        raise NotConfigured("Production Meesho Gateway is not configured. Use MEESHO_GATEWAY=mock.")

    def get_center_for_pincode(self, db: Session, pincode: str) -> Optional[Dict[str, Any]]:
        raise NotConfigured("Production Meesho Gateway is not configured. Use MEESHO_GATEWAY=mock.")

    def get_center(self, db: Session, center_id: str) -> Optional[Dict[str, Any]]:
        raise NotConfigured("Production Meesho Gateway is not configured. Use MEESHO_GATEWAY=mock.")

    def set_self_pickup(self, db: Session, order_id: str, center_id: str) -> Dict[str, Any]:
        raise NotConfigured("Production Meesho Gateway is not configured. Use MEESHO_GATEWAY=mock.")

    def set_payment_mode(self, db: Session, order_id: str, mode: str, ref: str) -> Dict[str, Any]:
        raise NotConfigured("Production Meesho Gateway is not configured. Use MEESHO_GATEWAY=mock.")

    def get_payment_status(self, db: Session, order_id: str) -> Dict[str, Any]:
        raise NotConfigured("Production Meesho Gateway is not configured. Use MEESHO_GATEWAY=mock.")


def get_meesho_gateway() -> BaseMeeshoGateway:
    """Factory returning mock or real Meesho Gateway based on env (§10.1)."""
    mode = os.environ.get("MEESHO_GATEWAY", "mock").lower()
    if mode == "real":
        return RealMeeshoGateway()
    return MockMeeshoGateway()
