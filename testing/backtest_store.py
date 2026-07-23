"""
Backtest Isolated Store (Z6)

Authority: Z6 (route split / 3-way strict separation)

Separate SQLite store for historical backtests AND paper forward-tests.
- Lives in `data/backtest.db` — a DIFFERENT file from `strategy_engine.db`.
- Models here have NO foreign keys back to live/paper tables.
- Zero live/paper data access: backtest runner reads market candles (public HL
  REST) + writes results here only. Anti-corruption layer = this module.

The unified runner (Z7: testing/runner.py --mode backtest|paper) is the only
writer. Live runners (instances/runner.py) NEVER touch this store.
"""

import os
from datetime import datetime, timezone

from sqlalchemy import (
    create_engine, Column, String, Float, Integer, Boolean,
    DateTime, Text, JSON,
)
from sqlalchemy.orm import declarative_base, sessionmaker


#=== Isolated engine (separate DB file) ===#
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH = os.path.join(_BASE_DIR, "data", "backtest.db")
_engine = create_engine(f"sqlite:///{_DB_PATH}", future=True)
Base = declarative_base()
Session = sessionmaker(bind=_engine)


def _now_utc():
    return datetime.now(timezone.utc)


class BacktestRun(Base):
    """One backtest or paper-forward-test run. No FK to live tables."""
    __tablename__ = "backtest_runs"

    id = Column(String(36), primary_key=True)
    # mode: "backtest" (historical sim) | "paper" (forward live-test, dry_run)
    mode = Column(String(16), nullable=False, index=True, default="backtest")
    token = Column(String(64), nullable=False)
    strategy_id = Column(String(64), nullable=False)
    timeframe = Column(String(16), nullable=False)
    profile = Column(String(64), nullable=False)
    activation = Column(Integer, default=8)
    offset = Column(Integer, default=3)
    leverage = Column(Integer, default=1)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    status = Column(String(32), default="pending")  # pending|running|done|error
    initial_capital = Column(Float, default=1000.0)
    final_capital = Column(Float, nullable=True)
    total_return_pct = Column(Float, default=0.0)
    win_rate = Column(Float, default=0.0)
    profit_factor = Column(Float, default=0.0)
    max_drawdown_pct = Column(Float, default=0.0)
    total_trades = Column(Integer, default=0)
    sharpe_ratio = Column(Float, default=0.0)
    trades_json = Column(JSON, default=list)
    equity_curve_json = Column(JSON, default=list)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_now_utc)
    completed_at = Column(DateTime, nullable=True)


class BacktestTrade(Base):
    """Individual fill inside a run. FK only to BacktestRun (same store)."""
    __tablename__ = "backtest_trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), nullable=False, index=True)
    token = Column(String(64), nullable=False)
    side = Column(String(8), nullable=False)      # LONG|SHORT
    size = Column(Float, default=0.0)
    entry_price = Column(Float, default=0.0)
    exit_price = Column(Float, default=0.0)
    pnl_usd = Column(Float, default=0.0)
    pnl_pct = Column(Float, default=0.0)
    opened_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)


def init_store():
    """Create tables if missing. Safe to call on startup."""
    Base.metadata.create_all(_engine)


def wipe_db():
    """Ephemeral store — drop all rows between runs if caller wants clean slate.
    Does NOT drop tables, just truncates data."""
    with Session() as s:
        s.query(BacktestTrade).delete()
        s.query(BacktestRun).delete()
        s.commit()


def save_run(run: BacktestRun):
    with Session() as s:
        s.add(run)
        s.commit()
        s.refresh(run)
        return run.id


def update_run(run_id: str, **fields):
    with Session() as s:
        r = s.query(BacktestRun).filter(BacktestRun.id == run_id).first()
        if not r:
            return None
        for k, v in fields.items():
            if hasattr(r, k):
                setattr(r, k, v)
        s.commit()
        return r.id


def add_trade(run_id: str, trade: BacktestTrade):
    trade.run_id = run_id
    with Session() as s:
        s.add(trade)
        s.commit()


def get_run(run_id: str) -> dict | None:
    with Session() as s:
        r = s.query(BacktestRun).filter(BacktestRun.id == run_id).first()
        return _run_to_dict(r) if r else None


def list_runs(mode: str = None, limit: int = 50) -> list:
    with Session() as s:
        q = s.query(BacktestRun)
        if mode:
            q = q.filter(BacktestRun.mode == mode)
        rows = q.order_by(BacktestRun.created_at.desc()).limit(limit).all()
        return [_run_to_dict(r) for r in rows]


def _run_to_dict(r: BacktestRun) -> dict:
    return {
        "id": r.id,
        "mode": r.mode,
        "token": r.token,
        "strategy_id": r.strategy_id,
        "timeframe": r.timeframe,
        "profile": r.profile,
        "activation": r.activation,
        "offset": r.offset,
        "leverage": r.leverage,
        "status": r.status,
        "initial_capital": r.initial_capital,
        "final_capital": r.final_capital,
        "total_return_pct": r.total_return_pct,
        "win_rate": r.win_rate,
        "profit_factor": r.profit_factor,
        "max_drawdown_pct": r.max_drawdown_pct,
        "total_trades": r.total_trades,
        "sharpe_ratio": r.sharpe_ratio,
        "trades_json": r.trades_json or [],
        "equity_curve_json": r.equity_curve_json or [],
        "created_at": r.created_at.isoformat() if r.created_at else "",
        "completed_at": r.completed_at.isoformat() if r.completed_at else "",
    }


def _trade_to_dict(t) -> dict:
    """Serialize a backtest trade (BacktestTrade dataclass or object) to JSON-safe dict.

    Matches the trade shape emitted by backtests.runner.BacktestResult.to_dict so
    the persisted trades_json is consistent with the live result payload.
    Handles both dataclass instances and plain objects/attrs defensively.
    """
    def _iso(v):
        return v.isoformat() if hasattr(v, "isoformat") else (v if v is not None else None)

    def _get(attr, default=None):
        return getattr(t, attr, default) if hasattr(t, attr) else default

    return {
        "entry_bar": _get("entry_bar"),
        "entry_time": _iso(_get("entry_time")),
        "entry_price": _get("entry_price", 0.0),
        "side": _get("side", ""),
        "exit_bar": _get("exit_bar"),
        "exit_time": _iso(_get("exit_time")),
        "exit_price": _get("exit_price"),
        "pnl_pct": _get("pnl_pct", 0.0),
        "pnl_usd": _get("pnl_usd", 0.0),
        "bars_held": _get("bars_held", 0),
        "qty": _get("qty", 0.0),
        "position_size": _get("position_size", 0.0),
        "stop_loss_price": _get("stop_loss_price"),
        "trail_activation": _get("trail_activation", 0.0),
        "trail_offset": _get("trail_offset", 0.0),
        "best_price": _get("best_price", 0.0),
        "trail_active": _get("trail_active", False),
        "trail_stop_price": _get("trail_stop_price"),
    }


__all__ = [
    "Base", "Session", "init_store", "wipe_db",
    "BacktestRun", "BacktestTrade",
    "save_run", "update_run", "add_trade", "get_run", "list_runs",
    "_run_to_dict", "_trade_to_dict",
]
