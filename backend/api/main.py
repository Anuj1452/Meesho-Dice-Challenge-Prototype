import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import routes_chat, routes_rider, routes_ops, routes_sse
from backend.models.database import init_db, get_session_factory, Customer

# Initialize database
init_db()

# Auto-seed if DB is empty (handles Vercel cold starts where /tmp is wiped)
def _auto_seed():
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        count = db.query(Customer).count()
        if count == 0:
            from backend.sim.seed_data import seed_database
            seed_database(db)
    except Exception:
        pass
    finally:
        db.close()

_auto_seed()

app = FastAPI(title="Valmo Mitra AI Prototype")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For prototype
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(routes_rider.router, prefix="/api/rider", tags=["rider"])
app.include_router(routes_ops.router, prefix="/api/ops", tags=["ops"])
app.include_router(routes_sse.router, prefix="/api/sse", tags=["sse"])

@app.get("/health")
def health():
    return {"status": "ok", "version": "2.1", "label": "SIMULATED"}

