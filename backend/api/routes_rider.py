from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from backend.models.database import get_session_factory
from backend.tools import rider_tools

router = APIRouter()
SessionLocal = get_session_factory()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/manifest/{rider_id}")
def get_rider_manifest(rider_id: str, db=Depends(get_db)):
    """Get today's delivery manifest for a rider (§5.2)."""
    return rider_tools.get_manifest(db, rider_id)


@router.get("/order/{rider_id}/{order_id}")
def get_rider_order_card(rider_id: str, order_id: str, db=Depends(get_db)):
    """Get single order details for the rider screen."""
    return rider_tools.get_order_card(db, order_id, rider_id)


class OutcomeRequest(BaseModel):
    order_id: str
    outcome: str
    reason: Optional[str] = None


@router.post("/outcome/{rider_id}")
def mark_delivery_outcome(rider_id: str, request: OutcomeRequest, db=Depends(get_db)):
    """Mark the outcome of a delivery stop."""
    return rider_tools.mark_outcome(db, request.order_id, rider_id, request.outcome, request.reason)


class ProblemRequest(BaseModel):
    order_id: str
    problem_type: str
    description: Optional[str] = None


@router.post("/problem/{rider_id}")
def report_delivery_problem(rider_id: str, request: ProblemRequest, db=Depends(get_db)):
    """Report an issue (gate locked, phone off) to trigger customer pin drop."""
    return rider_tools.report_problem(db, request.order_id, rider_id, request.problem_type, request.description)


@router.post("/nudge/{rider_id}/{order_id}")
def nudge_customer_arrival(rider_id: str, order_id: str, db=Depends(get_db)):
    """Nudge customer when rider reaches the location or in morning."""
    return rider_tools.nudge_customer(db, order_id, rider_id)


@router.post("/nudge-all/{rider_id}")
def nudge_all_customers_morning(rider_id: str, db=Depends(get_db)):
    """Send morning arrival nudge to all customers on today's manifest."""
    return rider_tools.nudge_all_customers(db, rider_id)


@router.post("/missed-call/{rider_id}/{order_id}")
def report_missed_call(rider_id: str, order_id: str, db=Depends(get_db)):
    """Log an unanswered call attempt (at least 3 attempts) and notify customer on WhatsApp."""
    return rider_tools.record_missed_call(db, order_id, rider_id)


@router.get("/route/{rider_id}")
def suggest_route(rider_id: str, db=Depends(get_db)):
    """Suggest delivery sequence based on skipped orders and pincode clusters."""
    return rider_tools.suggest_route_order(db, rider_id)


@router.get("/myday/{rider_id}")
def get_my_day_stats(rider_id: str, db=Depends(get_db)):
    """Get the Dead Mile Counter and ₹ saved metrics for the rider (§5.2, §9)."""
    return rider_tools.get_my_day(db, rider_id)
