from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from backend.models.database import get_session_factory
from backend.tools import ops_tools

router = APIRouter()
SessionLocal = get_session_factory()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/metrics/{hub_id}")
def get_hub_metrics(hub_id: str, days: int = 7, db=Depends(get_db)):
    """Get hub metrics (RTO%, attempts/delivery) (§5.3)."""
    return ops_tools.get_hub_metrics(db, hub_id, days)


@router.get("/queue/{hub_id}")
def get_review_queue(hub_id: str, db=Depends(get_db)):
    """List flagged cases needing ops review."""
    return {"queue": ops_tools.list_review_queue(db, hub_id)}


@router.get("/case/{order_id}")
def get_case_bundle(order_id: str, db=Depends(get_db)):
    """Get full case history bundle for an order."""
    return ops_tools.get_case_bundle(db, order_id)


@router.get("/score/{order_id}")
def explain_risk_score(order_id: str, db=Depends(get_db)):
    """Explain risk tier in plain words."""
    return ops_tools.explain_score(db, order_id)


@router.get("/pending-actions")
def get_pending_actions():
    """List actions proposed by copilot waiting for human approval."""
    return {"actions": ops_tools.list_pending_actions()}


class ResolveActionRequest(BaseModel):
    approved: bool
    reviewer: str = "Ops Lead"


@router.post("/pending-actions/{proposal_id}/resolve")
def resolve_pending_action(proposal_id: str, request: ResolveActionRequest):
    """Approve or reject a copilot proposed action."""
    return ops_tools.resolve_action(proposal_id, request.approved, request.reviewer)


class CopilotRequest(BaseModel):
    message: str
    order_id: Optional[str] = None
    hub_id: Optional[str] = None


@router.post("/copilot/chat")
def copilot_chat(request: CopilotRequest, db=Depends(get_db)):
    """Mock endpoint for the ops copilot chat panel."""
    # In a full build, this would hit the AgentRuntime with role="ops".
    # For now, return a simulated response.
    
    if "high" in request.message.lower() or "why" in request.message.lower():
        if request.order_id:
            score = ops_tools.explain_score(db, request.order_id)
            reply = score.get("summary", "Let me check that.")
        else:
            reply = "Please specify an order ID to check."
    elif "action" in request.message.lower() or "review" in request.message.lower():
        if request.order_id:
            ops_tools.propose_action(
                db, request.order_id, "hub_review", 
                "Ops requested manual review based on recent activity."
            )
            reply = f"I've proposed a Hub Review action for {request.order_id}. You can approve it in the Pending Actions panel."
        else:
            reply = "I need an order ID to propose an action."
    else:
        reply = "I'm your Ops Copilot. I can explain risk scores, fetch case bundles, or propose actions for you to approve."
        
    return {
        "reply": reply,
        "label": "SIMULATED"
    }
