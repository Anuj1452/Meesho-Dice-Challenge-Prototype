"""Deterministic ETA engine (§8).
All stage durations are SIMULATED and must be replaced with real Valmo lane data.
"""

from datetime import datetime, timezone, timedelta
from backend.models.enums import OrderState, LaneClass


# SIMULATED median stage durations in hours (§8)
# Replace with real Valmo lane data before quoting any accuracy.
STAGE_DURATIONS = {
    LaneClass.INTRA_REGION: {
        "pickup_to_sort": {"low": 4, "median": 8, "high": 14},
        "line_haul": {"low": 6, "median": 12, "high": 20},
        "destination_sort": {"low": 2, "median": 6, "high": 10},
        "hub_to_ofd": {"low": 2, "median": 6, "high": 12},
    },
    LaneClass.INTER_REGION: {
        "pickup_to_sort": {"low": 6, "median": 12, "high": 20},
        "line_haul": {"low": 18, "median": 36, "high": 60},
        "destination_sort": {"low": 4, "median": 8, "high": 16},
        "hub_to_ofd": {"low": 2, "median": 8, "high": 14},
    },
    LaneClass.REMOTE: {
        "pickup_to_sort": {"low": 8, "median": 16, "high": 28},
        "line_haul": {"low": 36, "median": 60, "high": 96},
        "destination_sort": {"low": 6, "median": 12, "high": 24},
        "hub_to_ofd": {"low": 4, "median": 10, "high": 18},
    },
}

# Map order states to remaining stages
STATE_REMAINING_STAGES = {
    OrderState.CONFIRMED: ["pickup_to_sort", "line_haul", "destination_sort", "hub_to_ofd"],
    OrderState.MANIFESTED: ["pickup_to_sort", "line_haul", "destination_sort", "hub_to_ofd"],
    OrderState.PICKED_UP_FROM_SELLER: ["line_haul", "destination_sort", "hub_to_ofd"],
    OrderState.IN_TRANSIT: ["destination_sort", "hub_to_ofd"],
    OrderState.AT_DESTINATION_HUB: ["hub_to_ofd"],
    OrderState.OUT_FOR_DELIVERY: [],
    OrderState.RESCHEDULED: ["hub_to_ofd"],
    OrderState.SKIPPED_TODAY: ["hub_to_ofd"],
    OrderState.FAILED_ATTEMPT: ["hub_to_ofd"],
}


def compute_eta(
    order_status: str,
    lane_class: str,
    deferral_count: int = 0,
    ordered_at: datetime | None = None,
) -> dict:
    """
    Compute delivery ETA range and confidence.

    Returns:
        {
            "eta_low": datetime,
            "eta_high": datetime,
            "eta_low_display": str,
            "eta_high_display": str,
            "confidence": "high" | "medium" | "low",
            "delayed": bool,
            "label": "SIMULATED"
        }
    """
    now = datetime.now(timezone.utc)
    status = OrderState(order_status) if isinstance(order_status, str) else order_status
    lane = LaneClass(lane_class) if isinstance(lane_class, str) else lane_class

    # OUT_FOR_DELIVERY = today
    if status == OrderState.OUT_FOR_DELIVERY:
        return {
            "eta_low": now,
            "eta_high": now + timedelta(hours=6),
            "eta_low_display": "Aaj",
            "eta_high_display": "Aaj shaam tak",
            "confidence": "high",
            "delayed": False,
            "label": "SIMULATED",
        }

    # Terminal states
    if status in (OrderState.DELIVERED, OrderState.PICKED_UP,
                  OrderState.RTO_INITIATED, OrderState.RETURNED):
        return {
            "eta_low": None,
            "eta_high": None,
            "eta_low_display": "N/A",
            "eta_high_display": "N/A",
            "confidence": "high",
            "delayed": False,
            "label": "SIMULATED",
        }

    # Self-pickup states
    if status in (OrderState.SELF_PICKUP_PENDING, OrderState.SELF_PICKUP_READY):
        return {
            "eta_low": now,
            "eta_high": now + timedelta(days=1),
            "eta_low_display": "Center pe ready hai" if status == OrderState.SELF_PICKUP_READY else "1-2 din",
            "eta_high_display": "Center pe pickup karein",
            "confidence": "medium" if status == OrderState.SELF_PICKUP_PENDING else "high",
            "delayed": False,
            "label": "SIMULATED",
        }

    # Compute remaining time
    remaining_stages = STATE_REMAINING_STAGES.get(status, ["hub_to_ofd"])
    durations = STAGE_DURATIONS.get(lane, STAGE_DURATIONS[LaneClass.INTER_REGION])

    total_low = sum(durations[stage]["low"] for stage in remaining_stages)
    total_median = sum(durations[stage]["median"] for stage in remaining_stages)
    total_high = sum(durations[stage]["high"] for stage in remaining_stages)

    # Adjust for deferrals: each deferral adds ~24 hours
    deferral_hours = deferral_count * 24
    total_low += deferral_hours
    total_high += deferral_hours

    eta_low = now + timedelta(hours=total_low)
    eta_high = now + timedelta(hours=total_high)

    # Determine confidence
    if status == OrderState.AT_DESTINATION_HUB:
        confidence = "medium"
    elif status in (OrderState.IN_TRANSIT, OrderState.PICKED_UP_FROM_SELLER):
        confidence = "low"
    else:
        confidence = "low"

    # Check if delayed (ordered > expected max)
    delayed = False
    if ordered_at:
        expected_max_hours = total_high + 24  # Buffer
        if (now - ordered_at).total_seconds() / 3600 > expected_max_hours:
            delayed = True

    # Format display
    def _format_date(dt: datetime) -> str:
        ist = dt + timedelta(hours=5, minutes=30)
        today = (now + timedelta(hours=5, minutes=30)).date()
        tomorrow = today + timedelta(days=1)

        if ist.date() == today:
            return "Aaj"
        elif ist.date() == tomorrow:
            return "Kal"
        else:
            return ist.strftime("%d %b")

    return {
        "eta_low": eta_low,
        "eta_high": eta_high,
        "eta_low_display": _format_date(eta_low),
        "eta_high_display": _format_date(eta_high),
        "confidence": confidence,
        "delayed": delayed,
        "label": "SIMULATED",
    }
