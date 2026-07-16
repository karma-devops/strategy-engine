"""
Authentication dependencies for strategy-engine.

- UI routes use HTTP Basic Auth with DASHBOARD_USERNAME / DASHBOARD_PASSWORD.
- API routes use X-API-Key header matching AGENT_API_KEY.
"""

import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.requests import Request

from config import config


# UI auth: HTTP Basic
ui_security = HTTPBasic(auto_error=False)


def verify_ui_credentials(credentials: HTTPBasicCredentials = Depends(ui_security)):
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )
    if not secrets.compare_digest(credentials.username, config.DASHBOARD_USERNAME or "") or not secrets.compare_digest(credentials.password, config.DASHBOARD_PASSWORD or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


# API auth: X-API-Key header
API_KEY_HEADER = "X-API-Key"


def verify_api_key(request: Request):
    """Verify that the X-API-Key header matches AGENT_API_KEY or a per-user PULS-R key."""
    if not config.AGENT_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AGENT_API_KEY not configured on server",
        )
    api_key = request.headers.get(API_KEY_HEADER)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key",
        )
    # Check global API key first (fast path)
    if secrets.compare_digest(api_key, config.AGENT_API_KEY or ""):
        return api_key
    # Check per-user PULS-R keys (puls_*_key format)
    if api_key.startswith("puls_"):
        from instances.models import SessionLocal, User
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.api_key == api_key).first()
            if user:
                return api_key
        finally:
            db.close()
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid or missing API key",
    )


def optional_api_key(request: Request):
    """Return the API key if present/valid (global or per-user PULS-R key), else None."""
    api_key = request.headers.get(API_KEY_HEADER)
    if not api_key:
        return None
    # Check global API key first
    if config.AGENT_API_KEY and secrets.compare_digest(api_key, config.AGENT_API_KEY):
        return api_key
    # Check per-user PULS-R keys
    if api_key.startswith("puls_"):
        from instances.models import SessionLocal, User
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.api_key == api_key).first()
            if user:
                return api_key
        finally:
            db.close()
    return None


def require_ui_or_api(request: Request):
    """Accept either valid UI Basic auth or valid API key."""
    # First try API key (stateless)
    api_key = request.headers.get(API_KEY_HEADER)
    if config.AGENT_API_KEY and secrets.compare_digest(api_key, config.AGENT_API_KEY):
        return "api"

    # Fall back to HTTP Basic via manually parsing Authorization header
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Basic "):
        import base64
        try:
            decoded = base64.b64decode(auth[6:]).decode("utf-8")
            username, password = decoded.split(":", 1)
            if secrets.compare_digest(username, config.DASHBOARD_USERNAME or "") and secrets.compare_digest(password, config.DASHBOARD_PASSWORD or ""):
                return "ui"
        except Exception:
            pass

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required (Basic or X-API-Key)",
        headers={"WWW-Authenticate": "Basic"},
    )
