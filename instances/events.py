"""
Shared event bus and log buffer for SSE streaming.
"""

import queue
from collections import deque
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

# In-memory log buffer (deque = O(1) append/popleft vs list.pop(0) O(n))
LOG_BUFFER = deque(maxlen=200)
MAX_LOGS = 200


def add_log(message: str, level: str = "info", dry_run: bool = None):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": message,
        "level": level,
        "dry_run": dry_run,
    }
    LOG_BUFFER.append(entry)
    event_bus.emit({"type": "log", "log": entry})


def get_logs(limit: int = 50) -> list:
    return list(LOG_BUFFER)[-limit:]
