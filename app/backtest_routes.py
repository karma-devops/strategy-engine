"""
Backtest Routes

Authority: Z1 (route split)

This module contains PURE backtest routes:
- `/app/backtests` → redirect to `/app/testing/historical`
- `/app/testing` → Testing section landing
- `/app/testing/historical` → Historical backtests page

Separated from routes.py to enforce bounded context: BACKTEST router cannot
accidentally query LIVE data. Backtesting uses isolated store strategy.
"""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from slowapi.errors import RateLimitExceeded

from api.ratelimit import limiter, READ_LIMIT
from config import config
from api.auth import verify_ui_credentials
from instances.models import engine, Backtest, get_or_seed_operator
from sqlalchemy.orm import sessionmaker

Session = sessionmaker(bind=engine)

router = APIRouter(prefix="/app")
templates = Jinja2Templates(directory="app/templates")


@router.get("/backtests", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def backtests_redirect(request: Request, username: str = Depends(verify_ui_credentials)):
    """Redirect /app/backtests → /app/testing/historical."""
    return RedirectResponse(url="/app/testing/historical", status_code=301)


@router.get("/testing", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def testing_index(request: Request, username: str = Depends(verify_ui_credentials)):
    """Testing section landing — Historical + Paper Trading."""
    return templates.TemplateResponse(
        request, "testing_index.html",
        context={
            "request": request,
            "api_key": config.AGENT_API_KEY or "",
            "active": "testing",
        },
    )


@router.get("/testing/historical", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def testing_historical(request: Request, username: str = Depends(verify_ui_credentials)):
    """Historical backtests — form + results table + equity curve SVG."""
    db = Session()
    try:
        backtests = db.query(Backtest).filter(Backtest.kind == "backtest").order_by(Backtest.created_at.desc()).limit(50).all()
        bt_data = [{
            "id": b.id, "instance_slug": b.instance_slug, "token": b.token,
            "strategy_id": b.strategy_id, "timeframe": b.timeframe, "profile": b.profile,
            "activation": b.activation, "offset": b.offset, "leverage": b.leverage,
            "status": b.status, "total_return_pct": b.total_return_pct or 0.0,
            "win_rate": b.win_rate or 0.0, "profit_factor": b.profit_factor or 0.0,
            "max_drawdown_pct": b.max_drawdown_pct or 0.0, "total_trades": b.total_trades or 0,
            "sharpe_ratio": b.sharpe_ratio or 0.0,
            "equity_curve": b.equity_curve_json or [],
            "trades_json": b.trades_json or [],
            "created_at": b.created_at.isoformat() if b.created_at else "",
        } for b in backtests]
        # Equity curve for the most recent completed backtest (for the chart card)
        latest_equity = next((b["equity_curve"] for b in bt_data if b["equity_curve"]), [])
        return templates.TemplateResponse(
            request, "testing_historical.html",
            context={
                "request": request, "api_key": config.AGENT_API_KEY or "",
                "backtests": bt_data, "latest_equity": latest_equity, "active": "testing",
                "chat_context": "backtester",
            },
        )
    except RateLimitExceeded:
        return limiter.exceeded_handler(request)
    finally:
        db.close()


#=== Export ===#
__all__ = ["router"]
