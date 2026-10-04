"""
Vercel Serverless Function entry point.
Exposes the FastAPI ASGI app for Vercel's Python runtime.
"""
import os
import sys

# Ensure the project root is in the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# For Vercel serverless: use /tmp for SQLite since the filesystem is read-only
os.environ.setdefault("DB_PATH", "/tmp/valmo_mitra.db")

# Import the FastAPI app — this also triggers init_db() and _auto_seed()
from backend.api.main import app
