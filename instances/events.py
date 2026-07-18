"""
Shared event bus and log buffer for SSE streaming.
"""

import queue
import threading
from collections import deque
from datetime import datetime, timezone


class EventBus:
    def __init__(self):
        self._listeners = []
        self._lock = threading.Lock()  # BUG #7: protect _listeners from concurrent mutation

    def emit(self, event: dict):
        # Snapshot under lock to avoid holding lock during q.put (which can block)
        with self._lock:
            listeners = list(self._listeners)
        for q in listeners:
            try:
                q.put(event)
            except Exception:
                pass

    def subscribe(self, q):
        with self._lock:
            self._listeners.append(q)

    def unsubscribe(self, q):
        with self._lock:
            if q in self._listeners:
                self._listeners.remove(q)


event_bus = EventBus()

# In-memory log buffer (deque = O(1) append/popleft vs list.pop(0) O(n))
LOG_BUFFER = deque(maxlen=200)
LOG_BUFFER_LOCK = threading.Lock()  # BUG #8: protect LOG_BUFFER append/pop from concurrent mutation
MAX_LOGS = 200


def add_log(message: str, level: str = "info", dry_run: bool = None):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": message,
        "level": level,
        "dry_run": dry_run,
    }
    with LOG_BUFFER_LOCK:
        LOG_BUFFER.append(entry)
    event_bus.emit({"type": "log", "log": entry})


def get_logs(limit: int = 50) -> list:
    with LOG_BUFFER_LOCK:
        return list(LOG_BUFFER)[-limit:]
