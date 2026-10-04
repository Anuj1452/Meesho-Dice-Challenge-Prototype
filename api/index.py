"""
Vercel Serverless Function entry point.
Wraps the FastAPI app so Vercel can serve it as a serverless Python function.
"""
import os
import sys

# Ensure the project root is in the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# For Vercel serverless: use /tmp for SQLite since the filesystem is read-only
# except for /tmp
os.environ.setdefault("DB_PATH", "/tmp/valmo_mitra.db")

from mangum import Mangum
from backend.api.main import app

# Mangum is the ASGI adapter for AWS Lambda / Vercel serverless
handler = Mangum(app, lifespan="off")
