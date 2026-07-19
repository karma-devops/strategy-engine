"""
FastAPI entrypoint for strategy-engine.
Serves UI at / and API at /api/v2.
"""

from contextlib import asynccontextmanager

import os

from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from config import config
from instances.manager import manager, seed_default_fleet
from instances.models import get_or_seed_operator
from withdrawal.scheduler import scheduler as withdrawal_scheduler
from api import instances, signals, positions, metrics, withdrawals, stream, strategies, killswitch, backtests, monitoring, metadata, credentials
from app import routes as ui_routes
from app import paper_routes, backtest_routes
from api.auth import verify_api_key, verify_ui_credentials, require_ui_or_api
from api.ratelimit import limiter, READ_LIMIT, WRITE_LIMIT, AUTH_LIMIT, add_rate_limiting, api_key_or_ip

# D1 fix: read version from VERSION file (single source of truth, no drift)
def _read_version() -> str:
    try:
        _here = os.path.dirname(os.path.abspath(__file__))
        _vf = os.path.join(_here, "VERSION")
        with open(_vf) as _f:
            return _f.read().strip()
    except Exception:
        return "0.0.0"

VERSION = _read_version()


@asynccontextmanager
async def lifespan(app: FastAPI):
    manager.start()
    seed_default_fleet()
    get_or_seed_operator()  # ensure operator user exists (multi-tenant seed)
    withdrawal_scheduler.start()
    print("[APP] Started instance manager + withdrawal scheduler")
    yield
    withdrawal_scheduler.stop()
    manager.stop()
    print("[APP] Shut down instance manager + withdrawal scheduler")


app = FastAPI(
    title="PULS·R Strategy Engine",
    description="Algorithmic trading engine for HyperLiquid perps. Multi-instance runner with live/dry-run modes, real-time SSE streaming, server-rendered dashboard, and PWA support.",
    version=VERSION,
    contact={"name": "Operator", "url": "https://karmaworks.asia"},
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)
app.state.limiter = limiter
add_rate_limiting(app)

# SECURITY (T3-0): never let the browser or service worker cache authenticated
# /app/* HTML — it bakes the per-user window.API_KEY + data into the markup.
# A cached page would leak one user's dashboard to another. Force no-store.
@app.middleware("http")
async def _no_cache_app_html(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/app/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
        response.headers["Pragma"] = "no-cache"
    return response


# Identity middleware: resolve the session user and expose their identity to
# ALL templates via request.state (NO operator fallback / hardcoded values).
# Fixes the cross-user leak where layout.html hardcoded "Karma" / operator email.
@app.middleware("http")
async def _inject_user_identity(request: Request, call_next):
    request.state.user_display = None
    request.state.user_email = None
    request.state.user_initial = "?"
    try:
        session = request.cookies.get("pulsr_session")
        if session:
            import hmac as _hmac, hashlib as _hl, base64 as _b64, json as _js, time as _t
            token, sig = session.split(".")
            expected = _hmac.new(config.INSTANCE_SECRET_KEY.encode(), token.encode(), _hl.sha256).hexdigest()
            if _hmac.compare_digest(sig, expected):
                payload = _js.loads(_b64.b64decode(token).decode())
                if payload.get("exp", 0) > int(_t.time()):
                    uname = payload.get("username")
                    if uname:
                        from instances.models import SessionLocal, User as _U
                        _db = SessionLocal()
                        try:
                            u = _db.query(_U).filter(_U.username == uname).first()
                            if u:
                                request.state.user_display = u.display_name or u.username
                                request.state.user_email = u.email or None
                                request.state.user_initial = (u.display_name or u.username or "?")[0].upper()
                        finally:
                            _db.close()
    except Exception:
        pass
    return await call_next(request)

# Static + templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# ── Public pages (no auth) ──
# All serve the landing SPA which handles its own client-side routing
@app.get("/", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def public_root(request: Request):
    return templates.TemplateResponse(request, "landing.html", context={"request": request, "page": "home"})

@app.get("/faq", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def public_faq(request: Request):
    return templates.TemplateResponse(request, "landing.html", context={"request": request, "page": "faq"})

@app.get("/about", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def public_about(request: Request):
    return templates.TemplateResponse(request, "landing.html", context={"request": request, "page": "about"})

# Health (public + rate limited)
@app.get("/health")
@limiter.limit(READ_LIMIT)
def health(request: Request):
    return {"status": "ok", "dry_run": config.DRY_RUN}

# ── User API Key Endpoints (accept Basic Auth OR X-API-Key) ──

@app.get("/api/v2/users/me/api-key")
@limiter.limit(READ_LIMIT)
def get_user_api_key(request: Request, auth_mode: str = Depends(require_ui_or_api)):
    """Return the current user's PULS-R API key (decrypted for display)."""
    from instances.models import SessionLocal, get_or_seed_operator, decrypt_api_key, encrypt_api_key, hash_api_key
    db = SessionLocal()
    try:
        user = get_or_seed_operator(db)
        # Migration: if api_key is plaintext (old format), re-encrypt it
        if user.api_key and user.api_key.startswith("puls_"):
            plaintext = user.api_key
            user.api_key = encrypt_api_key(plaintext)
            user.api_key_hash = hash_api_key(plaintext)
            db.commit()
            db.refresh(user)
        # Decrypt for display
        try:
            plaintext = decrypt_api_key(user.api_key) if user.api_key else ""
        except Exception:
            plaintext = ""  # Decryption failed — key may be corrupted
        return {"ok": True, "api_key": plaintext, "username": user.username}
    finally:
        db.close()


@app.post("/api/v2/users/me/api-key/regenerate")
@limiter.limit(WRITE_LIMIT)
def regenerate_api_key(request: Request, auth_mode: str = Depends(require_ui_or_api)):
    """Regenerate the current user's PULS-R API key (encrypted storage)."""
    from instances.models import SessionLocal, generate_api_key, get_or_seed_operator, store_user_api_key
    db = SessionLocal()
    try:
        user = get_or_seed_operator(db)
        new_key = generate_api_key()
        store_user_api_key(user, new_key, db)
        return {"ok": True, "api_key": new_key, "username": user.username}
    finally:
        db.close()

# ── Admin System Logs (Basic Auth only, verbose) ──
@app.get("/api/v2/system/logs")
@limiter.limit(READ_LIMIT)
def system_logs(request: Request, limit: int = 200, username: str = Depends(verify_ui_credentials)):
    """Full verbose system logs — admin only (Basic Auth required)."""
    from instances.events import get_logs
    logs = get_logs(limit)
    return {
        "ok": True,
        "count": len(logs),
        "logs": logs,
        "requested_by": username,
    }

@app.get("/api/v2/system/errors")
@limiter.limit(READ_LIMIT)
def system_errors(request: Request, username: str = Depends(verify_ui_credentials)):
    """Error-level logs only — admin only (Basic Auth required)."""
    from instances.events import get_logs
    all_logs = get_logs(200)
    errors = [l for l in all_logs if l.get("level") in ("error", "warn")]
    return {
        "ok": True,
        "count": len(errors),
        "errors": errors,
        "requested_by": username,
    }

# API routers (require X-API-Key + rate limit)
app.include_router(instances.router, prefix="/api/v2", dependencies=[Depends(verify_api_key)])
app.include_router(signals.router, prefix="/api/v2", dependencies=[Depends(verify_api_key)])
app.include_router(positions.router, prefix="/api/v2", dependencies=[Depends(verify_api_key)])
app.include_router(metrics.router, prefix="/api/v2", dependencies=[Depends(verify_api_key)])
app.include_router(withdrawals.router, prefix="/api/v2", dependencies=[Depends(verify_api_key)])
app.include_router(strategies.router, prefix="/api/v2", dependencies=[Depends(verify_api_key)])
app.include_router(killswitch.router, prefix="/api/v2", dependencies=[Depends(verify_api_key)])
app.include_router(backtests.router, prefix="/api/v2", dependencies=[Depends(verify_api_key)])
app.include_router(monitoring.router, prefix="/api/v2", dependencies=[Depends(verify_api_key)])
app.include_router(metadata.router, prefix="/api/v2", dependencies=[Depends(verify_api_key)])
app.include_router(credentials.router, dependencies=[Depends(verify_api_key)])

# Stream + logs at root (UI uses /stream and /logs)
# BUG #1: these were mounted with zero auth — add UI creds dependency
app.include_router(stream.router, dependencies=[Depends(verify_ui_credentials)])

# Logout route — public, no auth required (must be before auth-protected router)
@app.get("/logout", response_class=HTMLResponse)
async def logout_page(request: Request):
    from config import Config
    cfg = Config()
    
    # Try to get account data for the splash screen
    balance = "—"
    engines = "—"
    mode = "DRY RUN"
    try:
        from api.instances import get_summary_data
        data = get_summary_data()
        if data:
            v = data.get("account_value", 0)
            balance = f"${v:,.2f}"
            engines = f"{data.get('active_engines', 0)} / {data.get('total_engines', 0)}"
            mode = "LIVE" if not data.get("dry_run_global", True) else "DRY RUN"
    except Exception:
        pass
    
    return templates.TemplateResponse(
        request,
        "logout.html",
        context={
            "request": request,
            "api_key": cfg.AGENT_API_KEY or "",
            "active": "logout",
            "balance": balance,
            "engines": engines,
            "mode": mode,
        },
    )

# UI routes (require Basic Auth)
app.include_router(ui_routes.router, dependencies=[Depends(verify_ui_credentials)])
# Public UI routes (no auth — login, signup)
app.include_router(ui_routes.public_router)
# Paper Trading routes (separate module, Z1)
app.include_router(paper_routes.router, dependencies=[Depends(verify_ui_credentials)])
# Backtest routes (separate module, Z1)
app.include_router(backtest_routes.router, dependencies=[Depends(verify_ui_credentials)])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=config.PORT, reload=False)
