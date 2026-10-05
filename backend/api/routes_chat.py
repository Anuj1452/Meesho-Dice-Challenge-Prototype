import uuid
from fastapi import APIRouter, Depends, BackgroundTasks, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
load_dotenv()

from backend.models.database import get_session_factory, ChatMessage, ChatSession, Customer, Order
from backend.agent.runtime import AgentRuntime
from backend.services.meesho_gateway import get_meesho_gateway
from backend.gateway.tool_gateway import ToolGateway

router = APIRouter()
SessionLocal = get_session_factory()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ChatRequest(BaseModel):
    session_id: str
    phone_hash: str
    message: str
    message_type: Optional[str] = "text"
    button_payload: Optional[str] = ""


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    buttons: List[Dict[str, str]]
    error: Optional[str] = None


@router.post("/message", response_model=ChatResponse)
async def handle_customer_message(request: ChatRequest, db=Depends(get_db)):
    """Handle customer message and run through the turn pipeline (§3)."""
    runtime = AgentRuntime(db=db)
    
    # Run the turn pipeline (async — must be awaited)
    result = await runtime.process_turn(
        session_id=request.session_id,
        phone_hash=request.phone_hash,
        message_text=request.message,
        message_type=request.message_type or ("button_reply" if request.button_payload else "text"),
        button_payload=request.button_payload or "",
    )
    
    return ChatResponse(
        session_id=request.session_id,
        reply=result.get("response_text", "Sorry, error."),
        buttons=result.get("buttons", []),
        error=result.get("error")
    )


@router.get("/history/{session_id}")
def get_chat_history(session_id: str, db=Depends(get_db)):
    """Get chat history for a session."""
    messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.timestamp).all()
    return {
        "session_id": session_id,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "buttons": m.buttons,
                "timestamp": m.timestamp.isoformat()
            } for m in messages
        ]
    }


@router.get("/session/start/{phone_hash}")
def start_session(phone_hash: str, db=Depends(get_db)):
    """Initialize a customer session and return open orders to hydrate UI."""
    customer = db.query(Customer).filter(Customer.phone_hash == phone_hash).first()
    if not customer:
        session_id = str(uuid.uuid4())
        return {"session_id": session_id, "customer": None, "orders": []}

    # A new tab is a new conversation. Never reuse the customer's latest
    # session, otherwise turn limits and context leak between tabs.
    session_id = f"sess_{customer.phone_hash[:8]}_{uuid.uuid4().hex[:12]}"
    new_session = ChatSession(
        session_id=session_id,
        customer_id=customer.id,
        role="customer",
        verification_level="v0",
        turn_count=0,
    )
    db.add(new_session)
    db.commit()

    # Pre-fetch orders to show in UI drawer
    orders = db.query(Order).filter(Order.customer_id == customer.id).all()
    orders_data = [
        {
            "order_id": o.order_id,
            "product_name": o.product_name,
            "status": o.status,
            "amount": o.amount
        } for o in orders
    ]

    return {
        "session_id": session_id,
        "customer": {"name": customer.name, "language": customer.language},
        "orders": orders_data
    }


@router.post("/webhook/whatsapp")
def whatsapp_webhook(request: Request):
    """Meta Cloud API Webhook stub (§10.2)."""
    # In production, verify signature here and dedupe.
    return {"status": "success"}

@router.post("/payments/webhook")
def mock_payment_webhook(payload: dict, db=Depends(get_db)):
    """Mock webhook for payments (§7.2, §10.1)."""
    # Flips COD to Prepaid
    from backend.services.payments_adapter import PaymentsAdapter
    link_id = payload.get("link_id")
    payment_ref = payload.get("payment_ref", f"TXN_{uuid.uuid4().hex[:8].upper()}")
    amount_paid = payload.get("amount", 0.0)
    
    result = PaymentsAdapter.process_webhook(
        db=db,
        link_id=link_id,
        payment_ref=payment_ref,
        amount_paid=amount_paid
    )
    
    # Real-time SSE push would happen here.
    return result


@router.post("/demo/reset")
def reset_demo_data(db=Depends(get_db)):
    """Reset the demo database to fresh initial state with 14 customers and 14 stops."""
    import subprocess
    import sys
    from backend.models.database import Order, Customer, Rider, ValmoCenter, ChatSession, ChatMessage, TrackingEvent, AuditLog, Ticket, ScheduledCallback, PaymentLink
    from backend.sim.seed_data import CENTERS, CUSTOMERS, RIDERS, PRODUCTS, ORDER_SCENARIOS, CENTER_PINCODE_MAP, _awb, _order_id, _generate_tracking_events, _hash
    from datetime import datetime, timezone, timedelta
    import random

    db.query(ChatMessage).delete()
    db.query(ChatSession).delete()
    db.query(TrackingEvent).delete()
    db.query(AuditLog).delete()
    db.query(Ticket).delete()
    db.query(ScheduledCallback).delete()
    db.query(PaymentLink).delete()
    db.query(Order).delete()
    db.query(Customer).delete()
    db.query(Rider).delete()
    db.query(ValmoCenter).delete()
    db.commit()

    for c_data in CENTERS:
        db.add(ValmoCenter(**c_data))
    db.flush()

    customers = []
    for c_data in CUSTOMERS:
        cust = Customer(
            phone_hash=_hash(c_data["phone"]),
            name=c_data["name"],
            language=c_data["language"],
            city=c_data["city"],
            state=c_data["state"],
        )
        db.add(cust)
        customers.append(cust)
    db.flush()

    riders = []
    for r_data in RIDERS:
        r = Rider(
            rider_id=r_data["rider_id"],
            name=r_data["name"],
            phone_hash=_hash(f"rider_{r_data['rider_id']}"),
            hub_id=r_data["hub_id"],
        )
        db.add(r)
        riders.append(r)
    db.flush()

    amit = next(r for r in riders if r.rider_id == "RDR-001")

    for scenario in ORDER_SCENARIOS:
        customer = customers[scenario["customer_idx"]]
        product = PRODUCTS[scenario["product_idx"]]
        oid = _order_id()
        pincode = scenario["pincode"]
        center_id = CENTER_PINCODE_MAP.get(pincode, "VMC-DEL-01")
        ordered_at = datetime.now(timezone.utc) - timedelta(days=random.randint(2, 5))

        order = Order(
            order_id=oid,
            customer_id=customer.id,
            awb=_awb(),
            product_name=f"[SIMULATED] {product['name']}",
            product_category=product["category"],
            quantity=1,
            amount=product["amount"],
            payment_mode="cod" if scenario["is_cod"] else "prepaid",
            is_cod=scenario["is_cod"],
            amount_due=product["amount"] if scenario["is_cod"] else 0,
            address_text=scenario["address"],
            pincode=pincode,
            city=customer.city,
            state=customer.state,
            landmark=scenario.get("landmark", ""),
            customer_note=scenario.get("customer_note", ""),
            serving_center_id=center_id,
            lane_class="intra_region",
            status=scenario["status"].value,
            risk_tier=scenario["risk"].value,
            rider_id=amit.id,
            deferral_count=scenario.get("deferrals", 0),
            missed_call_count=scenario.get("missed_calls", 0),
            ordered_at=ordered_at,
            is_simulated=True,
        )
        db.add(order)
        db.flush()

        tracking_events = _generate_tracking_events(oid, scenario["status"], ordered_at)
        for evt in tracking_events:
            db.add(evt)

    db.commit()
    return {
        "status": "success",
        "message": "Demo data reset cleanly with 14 customers and 14 stops for Amit (RDR-001)",
        "customers_count": len(customers),
        "orders_count": len(ORDER_SCENARIOS)
    }
