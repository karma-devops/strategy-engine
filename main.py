"""
FastAPI entrypoint for strategy-engine.
Serves UI at / and API at /api/v2.
"""

from contextlib import asynccontextmanager

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
from api.auth import verify_api_key, verify_ui_credentials, require_ui_or_api
from api.ratelimit import limiter, READ_LIMIT, WRITE_LIMIT, AUTH_LIMIT, add_rate_limiting, api_key_or_ip


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
    version="0.095",
    contact={"name": "Operator", "url": "https://karmaworks.asia"},
    license_info={"name": "Proprietary"},
    lifespan=lifespan,
)
app.state.limiter = limiter
add_rate_limiting(app)

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

@app.get("/login", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def public_login(request: Request):
    return templates.TemplateResponse(request, "landing.html", context={"request": request, "page": "login"})

@app.get("/signup", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def public_signup(request: Request):
    return templates.TemplateResponse(request, "landing.html", context={"request": request, "page": "signup"})

# Health (public + rate limited)
@app.get("/health")
@limiter.limit(READ_LIMIT)
def health(request: Request):
    return {"status": "ok", "dry_run": config.DRY_RUN}

# ── User API Key Endpoints (accept Basic Auth OR X-API-Key) ──

@app.get("/api/v2/users/me/api-key")
@limiter.limit(READ_LIMIT)
def get_user_api_key(request: Request, auth_mode: str = Depends(require_ui_or_api)):
    """Return the current user's PULS-R API key. Auto-generates one if missing."""
    from instances.models import SessionLocal, get_or_seed_operator
    db = SessionLocal()
    try:
        user = get_or_seed_operator(db)
        return {"ok": True, "api_key": user.api_key, "username": user.username}
    finally:
        db.close()


@app.post("/api/v2/users/me/api-key/regenerate")
@limiter.limit(WRITE_LIMIT)
def regenerate_api_key(request: Request, auth_mode: str = Depends(require_ui_or_api)):
    """Regenerate the current user's PULS-R API key."""
    from instances.models import SessionLocal, generate_api_key, get_or_seed_operator
    db = SessionLocal()
    try:
        user = get_or_seed_operator(db)
        user.api_key = generate_api_key()
        db.commit()
        db.refresh(user)
        return {"ok": True, "api_key": user.api_key, "username": user.username}
    finally:
        db.close()

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
app.include_router(stream.router)

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=config.PORT, reload=False)
