# Valmo Mitra AI - Meesho DICE Challenge Prototype

> **SIMULATED prototype** - built for the Meesho DICE Challenge. It uses seeded data and mocked Meesho, payment, and WhatsApp integrations; it is not connected to Meesho production systems.

Valmo Mitra is a conversational delivery assistant for Meesho's Valmo logistics network. It helps customers resolve delivery issues in Hinglish, keeps riders’ manifests current, and gives hub operations a view of exceptions—all while enforcing deterministic guardrails around sensitive actions.

## What the prototype demonstrates

- A WhatsApp-style customer assistant for availability confirmation, rescheduling, same-pincode address updates, alternate receivers, delivery status, self-pickup, and COD-to-online-payment flows.
- A deterministic pre-router for button replies and short messages, with an OpenAI-backed agent and offline fallback for richer queries.
- Guarded tool execution: role checks, order ownership, idempotency, address/pincode locks, rate limiting, and post-response fact validation.
- A rider workflow with a live manifest, OTP-protected COD/high-value delivery, missed-call tracking, and fake-door-attempt detection.
- A hub-ops dashboard with exception queues, operational metrics, tickets, and simulated real-time updates.
- SQLite-backed seed data, SSE routes, and an optional Vercel deployment configuration.

## Architecture

```text
React + Vite simulator
  ├─ Customer WhatsApp UI
  ├─ Rider delivery app
  └─ Hub operations dashboard
            │
            ▼
FastAPI API → agent runtime → authorization gateway → tools → SQLite
                 │                    │
                 └─ OpenAI / fallback └─ mocked Meesho + payments adapters
```

## Repository layout

| Path | Purpose |
| --- | --- |
| `backend/agent` | pre-router, agent runtime, policy prompts, response validation |
| `backend/api` | FastAPI chat, rider, ops, and SSE endpoints |
| `backend/gateway` | permission, ownership, location-lock, and idempotency checks |
| `backend/tools` | customer, rider, and operations actions |
| `backend/sim` | clearly labelled seeded demo personas and orders |
| `frontend` | React/Vite three-panel prototype UI |
| `VALMO_MITRA_MASTER_SPEC_AND_DEBUG_GUIDE.md` | product vision, implemented behaviours, and engineering guide |
| `valmo_mitra_ai_spec_v2.md` | detailed agent-layer specification |

## Run locally

### 1. Configure the backend

```powershell
Copy-Item .env.example .env
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8000 --reload
```

The API is available at `http://127.0.0.1:8000` and its health check is `GET /health`.

### 2. Run the frontend

```powershell
Set-Location frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

### Optional OpenAI configuration

The prototype works with its fallback engine when no key is supplied. To use OpenAI, set `OPENAI_API_KEY` in your local `.env`; never commit that file.

## Checks

With the API running:

```powershell
.\venv\Scripts\python.exe test_api.py
.\venv\Scripts\python.exe test_flows.py
```

For the UI:

```powershell
Set-Location frontend
npm run build
```

## Important prototype boundaries

- All order, customer, payment, OTP, ETA, and cost data is synthetic or mocked.
- The integration seams are deliberately isolated in `backend/services/meesho_gateway.py` and `backend/services/payments_adapter.py`.
- `.env`, local SQLite files, logs, dependencies, and build output are excluded from Git.

## Team / competition use

This repository is intended as a demonstration submission for the Meesho DICE Challenge. Please review the two specification documents for the product assumptions, guardrails, test scenarios, and proposed production hardening.
