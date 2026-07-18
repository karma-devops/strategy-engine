"""
Paper Trading Routes

Authority: Z1 (route split)

This module contains PURE paper trading routes:
- `/app/paper` → redirect to `/app/testing/paper`
- `/app/testing/paper` → Paper Trading page (forward-testing, dry_run=True)

Separated from routes.py to enforce bounded context: PAPER mode cannot
accidentally query LIVE data.
"""

from fastapi import APIRouter, Request, Depends, Response
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from api.ratelimit import limiter, READ_LIMIT
from config import config
from api.auth import verify_ui_credentials
from instances.models import engine, Instance, AccountSnapshot, Trade, User, get_or_seed_operator
from app._common import _instances_by_mode
from sqlalchemy.orm import sessionmaker

Session = sessionmaker(bind=engine)

router = APIRouter(prefix="/app")
templates = Jinja2Templates(directory="app/templates")


@router.get("/paper", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def paper_redirect(request: Request, username: str = Depends(verify_ui_credentials)):
    """Redirect /app/paper → /app/testing/paper."""
    return RedirectResponse(url="/app/testing/paper", status_code=301)


@router.get("/testing/paper", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def testing_paper(request: Request, username: str = Depends(verify_ui_credentials)):
    """Paper Trading — forward-test instances (dry_run=True) with pure-SVG equity."""
    db = Session()
    try:
        user = get_or_seed_operator(db)
        instances = db.query(Instance).filter(
            Instance.user_id == user.id, Instance.dry_run == True
        ).all()
        inst_data, equity_series = [], []
        for i in instances:
            # P14d: paper-only snapshots (user_id may be NULL in older data)
            snaps = db.query(AccountSnapshot).filter(
                AccountSnapshot.instance_id == i.slug,
                AccountSnapshot.dry_run == True,
            ).filter(
                (AccountSnapshot.user_id == user.id) | (AccountSnapshot.user_id == None)
            ).order_by(AccountSnapshot.timestamp.asc()).all()
            series = [{"time": int(s.timestamp.timestamp()), "value": round(s.account_value, 2)} for s in snaps]
            equity_series.extend(series)
            inst_data.append({
                "slug": i.slug, "name": i.name, "token": i.token, "status": i.status,
                "unrealized_pnl": i.unrealized_pnl or 0.0, "start_balance": i.start_balance or 0.0,
                "equity": series,  # B.9: per-instance equity for sparkline
            })
        equity_series.sort(key=lambda x: x["time"])
        # P14d: paper trades for this user's dry_run instances
        paper_trades = db.query(Trade).filter(Trade.user_id == user.id, Trade.dry_run == True).order_by(Trade.timestamp.desc()).limit(50).all()
        paper_trade_data = [{
            "time": t.timestamp.strftime("%Y-%m-%d %H:%M") if t.timestamp else "",
            "time_unix": int(t.timestamp.timestamp()) if t.timestamp else 0,
            "instance": t.instance_id, "side": t.side,
            "size": round(t.size, 4), "pnl_usd": round(t.pnl_usd, 2),
        } for t in paper_trades]
        return templates.TemplateResponse(
            request, "testing_paper.html",
            context={
                "request": request, "api_key": config.AGENT_API_KEY or "",
                "instances": inst_data, "equity_series": equity_series,
                "paper_trades": paper_trade_data,
                "active_engines": sum(1 for i in inst_data if i["status"] == "running"),
                "total_engines": len(inst_data),
                "active": "testing",
            },
        )
    except RateLimitExceeded:
        limiter.exceeded_handler(request, _rate_limit_exceeded_handler)
    finally:
        db.close()


#=== Export ===#
__all__ = ["router"]
