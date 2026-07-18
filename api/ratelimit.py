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


def api_key_or_ip(request: Request):
    """Return a stable key that combines IP with API key if present.

    BUG #14: this is the key_func used by the Limiter below so that
    multiple agents behind one IP get separate buckets (not all
    sharing one IP bucket).
    """
    ip = get_remote_address(request)
    api_key = request.headers.get("X-API-Key", "")
    if api_key:
        return f"{ip}:{api_key}"
    return ip


# BUG #14: use api_key_or_ip as key_func so multiple agents behind one IP
# get separate buckets. Defined after api_key_or_ip to avoid NameError.
limiter = Limiter(key_func=api_key_or_ip)

AUTH_LIMIT = "5/minute"
WRITE_LIMIT = "20/minute"
READ_LIMIT = "100/minute"
STREAM_LIMIT = "200/minute"


def add_rate_limiting(app: FastAPI):
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
