"""
Monitoring API for strategy-engine:
- scores
- rotation recommendations
- alerts
- testing pool
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.auth import verify_api_key
from api.ratelimit import limiter, READ_LIMIT, WRITE_LIMIT
from monitoring.tracker import refresh_all_scores, get_latest_scores
from monitoring.rotator import generate_recommendations, list_pending, approve_recommendation
from monitoring.alerts import evaluate_and_create_alerts, list_active_alerts, dismiss_alert
from monitoring.testing_pool import list_pool, promote_asset, fail_asset
from instances.models import get_db, Alert


router = APIRouter()


class RefreshScoresRequest(BaseModel):
    days: int = 30


@router.post("/monitoring/scores/refresh")
@limiter.limit(WRITE_LIMIT)
def refresh_scores(
    request: Request,
    payload: RefreshScoresRequest,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    results = refresh_all_scores(db, days=payload.days)
    return {"ok": True, "scores": results}


@router.get("/monitoring/scores")
@limiter.limit(READ_LIMIT)
def get_scores(
    request: Request,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    return {"ok": True, "scores": get_latest_scores(db)}


@router.post("/monitoring/rotation/refresh")
@limiter.limit(WRITE_LIMIT)
def refresh_rotation(
    request: Request,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    recs = generate_recommendations(db)
    return {"ok": True, "recommendations": recs}


@router.get("/monitoring/rotation")
@limiter.limit(READ_LIMIT)
def get_rotation(
    request: Request,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    return {"ok": True, "recommendations": list_pending(db)}


@router.post("/monitoring/rotation/{rec_id}/approve")
@limiter.limit(WRITE_LIMIT)
def approve_rotation(
    request: Request,
    rec_id: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    row = approve_recommendation(db, rec_id, approved=True)
    if not row:
        return {"ok": False, "message": "Recommendation not found"}
    return {"ok": True, "recommendation": row}


@router.post("/monitoring/rotation/{rec_id}/reject")
@limiter.limit(WRITE_LIMIT)
def reject_rotation(
    request: Request,
    rec_id: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    row = approve_recommendation(db, rec_id, approved=False)
    if not row:
        return {"ok": False, "message": "Recommendation not found"}
    return {"ok": True, "recommendation": row}


@router.post("/alerts/evaluate")
@limiter.limit(WRITE_LIMIT)
def evaluate_alerts(
    request: Request,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    alerts = evaluate_and_create_alerts(db)
    return {"ok": True, "created": len(alerts), "alerts": alerts}


@router.get("/alerts")
@limiter.limit(READ_LIMIT)
def get_alerts(
    request: Request,
    instance_slug: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    query = db.query(Alert)  # noqa: F821 — Alert is imported via instances.models indirectly through monitoring.alerts
    if instance_slug:
        query = query.filter(Alert.instance_slug == instance_slug)
    rows = query.order_by(Alert.created_at.desc()).limit(limit).all()
    return {
        "ok": True,
        "alerts": [_alert_to_dict(r) for r in rows],
    }


@router.post("/alerts/{alert_id}/dismiss")
@limiter.limit(WRITE_LIMIT)
def dismiss_alert_endpoint(
    request: Request,
    alert_id: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    row = dismiss_alert(db, alert_id)
    if not row:
        return {"ok": False, "message": "Alert not found"}
    return {"ok": True, "alert": row}


@router.get("/testing-pool")
@limiter.limit(READ_LIMIT)
def testing_pool(
    request: Request,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    return {"ok": True, "assets": list_pool(db)}


@router.post("/testing-pool/{token}/promote")
@limiter.limit(WRITE_LIMIT)
def promote_pool_asset(
    request: Request,
    token: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    return promote_asset(token)


@router.post("/testing-pool/{token}/fail")
@limiter.limit(WRITE_LIMIT)
def fail_pool_asset(
    request: Request,
    token: str,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    return fail_asset(token, reason=reason or "")


def _alert_to_dict(a) -> dict:
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
