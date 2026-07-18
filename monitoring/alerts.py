"""
Internal alert generator for strategy-engine.
Creates Alert rows for operator review in the UI. No external notifications.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy.orm import Session

from instances.models import Alert, MonitoringScore, Trade, Instance, PositionSnapshot


def _now_utc():
    return datetime.now(timezone.utc)


def create_alert(
    db: Session,
    instance_slug: str | None,
    level: str,
    category: str,
    message: str,
    metric_value: float | None = None,
    threshold: float | None = None,
    internal_note: str | None = None,
) -> Alert:
    """Create and persist a single alert.

    BUG #9: dedup — if an active (non-dismissed) alert of the same
    (instance_slug, category) already exists, return it instead of
    creating a duplicate. This prevents alert spam on every scan.
    """
    existing = (
        db.query(Alert)
        .filter(Alert.instance_slug == instance_slug)
        .filter(Alert.category == category)
        .filter(Alert.dismissed.is_(False))
        .first()
    )
    if existing:
        return existing

    alert = Alert(
        instance_slug=instance_slug,
        level=level,
        category=category,
        message=message,
        metric_value=metric_value,
        threshold=threshold,
        internal_note=internal_note,
    )
    db.add(alert)
    db.commit()
    return alert


def evaluate_and_create_alerts(db: Session) -> list[dict[str, Any]]:
    """Scan scores/trades/positions and create new alerts."""
    since = _now_utc() - timedelta(days=30)
    alerts = []

    # 1. Portfolio-level drawdown > 15%
    # BUG #11: removed dead portfolio_value computation (was unused)
    # We don't have true portfolio baseline yet; use position snapshots sum
    # BUG #10: order_by timestamp so values[-1] is the most recent snapshot
    snaps = (
        db.query(PositionSnapshot)
        .filter(PositionSnapshot.timestamp >= since)
        .order_by(PositionSnapshot.timestamp.asc())
        .all()
    )
    if snaps:
        values = [s.unrealized_pnl_usd for s in snaps]
        peak = max(values) if values else 0
        if peak > 0:
            current = values[-1]
            dd = (peak - current) / peak * 100.0
            if dd > 15:
                a = create_alert(
                    db, None, "CRITICAL", "drawdown",
                    f"Portfolio drawdown {dd:.1f}% exceeds 15% threshold",
                    metric_value=dd, threshold=15.0,
                    internal_note="Check all running engines; consider global kill switch.",
                )
                alerts.append(_alert_to_dict(a))

    # 2. Per-engine alerts
    scores = db.query(MonitoringScore).order_by(MonitoringScore.computed_at.desc()).all()
    seen_slugs = set()
    for score in scores:
        if score.instance_slug in seen_slugs:
            continue
        seen_slugs.add(score.instance_slug)

        if score.max_drawdown_pct > 20:
            a = create_alert(
                db, score.instance_slug, "WARNING", "drawdown",
                f"Engine {score.instance_slug} 30d drawdown {score.max_drawdown_pct:.1f}% > 20%",
                metric_value=score.max_drawdown_pct, threshold=20.0,
                internal_note="Review position sizing and recent losses.",
            )
            alerts.append(_alert_to_dict(a))

        if score.profit_factor < 1.5 and score.total_trades >= 5:
            a = create_alert(
                db, score.instance_slug, "WARNING", "profitfactor",
                f"Engine {score.instance_slug} 30d profit factor {score.profit_factor:.2f} < 1.5",
                metric_value=score.profit_factor, threshold=1.5,
                internal_note="Strategy may be degrading; consider reducing allocation.",
            )
            alerts.append(_alert_to_dict(a))

        if score.total_trades == 0:
            a = create_alert(
                db, score.instance_slug, "INFO", "notrades",
                f"Engine {score.instance_slug} has no trades in the last 30 days",
                internal_note="Verify engine is running and market conditions are active.",
            )
            alerts.append(_alert_to_dict(a))

    # 3. Consecutive losses
    instances = db.query(Instance).all()
    for inst in instances:
        trades = (
            db.query(Trade)
            .filter(Trade.instance_id == inst.slug, Trade.timestamp >= since)
            .order_by(Trade.timestamp.desc())
            .limit(10)
            .all()
        )
        consecutive_losses = 0
        for t in trades:
            if t.pnl_usd <= 0:
                consecutive_losses += 1
            else:
                break
        if consecutive_losses >= 5:
            a = create_alert(
                db, inst.slug, "CRITICAL", "losses",
                f"Engine {inst.slug} has {consecutive_losses} consecutive losing trades",
                metric_value=float(consecutive_losses), threshold=5.0,
                internal_note="Consider kill switch or manual review before next entry.",
            )
            alerts.append(_alert_to_dict(a))

    return alerts


def list_active_alerts(db: Session, limit: int = 100) -> list[dict[str, Any]]:
    rows = (
        db.query(Alert)
        .filter(Alert.dismissed.is_(False))
        .order_by(Alert.created_at.desc())
        .limit(limit)
        .all()
    )
    return [_alert_to_dict(r) for r in rows]


def dismiss_alert(db: Session, alert_id: str) -> dict[str, Any] | None:
    row = db.query(Alert).filter(Alert.id == alert_id).first()
    if not row:
        return None
    row.dismissed = True
    row.dismissed_at = _now_utc()
    db.commit()
    return _alert_to_dict(row)


def _alert_to_dict(a: Alert) -> dict[str, Any]:
    return {
        "id": a.id,
        "instance_slug": a.instance_slug,
        "level": a.level,
        "category": a.category,
        "message": a.message,
        "metric_value": a.metric_value,
        "threshold": a.threshold,
        "dismissed": a.dismissed,
        "internal_note": a.internal_note,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "dismissed_at": a.dismissed_at.isoformat() if a.dismissed_at else None,
    }
