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
        # T4-3: 1-second portfolio metrics frame cadence (non-blocking)
        last_metrics_ts = 0.0
        try:
            while True:
                try:
                    event = q.get(timeout=1)
                    yield f"data: {json.dumps(event)}\n\n"
                except queue.Empty:
                    # No queued event this tick — emit metrics frame on 1s cadence
                    now = time.time()
                    if now - last_metrics_ts >= 1.0:
                        last_metrics_ts = now
                        try:
                            from core.exchange import hl_client
                            # Build metrics from the live exchange interface (defensive)
                            account_snapshot = {}
                            try:
                                # Best-effort full state; not all clients expose user_state directly
                                if hasattr(hl_client, "get_account_state"):
                                    account_snapshot = hl_client.get_account_state() or {}
                            except Exception:
                                account_snapshot = {}
                            portfolio_value = 0.0
                            try:
                                portfolio_value = float(hl_client.get_account_value() or 0.0)
                            except Exception:
                                portfolio_value = 0.0
                            metrics_payload = {
                                "type": "metrics",
                                "timestamp": now,
                                "data": {
                                    "portfolio_value": portfolio_value,
                                    "daily_pnl": account_snapshot.get("dailyPnl", 0.0),
                                    "margin_usage": account_snapshot.get("marginSummary", {}).get("marginUsed", 0.0),
                                },
                            }
                            yield f"data: {json.dumps(metrics_payload)}\n\n"
                        except Exception as metrics_err:
                            print(f"[Stream Engine Telemetry Error]: Failed to slice cache primitives: {str(metrics_err)}")
                    # Idle keepalive ping on the 5s boundary
                    elif int(now) % 5 == 0:
                        yield f"data: {json.dumps({'type': 'ping', 'ts': now})}\n\n"
                except Exception:
                    break
        finally:
            event_bus.unsubscribe(q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
