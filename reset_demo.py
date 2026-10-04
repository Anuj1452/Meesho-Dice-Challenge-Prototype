from backend.models.database import (
    get_session_factory, Base, get_engine, Order, Customer, Rider, ValmoCenter,
    ChatSession, ChatMessage, TrackingEvent, AuditLog, Ticket, ScheduledCallback, PaymentLink
)
from backend.models.enums import OrderState, RiskTier
from backend.sim.seed_data import (
    CENTERS, CUSTOMERS, RIDERS, PRODUCTS, ORDER_SCENARIOS,
    CENTER_PINCODE_MAP, _awb, _order_id, _generate_tracking_events, _hash
)
from datetime import datetime, timezone, timedelta
import random

engine = get_engine()
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

SessionLocal = get_session_factory()
db = SessionLocal()

# 1. Seed centers
for c_data in CENTERS:
    db.add(ValmoCenter(**c_data))
db.flush()

# 2. Seed customers
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

# 3. Seed riders
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

# 4. Seed all order scenarios
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
db.close()
print(f"Demo database refreshed: {len(customers)} customers, {len(ORDER_SCENARIOS)} orders for Amit (RDR-001)!")

