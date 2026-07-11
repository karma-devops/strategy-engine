"""
Rate limiting configuration using slowapi + in-memory storage.

Buckets:
- auth endpoints: 5 requests / minute
- write endpoints: 20 requests / minute  
- read endpoints: 100 requests / minute
- webhook/stream endpoints: 200 / minute

Limit key is based on client IP + API key (if present) for API requests,
or client IP for UI/basic auth requests.
"""

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, FastAPI

# In-memory limiter by default. Redis URL can be set via env RATE_LIMIT_REDIS_URL later.
limiter = Limiter(key_func=get_remote_address)

AUTH_LIMIT = "5/minute"
WRITE_LIMIT = "20/minute"
READ_LIMIT = "100/minute"
STREAM_LIMIT = "200/minute"


def add_rate_limiting(app: FastAPI):
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


def api_key_or_ip(request: Request):
    """Return a stable key that combines IP with API key if present."""
    ip = get_remote_address(request)
    api_key = request.headers.get("X-API-Key", "")
    if api_key:
        return f"{ip}:{api_key}"
    return ip
