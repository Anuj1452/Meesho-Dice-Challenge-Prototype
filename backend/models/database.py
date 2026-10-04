"""SQLAlchemy database models for Valmo Mitra AI."""

import os
import json
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, JSON,
    ForeignKey, Index, create_engine, event
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone_hash = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(100))
    language = Column(String(20), default="hinglish")
    preferred_slot = Column(String(50))
    city = Column(String(100))
    state = Column(String(100))
    opted_in = Column(Boolean, default=True)
    stopped = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    orders = relationship("Order", back_populates="customer")
    sessions = relationship("ChatSession", back_populates="customer")


class ValmoCenter(Base):
    """Valmo center directory (§5A)."""
    __tablename__ = "valmo_centers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    center_id = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    type = Column(String(20), nullable=False)  # last_mile_dc, sort_center, fm_hub
    city = Column(String(100), nullable=False)
    district = Column(String(100))
    state = Column(String(100), nullable=False)
    pincodes_served = Column(JSON, default=list)  # List of pincodes
    lat = Column(Float)
    lng = Column(Float)
    address = Column(Text)
    hours_json = Column(JSON)  # {"mon": "09:00-18:00", ...}
    weekly_off = Column(String(20))  # e.g., "sunday"
    holidays = Column(JSON, default=list)
    accepts_self_pickup = Column(Boolean, default=False)
    daily_pickup_capacity = Column(Integer, default=50)
    status = Column(String(10), default="active")  # active, paused


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(20), unique=True, nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    awb = Column(String(30), unique=True, index=True)

    # Product
    product_name = Column(String(200))
    product_category = Column(String(100))
    product_image_url = Column(String(500))
    quantity = Column(Integer, default=1)
    amount = Column(Float, nullable=False)

    # Payment
    payment_mode = Column(String(10), default="cod")  # cod, prepaid
    is_cod = Column(Boolean, default=True)
    amount_due = Column(Float)
    payment_link_id = Column(String(50))
    payment_link_expiry = Column(DateTime)
    payment_verified = Column(Boolean, default=False)

    # Delivery
    address_text = Column(Text)
    original_address = Column(Text)  # Preserves initial address before any customer edits
    pincode = Column(String(6), nullable=False, index=True)
    city = Column(String(100), nullable=False)
    state = Column(String(100), nullable=False)
    landmark = Column(String(200))
    customer_note = Column(String(300), default="")  # Special instruction from customer to rider
    lat = Column(Float)
    lng = Column(Float)

    # Center and routing
    serving_center_id = Column(String(20), ForeignKey("valmo_centers.center_id"))
    lane_class = Column(String(20), default="intra_region")

    # Self pickup (§7.3A)
    self_pickup = Column(Boolean, default=False)
    pickup_code = Column(String(6))
    pickup_ready_at = Column(DateTime)
    pickup_hold_expires = Column(DateTime)

    # Status
    status = Column(String(30), default="CONFIRMED")
    risk_tier = Column(String(10), default="low")

    # Availability & notes
    availability_slot = Column(String(100))
    delivery_note = Column(String(120))
    alternate_receiver = Column(String(100))
    deferral_count = Column(Integer, default=0)
    address_edit_count = Column(Integer, default=0)
    missed_call_count = Column(Integer, default=0)
    customer_response_status = Column(String(50), default="")

    # Rider
    rider_id = Column(Integer, ForeignKey("riders.id"))

    # Timestamps
    ordered_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    dispatched_at = Column(DateTime)
    delivered_at = Column(DateTime)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Simulated flag
    is_simulated = Column(Boolean, default=True)

    customer = relationship("Customer", back_populates="orders")
    rider = relationship("Rider", back_populates="orders")
    tracking_events = relationship("TrackingEvent", back_populates="order", order_by="TrackingEvent.timestamp")
    tickets = relationship("Ticket", back_populates="order")

    __table_args__ = (
        Index("ix_orders_customer_status", "customer_id", "status"),
    )


class Rider(Base):
    __tablename__ = "riders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rider_id = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    phone_hash = Column(String(64))
    hub_id = Column(String(20))
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    orders = relationship("Order", back_populates="rider")


class TrackingEvent(Base):
    __tablename__ = "tracking_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(20), ForeignKey("orders.order_id"), nullable=False, index=True)
    status = Column(String(30), nullable=False)
    location = Column(String(200))
    description = Column(Text)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    order = relationship("Order", back_populates="tracking_events")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), unique=True, nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    rider_id = Column(Integer, ForeignKey("riders.id"))
    role = Column(String(10), default="customer")  # customer, rider, ops
    turn_count = Column(Integer, default=0)
    messages_this_hour = Column(Integer, default=0)
    hour_window_start = Column(DateTime)
    verification_level = Column(String(10), default="v0")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    customer = relationship("Customer", back_populates="sessions")
    messages = relationship("ChatMessage", back_populates="session", order_by="ChatMessage.timestamp")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("chat_sessions.session_id"), nullable=False, index=True)
    role = Column(String(15), nullable=False)  # user, assistant, system
    content = Column(Text)
    buttons = Column(JSON)  # List of button payloads
    message_type = Column(String(20), default="text")  # text, button_reply, voice, image, location, template
    media_url = Column(String(500))
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    session = relationship("ChatSession", back_populates="messages")


class AuditLog(Base):
    """Every tool call is logged here (§5.5)."""
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), index=True)
    actor_role = Column(String(10))  # customer, rider, ops
    actor_id = Column(String(64))
    tool_name = Column(String(50), nullable=False)
    arguments = Column(JSON)
    result = Column(JSON)
    success = Column(Boolean, default=True)
    refusal_reason = Column(Text)
    model_rationale = Column(String(100))  # Max 20 words
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_audit_tool_time", "tool_name", "timestamp"),
    )


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(String(20), unique=True, nullable=False, index=True)
    order_id = Column(String(20), ForeignKey("orders.order_id"), nullable=False)
    category = Column(String(30), nullable=False)
    severity = Column(String(5), default="P3")
    status = Column(String(20), default="open")
    summary = Column(Text)  # 3-line summary
    photos = Column(JSON, default=list)
    messages = Column(JSON, default=list)  # Appended messages
    assigned_to = Column(String(100))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    order = relationship("Order", back_populates="tickets")


class ScheduledCallback(Base):
    __tablename__ = "scheduled_callbacks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    order_id = Column(String(20))
    scheduled_time = Column(DateTime, nullable=False)
    reason = Column(Text)
    status = Column(String(20), default="pending")  # pending, completed, cancelled
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class PaymentLink(Base):
    __tablename__ = "payment_links"

    id = Column(Integer, primary_key=True, autoincrement=True)
    link_id = Column(String(50), unique=True, nullable=False, index=True)
    order_id = Column(String(20), ForeignKey("orders.order_id"), nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String(20), default="active")  # active, paid, expired
    payment_url = Column(String(500))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=False)
    paid_at = Column(DateTime)


class PendingAction(Base):
    """Ops copilot proposals that need human approval (§5.3)."""
    __tablename__ = "pending_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action_id = Column(String(20), unique=True, nullable=False)
    action_type = Column(String(50), nullable=False)  # hub_review, callback, address_correction, goodwill
    target_id = Column(String(50))  # order_id, rider_id, hub_id
    description = Column(Text)
    proposed_by = Column(String(20), default="copilot")
    status = Column(String(20), default="pending")  # pending, approved, rejected
    approved_by = Column(String(100))
    evidence = Column(JSON)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime)


class CostTracker(Base):
    """Per-session cost tracking for the cost panel."""
    __tablename__ = "cost_tracker"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), index=True)
    event_type = Column(String(30))  # llm_call, template_sent, whisper_call
    tokens_in = Column(Integer, default=0)
    tokens_cached_in = Column(Integer, default=0)
    tokens_out = Column(Integer, default=0)
    cost_inr = Column(Float, default=0.0)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# === Database Setup ===

_engine = None
_SessionLocal = None


def _default_db_url():
    db_path = os.environ.get("DB_PATH", "./valmo_mitra.db")
    return f"sqlite:///{db_path}"


def get_engine(database_url: str = None):
    if database_url is None:
        database_url = _default_db_url()
    global _engine
    if _engine is None:
        _engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False} if "sqlite" in database_url else {},
            echo=False,
        )
        # Enable WAL mode for SQLite
        if "sqlite" in database_url:
            @event.listens_for(_engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
    return _engine


def get_session_factory(database_url: str = None):
    if database_url is None:
        database_url = _default_db_url()
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine(database_url)
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SessionLocal


def init_db(database_url: str = None):
    if database_url is None:
        database_url = _default_db_url()
    """Create all tables."""
    engine = get_engine(database_url)
    Base.metadata.create_all(bind=engine)
    return engine


def get_db():
    """FastAPI dependency for database sessions."""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
