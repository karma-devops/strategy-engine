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
from withdrawal.scheduler import scheduler as withdrawal_scheduler
from api import instances, signals, positions, metrics, withdrawals, stream, strategies, killswitch, backtests, monitoring
from app import routes as ui_routes
from api.auth import verify_api_key, verify_ui_credentials
from api.ratelimit import limiter, READ_LIMIT, WRITE_LIMIT, AUTH_LIMIT, add_rate_limiting, api_key_or_ip


@asynccontextmanager
async def lifespan(app: FastAPI):
    manager.start()
    seed_default_fleet()
    withdrawal_scheduler.start()
    print("[APP] Started instance manager + withdrawal scheduler")
    yield
    withdrawal_scheduler.stop()
    manager.stop()
    print("[APP] Shut down instance manager + withdrawal scheduler")


app = FastAPI(title="Strategy Engine", lifespan=lifespan)
app.state.limiter = limiter
add_rate_limiting(app)

# Static + templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Health (public + rate limited)
@app.get("/health")
@limiter.limit(READ_LIMIT)
def health(request: Request):
    return {"status": "ok", "dry_run": config.DRY_RUN}

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

# Stream + logs at root (UI uses /stream and /logs)
app.include_router(stream.router)

# UI routes (require Basic Auth)
app.include_router(ui_routes.router, dependencies=[Depends(verify_ui_credentials)])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=config.PORT, reload=False)
