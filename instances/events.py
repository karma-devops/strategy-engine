"""
Shared event bus and log buffer for SSE streaming.
"""

import queue
from datetime import datetime, timezone


class EventBus:
    def __init__(self):
        self._listeners = []

    def emit(self, event: dict):
        for q in self._listeners:
            try:
                q.put(event)
            except Exception:
                pass

    def subscribe(self, q):
        self._listeners.append(q)

    def unsubscribe(self, q):
        if q in self._listeners:
            self._listeners.remove(q)


event_bus = EventBus()

# In-memory log buffer
LOG_BUFFER = []
MAX_LOGS = 200


def add_log(message: str, level: str = "info"):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": message,
        "level": level,
    }
    LOG_BUFFER.append(entry)
    if len(LOG_BUFFER) > MAX_LOGS:
        LOG_BUFFER.pop(0)
    event_bus.emit({"type": "log", "log": entry})


def get_logs(limit: int = 50) -> list:
    return LOG_BUFFER[-limit:]
