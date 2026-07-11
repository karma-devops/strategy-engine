"""
SSE stream and logs endpoints.
"""

import json
import queue
import time

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from api.ratelimit import limiter, READ_LIMIT, STREAM_LIMIT
from instances.events import add_log, get_logs, event_bus

router = APIRouter()


@router.get("/logs")
@limiter.limit(READ_LIMIT)
def logs(request: Request, limit: int = 50):
    return {"ok": True, "logs": get_logs(limit)}


@router.get("/stream")
@limiter.limit(STREAM_LIMIT)
def stream(request: Request):
    q = queue.Queue()
    event_bus.subscribe(q)

    def event_generator():
        try:
            while True:
                try:
                    event = q.get(timeout=5)
                    yield f"data: {json.dumps(event)}\n\n"
                except queue.Empty:
                    yield f"data: {json.dumps({'type': 'ping', 'ts': time.time()})}\n\n"
                except Exception:
                    break
        finally:
            event_bus.unsubscribe(q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
