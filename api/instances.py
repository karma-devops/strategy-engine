"""
API routes for instance control.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.ratelimit import limiter, READ_LIMIT, WRITE_LIMIT
from engine.registry import STRATEGIES
from instances.models import get_db, Instance
from instances.manager import manager

router = APIRouter()


class CreateInstanceRequest(BaseModel):
    slug: str = Field(..., min_length=1, max_length=32, pattern=r"^[a-z0-9-]+$")
    name: Optional[str] = None
    token: str = Field(..., min_length=1, max_length=64)
    strategy_id: str = Field(..., min_length=1, max_length=64)
    mode: Optional[str] = "Scalp"
    profile: Optional[str] = "aggressive_8_3"
    timeframe: Optional[str] = "15m"
    leverage: Optional[int] = 10
    max_position_pct: Optional[float] = 0.97
    poll_interval_seconds: Optional[int] = 30
    activation: Optional[int] = 8
    offset: Optional[int] = 3
    dry_run: Optional[bool] = True
    enabled: Optional[bool] = True
    hyperliquid_private_key: Optional[str] = None
    account_address: Optional[str] = None
    withdrawal_address: Optional[str] = None


class UpdateInstanceRequest(BaseModel):
    name: Optional[str] = None
    leverage: Optional[int] = None
    max_position_pct: Optional[float] = Field(None, ge=0.01, le=1.0)
    poll_interval_seconds: Optional[int] = None
    activation: Optional[int] = None
    offset: Optional[int] = None
    dry_run: Optional[bool] = None
    enabled: Optional[bool] = None
    hyperliquid_private_key: Optional[str] = None
    account_address: Optional[str] = None
    withdrawal_address: Optional[str] = None


@router.get("/instances")
@limiter.limit(READ_LIMIT)
def list_instances(request: Request, db: Session = Depends(get_db)):
    instances = db.query(Instance).order_by(Instance.created_at.desc()).all()
    return {
        "ok": True,
        "instances": [
            {
                "slug": i.slug,
                "name": i.name,
                "token": i.token,
                "strategy_id": i.strategy_id,
                "mode": i.mode,
                "profile": i.profile,
                "timeframe": i.timeframe,
                "leverage": i.leverage,
                "max_position_pct": i.max_position_pct,
                "poll_interval_seconds": i.poll_interval_seconds,
                "activation": i.activation,
                "offset": i.offset,
                "dry_run": i.dry_run,
                "enabled": i.enabled,
                "status": i.status,
                "account_address_mask": i.mask_address(i.get_account_address()),
                "withdrawal_address_mask": i.mask_address(i.get_withdrawal_address()),
                "has_private_key": bool(i.hyperliquid_private_key_encrypted),
                "position_side": i.position_side,
                "position_size": i.position_size,
                "entry_price": i.entry_price,
                "mark_price": i.mark_price,
                "unrealized_pnl": i.unrealized_pnl,
                "unrealized_pnl_pct": i.unrealized_pnl_pct,
                "created_at": i.created_at.isoformat() if i.created_at else None,
            }
            for i in instances
        ],
    }


@router.get("/instances/active")
@limiter.limit(READ_LIMIT)
def list_active_instances(request: Request, db: Session = Depends(get_db)):
    rows = db.query(Instance).filter(Instance.status == "running").all()
    return {
        "ok": True,
        "instances": [{"slug": i.slug, "name": i.name, "token": i.token} for i in rows],
    }


@router.post("/instances")
@limiter.limit(WRITE_LIMIT)
def create_instance(
    request: Request,
    payload: CreateInstanceRequest,
    db: Session = Depends(get_db),
):
    """Create a new engine instance programmatically. Not exposed in the UI."""
    if payload.strategy_id not in STRATEGIES:
        return {"ok": False, "message": f"Unknown strategy_id: {payload.strategy_id}"}
    if db.query(Instance).filter(Instance.slug == payload.slug).first():
        return {"ok": False, "message": f"Instance slug already exists: {payload.slug}"}
    inst = Instance(
        slug=payload.slug,
        name=payload.name or payload.slug,
        token=payload.token,
        strategy_id=payload.strategy_id,
        mode=payload.mode,
        profile=payload.profile,
        timeframe=payload.timeframe,
        leverage=payload.leverage,
        max_position_pct=payload.max_position_pct,
        poll_interval_seconds=payload.poll_interval_seconds,
        activation=payload.activation,
        offset=payload.offset,
        dry_run=payload.dry_run,
        enabled=payload.enabled,
        status="stopped",
    )
    if payload.hyperliquid_private_key:
        inst.set_private_key(payload.hyperliquid_private_key)
    if payload.account_address:
        inst.account_address = payload.account_address
    if payload.withdrawal_address:
        inst.withdrawal_address = payload.withdrawal_address
    db.add(inst)
    db.commit()
    return {
        "ok": True,
        "message": f"Created instance {inst.slug}",
        "instance": {
            "slug": inst.slug,
            "name": inst.name,
            "token": inst.token,
            "strategy_id": inst.strategy_id,
            "status": inst.status,
        },
    }


@router.put("/instances/{instance_id}")
@limiter.limit(WRITE_LIMIT)
def update_instance(
    request: Request,
    instance_id: str,
    payload: UpdateInstanceRequest,
    db: Session = Depends(get_db),
):
    inst = db.query(Instance).filter(Instance.slug == instance_id).first()
    if not inst:
        return {"ok": False, "message": "Instance not found"}
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key == "hyperliquid_private_key" and value:
            inst.set_private_key(value)
        elif key in {"account_address", "withdrawal_address"} and value:
            setattr(inst, key, value)
        elif hasattr(inst, key):
            setattr(inst, key, value)
    db.commit()
    return {"ok": True, "message": f"Updated {inst.slug}"}


@router.post("/instances/{instance_id}/start")
@limiter.limit(WRITE_LIMIT)
def start_instance(request: Request, instance_id: str, db: Session = Depends(get_db)):
    inst = db.query(Instance).filter(Instance.slug == instance_id).first()
    if not inst:
        return {"ok": False, "message": "Instance not found"}
    manager.start_instance(inst)
    return {"ok": True, "message": f"Started {inst.name}"}


@router.post("/instances/{instance_id}/stop")
@limiter.limit(WRITE_LIMIT)
def stop_instance(request: Request, instance_id: str, db: Session = Depends(get_db)):
    ok = manager.stop_instance(instance_id)
    return {"ok": ok, "message": "Stopped" if ok else "Instance not running"}


@router.post("/instances/{instance_id}/close")
@limiter.limit(WRITE_LIMIT)
def close_instance_position(request: Request, instance_id: str, db: Session = Depends(get_db)):
    """Close the open position for an instance's token at market."""
    inst = db.query(Instance).filter(Instance.slug == instance_id).first()
    if not inst:
        return {"ok": False, "message": "Instance not found"}
    from core.exchange import get_hyperliquid_client
    client = get_hyperliquid_client(inst)
    result = client.market_close(inst.token)
    if result is None:
        return {"ok": False, "message": "Close failed — check logs"}
    return {"ok": True, "message": f"Closed {inst.token}", "result": result}


@router.get("/instances/{instance_id}/trades")
@limiter.limit(READ_LIMIT)
def get_trades(request: Request, instance_id: str, limit: int = 50, db: Session = Depends(get_db)):
    """Get trade history for an instance, most recent first."""
    from instances.models import Trade
    rows = (
        db.query(Trade)
        .filter(Trade.instance_id == instance_id)
        .order_by(Trade.timestamp.desc())
        .limit(limit)
        .all()
    )
    return {
        "ok": True,
        "trades": [
            {
                "id": t.id,
                "side": t.side,
                "size": t.size,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "pnl_usd": t.pnl_usd,
                "pnl_pct": t.pnl_pct,
                "price_diff": t.price_diff,
                "entry_cost": t.entry_cost,
                "exit_cost": t.exit_cost,
                "timestamp": t.timestamp.isoformat() if t.timestamp else None,
            }
            for t in rows
        ],
    }


@router.get("/trades")
@limiter.limit(READ_LIMIT)
def get_all_trades(request: Request, limit: int = 50, db: Session = Depends(get_db)):
    """Get recent trades across all instances, most recent first."""
    from instances.models import Trade
    rows = (
        db.query(Trade)
        .order_by(Trade.timestamp.desc())
        .limit(limit)
        .all()
    )
    return {
        "ok": True,
        "trades": [
            {
                "id": t.id,
                "instance_id": t.instance_id,
                "side": t.side,
                "size": t.size,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "pnl_usd": t.pnl_usd,
                "pnl_pct": t.pnl_pct,
                "price_diff": t.price_diff,
                "timestamp": t.timestamp.isoformat() if t.timestamp else None,
            }
            for t in rows
        ],
    }


@router.post("/instances/{instance_id}/restart")
@limiter.limit(WRITE_LIMIT)
def restart_instance(request: Request, instance_id: str, db: Session = Depends(get_db)):
    ok = manager.restart_instance(instance_id)
    return {"ok": ok, "message": "Restarted" if ok else "Instance not found"}


@router.delete("/instances/{instance_id}")
@limiter.limit(WRITE_LIMIT)
def delete_instance(request: Request, instance_id: str, db: Session = Depends(get_db)):
    manager.stop_instance(instance_id)
    inst = db.query(Instance).filter(Instance.slug == instance_id).first()
    if inst:
        db.delete(inst)
        db.commit()
    return {"ok": True, "message": "Deleted"}
