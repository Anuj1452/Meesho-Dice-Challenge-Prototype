"""Synthetic seed data for the Valmo Mitra AI prototype.
All data is SIMULATED and labelled accordingly (§15).

Demo scenario:
- Hub: VMC-DEL-01 (Rohini, Delhi)
- Rider: RDR-001 (Amit) has 14 orders today from 14 different customers
- Each customer has a distinct scenario to showcase a different AI feature

Payout logic (SIMULATED):
  Standard delivery: Rs18/order
  High RTO zone or far address: Rs30/order (Valmo Mitra bonus)
"""

import random
import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from backend.models.database import (
    Customer, Order, Rider, ValmoCenter, TrackingEvent,
    init_db, get_session_factory,
)
from backend.models.enums import OrderState, RiskTier, LaneClass, PaymentMode


def _hash(phone: str) -> str:
    return hashlib.sha256(phone.encode()).hexdigest()[:16]


def _order_id() -> str:
    return f"MS{random.randint(100000000, 999999999)}"


def _awb() -> str:
    return f"AWB{random.randint(10000000000, 99999999999)}"


# === SIMULATED Center Directory ===
CENTERS = [
    {
        "center_id": "VMC-DEL-01", "name": "Valmo Delhi Rohini Center", "type": "last_mile_dc",
        "city": "Delhi", "district": "North Delhi", "state": "Delhi",
        "pincodes_served": ["110085", "110086", "110089"],
        "lat": 28.7325, "lng": 77.1189, "address": "Plot 15, Sector 11, Rohini, Delhi 110085",
        "hours_json": {"mon": "09:00-19:00", "tue": "09:00-19:00", "wed": "09:00-19:00",
                       "thu": "09:00-19:00", "fri": "09:00-19:00", "sat": "09:00-17:00", "sun": "closed"},
        "weekly_off": "sunday", "holidays": ["2026-10-02", "2026-10-24"],
        "accepts_self_pickup": True, "daily_pickup_capacity": 40, "status": "active",
    },
    {
        "center_id": "VMC-DEL-02", "name": "Valmo Delhi Dwarka Center", "type": "last_mile_dc",
        "city": "Delhi", "district": "South West Delhi", "state": "Delhi",
        "pincodes_served": ["110075", "110077", "110078"],
        "lat": 28.5921, "lng": 77.0460, "address": "Sector 12, Dwarka, Delhi 110078",
        "hours_json": {"mon": "09:00-19:00", "tue": "09:00-19:00", "wed": "09:00-19:00",
                       "thu": "09:00-19:00", "fri": "09:00-19:00", "sat": "09:00-17:00", "sun": "closed"},
        "weekly_off": "sunday", "holidays": [], "accepts_self_pickup": True,
        "daily_pickup_capacity": 35, "status": "active",
    },
    {
        "center_id": "VMC-MUM-01", "name": "Valmo Mumbai Andheri Center", "type": "last_mile_dc",
        "city": "Mumbai", "district": "Mumbai Suburban", "state": "Maharashtra",
        "pincodes_served": ["400053", "400058", "400069"],
        "lat": 19.1197, "lng": 72.8464, "address": "Unit 7, Andheri MIDC, Mumbai 400053",
        "hours_json": {"mon": "09:00-19:00", "tue": "09:00-19:00", "wed": "09:00-19:00",
                       "thu": "09:00-19:00", "fri": "09:00-19:00", "sat": "09:00-17:00", "sun": "closed"},
        "weekly_off": "sunday", "holidays": [], "accepts_self_pickup": True,
        "daily_pickup_capacity": 50, "status": "active",
    },
    {
        "center_id": "VMC-BLR-01", "name": "Valmo Bangalore Whitefield Center", "type": "last_mile_dc",
        "city": "Bangalore", "district": "Bangalore Urban", "state": "Karnataka",
        "pincodes_served": ["560066", "560048", "560037"],
        "lat": 12.9698, "lng": 77.7500, "address": "ITPL Main Rd, Whitefield, Bangalore 560066",
        "hours_json": {"mon": "09:00-19:00", "tue": "09:00-19:00", "wed": "09:00-19:00",
                       "thu": "09:00-19:00", "fri": "09:00-19:00", "sat": "09:00-17:00", "sun": "closed"},
        "weekly_off": "sunday", "holidays": [], "accepts_self_pickup": True,
        "daily_pickup_capacity": 45, "status": "active",
    },
    {
        "center_id": "VMC-LKO-01", "name": "Valmo Lucknow Gomti Nagar Center", "type": "last_mile_dc",
        "city": "Lucknow", "district": "Lucknow", "state": "Uttar Pradesh",
        "pincodes_served": ["226010", "226012", "226016"],
        "lat": 26.8508, "lng": 80.9919, "address": "Vikas Nagar, Gomti Nagar, Lucknow 226010",
        "hours_json": {"mon": "09:00-18:00", "tue": "09:00-18:00", "wed": "09:00-18:00",
                       "thu": "09:00-18:00", "fri": "09:00-18:00", "sat": "09:00-15:00", "sun": "closed"},
        "weekly_off": "sunday", "holidays": [], "accepts_self_pickup": True,
        "daily_pickup_capacity": 30, "status": "active",
    },
    {
        "center_id": "VMC-JAI-01", "name": "Valmo Jaipur Mansarovar Center", "type": "last_mile_dc",
        "city": "Jaipur", "district": "Jaipur", "state": "Rajasthan",
        "pincodes_served": ["302020", "302017", "302019"],
        "lat": 26.8691, "lng": 75.7605, "address": "Shipra Path, Mansarovar, Jaipur 302020",
        "hours_json": {"mon": "09:00-18:00", "tue": "09:00-18:00", "wed": "09:00-18:00",
                       "thu": "09:00-18:00", "fri": "09:00-18:00", "sat": "09:00-15:00", "sun": "closed"},
        "weekly_off": "sunday", "holidays": [], "accepts_self_pickup": True,
        "daily_pickup_capacity": 25, "status": "active",
    },
    {
        "center_id": "VMC-PAT-01", "name": "Valmo Patna Kankarbagh Center", "type": "last_mile_dc",
        "city": "Patna", "district": "Patna", "state": "Bihar",
        "pincodes_served": ["800020", "800001", "800004"],
        "lat": 25.5941, "lng": 85.1376, "address": "Ashiana Rd, Kankarbagh, Patna 800020",
        "hours_json": {"mon": "09:00-18:00", "tue": "09:00-18:00", "wed": "09:00-18:00",
                       "thu": "09:00-18:00", "fri": "09:00-18:00", "sat": "09:00-15:00", "sun": "closed"},
        "weekly_off": "sunday", "holidays": [], "accepts_self_pickup": True,
        "daily_pickup_capacity": 20, "status": "active",
    },
    {
        "center_id": "VMC-IND-01", "name": "Valmo Indore Vijay Nagar Center", "type": "last_mile_dc",
        "city": "Indore", "district": "Indore", "state": "Madhya Pradesh",
        "pincodes_served": ["452010", "452001", "452009"],
        "lat": 22.7533, "lng": 75.8937, "address": "AB Road, Vijay Nagar, Indore 452010",
        "hours_json": {"mon": "09:00-18:00", "tue": "09:00-18:00", "wed": "09:00-18:00",
                       "thu": "09:00-18:00", "fri": "09:00-18:00", "sat": "09:00-15:00", "sun": "closed"},
        "weekly_off": "sunday", "holidays": [], "accepts_self_pickup": False,
        "daily_pickup_capacity": 0, "status": "active",
    },
    # Sort centers (internal only, never shown to customers — R-31)
    {
        "center_id": "VMC-SC-DEL", "name": "Delhi Sort Center", "type": "sort_center",
        "city": "Delhi", "district": "Central Delhi", "state": "Delhi",
        "pincodes_served": [], "lat": 28.6139, "lng": 77.2090,
        "address": "Internal — not customer-facing", "hours_json": {},
        "weekly_off": "", "holidays": [], "accepts_self_pickup": False,
        "daily_pickup_capacity": 0, "status": "active",
    },
]

# === SIMULATED Customers — 14 customers, all in Rohini (VMC-DEL-01) pincodes ===
CUSTOMERS = [
    # idx 0: Priya - IN_TRANSIT, COD Rs449
    {"phone": "9198765001", "name": "Priya Sharma",   "language": "hinglish",
     "city": "Delhi", "state": "Delhi", "pincode": "110085"},
    # idx 1: Rahul - OUT_FOR_DELIVERY, HIGH risk
    {"phone": "9198765002", "name": "Rahul Verma",    "language": "hindi",
     "city": "Delhi", "state": "Delhi", "pincode": "110085"},
    # idx 2: Anita - FAILED_ATTEMPT, wants reschedule
    {"phone": "9198765003", "name": "Anita Patel",    "language": "hinglish",
     "city": "Delhi", "state": "Delhi", "pincode": "110086"},
    # idx 3: Suresh - AT_HUB, COD Rs1299, wants payment link
    {"phone": "9198765004", "name": "Suresh Kumar",   "language": "hindi",
     "city": "Delhi", "state": "Delhi", "pincode": "110086"},
    # idx 4: Meena - RESCHEDULED 2x, HIGH risk, angry
    {"phone": "9198765005", "name": "Meena Devi",     "language": "hindi",
     "city": "Delhi", "state": "Delhi", "pincode": "110089"},
    # idx 5: Vikram - OUT_FOR_DELIVERY, wants address change same pincode
    {"phone": "9198765006", "name": "Vikram Singh",   "language": "hinglish",
     "city": "Delhi", "state": "Delhi", "pincode": "110085"},
    # idx 6: Deepa - OUT_FOR_DELIVERY, PREPAID, leave with neighbour
    {"phone": "9198765007", "name": "Deepa Joshi",    "language": "hindi",
     "city": "Delhi", "state": "Delhi", "pincode": "110086"},
    # idx 7: Arjun - FAILED_ATTEMPT, missed call x2, HIGH risk
    {"phone": "9198765008", "name": "Arjun Malhotra", "language": "hinglish",
     "city": "Delhi", "state": "Delhi", "pincode": "110089"},
    # idx 8: Sunita - OUT_FOR_DELIVERY, PREPAID, wants tracking
    {"phone": "9198765009", "name": "Sunita Rao",     "language": "hinglish",
     "city": "Delhi", "state": "Delhi", "pincode": "110085"},
    # idx 9: Ramesh - AT_HUB, COD Rs1899, wants payment link
    {"phone": "9198765010", "name": "Ramesh Gupta",   "language": "hindi",
     "city": "Delhi", "state": "Delhi", "pincode": "110086"},
    # idx 10: Kavita - RESCHEDULED x1, worried
    {"phone": "9198765011", "name": "Kavita Sharma",  "language": "hinglish",
     "city": "Delhi", "state": "Delhi", "pincode": "110089"},
    # idx 11: Mohan - OUT_FOR_DELIVERY, far/high-RTO zone, Rs30 payout
    {"phone": "9198765012", "name": "Mohan Lal",      "language": "hindi",
     "city": "Delhi", "state": "Delhi", "pincode": "110089"},
    # idx 12: Geeta - FAILED_ATTEMPT, wants self-pickup
    {"phone": "9198765013", "name": "Geeta Pandey",   "language": "hinglish",
     "city": "Delhi", "state": "Delhi", "pincode": "110085"},
    # idx 13: Sanjay - OUT_FOR_DELIVERY, PREPAID, gate note scenario
    {"phone": "9198765014", "name": "Sanjay Tiwari",  "language": "hindi",
     "city": "Delhi", "state": "Delhi", "pincode": "110086"},
]

# === SIMULATED Riders ===
RIDERS = [
    # RDR-001 (Amit) handles VMC-DEL-01 — all 5 demo customers are in his manifest
    {"rider_id": "RDR-001", "name": "Amit",   "hub_id": "VMC-DEL-01"},
    {"rider_id": "RDR-002", "name": "Rajesh", "hub_id": "VMC-DEL-02"},
    {"rider_id": "RDR-003", "name": "Vikram", "hub_id": "VMC-MUM-01"},
    {"rider_id": "RDR-004", "name": "Sunil",  "hub_id": "VMC-BLR-01"},
    {"rider_id": "RDR-005", "name": "Pappu",  "hub_id": "VMC-LKO-01"},
    {"rider_id": "RDR-006", "name": "Gopal",  "hub_id": "VMC-JAI-01"},
    {"rider_id": "RDR-007", "name": "Raju",   "hub_id": "VMC-PAT-01"},
    {"rider_id": "RDR-008", "name": "Kamal",  "hub_id": "VMC-IND-01"},
]

# === SIMULATED Products ===
PRODUCTS = [
    {"name": "Women's Cotton Kurti - Blue Floral",     "category": "Women Ethnic",     "amount": 449},   # 0
    {"name": "Men's Slim Fit Jeans - Black",           "category": "Men Western",       "amount": 599},   # 1
    {"name": "Gold Plated Jhumka Earrings",            "category": "Jewellery",         "amount": 199},   # 2
    {"name": "Kitchen Mixer Grinder 500W",             "category": "Home Appliances",   "amount": 1299},  # 3
    {"name": "Cotton Bedsheet Double - Jaipuri Print", "category": "Home Furnishing",   "amount": 349},   # 4
    {"name": "Girls' Party Dress - Pink",              "category": "Kids",              "amount": 399},   # 5
    {"name": "Men's Sports Shoes - White",             "category": "Footwear",          "amount": 699},   # 6
    {"name": "Silk Saree - Green Banarasi",            "category": "Women Ethnic",      "amount": 899},   # 7
    {"name": "Stainless Steel Lunch Box Set",          "category": "Kitchen",           "amount": 249},   # 8
    {"name": "Phone Back Cover - Transparent",         "category": "Mobile Accessories","amount": 149},   # 9
    {"name": "Casual Men's Polo T-Shirt - Navy",       "category": "Men Western",       "amount": 379},   # 10
    {"name": "Women's Palazzo Set - Printed",          "category": "Women Ethnic",      "amount": 529},   # 11
    {"name": "Smart LED Bulb 9W (Pack of 4)",          "category": "Home Appliances",   "amount": 299},   # 12
    {"name": "Digital Wall Clock - Wooden",            "category": "Home Decor",        "amount": 499},   # 13
    {"name": "Kids Story Book Set (5 Books)",          "category": "Books",             "amount": 349},   # 14
    {"name": "Formal Shirt Men's - White Check",       "category": "Men Western",       "amount": 649},   # 15
    {"name": "Stainless Steel Water Bottle 1L",        "category": "Kitchen",           "amount": 249},   # 16
    {"name": "Heavy Mixer Grinder 750W",               "category": "Home Appliances",   "amount": 1899},  # 17
    {"name": "Cotton Anarkali Suit - Red",             "category": "Women Ethnic",      "amount": 799},   # 18
    {"name": "Wireless Bluetooth Earbuds",             "category": "Mobile Accessories","amount": 899},   # 19
]


def _compute_payout(risk: RiskTier, is_far_zone: bool = False) -> int:
    """Compute rider payout per delivery (SIMULATED).
    Standard Rs15. High-RTO zone or far address Rs30 (Valmo Mitra incentive).
    """
    if risk == RiskTier.HIGH or is_far_zone:
        return 30
    return 15

CENTER_PINCODE_MAP = {}
for c in CENTERS:
    for pin in c["pincodes_served"]:
        CENTER_PINCODE_MAP[pin] = c["center_id"]


# === DEMO ORDER SCENARIOS — all assigned to RDR-001 at VMC-DEL-01 ===
# is_far_zone=True marks deliveries far from hub (high-RTO belt) -> payout Rs30
ORDER_SCENARIOS = [
    # 1. Priya Sharma — IN_TRANSIT, COD Rs449, MEDIUM risk
    {
        "customer_idx": 0, "product_idx": 0,
        "status": OrderState.IN_TRANSIT, "risk": RiskTier.MEDIUM,
        "pincode": "110085", "is_cod": True,
        "address": "B-42, Sector 7, Rohini, Delhi 110085",
        "landmark": "Near Mother Dairy Booth",
        "customer_note": "", "rider_hub": "VMC-DEL-01", "is_far_zone": False,
    },
    # 2. Rahul Verma — OUT_FOR_DELIVERY, COD Rs599, HIGH risk (past RTO)
    {
        "customer_idx": 1, "product_idx": 1,
        "status": OrderState.OUT_FOR_DELIVERY, "risk": RiskTier.HIGH,
        "pincode": "110085", "is_cod": True,
        "address": "House 15, Pocket C, Sector 14, Rohini, Delhi 110085",
        "landmark": "Opposite Green Park",
        "customer_note": "Call before coming, gate locked after 6pm",
        "rider_hub": "VMC-DEL-01", "is_far_zone": False,
    },
    # 3. Anita Patel — FAILED_ATTEMPT, COD Rs199, MEDIUM risk
    {
        "customer_idx": 2, "product_idx": 2,
        "status": OrderState.FAILED_ATTEMPT, "risk": RiskTier.MEDIUM,
        "pincode": "110086", "is_cod": True,
        "address": "Flat 203, Tower B, Sector 4, Rohini, Delhi 110086",
        "landmark": "Near Rohini East Metro",
        "customer_note": "", "rider_hub": "VMC-DEL-01", "is_far_zone": False,
    },
    # 4. Suresh Kumar — AT_DESTINATION_HUB, COD Rs1299, LOW risk
    {
        "customer_idx": 3, "product_idx": 3,
        "status": OrderState.AT_DESTINATION_HUB, "risk": RiskTier.LOW,
        "pincode": "110086", "is_cod": True,
        "address": "Plot 9, DDA Flats, Sector 11, Rohini, Delhi 110086",
        "landmark": "Near Rohini Sector 11 bus stop",
        "customer_note": "", "rider_hub": "VMC-DEL-01", "is_far_zone": False,
    },
    # 5. Meena Devi — RESCHEDULED x2, COD Rs399, HIGH risk
    {
        "customer_idx": 4, "product_idx": 5,
        "status": OrderState.RESCHEDULED, "risk": RiskTier.HIGH,
        "pincode": "110089", "is_cod": True,
        "address": "House 3, Gali No 5, Sector 24, Rohini, Delhi 110089",
        "landmark": "Near Rohini Sector 24 Metro",
        "customer_note": "Please call before delivery",
        "deferrals": 2, "rider_hub": "VMC-DEL-01", "is_far_zone": True,
    },
    # 6. Vikram Singh — OUT_FOR_DELIVERY, address change same pincode
    {
        "customer_idx": 5, "product_idx": 6,
        "status": OrderState.OUT_FOR_DELIVERY, "risk": RiskTier.LOW,
        "pincode": "110085", "is_cod": True,
        "address": "C-15, Block C, Sector 9, Rohini, Delhi 110085",
        "landmark": "Near HDFC Bank",
        "customer_note": "", "rider_hub": "VMC-DEL-01", "is_far_zone": False,
    },
    # 7. Deepa Joshi — OUT_FOR_DELIVERY, PREPAID, leave with neighbour
    {
        "customer_idx": 6, "product_idx": 7,
        "status": OrderState.OUT_FOR_DELIVERY, "risk": RiskTier.MEDIUM,
        "pincode": "110086", "is_cod": False,
        "address": "D-4, Pocket 2, Sector 8, Rohini, Delhi 110086",
        "landmark": "Near Sector 8 Park",
        "customer_note": "", "rider_hub": "VMC-DEL-01", "is_far_zone": False,
    },
    # 8. Arjun Malhotra — FAILED_ATTEMPT, missed call x2, HIGH risk
    {
        "customer_idx": 7, "product_idx": 8,
        "status": OrderState.FAILED_ATTEMPT, "risk": RiskTier.HIGH,
        "pincode": "110089", "is_cod": True,
        "address": "E-77, Sector 26, Rohini, Delhi 110089",
        "landmark": "Near Sector 26 Chowk",
        "customer_note": "", "missed_calls": 2,
        "rider_hub": "VMC-DEL-01", "is_far_zone": True,
    },
    # 9. Sunita Rao — OUT_FOR_DELIVERY, PREPAID, wants tracking
    {
        "customer_idx": 8, "product_idx": 9,
        "status": OrderState.OUT_FOR_DELIVERY, "risk": RiskTier.LOW,
        "pincode": "110085", "is_cod": False,
        "address": "F-22, Pocket 4, Sector 16, Rohini, Delhi 110085",
        "landmark": "Near Rohini West Metro",
        "customer_note": "", "rider_hub": "VMC-DEL-01", "is_far_zone": False,
    },
    # 10. Ramesh Gupta — AT_HUB, COD Rs1899, wants payment link
    {
        "customer_idx": 9, "product_idx": 17,
        "status": OrderState.AT_DESTINATION_HUB, "risk": RiskTier.MEDIUM,
        "pincode": "110086", "is_cod": True,
        "address": "G-3, MIG Flats, Sector 12, Rohini, Delhi 110086",
        "landmark": "Near SBI Bank Branch",
        "customer_note": "", "rider_hub": "VMC-DEL-01", "is_far_zone": False,
    },
    # 11. Kavita Sharma — RESCHEDULED x1, worried
    {
        "customer_idx": 10, "product_idx": 10,
        "status": OrderState.RESCHEDULED, "risk": RiskTier.MEDIUM,
        "pincode": "110089", "is_cod": True,
        "address": "H-11, Pocket 1, Sector 21, Rohini, Delhi 110089",
        "landmark": "Near Sector 21 Park",
        "customer_note": "", "deferrals": 1,
        "rider_hub": "VMC-DEL-01", "is_far_zone": True,
    },
    # 12. Mohan Lal — OUT_FOR_DELIVERY, far/high-RTO zone, Rs30 payout
    {
        "customer_idx": 11, "product_idx": 11,
        "status": OrderState.OUT_FOR_DELIVERY, "risk": RiskTier.HIGH,
        "pincode": "110089", "is_cod": True,
        "address": "I-8, Gali 3, Sector 28, Rohini, Delhi 110089",
        "landmark": "Near Outer Ring Road overpass",
        "customer_note": "Ring bell twice, top floor flat",
        "rider_hub": "VMC-DEL-01", "is_far_zone": True,
    },
    # 13. Geeta Pandey — FAILED_ATTEMPT, wants self-pickup
    {
        "customer_idx": 12, "product_idx": 12,
        "status": OrderState.FAILED_ATTEMPT, "risk": RiskTier.LOW,
        "pincode": "110085", "is_cod": True,
        "address": "J-55, Sector 6, Rohini, Delhi 110085",
        "landmark": "Near Community Centre",
        "customer_note": "", "rider_hub": "VMC-DEL-01", "is_far_zone": False,
    },
    # 14. Sanjay Tiwari — OUT_FOR_DELIVERY, PREPAID, gate note scenario
    {
        "customer_idx": 13, "product_idx": 13,
        "status": OrderState.OUT_FOR_DELIVERY, "risk": RiskTier.LOW,
        "pincode": "110086", "is_cod": False,
        "address": "K-2, Pocket 3, Sector 3, Rohini, Delhi 110086",
        "landmark": "Near Pocket 3 Gate",
        "customer_note": "", "rider_hub": "VMC-DEL-01", "is_far_zone": False,
    },
]


def _generate_tracking_events(order_id: str, status: OrderState, ordered_at: datetime) -> list:
    """Generate realistic tracking events up to the current status."""
    events = []
    state_sequence = [
        (OrderState.CONFIRMED,              "Order placed and confirmed",          "Seller Warehouse"),
        (OrderState.MANIFESTED,             "Order packed and ready for pickup",   "Seller Warehouse"),
        (OrderState.PICKED_UP_FROM_SELLER,  "Picked up from seller",              "Seller City"),
        (OrderState.IN_TRANSIT,             "In transit to destination",           "Delhi Sort Center"),
        (OrderState.AT_DESTINATION_HUB,     "Arrived at Rohini Delivery Center",  "Rohini, Delhi"),
        (OrderState.OUT_FOR_DELIVERY,       "Out for delivery with Amit",          "Rohini, Delhi"),
    ]

    terminal_states = {
        OrderState.DELIVERED:      ("[SIMULATED] Delivered successfully",                    "Customer Address"),
        OrderState.FAILED_ATTEMPT: ("[SIMULATED] Delivery attempted, customer not available","Customer Address"),
        OrderState.SKIPPED_TODAY:  ("[SIMULATED] Delivery deferred to next day",             "Rohini Center"),
        OrderState.RESCHEDULED:    ("[SIMULATED] Rescheduled by customer",                   "Rohini Center"),
    }

    current_time = ordered_at
    for state, desc, loc in state_sequence:
        current_time += timedelta(hours=random.randint(4, 16))
        events.append(TrackingEvent(
            order_id=order_id, status=state.value,
            location=loc, description=f"[SIMULATED] {desc}",
            timestamp=current_time,
        ))
        if state == status:
            break

    if status in terminal_states:
        desc, loc = terminal_states[status]
        current_time += timedelta(hours=random.randint(1, 6))
        events.append(TrackingEvent(
            order_id=order_id, status=status.value,
            location=loc, description=desc,
            timestamp=current_time,
        ))

    return events


def seed_database(db: Session) -> dict:
    """Seed the database with SIMULATED data. Returns summary counts."""
    existing = db.query(Customer).count()
    if existing > 0:
        return {"status": "already_seeded", "customers": existing}

    # 1. Seed centers
    centers_created = 0
    for c_data in CENTERS:
        center = ValmoCenter(**c_data)
        db.add(center)
        centers_created += 1
    db.flush()

    # 2. Seed customers
    customers = []
    for c_data in CUSTOMERS:
        customer = Customer(
            phone_hash=_hash(c_data["phone"]),
            name=c_data["name"],
            language=c_data["language"],
            city=c_data["city"],
            state=c_data["state"],
        )
        db.add(customer)
        customers.append(customer)
    db.flush()

    # 3. Seed riders
    riders = []
    for r_data in RIDERS:
        rider = Rider(
            rider_id=r_data["rider_id"],
            name=r_data["name"],
            phone_hash=_hash(f"rider_{r_data['rider_id']}"),
            hub_id=r_data["hub_id"],
        )
        db.add(rider)
        riders.append(rider)
    db.flush()

    # RDR-001 object (Amit) for quick lookup
    amit = next(r for r in riders if r.rider_id == "RDR-001")

    # 4. Seed orders with tracking events
    orders_created = 0
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
            lane_class=LaneClass.INTRA_REGION.value,
            status=scenario["status"].value,
            risk_tier=scenario["risk"].value,
            rider_id=amit.id,   # ALL orders assigned to Amit (RDR-001)
            deferral_count=scenario.get("deferrals", 0),
            missed_call_count=scenario.get("missed_calls", 0),
            ordered_at=ordered_at,
            is_simulated=True,
        )

        if scenario["status"] == OrderState.DELIVERED:
            order.delivered_at = datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 24))

        db.add(order)
        db.flush()

        tracking_events = _generate_tracking_events(oid, scenario["status"], ordered_at)
        for evt in tracking_events:
            db.add(evt)

        orders_created += 1

    db.commit()

    return {
        "status": "seeded",
        "customers": len(customers),
        "riders": len(riders),
        "centers": centers_created,
        "orders": orders_created,
        "label": "ALL DATA IS SIMULATED",
    }


# Phone-to-hash lookup (use these in the frontend to switch users)
PHONE_HASH_MAP = {c["phone"]: _hash(c["phone"]) for c in CUSTOMERS}
HASH_PHONE_MAP = {v: k for k, v in PHONE_HASH_MAP.items()}

# Print hashes for dev reference
if __name__ == "__main__":
    print("\n=== DEMO USER PHONE HASHES (use in frontend) ===")
    scenarios = [
        "IN_TRANSIT + COD — 'kahan hai mera order?'",
        "OUT_FOR_DELIVERY + HIGH risk — rider nudge, delivery note",
        "FAILED_ATTEMPT — reschedule / set_availability",
        "AT_HUB + COD — 'online pay karna hai' → payment link",
        "RESCHEDULED x2 + HIGH risk — angry, escalate to human",
        "OUT_FOR_DELIVERY — address change in same pincode",
        "OUT_FOR_DELIVERY — leave with neighbour",
        "FAILED_ATTEMPT — missed call x2, high risk",
        "OUT_FOR_DELIVERY — PREPAID tracking check",
        "AT_HUB + COD Rs1899 — payment link request",
        "RESCHEDULED x1 — deferral check",
        "OUT_FOR_DELIVERY — far zone, Rs30 payout",
        "FAILED_ATTEMPT — self-pickup request",
        "OUT_FOR_DELIVERY — gate note scenario",
    ]
    for i, c in enumerate(CUSTOMERS):
        h = _hash(c["phone"])
        sc = scenarios[i] if i < len(scenarios) else "Demo customer"
        print(f"  [{i+1:02d}] {c['name']:18s} | {c['phone']} → hash: {h} | {sc}")
    print()
