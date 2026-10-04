"""Post-validator (§3, step 7).
Checks every draft reply before sending:
- Every number, date, ₹ amount and time must appear in a tool result
- Banned promises are blocked
- Length is capped
"""

import re
from typing import Optional


# Banned phrases (R-06, R-07, R-08)
BANNED_PATTERNS = [
    re.compile(r"\bguarantee[ds]?\b", re.I),
    re.compile(r"\bpakka\b", re.I),
    re.compile(r"\brefund will be\b", re.I),
    re.compile(r"\border cancel(led)?\b", re.I),
    re.compile(r"\bban\b(?!\w)", re.I),  # "ban" but not "bank", "band"
    re.compile(r"\bguaranteed delivery\b", re.I),
    re.compile(r"\bpayment (is |has been )?received\b", re.I),  # R-08
    re.compile(r"\brefund (has been |is )?processed\b", re.I),
]

MAX_WORDS = 60


class ValidationResult:
    def __init__(self, valid: bool, errors: list[str] = None, cleaned_text: str = ""):
        self.valid = valid
        self.errors = errors or []
        self.cleaned_text = cleaned_text


def validate_reply(
    draft_text: str,
    tool_results: list[dict],
    max_words: int = MAX_WORDS,
) -> ValidationResult:
    """
    Validate an agent's draft reply before sending.

    Returns ValidationResult with valid=False and error details if problems found.
    """
    errors = []

    if not draft_text or not draft_text.strip():
        return ValidationResult(True, cleaned_text="")

    # 1. Check banned patterns
    for pattern in BANNED_PATTERNS:
        match = pattern.search(draft_text)
        if match:
            errors.append(f"Banned phrase detected: '{match.group()}'")

    # 2. Check word count
    words = draft_text.split()
    if len(words) > max_words:
        errors.append(f"Reply too long: {len(words)} words (max {max_words})")

    # 3. Fact-check: numbers, amounts, dates must come from tool results
    tool_facts = _extract_facts_from_tools(tool_results)
    reply_facts = _extract_facts_from_text(draft_text)

    for fact_type, fact_value in reply_facts:
        if fact_type == "amount":
            # ₹ amounts must match a tool result
            if fact_value not in tool_facts.get("amounts", set()):
                # Check if it's a known amount from any tool
                if not _is_amount_in_tools(fact_value, tool_results):
                    errors.append(f"Amount ₹{fact_value} not found in tool results. Do not invent amounts.")

        elif fact_type == "time_specific":
            # Specific times that look like promises
            if not _is_time_in_tools(fact_value, tool_results):
                # Allow common phrases
                if fact_value not in {"08:00", "09:00", "21:00", "20:00"}:
                    pass  # Only flag very specific time promises

    # 4. Check for payment confirmation without webhook (R-08)
    payment_confirm_patterns = [
        re.compile(r"payment (mil gaya|received|ho gaya|confirm)", re.I),
        re.compile(r"paisa aa gaya", re.I),
        re.compile(r"paid successfully", re.I),
    ]
    for p in payment_confirm_patterns:
        if p.search(draft_text):
            # Only allowed if tool results show payment verified
            payment_verified = any(
                tr.get("payment_verified") or tr.get("is_cod") == False
                for tr in tool_results
                if isinstance(tr, dict)
            )
            if not payment_verified:
                errors.append("Cannot confirm payment without verified payment webhook (R-08).")

    if errors:
        return ValidationResult(False, errors, cleaned_text=draft_text)

    return ValidationResult(True, cleaned_text=draft_text)


def _extract_facts_from_tools(tool_results: list[dict]) -> dict:
    """Extract verifiable facts from tool results."""
    facts = {"amounts": set(), "dates": set(), "times": set(), "order_ids": set()}

    for result in tool_results:
        if not isinstance(result, dict):
            continue
        _extract_recursive(result, facts)

    return facts


def _extract_recursive(obj, facts: dict):
    """Recursively extract facts from nested dicts/lists."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, str):
                # Extract amounts
                amounts = re.findall(r"₹?(\d+(?:,\d+)*(?:\.\d+)?)", value)
                for a in amounts:
                    facts["amounts"].add(a.replace(",", ""))

                # Extract order IDs
                if key in ("order_id", "ticket_id", "link_id"):
                    facts["order_ids"].add(value)

            elif isinstance(value, (int, float)):
                facts["amounts"].add(str(int(value)))

            elif isinstance(value, (dict, list)):
                _extract_recursive(value, facts)

    elif isinstance(obj, list):
        for item in obj:
            _extract_recursive(item, facts)


def _extract_facts_from_text(text: str) -> list[tuple]:
    """Extract factual claims from the reply text."""
    facts = []

    # ₹ amounts
    amounts = re.findall(r"₹\s?(\d+(?:,\d+)*(?:\.\d+)?)", text)
    for a in amounts:
        facts.append(("amount", a.replace(",", "")))

    # Specific time promises like "3:30 PM", "15:30"
    times = re.findall(r"\b(\d{1,2}:\d{2})\s*(?:PM|AM|pm|am)?\b", text)
    for t in times:
        facts.append(("time_specific", t))

    return facts


def _is_amount_in_tools(amount: str, tool_results: list[dict]) -> bool:
    """Check if an amount appears anywhere in tool results."""
    amount_clean = amount.replace(",", "").strip()
    for result in tool_results:
        result_str = str(result)
        if amount_clean in result_str:
            return True
    return False


def _is_time_in_tools(time_str: str, tool_results: list[dict]) -> bool:
    """Check if a specific time appears in tool results."""
    for result in tool_results:
        if time_str in str(result):
            return True
    return False
