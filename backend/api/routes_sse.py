import asyncio
import json
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

router = APIRouter()

# In a real app, this would be a Redis Pub/Sub channel or similar.
# For the prototype, we use a simple in-memory queue or just simulated events.
# We will simulate events for demonstration purposes.

@router.get("/stream")
async def message_stream(request: Request):
    """SSE endpoint for real-time live manifest and dashboard updates (§3)."""
    async def event_generator():
        while True:
            # Check for client disconnect
            if await request.is_disconnected():
                break
                
            # Yield a keep-alive comment every 15 seconds
            yield {
                "event": "ping",
                "data": json.dumps({"status": "alive", "label": "SIMULATED"})
            }
            await asyncio.sleep(15)

    return EventSourceResponse(event_generator())
