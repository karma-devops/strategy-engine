"""
Backtest API for strategy-engine.

- POST /api/v2/backtests/run      start a backtest
- GET  /api/v2/backtests          list backtests (optionally ?instance_slug=...)
- GET  /api/v2/backtests/{id}     fetch one backtest result
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.auth import verify_api_key
from api.ratelimit import limiter, READ_LIMIT, WRITE_LIMIT
from backtests.runner import run_backtest
from instances.models import Backtest, get_db, Instance


router = APIRouter()


class RunBacktestRequest(BaseModel):
    instance_slug: str | None = None  # Optional — can run standalone with token+strategy
    days: int = Field(default=30, ge=1, le=365)
    initial_capital: float = Field(default=100.0, gt=0)
    # Required for standalone (no instance) — optional if instance provided
    token: str | None = None
    strategy_id: str | None = None
    timeframe: str | None = None
    mode: str | None = None
    profile: str | None = None
    activation: int | None = None
    offset: int | None = None
    leverage: int | None = None
    tick_mode: int = Field(default=1, ge=1, le=28)  # 1=OHLC, 4=basic, 28=high


@router.post("/backtests/run")
@limiter.limit(WRITE_LIMIT)
def run_backtest_endpoint(
    request: Request,
    payload: RunBacktestRequest,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    # Try to load instance if slug provided
    instance = None
    if payload.instance_slug:
        instance = db.query(Instance).filter(Instance.slug == payload.instance_slug).first()

    # Build params: use payload overrides, fall back to instance config, then defaults
    token = payload.token or (instance.token if instance else None)
    strategy_id = payload.strategy_id or (instance.strategy_id if instance else None)
    timeframe = payload.timeframe or (instance.timeframe if instance else "15m")
    mode = payload.mode or (instance.mode if instance else "Scalp")
    profile = payload.profile or (instance.profile if instance else "aggressive_8_3")
    activation = payload.activation if payload.activation is not None else (instance.activation if instance else 8)
    offset = payload.offset if payload.offset is not None else (instance.offset if instance else 3)
    leverage = payload.leverage if payload.leverage is not None else (instance.leverage if instance else 1)
    slug = payload.instance_slug or "standalone"

    if not token or not strategy_id:
        return {"ok": False, "message": "token and strategy_id are required for standalone backtests"}

    result = run_backtest(
        instance_slug=slug,
        token=token,
        strategy_id=strategy_id,
        timeframe=timeframe,
        mode=mode,
        profile=profile,
        activation=activation,
        offset=offset,
        leverage=leverage,
        days=payload.days,
        initial_capital=payload.initial_capital,
        tick_mode=payload.tick_mode,
    )

    # Z6/Z7: persist to ISOLATED store (data/backtest.db), never shared strategy_engine.db
    from testing.backtest_store import BacktestRun, save_run, init_store, _trade_to_dict
    from datetime import datetime
    record = BacktestRun(
        id=result.id,
        mode="backtest",
        token=result.token,
        strategy_id=result.strategy_id,
        timeframe=result.timeframe,
        profile=result.profile,
        activation=result.activation,
        offset=result.offset,
        leverage=result.leverage,
        start_date=result.start_date,
        end_date=result.end_date,
        status=result.status,
        initial_capital=result.initial_capital,
        final_capital=result.final_capital,
        total_return_pct=result.total_return_pct,
        win_rate=result.win_rate,
        profit_factor=result.profit_factor,
        max_drawdown_pct=result.max_drawdown_pct,
        total_trades=result.total_trades,
        sharpe_ratio=result.sharpe_ratio,
        trades_json=[_trade_to_dict(t) for t in (result.trades or [])],
        equity_curve_json=result.equity_curve,
        error_message=result.error_message,
    )
    init_store()
    save_run(record)

    return {
        "ok": True,
        "message": f"Backtest {result.id} finished with status {result.status}",
        "backtest": result.to_dict(),
    }


@router.get("/backtests")
@limiter.limit(READ_LIMIT)
def list_backtests(
    request: Request,
    instance_slug: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    query = db.query(Backtest)
    if instance_slug:
        query = query.filter(Backtest.instance_slug == instance_slug)
    query = query.order_by(Backtest.created_at.desc()).limit(limit)
    rows = query.all()
    return {
        "ok": True,
        "backtests": [_row_to_dict(b) for b in rows],
    }


@router.get("/backtests/{backtest_id}")
@limiter.limit(READ_LIMIT)
def get_backtest(
    request: Request,
    backtest_id: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    row = db.query(Backtest).filter(Backtest.id == backtest_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return {"ok": True, "backtest": _row_to_dict(row)}


def _row_to_dict(row: Backtest) -> dict:
    return {
        "id": row.id,
        "instance_slug": row.instance_slug,
        "token": row.token,
        "strategy_id": row.strategy_id,
        "timeframe": row.timeframe,
        "mode": row.mode,
        "profile": row.profile,
        "activation": row.activation,
        "offset": row.offset,
        "leverage": row.leverage,
        "start_date": row.start_date.isoformat() if row.start_date else None,
        "end_date": row.end_date.isoformat() if row.end_date else None,
        "status": row.status,
        "initial_capital": row.initial_capital,
        "final_capital": row.final_capital,
        "total_return_pct": row.total_return_pct,
        "win_rate": row.win_rate,
        "profit_factor": row.profit_factor,
        "max_drawdown_pct": row.max_drawdown_pct,
        "total_trades": row.total_trades,
        "sharpe_ratio": row.sharpe_ratio,
        "trades": row.trades_json or [],
        "equity_curve": row.equity_curve_json or [],
        "error_message": row.error_message,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
    }


class RunReplayRequest(BaseModel):
    instance_slug: str = Field(..., min_length=1)
    days: int = Field(default=30, ge=1, le=365)
    initial_capital: float = Field(default=100.0, gt=0)
    tick_mode: int = Field(default=1, ge=1, le=28)
    speed: float = Field(default=1.0, ge=0.1, le=100.0)


@router.post("/backtests/replay")
@limiter.limit(WRITE_LIMIT)
def replay_backtest(
    request: Request,
    payload: RunReplayRequest,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    """Bar-replay: replay historical candles through the backtest runner with tick simulation.
    
    More accurate than static backtest because it evaluates trailing stops
    at intra-bar resolution (configurable tick_mode).
    """
    instance = db.query(Instance).filter(Instance.slug == payload.instance_slug).first()
    if not instance:
        return {"ok": False, "message": f"Instance not found: {payload.instance_slug}"}
    
    result = run_backtest(
        instance_slug=instance.slug,
        token=instance.token,
        strategy_id=instance.strategy_id,
        timeframe=instance.timeframe,
        mode=instance.mode,
        profile=instance.profile,
        activation=instance.activation,
        offset=instance.offset,
        leverage=instance.leverage,
        days=payload.days,
        initial_capital=payload.initial_capital,
        tick_mode=payload.tick_mode,
    )
    
    # Z6/Z7: persist to ISOLATED store (data/backtest.db), never shared strategy_engine.db
    from testing.backtest_store import BacktestRun, save_run, init_store, _trade_to_dict
    from datetime import datetime
    record = BacktestRun(
        id=result.id,
        mode="backtest",
        token=result.token,
        strategy_id=result.strategy_id,
        timeframe=result.timeframe,
        profile=result.profile,
        activation=result.activation,
        offset=result.offset,
        leverage=result.leverage,
        start_date=result.start_date,
        end_date=result.end_date,
        status=result.status,
        initial_capital=result.initial_capital,
        final_capital=result.final_capital,
        total_return_pct=result.total_return_pct,
        win_rate=result.win_rate,
        profit_factor=result.profit_factor,
        max_drawdown_pct=result.max_drawdown_pct,
        total_trades=result.total_trades,
        sharpe_ratio=result.sharpe_ratio,
        trades_json=[_trade_to_dict(t) for t in (result.trades or [])],
        equity_curve_json=result.equity_curve,
        error_message=result.error_message,
    )
    init_store()
    save_run(record)
    
    return {
        "ok": True,
        "message": f"Bar-replay {result.id} finished with status {result.status} (tick_mode={payload.tick_mode})",
        "backtest": result.to_dict(),
    }
