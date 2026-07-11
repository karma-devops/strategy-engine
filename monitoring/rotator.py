"""
Rotation recommendations for strategy-engine.
Generates INCREASE / REDUCE / HOLD suggestions based on latest MonitoringScore.
All recommendations require manual operator approval.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from instances.models import RotationRecommendation, Instance
from monitoring.tracker import get_latest_scores


def _now_utc():
    return datetime.now(timezone.utc)


def generate_recommendations(db: Session) -> list[dict[str, Any]]:
    """Generate rotation recommendations for all instances."""
    scores = get_latest_scores(db)
    instances = {i.slug: i for i in db.query(Instance).all()}
    recommendations = []

    for s in scores:
        slug = s["instance_slug"]
        inst = instances.get(slug)
        if not inst:
            continue

        # Default allocation proxy: max_position_pct scaled to fleet total.
        current_alloc = (inst.max_position_pct or 0.0) * 100.0
        action = "HOLD"
        reason = "No strong rotation signal."
        suggested = current_alloc

        score = s["score"]
        dd = s["max_drawdown_pct"]
        pf = s["profit_factor"]
        trades = s["total_trades"]

        if score < 45 or dd > 20 or pf < 1.0:
            action = "REDUCE"
            suggested = max(5.0, current_alloc * 0.5)
            reason = f"Score {score:.1f}, drawdown {dd:.1f}%, PF {pf:.2f} — reduce exposure."
        elif score >= 75 and pf >= 2.0 and trades >= 5 and current_alloc < 30:
            action = "INCREASE"
            suggested = min(30.0, current_alloc * 1.5)
            reason = f"Score {score:.1f}, PF {pf:.2f} — strong performer, consider increasing allocation."

        rec = RotationRecommendation(
            instance_slug=slug,
            action=action,
            reason=reason,
            suggested_allocation_pct=suggested,
            current_allocation_pct=current_alloc,
        )
        db.add(rec)
        recommendations.append({
            "id": rec.id,
            "instance_slug": slug,
            "action": action,
            "reason": reason,
            "current_allocation_pct": current_alloc,
            "suggested_allocation_pct": suggested,
            "approved": None,
            "created_at": rec.created_at.isoformat() if rec.created_at else None,
        })

    db.commit()
    return recommendations


def list_pending(db: Session) -> list[dict[str, Any]]:
    rows = db.query(RotationRecommendation).filter(RotationRecommendation.approved.is_(None)).order_by(RotationRecommendation.created_at.desc()).all()
    return [_row_to_dict(r) for r in rows]


def approve_recommendation(db: Session, rec_id: str, approved: bool) -> dict[str, Any] | None:
    row = db.query(RotationRecommendation).filter(RotationRecommendation.id == rec_id).first()
    if not row:
        return None
    row.approved = approved
    row.approved_at = _now_utc()
    db.commit()
    return _row_to_dict(row)


def _row_to_dict(row: RotationRecommendation) -> dict[str, Any]:
    return {
        "id": row.id,
        "instance_slug": row.instance_slug,
        "action": row.action,
        "reason": row.reason,
        "current_allocation_pct": row.current_allocation_pct,
        "suggested_allocation_pct": row.suggested_allocation_pct,
        "approved": row.approved,
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
