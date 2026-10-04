"""Pre-router: handles deterministic responses with zero LLM calls (§3, step 2).
This is the cost lever — every message handled here saves an LLM call.
"""

import re
import yaml
import os
from typing import Optional


def _load_config():
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "agent.yaml")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


CONFIG = _load_config()
PRE_ROUTER_CONFIG = CONFIG.get("pre_router", {})

STATUS_KEYWORDS = set(PRE_ROUTER_CONFIG.get("status_keywords", ["status", "kahan hai", "where", "track"]))
HELP_KEYWORDS = set(PRE_ROUTER_CONFIG.get("help_keywords", ["help", "madad"]))
STOP_KEYWORDS = set(PRE_ROUTER_CONFIG.get("stop_keywords", ["stop", "band karo"]))
THANKS_KEYWORDS = set(PRE_ROUTER_CONFIG.get("thanks_keywords", ["thanks", "thank you", "ok", "okay", "theek hai"]))
GREETING_KEYWORDS = set(PRE_ROUTER_CONFIG.get("greeting_keywords", ["hi", "hello", "namaste", "hey"]))


class PreRouterResult:
    """Result from the pre-router."""

    def __init__(
        self,
        handled: bool,
        response_text: str = "",
        buttons: list[dict] | None = None,
        action: str = "",
        tool_calls: list | None = None,
    ):
        self.handled = handled
        self.response_text = response_text
        self.buttons = buttons or []
        self.action = action
        self.tool_calls = tool_calls  # Tool calls to execute without LLM


def route(
    message_text: str,
    message_type: str = "text",
    button_payload: str = "",
    customer_name: str = "",
) -> PreRouterResult:
    """
    Deterministic pre-router. Returns handled=True if no LLM needed.

    Handles: button payloads, numbered replies, STOP, status/help keywords,
    thanks, emoji-only messages, greetings.
    """
    text = message_text.strip().lower()

    # === Button payloads (WhatsApp interactive reply buttons) ===
    if message_type == "button_reply" and button_payload:
        return _handle_button(button_payload, customer_name)

    # === Numbered replies ("1", "2", "3") ===
    if text in ("1", "2", "3"):
        return _handle_numbered_reply(text)

    # === STOP (R-29) ===
    for kw in STOP_KEYWORDS:
        if kw in text:
            return PreRouterResult(
                handled=True,
                response_text="Aapko aur messages nahi bhejenge. Agar aapko dobara help chahiye, toh kabhi bhi message karein. 🙏",
                action="stop",
            )

    # === Thanks / acknowledgments ===
    if text in THANKS_KEYWORDS or text in {"👍", "🙏", "👌", "ok", "ji", "accha", "thik hai", "sahi hai"}:
        return PreRouterResult(
            handled=True,
            response_text="🙏 Zaroorat ho toh kabhi bhi message karein!",
            action="thanks",
        )

    # === Emoji-only messages ===
    if _is_emoji_only(text):
        return PreRouterResult(
            handled=True,
            response_text="😊 Kuch aur help chahiye? Ye options dekhein:",
            buttons=[
                {"id": "btn_status", "title": "Order status"},
                {"id": "btn_help", "title": "Help chahiye"},
            ],
            action="emoji",
        )

    # === Greeting ===
    for kw in GREETING_KEYWORDS:
        if text == kw or text.startswith(kw + " ") or text.startswith(kw + ","):
            name_part = f" {customer_name}" if customer_name else ""
            return PreRouterResult(
                handled=True,
                response_text=f"Namaste{name_part}! 🙏 Main Valmo Mitra hoon, aapka delivery helper. Kaise madad kar sakta hoon?",
                buttons=[
                    {"id": "btn_status", "title": "Order status"},
                    {"id": "btn_help", "title": "Help chahiye"},
                    {"id": "btn_callback", "title": "Callback chahiye"},
                ],
                action="greeting",
            )

    # === Interactive Nudge & Missed Call Direct Actions ===
    if text in ("available today", "main available hoon", "aaj available hoon", "available hoon", "yes available", "aaj aao", "aaj aa jao", "aaj deliver karo"):
        return _handle_button("btn_available_today", customer_name)

    if text in ("not available today", "kal aaiye", "kal aao", "kal aana", "kal deliver karo", "aaj available nahi", "aaj available nahi hoon", "kal"):
        return _handle_button("btn_not_today", customer_name)

    if text in ("change address", "address change", "pincode address", "address badalna", "naya address"):
        return _handle_button("btn_change_address", customer_name)

    if any(k in text for k in (
        "call rider", "rider ko call", "rider number", "rider ka number",
        "call rider back", "rider call", "rider se baat", "talk to rider",
        "call the rider", "rider se baat karni", "rider se baat karo",
        "rider ko phone", "rider contact", "rider dial", "rider ko bolo"
    )):
        return _handle_button("btn_call_rider", customer_name)

    if text in ("padosi", "security", "security guard", "leave with neighbor", "guard ko de do", "padosi ko de do"):
        return _handle_button("btn_leave_neighbor", customer_name)

    # === Plain "status" keyword ===
    for kw in STATUS_KEYWORDS:
        if text == kw or (len(text) < 30 and kw in text):
            return PreRouterResult(
                handled=True,
                response_text="",  # Will trigger get_orders tool
                action="status_query",
                tool_calls=[{"name": "get_orders", "args": {}}],
            )

    # === Plain "help" ===
    for kw in HELP_KEYWORDS:
        if text == kw:
            return PreRouterResult(
                handled=True,
                response_text="Main in cheezon mein madad kar sakta hoon:",
                buttons=[
                    {"id": "btn_status", "title": "Order status"},
                    {"id": "btn_address", "title": "Address badalna hai"},
                    {"id": "btn_callback", "title": "Callback chahiye"},
                ],
                action="help",
            )

    # === Not handled — pass to LLM ===
    return PreRouterResult(handled=False)


def _handle_button(payload: str, customer_name: str = "") -> PreRouterResult:
    """Handle interactive button replies."""
    handlers = {
        "btn_status": PreRouterResult(
            handled=True, response_text="", action="status_query",
            tool_calls=[{"name": "get_orders", "args": {}}],
        ),
        "btn_help": PreRouterResult(
            handled=True,
            response_text="Main in cheezon mein help kar sakta hoon:",
            buttons=[
                {"id": "btn_status", "title": "Order status"},
                {"id": "btn_address", "title": "Address badalna"},
                {"id": "btn_callback", "title": "Callback chahiye"},
            ],
            action="help",
        ),
        "btn_available": PreRouterResult(
            handled=True, response_text="Bahut badiya! 👍 Rider aaj aapke address par deliver karega. Kripya COD amount / OTP ready rakhein.",
            buttons=[{"id": "btn_call_rider", "title": "📞 Call Rider"}],
            action="set_available",
            tool_calls=[{"name": "set_availability", "args": {"slot": "Available Today"}}],
        ),
        "btn_available_today": PreRouterResult(
            handled=True,
            response_text="Bahut badiya! 👍 Rider aaj aapke address par aayega. Kripya phone active rakhein aur COD amount / OTP ready rakhein.",
            buttons=[{"id": "btn_call_rider", "title": "📞 Call Rider"}],
            action="set_available_today",
            tool_calls=[{"name": "set_availability", "args": {"slot": "Available Today"}}],
        ),
        "btn_not_today": PreRouterResult(
            handled=True,
            response_text="Theek hai! 🗓️ Aapka order kal ke liye schedule kar diya gaya hai. Rider aaj nahi aayega aur kal attempt karega.",
            buttons=[{"id": "btn_status", "title": "Order status"}],
            action="defer_delivery",
            tool_calls=[{"name": "set_availability", "args": {"slot": "Tomorrow"}}],
        ),
        "btn_tomorrow": PreRouterResult(
            handled=True,
            response_text="Aapka order kal ke liye schedule kar diya gaya hai. 🗓️",
            action="set_tomorrow",
            tool_calls=[{"name": "set_availability", "args": {"slot": "Tomorrow"}}],
        ),
        "btn_change_address": PreRouterResult(
            handled=True,
            response_text="Apna naya delivery address batayein (same pincode mein hona chahiye). Jaise hi aap address likhenge, hum use update kar denge 📍",
            action="address_prompt",
        ),
        "btn_call_rider": PreRouterResult(
            handled=True,
            response_text="Rider Amit ka masked number: +91 98765 00000 📞\nAap neeche button par tap karke phone dialer se seedhe call kar sakte hain:",
            buttons=[{"id": "btn_dial_rider", "title": "📞 Open Dialer (+91 98765 00000)"}],
            action="call_rider",
        ),
        "btn_leave_neighbor": PreRouterResult(
            handled=True,
            response_text="Noted! 🏠 Rider ko note bhej diya gaya hai: 'Padosi / Security Guard ko de dein'.",
            action="leave_neighbor",
            tool_calls=[{"name": "add_delivery_note", "args": {"note": "Padosi / Security Guard ko de dein"}}],
        ),
        "btn_alt_number": PreRouterResult(
            handled=True,
            response_text="Kripya alternate contact person ka naam aur mobile number yahan type karein:",
            action="alt_number_prompt",
        ),
        "btn_location": PreRouterResult(
            handled=True,
            response_text="Please apna location pin share karein 📍",
            action="request_location",
        ),
        "btn_confirm_yes": PreRouterResult(
            handled=True, response_text="Aapka request confirm ho gaya hai! Shukriya. 🙏", action="confirmed_yes",
        ),
        "btn_confirm_no": PreRouterResult(
            handled=True, response_text="Kya badalna hai? Bataiyein:",
            buttons=[
                {"id": "btn_address", "title": "Address"},
                {"id": "btn_time", "title": "Delivery time"},
                {"id": "btn_callback", "title": "Callback chahiye"},
            ],
            action="confirmed_no",
        ),
        "btn_callback": PreRouterResult(
            handled=True, response_text="Callback schedule kar diya gaya hai. Hamari team aapko jald hi call karegi. 📞", action="schedule_callback",
            tool_calls=[{"name": "schedule_callback", "args": {"reason": "Customer requested callback"}}],
        ),
        "btn_address": PreRouterResult(
            handled=True,
            response_text="Apna naya address batayein (same pincode mein):",
            action="address_prompt",
        ),
        "btn_time": PreRouterResult(
            handled=True,
            response_text="Kab delivery chahiye?",
            buttons=[
                {"id": "btn_available_today", "title": "Aaj"},
                {"id": "btn_not_today", "title": "Kal"},
            ],
            action="time_prompt",
        ),
        "btn_pay_online": PreRouterResult(
            handled=True, response_text="", action="payment_link",
            tool_calls=[{"name": "create_payment_link", "args": {}}],
        ),
        "btn_self_pickup": PreRouterResult(
            handled=True, response_text="", action="self_pickup",
            tool_calls=[{"name": "get_pickup_options", "args": {}}],
        ),
    }

    result = handlers.get(payload)
    if result:
        return result

    # Check button text matching
    payload_lower = payload.lower()
    for key, handler in handlers.items():
        if key.lower() == payload_lower:
            return handler
        if key.replace("btn_", "").replace("_", " ") in payload_lower:
            return handler

    # Unknown button — pass to LLM
    return PreRouterResult(handled=False)



def _handle_numbered_reply(number: str) -> PreRouterResult:
    """Handle numbered shortcut replies."""
    mapping = {
        "1": PreRouterResult(
            handled=True, response_text="", action="status_query",
            tool_calls=[{"name": "get_orders", "args": {}}],
        ),
        "2": PreRouterResult(
            handled=True,
            response_text="Kaise madad chahiye?",
            buttons=[
                {"id": "btn_address", "title": "Address badalna"},
                {"id": "btn_time", "title": "Delivery time"},
                {"id": "btn_callback", "title": "Callback"},
            ],
            action="help",
        ),
        "3": PreRouterResult(
            handled=True, response_text="", action="schedule_callback",
            tool_calls=[{"name": "schedule_callback", "args": {"reason": "Customer pressed 3"}}],
        ),
    }
    return mapping.get(number, PreRouterResult(handled=False))


def _is_emoji_only(text: str) -> bool:
    """Check if text contains only emoji."""
    import re
    emoji_pattern = re.compile(
        "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U0001F900-\U0001F9FF"
        "\U0001FA00-\U0001FA6F\U00002600-\U000026FF\U0000FE00-\U0000FE0F"
        "\U0000200D\U00002764\U0000FEFF]+",
        re.UNICODE,
    )
    cleaned = emoji_pattern.sub("", text).strip()
    return len(text) > 0 and len(cleaned) == 0
