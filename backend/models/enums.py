"""Order state enums and constants for the Valmo Mitra AI system."""

from enum import Enum


class OrderState(str, Enum):
    """Order state machine states — includes v1 + self-pickup states from §7.3A."""
    CONFIRMED = "CONFIRMED"
    MANIFESTED = "MANIFESTED"
    PICKED_UP_FROM_SELLER = "PICKED_UP_FROM_SELLER"
    IN_TRANSIT = "IN_TRANSIT"
    AT_DESTINATION_HUB = "AT_DESTINATION_HUB"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    SKIPPED_TODAY = "SKIPPED_TODAY"
    RESCHEDULED = "RESCHEDULED"
    FAILED_ATTEMPT = "FAILED_ATTEMPT"
    # Self-pickup states (§7.3A)
    SELF_PICKUP_PENDING = "SELF_PICKUP_PENDING"
    SELF_PICKUP_READY = "SELF_PICKUP_READY"
    PICKED_UP = "PICKED_UP"  # Customer picked up from center
    # Terminal
    RTO_INITIATED = "RTO_INITIATED"
    RETURNED = "RETURNED"


class VerificationLevel(str, Enum):
    """Identity verification levels (§4)."""
    UNKNOWN = "unknown"
    V0 = "v0"  # Phone matches order
    V1 = "v1"  # V0 + button confirmation
    V2 = "v2"  # V1 + payment verification


class ToolTier(str, Enum):
    """Tool authorization tiers (§5)."""
    A0_READ = "A0"
    A1_LOW_WRITE = "A1"
    A2_CONFIRMED_WRITE = "A2"
    A3_MONEY = "A3"
    A4_FORBIDDEN = "A4"


class UserRole(str, Enum):
    """Agent runtime roles."""
    CUSTOMER = "customer"
    RIDER = "rider"
    OPS = "ops"


class RiskTier(str, Enum):
    """Order risk tiers from the risk engine."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TicketCategory(str, Enum):
    """Complaint ticket categories (§7.4)."""
    NOT_RECEIVED = "not_received"
    LATE_DELIVERY = "late_delivery"
    DAMAGED_WRONG = "damaged_wrong"
    RIDER_BEHAVIOUR = "rider_behaviour"
    PAYMENT_CHARGE = "payment_charge"
    ADDRESS_ISSUE = "address_issue"
    PRODUCT_QUALITY = "product_quality"


class TicketSeverity(str, Enum):
    """Ticket severity levels."""
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class TicketStatus(str, Enum):
    """Ticket lifecycle status."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class AttemptOutcome(str, Enum):
    """Rider delivery attempt outcomes (§5.2)."""
    DELIVERED = "delivered"
    FAILED_NOT_AVAILABLE = "failed_not_available"
    FAILED_REFUSED = "failed_refused"
    FAILED_ADDRESS_ISSUE = "failed_address_issue"
    REVISIT_TODAY = "revisit_today"


class CenterType(str, Enum):
    """Valmo center types (§5A)."""
    LAST_MILE_DC = "last_mile_dc"
    SORT_CENTER = "sort_center"
    FM_HUB = "fm_hub"


class CenterStatus(str, Enum):
    """Center operational status."""
    ACTIVE = "active"
    PAUSED = "paused"


class LaneClass(str, Enum):
    """Shipping lane classification for ETA (§8)."""
    INTRA_REGION = "intra_region"
    INTER_REGION = "inter_region"
    REMOTE = "remote"


class PaymentMode(str, Enum):
    """Order payment mode."""
    COD = "cod"
    PREPAID = "prepaid"


class DistanceBand(str, Enum):
    """Distance from center for self-pickup (§7.3A)."""
    NEAR_2KM = "2km"
    MEDIUM_5KM = "5km"
    FAR_10KM = "10km+"


# === State Machine Transitions ===
VALID_TRANSITIONS = {
    OrderState.CONFIRMED: [OrderState.MANIFESTED, OrderState.SELF_PICKUP_PENDING],
    OrderState.MANIFESTED: [OrderState.PICKED_UP_FROM_SELLER, OrderState.SELF_PICKUP_PENDING],
    OrderState.PICKED_UP_FROM_SELLER: [OrderState.IN_TRANSIT, OrderState.SELF_PICKUP_PENDING],
    OrderState.IN_TRANSIT: [OrderState.AT_DESTINATION_HUB, OrderState.SELF_PICKUP_PENDING],
    OrderState.AT_DESTINATION_HUB: [OrderState.OUT_FOR_DELIVERY, OrderState.SELF_PICKUP_PENDING],
    OrderState.OUT_FOR_DELIVERY: [
        OrderState.DELIVERED,
        OrderState.FAILED_ATTEMPT,
        OrderState.SKIPPED_TODAY,
    ],
    OrderState.FAILED_ATTEMPT: [
        OrderState.RESCHEDULED,
        OrderState.OUT_FOR_DELIVERY,
        OrderState.SELF_PICKUP_PENDING,
        OrderState.RTO_INITIATED,
    ],
    OrderState.SKIPPED_TODAY: [
        OrderState.RESCHEDULED,
        OrderState.OUT_FOR_DELIVERY,
        OrderState.SELF_PICKUP_PENDING,
        OrderState.RTO_INITIATED,
    ],
    OrderState.RESCHEDULED: [
        OrderState.OUT_FOR_DELIVERY,
        OrderState.SELF_PICKUP_PENDING,
        OrderState.RTO_INITIATED,
    ],
    OrderState.SELF_PICKUP_PENDING: [
        OrderState.SELF_PICKUP_READY,
        OrderState.RESCHEDULED,  # Switch back to home delivery
        OrderState.RTO_INITIATED,
    ],
    OrderState.SELF_PICKUP_READY: [
        OrderState.PICKED_UP,
        OrderState.RTO_INITIATED,  # Hold expired
    ],
    OrderState.DELIVERED: [],
    OrderState.PICKED_UP: [],
    OrderState.RTO_INITIATED: [OrderState.RETURNED],
    OrderState.RETURNED: [],
}

# States where address edit is allowed (same-pincode updates allowed in all active delivery states)
ADDRESS_EDIT_ALLOWED_STATES = {
    OrderState.CONFIRMED,
    OrderState.MANIFESTED,
    OrderState.PICKED_UP_FROM_SELLER,
    OrderState.IN_TRANSIT,
    OrderState.AT_DESTINATION_HUB,
    OrderState.OUT_FOR_DELIVERY,
    OrderState.FAILED_ATTEMPT,
    OrderState.RESCHEDULED,
    OrderState.SKIPPED_TODAY,
}

# States where self-pickup switch is allowed (§7.3A)
SELF_PICKUP_ALLOWED_STATES = {
    OrderState.CONFIRMED,
    OrderState.MANIFESTED,
    OrderState.PICKED_UP_FROM_SELLER,
    OrderState.IN_TRANSIT,
    OrderState.AT_DESTINATION_HUB,
    OrderState.SKIPPED_TODAY,
    OrderState.RESCHEDULED,
    OrderState.FAILED_ATTEMPT,
}

# Human-readable state names (R-17: no jargon)
STATE_DISPLAY_NAMES = {
    OrderState.CONFIRMED: "Order confirm ho gaya hai",
    OrderState.MANIFESTED: "Order pack ho raha hai",
    OrderState.PICKED_UP_FROM_SELLER: "Seller se pick up ho gaya",
    OrderState.IN_TRANSIT: "Aapke shehar ki taraf aa raha hai",
    OrderState.AT_DESTINATION_HUB: "Aapke area ke center pe pahunch gaya",
    OrderState.OUT_FOR_DELIVERY: "Delivery ke liye nikal chuka hai",
    OrderState.DELIVERED: "Deliver ho gaya",
    OrderState.SKIPPED_TODAY: "Aaj delivery nahi ho paayi",
    OrderState.RESCHEDULED: "Nayi date pe schedule hai",
    OrderState.FAILED_ATTEMPT: "Delivery try ki, par ho nahi paayi",
    OrderState.SELF_PICKUP_PENDING: "Self pickup ke liye ready ho raha hai",
    OrderState.SELF_PICKUP_READY: "Center pe taiyaar hai, pickup karein",
    OrderState.PICKED_UP: "Aapne pickup kar liya",
    OrderState.RTO_INITIATED: "Wapas ja raha hai",
    OrderState.RETURNED: "Wapas ho gaya",
}
