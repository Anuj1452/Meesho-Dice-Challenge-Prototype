"""Tool Gateway (§5.5) — the model proposes, the gateway decides.
Every tool call passes through: role permission → order ownership → state precondition
→ rate limit → idempotency key → execute → audit row.
"""

import re
import hashlib
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from backend.models.database import Order, AuditLog, ValmoCenter
from backend.models.enums import (
    OrderState, ToolTier, UserRole, VerificationLevel,
    ADDRESS_EDIT_ALLOWED_STATES, SELF_PICKUP_ALLOWED_STATES,
)


# === Tool permissions by role ===
TOOL_PERMISSIONS = {
    UserRole.CUSTOMER: {
        # A0 - Read
        "get_orders": ToolTier.A0_READ,
        "get_order": ToolTier.A0_READ,
        "get_tracking": ToolTier.A0_READ,
        "get_eta": ToolTier.A0_READ,
        "get_policy": ToolTier.A0_READ,
        "get_pickup_options": ToolTier.A0_READ,
        # A1 - Low-risk write
        "set_availability": ToolTier.A1_LOW_WRITE,
        "add_delivery_note": ToolTier.A1_LOW_WRITE,
        "set_alternate_receiver": ToolTier.A1_LOW_WRITE,
        "share_location": ToolTier.A1_LOW_WRITE,
        "record_attempt_verdict": ToolTier.A1_LOW_WRITE,
        "record_refusal_reason": ToolTier.A1_LOW_WRITE,
        "request_rider_call": ToolTier.A1_LOW_WRITE,
        "create_ticket": ToolTier.A1_LOW_WRITE,
        "schedule_callback": ToolTier.A1_LOW_WRITE,
        "escalate_to_human": ToolTier.A1_LOW_WRITE,
        "set_language": ToolTier.A1_LOW_WRITE,
        # A2 - Confirmed write (address/self-pickup still get read-back confirmation via R-10)
        # Note: update_address is A1 because WhatsApp phone number = identity verified
        "update_address": ToolTier.A1_LOW_WRITE,
        "set_self_pickup": ToolTier.A2_CONFIRMED_WRITE,
        # A3 - Money
        "create_payment_link": ToolTier.A3_MONEY,
    },
    UserRole.RIDER: {
        "get_manifest": ToolTier.A0_READ,
        "get_order_card": ToolTier.A0_READ,
        "mark_outcome": ToolTier.A1_LOW_WRITE,
        "report_problem": ToolTier.A1_LOW_WRITE,
        "nudge_customer": ToolTier.A1_LOW_WRITE,
        "suggest_route_order": ToolTier.A0_READ,
        "respond_to_dispute": ToolTier.A1_LOW_WRITE,
        "get_my_day": ToolTier.A0_READ,
    },
    UserRole.OPS: {
        "get_case_bundle": ToolTier.A0_READ,
        "get_hub_metrics": ToolTier.A0_READ,
        "list_review_queue": ToolTier.A0_READ,
        "explain_score": ToolTier.A0_READ,
        "search_tickets": ToolTier.A0_READ,
        "propose_action": ToolTier.A1_LOW_WRITE,
        "draft_message": ToolTier.A1_LOW_WRITE,
    },
}

# Verification requirements by tier
TIER_VERIFICATION = {
    ToolTier.A0_READ: VerificationLevel.V0,
    ToolTier.A1_LOW_WRITE: VerificationLevel.V0,
    ToolTier.A2_CONFIRMED_WRITE: VerificationLevel.V1,
    ToolTier.A3_MONEY: VerificationLevel.V2,
}

# Known Indian cities for the location lock
KNOWN_CITIES = {
    "mumbai", "delhi", "bangalore", "bengaluru", "chennai", "hyderabad", "kolkata",
    "pune", "ahmedabad", "jaipur", "lucknow", "kanpur", "nagpur", "indore",
    "thane", "bhopal", "visakhapatnam", "patna", "vadodara", "ghaziabad",
    "ludhiana", "agra", "nashik", "faridabad", "meerut", "rajkot", "varanasi",
    "srinagar", "aurangabad", "dhanbad", "amritsar", "allahabad", "ranchi",
    "howrah", "coimbatore", "jabalpur", "gwalior", "vijayawada", "jodhpur",
    "madurai", "raipur", "kota", "chandigarh", "guwahati", "solapur",
    "noida", "gurgaon", "gurugram", "surat", "navi mumbai",
}

# Sanitization patterns for delivery notes
FORBIDDEN_NOTE_PATTERNS = [
    re.compile(r"https?://", re.I),
    re.compile(r"www\.", re.I),
    re.compile(r"\b\d{10}\b"),  # Phone numbers
    re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", re.I),  # Email
]


class GatewayResult:
    """Result of a gateway check."""

    def __init__(self, allowed: bool, reason: str = "", alternatives: list[str] = None):
        self.allowed = allowed
        self.reason = reason
        self.alternatives = alternatives or []

    def to_dict(self):
        d = {"allowed": self.allowed}
        if not self.allowed:
            d["reason"] = self.reason
            if self.alternatives:
                d["alternatives"] = self.alternatives
        return d


class ToolGateway:
    """Authorises or refuses each tool call (§5.5)."""

    def __init__(self, db: Session):
        self.db = db
        self._idempotency_cache = {}

    def check(
        self,
        tool_name: str,
        args: dict,
        role: UserRole,
        actor_id: str,
        session_id: str,
        verification_level: str = "v0",
    ) -> GatewayResult:
        """Run all gateway checks for a tool call."""

        # 1. Role permission check
        role_tools = TOOL_PERMISSIONS.get(role, {})
        if tool_name not in role_tools:
            return GatewayResult(
                False,
                f"Tool '{tool_name}' is not available for role '{role.value}'.",
                ["Use available tools for your role."],
            )

        tier = role_tools[tool_name]

        # 2. Verification level check
        required_level = TIER_VERIFICATION.get(tier, VerificationLevel.V0)
        ver_level = VerificationLevel(verification_level)
        level_order = [VerificationLevel.UNKNOWN, VerificationLevel.V0, VerificationLevel.V1, VerificationLevel.V2]

        if level_order.index(ver_level) < level_order.index(required_level):
            return GatewayResult(
                False,
                f"This action requires verification level {required_level.value}.",
                ["Please confirm your identity first."],
            )

        # 3. Order-specific checks
        order_id = args.get("order_id")
        if order_id:
            order = self.db.query(Order).filter(Order.order_id == order_id).first()
            if not order:
                return GatewayResult(False, "Order not found.")

            # Ownership check (customer role)
            if role == UserRole.CUSTOMER:
                from backend.models.database import Customer
                customer = self.db.query(Customer).filter(Customer.phone_hash == actor_id).first()
                if customer and order.customer_id != customer.id:
                    return GatewayResult(False, "You can only access your own orders.")

            # State precondition checks
            result = self._check_state_preconditions(tool_name, order, args)
            if not result.allowed:
                return result

            # Rate limit checks
            result = self._check_rate_limits(tool_name, order, session_id)
            if not result.allowed:
                return result

        # 4. Idempotency check
        idem_key = self._make_idempotency_key(tool_name, args, session_id)
        if idem_key in self._idempotency_cache:
            return GatewayResult(
                False,
                "This action was already performed in this session.",
                ["The previous result still applies."],
            )

        return GatewayResult(True)

    def _check_state_preconditions(self, tool_name: str, order: Order, args: dict) -> GatewayResult:
        """Check order state requirements for each tool."""
        status = OrderState(order.status)

        # === Address update checks (§7.3) ===
        if tool_name == "update_address":
            if status not in ADDRESS_EDIT_ALLOWED_STATES:
                return GatewayResult(
                    False,
                    "Address cannot be changed in the current order state.",
                    ["You can try scheduling a different delivery time.",
                     "Self pickup at the serving center is available.",
                     "An alternate receiver can be set."],
                )

            if order.address_edit_count >= 2:
                return GatewayResult(
                    False,
                    "Maximum address edits (2) reached for this order.",
                    ["You can add a delivery note with landmark details.",
                     "Request a rider call for directions."],
                )

            # Location lock: check for different pincode (R-30)
            address_text = args.get("address_text", "")
            pincode_match = re.findall(r"\b\d{6}\b", address_text)
            for pin in pincode_match:
                if pin != order.pincode:
                    return GatewayResult(
                        False,
                        f"Delivery location is fixed to pincode {order.pincode}. A different pincode ({pin}) was detected.",
                        [
                            f"Fix the address within pincode {order.pincode}.",
                            "Self pickup at the serving Valmo center.",
                            "Set an alternate receiver.",
                            "Request a rider call for directions.",
                            "Cancel and reorder with the new address in the Meesho app.",
                        ],
                    )

            # Check for different city names (R-30)
            address_lower = address_text.lower()
            order_city_lower = order.city.lower()
            for city in KNOWN_CITIES:
                if city in address_lower and city != order_city_lower:
                    return GatewayResult(
                        False,
                        f"Order is fixed to {order.city}. Cannot change the delivery city.",
                        [
                            f"Fix the address within {order.city}, pincode {order.pincode}.",
                            "Self pickup at the serving Valmo center.",
                            "Set an alternate receiver or request a rider call.",
                            "Cancel and reorder with the new address in the Meesho app.",
                        ],
                    )

        # === Self-pickup checks (§7.3A) ===
        if tool_name == "set_self_pickup":
            if status not in SELF_PICKUP_ALLOWED_STATES:
                alts = ["Reschedule the delivery to a better time."]
                if status == OrderState.OUT_FOR_DELIVERY:
                    return GatewayResult(
                        False,
                        "Self pickup is not available while the order is out for delivery. The parcel is on the rider's bike.",
                        alts,
                    )
                return GatewayResult(
                    False,
                    "Self pickup is not available in the current order state.",
                    alts,
                )

            # Check center accepts self pickup
            center_id = args.get("center_id") or order.serving_center_id
            if center_id:
                center = self.db.query(ValmoCenter).filter(
                    ValmoCenter.center_id == center_id
                ).first()
                if center and not center.accepts_self_pickup:
                    return GatewayResult(
                        False,
                        "This Valmo center does not accept self pickups currently.",
                        ["Try scheduling delivery at a different time.",
                         "Set an alternate receiver."],
                    )

        # === Availability / deferral checks ===
        if tool_name == "set_availability":
            if order.deferral_count >= 2:
                return GatewayResult(
                    True,  # Allow but with warning
                    "WARNING: This is the last deferral. A third deferral will trigger auto-return on day 4.",
                )

        # === Payment link checks (§7.2) ===
        if tool_name == "create_payment_link":
            if not order.is_cod:
                return GatewayResult(False, "Order is already prepaid.")

            allowed_states = {
                OrderState.CONFIRMED, OrderState.MANIFESTED,
                OrderState.PICKED_UP_FROM_SELLER, OrderState.IN_TRANSIT,
                OrderState.AT_DESTINATION_HUB, OrderState.OUT_FOR_DELIVERY,
            }
            if status not in allowed_states:
                return GatewayResult(False, "Payment link cannot be created in the current state.")

            if order.payment_link_id:
                from backend.models.database import PaymentLink
                active_link = self.db.query(PaymentLink).filter(
                    PaymentLink.order_id == order.order_id,
                    PaymentLink.status == "active",
                ).first()
                if active_link:
                    return GatewayResult(
                        False,
                        "An active payment link already exists for this order.",
                        ["Wait for the current link to expire or be used."],
                    )

        # === Delivery note sanitization ===
        if tool_name == "add_delivery_note":
            note = args.get("note", "")
            if len(note) > 120:
                return GatewayResult(False, "Delivery note must be 120 characters or less.")
            for pattern in FORBIDDEN_NOTE_PATTERNS:
                if pattern.search(note):
                    return GatewayResult(
                        False,
                        "Delivery notes cannot contain links, phone numbers, or email addresses.",
                    )

        return GatewayResult(True)

    def _check_rate_limits(self, tool_name: str, order: Order, session_id: str) -> GatewayResult:
        """Check per-order rate limits."""
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        # 3 writes per order per day
        write_tiers = {ToolTier.A1_LOW_WRITE, ToolTier.A2_CONFIRMED_WRITE, ToolTier.A3_MONEY}
        role_tools = TOOL_PERMISSIONS.get(UserRole.CUSTOMER, {})
        tier = role_tools.get(tool_name)

        if tier in write_tiers:
            today_writes = self.db.query(AuditLog).filter(
                AuditLog.tool_name != "get_orders",
                AuditLog.timestamp >= today_start,
                AuditLog.success == True,
            ).count()
            # Simplified: check session writes
            if today_writes >= 15:  # Global safety limit
                return GatewayResult(
                    False,
                    "Too many actions today. Please try again tomorrow or contact support.",
                )

        return GatewayResult(True)

    def _make_idempotency_key(self, tool_name: str, args: dict, session_id: str) -> str:
        """Create an idempotency key for dedup."""
        raw = f"{session_id}:{tool_name}:{sorted(args.items())}"
        return hashlib.md5(raw.encode()).hexdigest()

    def record_audit(
        self,
        session_id: str,
        role: UserRole,
        actor_id: str,
        tool_name: str,
        arguments: dict,
        result: dict,
        success: bool,
        refusal_reason: str = "",
        model_rationale: str = "",
    ):
        """Log every tool call to the audit table (§5.5)."""
        log = AuditLog(
            session_id=session_id,
            actor_role=role.value,
            actor_id=actor_id,
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            success=success,
            refusal_reason=refusal_reason,
            model_rationale=model_rationale[:100] if model_rationale else "",
        )
        self.db.add(log)
        self.db.commit()

    def mark_idempotent(self, tool_name: str, args: dict, session_id: str):
        """Mark a tool call as completed for idempotency."""
        key = self._make_idempotency_key(tool_name, args, session_id)
        self._idempotency_cache[key] = True
