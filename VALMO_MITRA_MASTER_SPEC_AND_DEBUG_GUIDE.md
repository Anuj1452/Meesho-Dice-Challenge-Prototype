# Valmo Mitra AI — Master Project Specification & Engineering Debug Guide

> **Target Audience for this Document:** Autonomous AI Coding Agent (Codex) & Engineers.
> **Instructions for Codex:** You do **not** need to rebuild this project from scratch. The codebase is fully implemented with a working FastAPI backend, SQLite database, and React + Vite frontend. Your task is to **debug, refine, harden, and complete the advanced edge cases** outlined in this specification. Read this document thoroughly before inspecting the code.

---

## 1. Executive Summary & Product Vision

### 1.1 What We Are Building
**Valmo Mitra** is Meesho’s AI-powered conversational logistics assistant built on top of Meesho’s in-house logistics network (**Valmo**). It operates primarily over WhatsApp in **Hinglish** (Romanized Hindi + English) and native Indian languages.

### 1.2 The Core Problem
In Indian e-commerce (especially Tier 2, Tier 3, and Tier 4 towns):
- 30%+ of failed first-attempt deliveries (NDR - Non-Delivery Reports) occur due to customer unavailability, incorrect/incomplete addresses, or unreachable phones.
- Riders make fake door attempts ("Customer not reachable" or "Address incomplete") to meet tight delivery manifest schedules.
- Customer support costs are high, and customers get frustrated when delivery updates are opaque.

### 1.3 How Valmo Mitra Solves It
1. **Morning Delivery Nudges:** Customers receive interactive morning WhatsApp alerts asking for delivery confirmation (*"Available Today"* vs *"Reschedule Tomorrow"* vs *"Change Address"* vs *"Leave with Neighbor"*).
2. **Deterministic Pre-Router + LLM Dual Engine:** Simple button clicks and short deterministic replies cost ₹0 in LLM fees via regex/rule-based routing. Complex queries and free-form instructions run through an LLM agent with strict tool calling and security gateway validation.
3. **Real-time Manifest Synchronization:** When a customer reschedules or updates their address, the **Rider App Manifest** and **Hub Operations Dashboard** update in real time with audio-visual notifications, preventing wasted rider trips.
4. **Strict Guardrails & Zero Hallucination:** The agent can never invent delivery dates, refund guarantees, or money amounts. All data must originate from tool calls validated by an authorization gateway.

---

## 2. Complete Architecture & Tech Stack

### 2.1 Technology Stack
- **Backend:** Python 3.10+, FastAPI (Asynchronous REST API + Uvicorn server).
- **Database:** SQLite with SQLAlchemy ORM (`backend/models/database.py`).
- **NLU / Intelligence:**
  - Primary: OpenAI Chat Completions with Function Calling (`gpt-4o-mini`).
  - Resilient Fallback: `SmartFallbackEngine` inside `backend/nlu/llm_client.py` for offline/rate-limited environments.
  - Deterministic Pre-Router: `backend/agent/pre_router.py`.
- **Security & Authorization:** `ToolGateway` (`backend/gateway/tool_gateway.py`) with Tiered Permissions (A0 Read, A1 Low-Write, A2 Confirmed-Write, A3 Money).
- **Frontend:** React 18, Vite, Tailwind CSS / Vanilla CSS, Lucide Icons.
- **Port Bindings:**
  - Frontend: `http://localhost:5173`
  - Backend API: `http://localhost:8000`

### 2.2 Directory Structure
```text
├── backend/
│   ├── agent/
│   │   ├── pre_router.py         # Deterministic keyword & WhatsApp button router (saves LLM cost)
│   │   ├── runtime.py            # Orchestrator: Pre-router -> Context -> LLM -> Gateway -> Post-Validator -> DB
│   │   └── post_validator.py     # Fact-checker & banned phrase blocker (guarantees, refunds, hallucinated amounts)
│   ├── api/
│   │   ├── main.py               # FastAPI entry point, CORS, and sub-routers mounting
│   │   ├── routes_chat.py        # /api/chat/message, /history, /session
│   │   ├── routes_rider.py       # /api/rider/manifest, /myday, /trip-status
│   │   └── routes_ops.py         # /api/ops/queue, /metrics, /pending-actions, /escalate
│   ├── database/
│   │   ├── connection.py         # SQLite engine and session factory
│   │   └── seed_data.py          # Populates 14 customer personas, hubs, riders, orders
│   ├── gateway/
│   │   └── tool_gateway.py       # Validates role permissions, pincode lock, idempotency, rate limits
│   ├── models/
│   │   ├── database.py           # SQLAlchemy tables: Customer, Order, TrackingEvent, Ticket, Rider, ValmoCenter
│   │   └── enums.py              # OrderState, ToolTier, VerificationLevel, UserRole
│   ├── nlu/
│   │   └── llm_client.py         # OpenAIClient + SmartFallbackEngine abstraction
│   ├── services/
│   │   ├── eta_engine.py         # ETA calculator (range-based delivery estimates)
│   │   └── meesho_gateway.py     # External API mock for Meesho order/tracking webhooks
│   └── tools/
│       ├── customer_tools.py     # 12 customer-facing actions (set_availability, update_address, etc.)
│       └── rider_tools.py        # Rider-facing actions (complete_delivery, fake_attempt_flag, etc.)
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── CustomerChat.jsx  # WhatsApp mobile simulator for customers
│   │   │   ├── RiderApp.jsx      # Mobile delivery app for delivery executives (Amit)
│   │   │   ├── OpsDashboard.jsx  # Hub manager dashboard for exception management
│   │   │   └── SystemAudit.jsx   # Real-time event log, gateway audit, token cost monitor
│   │   ├── App.jsx               # Master 3-column split view (Customer | Rider | Ops)
│   │   ├── index.css             # Glassmorphism, animations, mobile phone bezels
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
└── .env                          # OPENAI_API_KEY, LLM_PROVIDER, LLM_MODEL
```

---

## 3. Core Features & Personas

### 3.1 Customer Personas (Pre-seeded in SQLite)
1. **Anita Patel (`d3aba319ff24da92`):**
   - Scenario: Order `MS769522011`, Out for Delivery.
   - Behavior: Confirms availability (*"Main ghar par hi hoon, aaj hi bhej do"*).
   - Expected Output: Marks order `available_today`, alerts rider on manifest, provides masked call rider button.
2. **Vikram Singh (`01bc0cf8c7ded7f2`):**
   - Scenario: Order `MS695474130`, Out for Delivery.
   - Behavior: Customer is busy today, wants delivery tomorrow (*"Aaj nahi, kal dopahar 2 baje bhejna"*).
   - Expected Output: Sets order to `SKIPPED_TODAY`, increments deferral count, schedules for tomorrow, warns rider to skip stop.
3. **Deepa Joshi (`14f7c36e478b5803`):**
   - Scenario: Order `MS100293847`, Needs address change.
   - Behavior: Intent query -> system prompts for address -> customer provides new address in same pincode (`110086`).
   - Expected Output: Updates address, records `original_address`, rider manifest reflects the change with a visual badge.

### 3.2 User Roles & Split-Screen Interfaces
- **Customer WhatsApp Simulator (`CustomerChat.jsx`):**
  - Interactive WhatsApp UI with incoming morning nudge, quick reply buttons, voice note placeholder, status ticks.
- **Rider Delivery App (`RiderApp.jsx`):**
  - Daily trip manifest (e.g. 14 stops), stop-by-stop navigation, COD collection indicators, dynamic status badges (*"Available Today"*, *"Rescheduled"*, *"Address Updated"*), masked customer calling.
- **Hub Control Dashboard (`OpsDashboard.jsx`):**
  - Real-time exception resolution, delivery success rate metrics, pending escalations, agent intervention triggers.

---

## 4. Key Lessons Learned & Important Architecture Details

When building and testing this prototype, several key behaviors and constraints were uncovered that you **must preserve**:

### 4.1 UTF-8 Encoding & Mojibake Protection
- Emoji symbols (👍, 📍, 📞, 📅, 🙏) and Hindi characters can easily trigger `UnicodeEncodeError: 'charmap'` on Windows machines or display garbled characters (mojibake) if files are saved without UTF-8 encoding.
- Always use `encoding="utf-8"` or `encoding="utf-8-sig"` in all Python file reads/writes.
- Never use Latin-1/cp1252 fallbacks.

### 4.2 Multi-Turn Address Change Logic
- **Do not save intent queries as addresses!**
  - If a user sends `"mujhe address change krna hai"` or `"address kese change kra?"`, this is a **request/question**, not a new address.
  - The AI must prompt: *"Apna naya delivery address batayein (same pincode mein hona chahiye jaise Flat/House No., Gali/Road, Landmark). Jaise hi aap address likhenge, hum use update kar denge 📍"*
- **Pincode & Locality Locking (Rule R-30):**
  - Address modifications are **strictly allowed only within the original order pincode**.
  - If a customer types a different 6-digit pincode (e.g. `110011` when order is `110085`), the `ToolGateway` rejects the tool call with: *"Delivery location is fixed to pincode 110085. A different pincode (110011) was detected."*
  - Maximum of **2 address updates per order**. Subsequent attempts must be rejected.

### 4.3 Deterministic Pre-Router vs. Intelligent LLM Agent
- WhatsApp interactive buttons pass `message_type: 'button_reply'` with a clean `button_payload` (e.g. `btn_available_today`, `btn_not_today`, `btn_call_rider`).
- The pre-router intercepts button replies and exact short keywords (*"1"*, *"2"*, *"stop"*, *"thanks"*) to save 100% of LLM cost.
- Long text, multi-sentence queries, or specific address strings must **bypass the pre-router** and pass directly to the LLM agent (`AgentRuntime._llm_pipeline`).

### 4.4 OpenAI Rate Limits (429) & SmartFallbackEngine
- Free/low-tier OpenAI keys frequently hit the 50 requests/day (RPD) or rate-limit ceiling.
- `backend/nlu/llm_client.py` contains a `SmartFallbackEngine` that intercepts 429 errors or timeouts and provides conversational NLU and tool execution so the system never crashes with generic error messages (*"Abhi kuch problem aa rahi hai"*).

### 4.5 Tool Authorization Gateway (`ToolGateway`)
- Before any tool is executed, `ToolGateway.check()` verifies:
  1. Role permissions (customer vs rider vs ops).
  2. Order ownership (customer cannot manipulate another user's order).
  3. Preconditions (e.g. address change not allowed if order is already DELIVERED).
  4. Location locking (pincode and city match).
  5. Idempotency (prevents double-booking or duplicated actions).

---

## 5. Required Improvements & Debug Checklist for Codex

Codex, you should focus your work on completing and refining the following specific areas:

### Task 1: Complete Address Parsing & Partial Address Clarification
- **Current Behavior:** If a customer enters a very short string like *"near temple"*, the system may attempt to update the address without asking for the flat or house number.
- **Required Improvement:**
  - In `backend/tools/customer_tools.py` and `backend/nlu/llm_client.py`, check address completeness.
  - If the user provides only a landmark or partial street (fewer than 4 words or lacking a house/flat identifier), have the agent ask: *"Kripya house/flat number aur street details bhi batayein taaki rider ko parcel deliver karne mein pareshani na ho 📍"*.

### Task 2: Strict Audio/Voice Note Flow (WhatsApp Voice Memo Mocking)
- **Current Behavior:** The frontend has a microphone icon in `CustomerChat.jsx`, but sending an audio message only sends a placeholder or text message.
- **Required Improvement:**
  - Support `message_type: 'audio'` in `routes_chat.py`.
  - Simulate speech-to-text (Whisper mock or transcribed text) in `runtime.py` so audio notes like *"Bhaiya main 5 baje aaunga parcel padosi ko de dena"* are transcribed and routed to `set_alternate_receiver` or `set_availability`.

### Task 3: Fake Door Attempt & OTP Delivery Validation
- **Current Behavior:** In `RiderApp.jsx`, clicking "Delivered" immediately marks the order delivered.
- **Required Improvement:**
  - Introduce an OTP requirement for Cash-on-Delivery (COD) and high-value orders.
  - When the rider clicks "Delivered", require a 4-digit OTP.
  - The customer's WhatsApp chat should receive the simulated OTP message: *"Aapka delivery OTP hai 4821. Rider ko parcel lene ke baad hi ye OTP dein."*
  - If the rider clicks "No Answer (0/3)" 3 times, check customer GPS coordinates vs rider GPS coordinates to detect and flag "Fake Door Attempt" (Rule R-14).

### Task 4: Auto-Cancellation & Escalation Protocol (Negative Action Protocol)
- **Current Behavior:** The system has rule R-04/R-06 in `SYSTEM_PROMPT` stating the agent cannot cancel orders, but if the customer repeatedly says *"Order cancel karo, mujhe nahi chahiye"*, the conversation can loop.
- **Required Improvement:**
  - Implement the **Negative Action Protocol**:
    1. First attempt: Empathize and ask why they want to cancel (offer rescheduling, address change, or fee waiver).
    2. Second attempt: If customer insists on cancelling, explain that orders cannot be cancelled once out for delivery via WhatsApp, guide them to the Meesho App (`My Orders -> Cancel`), and call `create_ticket(category="cancellation_request")`.
    3. Third attempt: Escalate to human support via `escalate_to_human()` and notify the Hub Ops Dashboard.

### Task 5: Database Persistence & Session Isolation Verification
- **Current Behavior:** SQLite uses `InMemoryStore` or `backend.database.connection.SessionLocal`.
- **Required Improvement:**
  - Ensure that multiple chat tabs or user switches do not leak turn state across session IDs.
  - Ensure that every session creation cleanly initializes turn count to 0 and caps turns at 12 turns max before triggering human escalation.

---

## 6. How to Run the Environment Locally

### Backend (FastAPI)
```powershell
# Navigate to the backend directory
cd "backend"
# Run with virtual environment
..\venv\Scripts\python.exe -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8000 --reload
```
Health check endpoint: `GET http://127.0.0.1:8000/health`

### Frontend (React + Vite)
```powershell
# Navigate to the frontend directory
cd "frontend"
npm install
npm run dev
```
Frontend URL: `http://localhost:5173`

---

## 7. Verification Test Suite

Codex can run the following automated Python test to verify that the core flows work:

```python
import urllib.request
import json
import uuid

def send(phone_hash, message, msg_type="text"):
    body = {
        "session_id": f"test_{uuid.uuid4().hex[:6]}",
        "phone_hash": phone_hash,
        "message": message,
        "message_type": msg_type
    }
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/chat/message",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())

# Test 1: Availability
res1 = send("d3aba319ff24da92", "Main ghar par hi hoon, aaj hi bhej do")
print("Anita response:", res1["reply"])

# Test 2: Reschedule
res2 = send("01bc0cf8c7ded7f2", "Aaj nahi, kal dopahar 2 baje bhejna")
print("Vikram response:", res2["reply"])

# Test 3: Address intent (should ask for address)
res3 = send("14f7c36e478b5803", "mujhe address change krna hai")
print("Deepa prompt:", res3["reply"])

# Test 4: Address update with same pincode
res4 = send("14f7c36e478b5803", "Flat 402, Royal Residency, Rohini Sector 7, Delhi 110086")
print("Deepa updated:", res4["reply"])
```

---

*This concludes the master project specification. Codex, proceed with debugging and enhancing the checklist items in Section 5.*
