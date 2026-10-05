"""LLM client abstraction layer (§3A).
Only this file may import a provider SDK.
Includes smart fallback when OpenAI API limits/errors occur.
"""

import os
import re
import json
import asyncio
from dataclasses import dataclass, field
from typing import Optional
from abc import ABC, abstractmethod
from dotenv import load_dotenv
from backend.gateway.tool_gateway import KNOWN_CITIES
load_dotenv()


@dataclass
class ToolCall:
    name: str
    args: dict
    id: str = ""


@dataclass
class LLMResult:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict = field(default_factory=lambda: {"in": 0, "cached_in": 0, "out": 0})


class SmartFallbackEngine:
    """Smart conversational NLU engine for when OpenAI API is rate-limited (429) or offline."""

    @staticmethod
    def process(messages: list[dict], tools: list[dict] | None = None) -> LLMResult:
        # Check if there are tool results in messages
        tool_results = [m for m in messages if m.get("role") == "tool"]
        if tool_results:
            last_tool_res = tool_results[-1]
            try:
                res_data = json.loads(last_tool_res.get("content", "{}"))
            except Exception:
                res_data = {}

            # Handle tool errors
            if "error" in res_data:
                err_msg = res_data["error"]
                return LLMResult(text=f"{err_msg} ⚠️")

            # 1. set_availability response
            if "slot" in res_data or "scheduled_for" in res_data:
                slot_val = str(res_data.get("slot", "")).lower()
                scheduled_for = res_data.get("scheduled_for", "kal")
                if "today" in slot_val or "aaj" in slot_val:
                    return LLMResult(
                        text="Bahut badiya! 👍 Rider aaj aapke address par deliver karega. Kripya phone active rakhein aur COD amount / OTP ready rakhein."
                    )
                else:
                    return LLMResult(
                        text=f"Theek hai! 📅 Aapka order {scheduled_for} ke liye schedule kar diya gaya hai. Rider aaj nahi aayega aur kal attempt karega."
                    )

            # 2. update_address response
            if "new_address" in res_data or (res_data.get("success") and "order_id" in res_data and "landmark" in res_data):
                new_addr = res_data.get("new_address", "")
                addr_line = f"\nNaya Address: {new_addr}" if new_addr else ""
                landmark = res_data.get("landmark", "")
                landmark_line = f"\nLandmark: {landmark} (pehle wala hi rakha gaya hai)" if landmark else ""
                return LLMResult(
                    text=f"Aapka delivery address successfully update kar diya gaya hai! 📍{addr_line}{landmark_line}\nRider ab is naye address par delivery karega."
                )

            # 3. set_alternate_receiver response
            if "alternate_receiver" in res_data or "receiver_name" in res_data:
                name = res_data.get("alternate_receiver") or res_data.get("receiver_name") or "padosi"
                return LLMResult(
                    text=f"Theek hai! Humne note kar liya hai ki parcel {name} ko deliver kiya ja sakta hai. 🏠"
                )

            # 4. add_delivery_note response
            if "note" in res_data:
                return LLMResult(
                    text=f"Rider ke liye delivery instructions update kar di gayi hain: {res_data.get('note')} 📝"
                )

            # 5. schedule_callback response
            if "ticket_id" in res_data or "callback" in str(last_tool_res):
                return LLMResult(
                    text="Callback schedule kar diya gaya hai. Hamari team aapko jald hi call karegi. 📞"
                )

            # 6. get_orders / get_tracking response
            if "open_orders" in res_data:
                orders = res_data.get("open_orders", [])
                if orders:
                    o = orders[0]
                    return LLMResult(
                        text=f"Aapka order #{o.get('order_id')} ({o.get('product')}) out for delivery hai. Amount: {o.get('amount')} ({o.get('payment')}). 🚚"
                    )

            return LLMResult(
                text="Aapki request successfully update ho gayi hai! 🙏"
            )

        # Get latest user message
        user_texts = [m["content"] for m in messages if m.get("role") == "user" and not m["content"].startswith("[SYSTEM")]
        latest_text = user_texts[-1] if user_texts else ""
        lower = latest_text.lower().strip()

        # Interpret compact contact details through the pending conversation
        # state, instead of accidentally treating the phone number as a note.
        if SmartFallbackEngine._expects_alternate_receiver(messages):
            person = SmartFallbackEngine._extract_person_contact(latest_text)
            if person["name"] and person["phone"]:
                args = {"name": person["name"], "contact_phone": person["phone"]}
                pending_order_id = SmartFallbackEngine._order_context_value(messages, "ORDER_ID")
                if pending_order_id:
                    args["order_id"] = pending_order_id
                return LLMResult(text="", tool_calls=[ToolCall(name="set_alternate_receiver", args=args, id="call_alt_contact")])
            missing = "naam" if not person["name"] else "10-digit mobile number"
            return LLMResult(text=f"Alternate receiver ka {missing} bhi bhej dijiye, phir main rider ke liye record kar dunga.")

        # Resolve a relative landmark from the authoritative order snapshot,
        # rather than treating the customer's wording as a new landmark. This
        # covers equivalent Hinglish/English phrasing without binding the flow
        # to one literal sentence.
        saved_landmark = SmartFallbackEngine._order_context_value(messages, "Landmark")
        previous_address = SmartFallbackEngine._latest_complete_address(user_texts[:-1])
        if saved_landmark and previous_address and SmartFallbackEngine._is_relative_landmark_reference(lower):
            args = {"address_text": previous_address, "landmark": saved_landmark}
            order_id_from_context = SmartFallbackEngine._order_context_value(messages, "ORDER_ID")
            if order_id_from_context:
                args["order_id"] = order_id_from_context
            return LLMResult(text="", tool_calls=[ToolCall(name="update_address", args=args, id="call_addr_landmark")])

        # Extract order_id if present in system context or messages
        order_id = None
        for m in messages:
            found = re.search(r"ORD-[\w-]+", str(m.get("content", "")))
            if found:
                order_id = found.group(0)
                break

        # Check if user message is just an address change INTENT or QUESTION (not providing the address yet)
        address_intent_patterns = [
            "mujhe address change", "address change krna", "address change karna",
            "address badalna", "address kaise change", "address kese change",
            "change address", "change my address", "address update karna",
            "address update krna", "naya address dalna", "address badal do",
            "pata change", "pata badalna", "location change", "kese change kra",
            "kaise change kare", "address kaise badle", "address kese badle"
        ]
        is_addr_intent = any(p in lower for p in address_intent_patterns)

        # Check if user message contains an actual concrete address
        has_address_indicators = any(w in lower for w in ["flat", "house", "h.no", "h no", "h-no", "plot", "gali", "pocket", "sector", "block", "floor", "residency", "apartment", "colony", "nagar", "road", "marg", "near", "opposite", "behind", "opp."])
        has_pincode = bool(re.search(r"\b\d{6}\b", lower))

        location_conflict = SmartFallbackEngine._address_location_conflict(messages, latest_text)
        if location_conflict and (has_address_indicators or has_pincode):
            city = location_conflict["city"]
            pincode = location_conflict["pincode"]
            return LLMResult(
                text=(f"Delivery address {city} aur pincode {pincode} ke andar hi update ho sakta hai. "
                      f"Kripya {city}, {pincode} mein apna Flat/House No., street aur nearest landmark ke saath sahi address bhej dijiye 📍")
            )

        # Do not turn a landmark such as "near temple" into an address update.
        address_words = re.findall(r"\w+", lower)
        has_house_identifier = bool(re.search(r"\b(?:flat|house|h\.?(?:\s*no)?|plot|building|block|floor|door)\s*[-#:]?\s*\d", lower))
        has_street_detail = any(w in lower for w in ["gali", "street", "road", "sector", "colony", "nagar", "marg", "residency", "apartment", "pocket"])

        # If it's an intent question or simple request, ask them for the address
        if is_addr_intent or (("address" in lower or "pata" in lower) and not has_address_indicators and not has_pincode):
            return LLMResult(
                text="Apna naya delivery address batayein (same pincode mein hona chahiye jaise Flat/House No., Gali/Road, Landmark). Jaise hi aap address likhenge, hum use update kar denge 📍"
            )

        if (has_address_indicators or has_pincode) and (len(address_words) < 4 or not has_house_identifier or not has_street_detail):
            return LLMResult(text="Kripya house/flat number aur street details bhi batayein taaki rider ko parcel deliver karne mein pareshani na ho 📍")

        # Collect a complete address first, then ask for a landmark. This lets
        # the next turn resolve references such as an unchanged prior landmark
        # against the stored order context before any write takes place.
        if has_address_indicators or has_pincode:
            addr = re.sub(r"^(mera|meri|naya)?\s*address\s*(change|update)?\s*(karna hai|kardo|hai)?\s*[:,-]?\s*", "", latest_text, flags=re.IGNORECASE).strip()
            if not addr:
                addr = latest_text
            return LLMResult(text="Naya address noted hai. Landmark bhi batayein; agar purana landmark hi rakhna hai, bas usi baat ko bata dijiye.")

        # 1. Rescheduling / Availability
        if any(w in lower for w in ["kal", "tomorrow", "parso", "dopahar", "shaam", "baad me", "reschedule", "nahi"]):
            slot = "Tomorrow"
            if "parso" in lower or "day after" in lower:
                slot = "Day After Tomorrow"
            elif "shaam" in lower or "evening" in lower:
                slot = "Tomorrow Evening"
            elif "dopahar" in lower or "afternoon" in lower or "2 baje" in lower:
                slot = "Tomorrow Afternoon"
            args = {"slot": slot}
            if order_id:
                args["order_id"] = order_id
            return LLMResult(
                text="",
                tool_calls=[ToolCall(name="set_availability", args=args, id="call_avail_1")]
            )

        if re.search(r"\b(?:[1-9]|1[0-2])\s*baje\b", lower):
            args = {"slot": "Today after " + re.search(r"\b((?:[1-9]|1[0-2])\s*baje)\b", lower).group(1)}
            if order_id:
                args["order_id"] = order_id
            return LLMResult(text="", tool_calls=[ToolCall(name="set_availability", args=args, id="call_avail_time")])

        if any(w in lower for w in ["aaj", "today", "aaj hi", "available hoon", "ghar par hoon", "deliver today"]):
            args = {"slot": "Available Today"}
            if order_id:
                args["order_id"] = order_id
            return LLMResult(
                text="",
                tool_calls=[ToolCall(name="set_availability", args=args, id="call_avail_2")]
            )

        # 3. Neighbor / Guard
        if any(w in lower for w in ["padosi", "neighbor", "guard", "security", "uncle", "aunty", "flatmate"]):
            has_receiver_location = bool(re.search(r"\b(?:flat|house|door)\s*\d+\b|\b\d{10}\b", lower))
            if not has_receiver_location:
                return LLMResult(text="Parcel padosi ko dene ke liye unka full name aur flat/door number ya contact number bhi batayein.")
            return LLMResult(text="Unka naam aur 10-digit mobile number bhej dijiye. Main use alternate receiver ke secure record mein save kar dunga.")

        # 4. Alternate Phone / Note
        phone_match = re.search(r"\b\d{10}\b", lower)
        if phone_match or any(w in lower for w in ["number", "alternate", "call on"]):
            args = {"note": latest_text[:100]}
            if order_id:
                args["order_id"] = order_id
            return LLMResult(
                text="",
                tool_calls=[ToolCall(name="add_delivery_note", args=args, id="call_note_1")]
            )

        # 5. Call Rider
        if any(w in lower for w in ["call rider", "rider call", "rider se baat", "rider number", "rider ka number", "phone dialer"]):
            return LLMResult(
                text="Rider Amit ka masked number: +91 98765 00000 📞\nAap neeche button par tap karke phone dialer se seedhe call kar sakte hain:"
            )

        # 6. Status / Where
        if any(w in lower for w in ["status", "kahan", "where", "track", "kab aayega", "kab aayegi"]):
            return LLMResult(
                text="",
                tool_calls=[ToolCall(name="get_orders", args={}, id="call_ord_1")]
            )

        # 7. Callback
        if any(w in lower for w in ["callback", "call back", "agent", "executive", "baat karni hai"]):
            args = {"reason": "Customer request"}
            if order_id:
                args["order_id"] = order_id
            return LLMResult(
                text="",
                tool_calls=[ToolCall(name="schedule_callback", args=args, id="call_cb_1")]
            )

        # Default fallback response
        return LLMResult(
            text="Namaste! Main aapki delivery mein madad ke liye yahan hoon. Aap delivery time reschedule kar sakte hain, address update kar sakte hain ya status check kar sakte hain. 😊"
        )

    @staticmethod
    def _order_context_value(messages: list[dict], field: str) -> str:
        """Read a field only from the runtime's structured order context."""
        for message in messages:
            if message.get("role") != "system":
                continue
            match = re.search(rf"{re.escape(field)}:\s*([^|\n]+)", message.get("content", ""), re.I)
            if match:
                return match.group(1).strip()
            if field == "ORDER_ID":
                match = re.search(r"\b(?:ORD-[\w-]+|MS\d+)\b", message.get("content", ""))
                if match:
                    return match.group(0)
        return ""

    @staticmethod
    def _latest_complete_address(messages: list[str]) -> str:
        """Find the customer's latest address-shaped utterance, not a prompt."""
        for text in reversed(messages):
            lower = text.lower()
            has_house = bool(re.search(r"\b(?:flat|house|h\.?(?:\s*no)?|plot|building|block|floor|door)\s*[-#:]?\s*\d", lower))
            has_street = any(word in lower for word in ("gali", "street", "road", "sector", "colony", "nagar", "marg", "residency", "apartment", "pocket"))
            if has_house and has_street:
                return text.strip()
        return ""

    @staticmethod
    def _is_relative_landmark_reference(text: str) -> bool:
        """Classify meaning (keep prior landmark), not an exact canned phrase."""
        landmark_terms = ("landmark", "location", "nishani", "pehchan")
        continuity_terms = (
            "same", "existing", "previous", "old", "as before", "unchanged",
            "wahi", "vahi", "pehle wala", "purana", "same hi", "rehega", "rahega",
        )
        return any(term in text for term in landmark_terms) and any(term in text for term in continuity_terms)

    @staticmethod
    def _address_location_conflict(messages: list[dict], address: str) -> dict | None:
        """Compare a proposed address with the authoritative order location."""
        city = SmartFallbackEngine._order_context_value(messages, "City")
        pincode = SmartFallbackEngine._order_context_value(messages, "Pincode")
        if not city or not pincode:
            return None
        pins = re.findall(r"\b\d{6}\b", address)
        has_other_pin = any(pin != pincode for pin in pins)
        normalized = address.lower()
        expected_city = city.lower().strip()
        mentioned_other_city = any(
            known_city in normalized and known_city != expected_city
            for known_city in KNOWN_CITIES
        )
        return {"city": city, "pincode": pincode} if has_other_pin or mentioned_other_city else None

    @staticmethod
    def _expects_alternate_receiver(messages: list[dict]) -> bool:
        """Infer an unresolved alternate-receiver request from recent dialogue."""
        # The final message is the candidate reply; inspect what preceded it.
        for message in reversed(messages[:-1]):
            if message.get("role") == "assistant":
                text = (message.get("content") or "").lower()
                receiver = any(term in text for term in ("alternate", "padosi", "neighbour", "neighbor", "security"))
                asks_for_identity = any(term in text for term in ("naam", "name"))
                asks_for_contact = any(term in text for term in ("mobile", "phone", "number", "flat", "house"))
                return receiver and asks_for_identity and asks_for_contact
            if message.get("role") == "user":
                break
        return False

    @staticmethod
    def _extract_person_contact(text: str) -> dict:
        """Extract a name/contact pair regardless of their order in the reply."""
        phone_match = re.search(r"(?<!\d)([6-9]\d{9})(?!\d)", text)
        phone = phone_match.group(1) if phone_match else ""
        remainder = re.sub(r"(?<!\d)[6-9]\d{9}(?!\d)", " ", text)
        tokens = re.findall(r"[A-Za-zÀ-ÿ\u0900-\u097F]+", remainder)
        labels = {"name", "naam", "number", "mobile", "phone", "contact", "alternate", "person"}
        name = " ".join(token for token in tokens if token.lower() not in labels).strip()
        return {"name": name, "phone": phone}


class BaseLLMClient(ABC):
    """Interface all providers must implement."""

    @abstractmethod
    async def complete(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        json_schema: dict | None = None,
        timeout: float = 6.0,
    ) -> LLMResult:
        ...


class OpenAIClient(BaseLLMClient):
    """OpenAI Chat Completions with tool calling (default provider)."""

    def __init__(self, model: str = None):
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError("Install openai: pip install openai")

        self.model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def complete(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        json_schema: dict | None = None,
        timeout: float = 6.0,
    ) -> LLMResult:
        api_messages = [{"role": "system", "content": system}]
        api_messages.extend(messages)

        kwargs = {
            "model": self.model,
            "messages": api_messages,
            "temperature": 0.3,
            "max_tokens": 500,
            "timeout": timeout,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        if json_schema:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "response",
                    "schema": json_schema,
                    "strict": True,
                }
            }

        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(**kwargs),
                timeout=timeout + 2,
            )
            message = response.choices[0].message
            result = LLMResult()

            if message.content:
                result.text = message.content

            if message.tool_calls:
                for tc in message.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                    except json.JSONDecodeError:
                        args = {"_raw": tc.function.arguments}
                    result.tool_calls.append(ToolCall(name=tc.function.name, args=args, id=tc.id))

            if response.usage:
                result.usage = {
                    "in": response.usage.prompt_tokens,
                    "cached_in": getattr(response.usage, "prompt_tokens_cached", 0) or 0,
                    "out": response.usage.completion_tokens,
                }

            return result

        except Exception as e:
            # When OpenAI hits rate limit (429) or network issue, smoothly fallback to SmartFallbackEngine
            print(f"[WARN] OpenAI API exception ({e}), activating SmartFallbackEngine...")
            return SmartFallbackEngine.process(messages, tools)


class MockLLMClient(BaseLLMClient):
    """Fallback client for testing without an API key."""

    async def complete(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        json_schema: dict | None = None,
        timeout: float = 6.0,
    ) -> LLMResult:
        return SmartFallbackEngine.process(messages, tools)


def get_llm_client() -> BaseLLMClient:
    """Factory: select provider from env var (§3A)."""
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    api_key = os.getenv("OPENAI_API_KEY", "")

    if provider == "openai" and api_key and not api_key.startswith("sk-your"):
        return OpenAIClient()
    elif provider == "mock" or not api_key or api_key.startswith("sk-your"):
        print("[INFO] Using MockLLMClient — set OPENAI_API_KEY for real LLM")
        return MockLLMClient()
    else:
        print(f"[WARN] Unknown LLM_PROVIDER={provider}, falling back to mock")
        return MockLLMClient()
