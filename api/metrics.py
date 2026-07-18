"""
API routes for metrics.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from api.ratelimit import limiter, READ_LIMIT
from instances.models import get_db, Signal, Trade, AccountSnapshot, Instance
from core.exchange import hl_client

router = APIRouter()


@router.get("/metrics")
@limiter.limit(READ_LIMIT)
def get_metrics(request: Request, dry_run: bool = None, instance_id: str = None, db: Session = Depends(get_db)):
    q_signals = db.query(Signal)
    q_trades = db.query(Trade)
    if dry_run is not None:
        q_signals = q_signals.filter(Signal.dry_run == dry_run)
        q_trades = q_trades.filter(Trade.dry_run == dry_run)
    if instance_id is not None:
        q_signals = q_signals.filter(Signal.instance_id == instance_id)
        q_trades = q_trades.filter(Trade.instance_id == instance_id)
    total_signals = q_signals.count()
    buy_signals = q_signals.filter(Signal.direction == "BUY").count()
    sell_signals = q_signals.filter(Signal.direction == "SELL").count()

    trades = q_trades.all()
    realized_pnl = sum(t.pnl_usd for t in trades)
    winning_trades = [t for t in trades if t.pnl_usd > 0]
    losing_trades = [t for t in trades if t.pnl_usd <= 0]
    win_rate = len(winning_trades) / len(trades) * 100 if trades else 0

    last_account = (
        db.query(AccountSnapshot)
        .order_by(AccountSnapshot.timestamp.desc())
        .first()
    )

    account_value = hl_client.get_account_value()
    return {
        "ok": True,
        "total_signals": total_signals,
        "buy_signals": buy_signals,
        "sell_signals": sell_signals,
        "total_trades": len(trades),
        "realized_pnl_usd": realized_pnl,
        "win_rate": round(win_rate, 2),
        "avg_win": round(sum(t.pnl_usd for t in winning_trades) / len(winning_trades), 2) if winning_trades else 0,
        "avg_loss": round(sum(t.pnl_usd for t in losing_trades) / len(losing_trades), 2) if losing_trades else 0,
        "account_value": account_value,
        "last_account_snapshot": {
            "account_value": last_account.account_value,
            "timestamp": last_account.timestamp.isoformat(),
        } if last_account else None,
    }


@router.get("/metrics/account")
@limiter.limit(READ_LIMIT)
def get_account_snapshots(request: Request, dry_run: bool = None, db: Session = Depends(get_db)):
    """Return account snapshots for the Pulse Graph and hero stats. Filter by dry_run if provided."""
    q = db.query(AccountSnapshot)
    if dry_run is not None:
        q = q.filter(AccountSnapshot.dry_run == dry_run)
    # BUG #20: order DESC, take most recent 500, then reverse to ascending
    # for the graph. Old code used asc().limit(500) which froze on stale data
    # once snapshot count exceeded 500.
    snapshots = q.order_by(AccountSnapshot.timestamp.desc()).limit(500).all()
    snapshots.reverse()  # back to ascending for chart rendering
    active = db.query(Instance).filter(Instance.status == "running").count()
    total_instances = db.query(Instance).count()
    latest = snapshots[-1] if snapshots else None

    # Calculate drawdown from latest snapshot series
    peak = 0.0
    max_dd = 0.0
    for s in snapshots:
        v = s.account_value
        if v > peak:
            peak = v
        if peak > 0:
            dd = (peak - v) / peak
            if dd > max_dd:
                max_dd = dd

    open_pnl = sum(
        (i.unrealized_pnl or 0.0)
        for i in db.query(Instance).all()
    )

    return {
        "ok": True,
        "snapshots": [
            {
                "timestamp": s.timestamp.isoformat(),
                "account_value": s.account_value,
            }
            for s in snapshots
        ],
        "account_value": latest.account_value if latest else 0.0,
        "drawdown_pct": round(max_dd * 100.0, 2),
        "active_engines": active,
        "total_engines": total_instances,
        "open_pnl": round(open_pnl, 2),
    }
