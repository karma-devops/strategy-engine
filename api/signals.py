"""
API routes for signals.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.ratelimit import limiter, READ_LIMIT, WRITE_LIMIT
from instances.events import event_bus, add_log
from instances.models import get_db, Instance, Signal

router = APIRouter()


class InjectSignalRequest(BaseModel):
    direction: str = Field(..., pattern=r"^(BUY|SELL|NEUTRAL)$")
    signal: Optional[float] = 0.0
    metadata: Optional[dict] = {}
    reasoning: Optional[str] = None
    trade_active: Optional[bool] = False
    executed: Optional[bool] = False


@router.post("/signals/{instance_id}")
@limiter.limit(WRITE_LIMIT)
def inject_signal(
    request: Request,
    instance_id: str,
    payload: InjectSignalRequest,
    db: Session = Depends(get_db),
):
    """Inject a test signal for an instance. Does NOT execute a trade."""
    inst = db.query(Instance).filter(Instance.slug == instance_id).first()
    if not inst:
        return {"ok": False, "message": "Instance not found"}
    signal_row = Signal(
        instance_id=instance_id,
        direction=payload.direction,
        signal=payload.signal,
        trade_active=payload.trade_active,
        executed=payload.executed,
        metadata_json=payload.metadata or {},
        reasoning_text=payload.reasoning,
    )
    db.add(signal_row)
    db.commit()
    event_bus.emit(
        {
            "type": "signal",
            "instance_id": instance_id,
            "token": inst.token,
            "direction": payload.direction,
            "signal": payload.signal,
            "trade_active": payload.trade_active,
            "executed": payload.executed,
            "metadata": payload.metadata or {},
            "injected": True,
        }
    )
    add_log(
        f"[API] Injected {payload.direction} signal for {instance_id} ({inst.token})",
        "signal",
    )
    return {
        "ok": True,
        "message": f"Injected {payload.direction} signal for {instance_id}",
        "signal": {
            "id": signal_row.id,
            "direction": signal_row.direction,
            "signal": signal_row.signal,
            "timestamp": signal_row.timestamp.isoformat() if signal_row.timestamp else None,
        },
    }


@router.get("/instances/{instance_id}/signals")
@limiter.limit(READ_LIMIT)
def get_signals(request: Request, instance_id: str, limit: int = 50, db: Session = Depends(get_db)):
    rows = (
        db.query(Signal)
        .filter(Signal.instance_id == instance_id)
        .order_by(Signal.timestamp.desc())
        .limit(limit)
        .all()
    )
    return {
        "ok": True,
        "signals": [
            {
                "id": s.id,
                "direction": s.direction,
                "signal": s.signal,
                "trade_active": s.trade_active,
                "executed": s.executed,
                "metadata": s.metadata_json,
                "reasoning": s.reasoning_text,
                "timestamp": s.timestamp.isoformat() if s.timestamp else None,
            }
            for s in rows
        ],
    }
