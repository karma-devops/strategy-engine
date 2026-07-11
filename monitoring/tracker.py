"""
Performance tracker for strategy-engine.
Computes per-engine metrics over a rolling window and stores MonitoringScore rows.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from instances.models import Trade, PositionSnapshot, MonitoringScore, AccountSnapshot, Instance


def _now_utc():
    return datetime.now(timezone.utc)


def compute_instance_metrics(
    db: Session,
    slug: str,
    days: int = 30,
) -> dict[str, Any]:
    """Compute metrics for one instance over the last N days."""
    since = _now_utc() - timedelta(days=days)

    trades = (
        db.query(Trade)
        .filter(Trade.instance_id == slug, Trade.timestamp >= since)
        .order_by(Trade.timestamp)
        .all()
    )

    wins = [t for t in trades if t.pnl_usd > 0]
    losses = [t for t in trades if t.pnl_usd <= 0]

    total_trades = len(trades)
    win_rate = (len(wins) / total_trades * 100.0) if total_trades else 0.0
    gross_profit = sum(t.pnl_usd for t in wins)
    gross_loss = abs(sum(t.pnl_usd for t in losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)

    # Return from account snapshots
    snapshots = (
        db.query(AccountSnapshot)
        .filter(AccountSnapshot.instance_id == slug, AccountSnapshot.timestamp >= since)
        .order_by(AccountSnapshot.timestamp)
        .all()
    )
    return_pct = 0.0
    if len(snapshots) >= 2:
        start = snapshots[0].account_value
        end = snapshots[-1].account_value
        if start > 0:
            return_pct = ((end / start) - 1.0) * 100.0

    # Max drawdown from snapshots
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

    # Consistency: std of daily returns
    consistency = 0.0
    if len(snapshots) > 2:
        rets = []
        for i in range(1, len(snapshots)):
            prev = snapshots[i - 1].account_value
            curr = snapshots[i].account_value
            if prev > 0:
                rets.append((curr / prev) - 1.0)
        if rets:
            mean_ret = sum(rets) / len(rets)
            variance = sum((r - mean_ret) ** 2 for r in rets) / len(rets)
            std = math.sqrt(variance)
            consistency = max(0.0, 1.0 - std * 10)  # higher = more consistent

    return {
        "return_pct": return_pct,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "max_drawdown_pct": max_dd * 100.0,
        "total_trades": total_trades,
        "consistency": consistency,
    }


def score_instance(metrics: dict[str, Any]) -> tuple[float, str]:
    """
    Score 0-100 and status flag.
    Weights: Return 30%, win rate 20%, profit factor 25%, drawdown 15%, consistency 10%.
    """
    ret = metrics.get("return_pct", 0.0)
    wr = metrics.get("win_rate", 0.0)
    pf = metrics.get("profit_factor", 0.0)
    dd = metrics.get("max_drawdown_pct", 0.0)
    consistency = metrics.get("consistency", 0.0)

    ret_score = min(ret / 50.0, 1.0) * 30.0
    wr_score = min(wr / 70.0, 1.0) * 20.0
    pf_score = min(pf / 3.0, 1.0) * 25.0
    dd_score = max(0.0, 1.0 - dd / 20.0) * 15.0
    cons_score = consistency * 10.0

    score = ret_score + wr_score + pf_score + dd_score + cons_score
    score = max(0.0, min(100.0, score))

    if score >= 75:
        status = "OPTIMAL"
    elif score >= 60:
        status = "HOLD"
    elif score >= 45:
        status = "MONITOR"
    else:
        status = "UNDERPERFORM"

    return score, status


def refresh_all_scores(db: Session, days: int = 30):
    """Compute and store scores for every instance."""
    instances = db.query(Instance).all()
    results = []
    for inst in instances:
        metrics = compute_instance_metrics(db, inst.slug, days=days)
        score, status = score_instance(metrics)
        row = MonitoringScore(
            instance_slug=inst.slug,
            period_days=days,
            return_pct=metrics["return_pct"],
            win_rate=metrics["win_rate"],
            profit_factor=metrics["profit_factor"],
            max_drawdown_pct=metrics["max_drawdown_pct"],
            total_trades=metrics["total_trades"],
            consistency=metrics["consistency"],
            score=score,
            status=status,
        )
        db.add(row)
        results.append({
            "slug": inst.slug,
            "score": score,
            "status": status,
            **metrics,
        })
    db.commit()
    return results


def get_latest_scores(db: Session) -> list[dict[str, Any]]:
    """Return the most recent score row per instance."""
    from sqlalchemy import func
    subq = (
        db.query(
            MonitoringScore.instance_slug,
            func.max(MonitoringScore.computed_at).label("max_at"),
        )
        .group_by(MonitoringScore.instance_slug)
        .subquery()
    )
    rows = (
        db.query(MonitoringScore)
        .join(
            subq,
            (MonitoringScore.instance_slug == subq.c.instance_slug)
            & (MonitoringScore.computed_at == subq.c.max_at),
        )
        .all()
    )
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(row: MonitoringScore) -> dict[str, Any]:
    return {
        "instance_slug": row.instance_slug,
        "period_days": row.period_days,
        "return_pct": row.return_pct,
        "win_rate": row.win_rate,
        "profit_factor": row.profit_factor,
        "max_drawdown_pct": row.max_drawdown_pct,
        "total_trades": row.total_trades,
        "consistency": row.consistency,
        "score": row.score,
        "status": row.status,
        "computed_at": row.computed_at.isoformat() if row.computed_at else None,
    }
