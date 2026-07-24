"""
API routes for instance control.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.ratelimit import limiter, READ_LIMIT, WRITE_LIMIT
from api.auth import verify_api_key
from api.credentials import _current_user_id
from engine.registry import STRATEGIES
from instances.models import get_db, Instance, AccountSnapshot, PositionSnapshot
from instances.manager import manager
from api.killswitch import is_global_killed, is_instance_killed

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
    token: Optional[str] = None
    strategy_id: Optional[str] = None
    timeframe: Optional[str] = None
    mode: Optional[str] = None
    profile: Optional[str] = None
    leverage: Optional[int] = None
    max_position_pct: Optional[float] = Field(None, ge=0.01, le=1.0)
    poll_interval_seconds: Optional[int] = None
    activation: Optional[int] = None
    offset: Optional[int] = None
    dry_run: Optional[bool] = None
    enabled: Optional[bool] = None
    start_balance: Optional[float] = None
    balance_mode: Optional[str] = None
    hyperliquid_private_key: Optional[str] = None
    account_address: Optional[str] = None
    withdrawal_address: Optional[str] = None
    hl_credential_id: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "timeframe": "5m",
                    "leverage": 3,
                    "dry_run": False,
                    "max_position_pct": 0.97,
                    "poll_interval_seconds": 30,
                }
            ]
        }
    }


@router.get("/instances")
@limiter.limit(READ_LIMIT)
def list_instances(request: Request, db: Session = Depends(get_db), api_key: str = Depends(verify_api_key)):
    # PER-USER ISOLATION: only return engines owned by the authenticated user.
    # No operator fallback — a global/missing key raises 403 in _current_user_id.
    user_id = _current_user_id(db, request)
    instances = (
        db.query(Instance)
        .filter(Instance.user_id == user_id)
        .order_by(Instance.created_at.desc())
        .all()
    )
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
                "start_balance": i.start_balance,
                "balance_mode": i.balance_mode,
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
                "liquidation_price": i.liquidation_price or 0.0,
                "stop_loss": i.stop_loss,
                "take_profit": i.take_profit,
                "created_at": i.created_at.isoformat() if i.created_at else None,
            }
            for i in instances
        ],
    }


def get_summary_data(mode: str = "live"):
    """Standalone summary data fetcher for logout page (no request context needed).
    
    mode: "live" (default), "paper", or "all". Paper and live must never mix.
    """
    from instances.models import SessionLocal, AccountSnapshot, Instance, PositionSnapshot
    # Determine dry_run filter from mode
    if mode == "paper":
        dry_run_filter = True
    elif mode == "all":
        dry_run_filter = None
    else:  # "live" (default)
        dry_run_filter = False

    db = SessionLocal()
    try:
        instances = db.query(Instance).order_by(Instance.created_at.asc()).all()
        snap_q = db.query(AccountSnapshot).order_by(AccountSnapshot.timestamp.asc()).limit(500)
        if dry_run_filter is not None:
            snap_q = snap_q.filter(AccountSnapshot.dry_run == dry_run_filter)
        snapshots = snap_q.all()
        latest = snapshots[-1] if snapshots else None
        active = sum(1 for i in instances if i.status == "running")
        account_value = latest.account_value if latest else 0.0
        has_hl_credentials = False
        try:
            from core.exchange import get_hyperliquid_client
            hl = get_hyperliquid_client()
            has_hl_credentials = getattr(hl, 'has_credentials', False)
            if has_hl_credentials:
                live_val = hl.get_account_value()
                if live_val > 0:
                    account_value = round(live_val, 2)
        except Exception:
            pass
        return {
            "account_value": account_value,
            "active_engines": active,
            "total_engines": len(instances),
            "dry_run_global": all(i.dry_run for i in instances) if instances else True,
            "has_hl_credentials": has_hl_credentials,
        }
    finally:
        db.close()


@router.get("/summary")
@limiter.limit(READ_LIMIT)
def summary(request: Request, db: Session = Depends(get_db), hours: int = 24, mode: str = "live"):
    """Live KPI + fleet summary for frontend polling (mirrors dashboard route).
    
    mode: "live" (default) — show only live (dry_run=False) data.
          "paper" — show only paper (dry_run=True) data.
          "all" — show everything (no filter).
    Paper and live must never be mixed in the same metric.
    """
    from instances.models import AccountSnapshot, Trade, User
    # PER-USER ISOLATION: scope everything to the authenticated user. No operator
    # fallback — _current_user_id raises 403 for a global/missing key.
    user_id = _current_user_id(db, request)
    user = db.query(User).filter(User.id == user_id).first()
    is_operator = bool(user and user.username == "operator")

    # Determine dry_run filter from mode parameter
    if mode == "paper":
        dry_run_filter = True
    elif mode == "all":
        dry_run_filter = None  # no filter
    else:  # "live" (default)
        dry_run_filter = False

    instances = db.query(Instance).filter(Instance.user_id == user_id).order_by(Instance.created_at.asc()).all()
    instances_data = []
    for i in instances:
        snap = (
            db.query(PositionSnapshot)
            .filter(PositionSnapshot.instance_id == i.slug)
            .order_by(PositionSnapshot.timestamp.desc())
            .first()
        )
        instances_data.append({
            "slug": i.slug,
            "name": i.name,
            "token": i.token,
            "strategy_id": i.strategy_id,
            "timeframe": i.timeframe,
            "status": i.status,
            "position_side": i.position_side or "FLAT",
            "leverage": i.leverage,
            "max_position_pct": i.max_position_pct,
            "dry_run": i.dry_run,
            "unrealized_pnl": i.unrealized_pnl or 0.0,
            "unrealized_pnl_pct": i.unrealized_pnl_pct or 0.0,
            "entry_price": snap.entry_price if snap else (i.entry_price or 0.0),
            "mark_price": snap.mark_price if snap else (i.mark_price or 0.0),
            "position_size": snap.size if snap else (i.position_size or 0.0),
            # A4: for RUNNING live instances, enrich liq price from HL live
            # position data instead of relying on the stale DB field (which the
            # runner only repopulates on adopt/close, not every tick).
            "liquidation_price": i.liquidation_price or 0.0,
            "stop_loss": i.stop_loss,
            "take_profit": i.take_profit,
        })
        # A4 live enrichment: if this instance is running (live), pull the
        # open position fresh from HL so the dashboard/engine position cards
        # show real values (not 0.0 / stale-NONE). This fires for ALL
        # running live instances — including the case where the DB
        # position_side went stale-NONE but HL still holds a position
        # (the flash-vanish bug). HL is the source of truth for rendering.
        if i.status == "running" and i.dry_run is False:
            try:
                from core.exchange import get_hyperliquid_client
                _hl = get_hyperliquid_client(i)
                _pos = _hl.get_position(i.token)
                if _pos:
                    _szi = float(_pos.get("szi") or 0)
                    if _szi != 0:
                        instances_data[-1]["position_side"] = "LONG" if _szi > 0 else "SHORT"
                        instances_data[-1]["position_size"] = abs(_szi)
                        if _pos.get("entryPx") is not None:
                            instances_data[-1]["entry_price"] = float(_pos["entryPx"])
                        if _pos.get("markPx") is not None:
                            instances_data[-1]["mark_price"] = float(_pos["markPx"])
                        if _pos.get("unrealizedPnl") is not None:
                            instances_data[-1]["unrealized_pnl"] = float(_pos["unrealizedPnl"])
                    if _pos.get("liquidationPx"):
                        instances_data[-1]["liquidation_price"] = float(_pos["liquidationPx"])
            except Exception as _e:
                pass  # keep DB value on HL error
    # Filter snapshots by hours range AND dry_run mode for pulse graph.
    # Paper and live must never share the same equity curve.
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    snap_q = (
        db.query(AccountSnapshot)
        .filter(AccountSnapshot.timestamp >= cutoff)
        .filter(AccountSnapshot.source == "perp")  # B4: HL-native only — consistent pulse/KPI
    )
    if dry_run_filter is not None:
        snap_q = snap_q.filter(AccountSnapshot.dry_run == dry_run_filter)
    snapshots = snap_q.order_by(AccountSnapshot.timestamp.asc()).limit(500).all()
    equity_series = [{"time": s.timestamp.isoformat(), "value": s.account_value} for s in snapshots]
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
    # Always query HL live for real-time portfolio value; fall back to snapshot
    latest = snapshots[-1] if snapshots else None
    active = sum(1 for i in instances if i.status == "running")
    # Separate open PnL by mode — never mix paper and live.
    if dry_run_filter is not None:
        open_pnl = round(sum((i.unrealized_pnl or 0.0) for i in instances if i.dry_run == dry_run_filter), 2)
        filtered_instances = [i for i in instances if i.dry_run == dry_run_filter]
    else:
        open_pnl = round(sum((i.unrealized_pnl or 0.0) for i in instances), 2)
        filtered_instances = instances

    account_value = latest.account_value if latest else 0.0
    has_hl_credentials = False
    # Live HL value ONLY for operator, or a user who stored their OWN hl_api
    # credential. Never call the operator's global client for a normal user —
    # that leaks operator's live $ value. Non-operator with no credential keeps
    # their snapshot/0 value (correct isolation).
    if is_operator:
        try:
            from core.exchange import get_hyperliquid_client
            hl = get_hyperliquid_client()
            has_hl_credentials = getattr(hl, 'has_credentials', False)
            if has_hl_credentials:
                live_val = hl.get_perp_account_value()  # C1: HL-native perp-only, matches B4 source='perp' pulse/KPI
                if live_val > 0:
                    account_value = round(live_val, 2)
        except Exception:
            pass
    else:
        from instances.models import Credential
        cred = db.query(Credential).filter(
            Credential.user_id == user_id, Credential.type == "hl_api", Credential.is_active == True
        ).first()
        has_hl_credentials = cred is not None

    # Realized PnL: sum of closed trades matching the current mode filter.
    # Never mix paper and live trade PnL.
    from instances.models import Trade
    trade_q = db.query(Trade)
    if dry_run_filter is not None:
        trade_q = trade_q.filter(Trade.dry_run == dry_run_filter)
    all_trades = trade_q.all()
    realized_pnl = round(sum(t.pnl_usd for t in all_trades), 2) if all_trades else 0.0

    # Best performing engine: highest realized PnL per instance (mode-filtered)
    from collections import defaultdict
    engine_pnl = defaultdict(float)
    for t in all_trades:
        engine_pnl[t.instance_id] += t.pnl_usd
    best_engine_slug = None
    best_engine_pnl = 0.0
    best_engine_token = None
    best_engine_strategy = None
    if engine_pnl:
        best_slug = max(engine_pnl, key=engine_pnl.get)
        best_engine_slug = best_slug
        best_engine_pnl = round(engine_pnl[best_slug], 2)
        best_inst = db.query(Instance).filter(Instance.slug == best_slug).first()
        if best_inst:
            best_engine_token = best_inst.token
            best_engine_strategy = best_inst.strategy_id

    # User start balance for pulse graph baseline (the authenticated user)
    start_balance = user.start_balance if user and user.start_balance > 0 else 0.0

    return {
        "ok": True,
        "account_value": account_value,
        "realized_pnl": realized_pnl,
        "best_engine": best_engine_slug,
        "best_engine_pnl": best_engine_pnl,
        "best_engine_token": best_engine_token,
        "best_engine_strategy": best_engine_strategy,
        "start_balance": start_balance,
        "drawdown_pct": round(max_dd * 100.0, 2),
        "active_engines": active,
        "total_engines": len(instances),
        "open_pnl": open_pnl,
        "instances": instances_data,
        "equity_series": equity_series,
        "dry_run_global": all(i.dry_run for i in instances) if instances else True,
        "has_hl_credentials": has_hl_credentials,
        "mode": mode,  # P14: paper/live separation — client knows which mode it's viewing
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
    api_key: str = Depends(verify_api_key),
):
    """Create a new engine instance programmatically. Not exposed in the UI.

    PER-USER ISOLATION: the engine is owned by the authenticated user. A
    global/missing key raises 403 in _current_user_id (no operator fallback).
    """
    user_id = _current_user_id(db, request)
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
        user_id=user_id,  # PER-USER ISOLATION: bind ownership
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


@router.put("/instances/{instance_id}/strategy-config")
@limiter.limit(WRITE_LIMIT)
def update_strategy_config(
    request: Request,
    instance_id: str,
    payload: dict,
    db: Session = Depends(get_db),
):
    """Save per-instance strategy parameter overrides (Pine input.* equivalent).

    Validates each key against the strategy's declared get_parameters() schema
    and coerces values to the declared type. Unknown keys are rejected (400)
    instead of silently becoming a no-op. After a successful save the instance
    is restarted so the running engine picks up the new config live.
    """
    inst = db.query(Instance).filter(Instance.slug == instance_id).first()
    if not inst:
        return {"ok": False, "message": "Instance not found"}

    from engine.registry import get_strategy
    strategy_cls = get_strategy(inst.strategy_id)
    if not strategy_cls:
        return {"ok": False, "message": f"Unknown strategy {inst.strategy_id}"}

    # Build {name: type} map from the strategy's declared parameters.
    param_schema = {p["name"]: p.get("type", "float") for p in strategy_cls.get_parameters()}

    validated: dict = {}
    invalid_keys: list = []
    for key, value in payload.items():
        if key not in param_schema:
            invalid_keys.append(key)
            continue
        ptype = param_schema[key]
        try:
            if ptype == "int":
                validated[key] = int(value)
            elif ptype == "float":
                validated[key] = float(value)
            elif ptype == "bool":
                validated[key] = bool(value) if not isinstance(value, str) else value.lower() in ("1", "true", "yes", "on")
            elif ptype == "select":
                validated[key] = value  # option whitelist enforced client-side; accept as-is
            else:
                validated[key] = float(value)
        except (ValueError, TypeError):
            return {
                "ok": False,
                "message": f"Invalid value for parameter '{key}': expected {ptype}, got {value!r}",
            }

    if invalid_keys:
        return {
            "ok": False,
            "message": f"Unknown parameter(s): {', '.join(invalid_keys)}. Valid: {', '.join(param_schema.keys())}",
        }

    inst.strategy_config = validated
    db.commit()

    # Restart so the live engine re-reads strategy_config at _run_once start.
    restarted = manager.restart_instance(inst.slug)

    return {
        "ok": True,
        "message": f"Strategy config saved for {inst.slug}" + ("" if restarted else " (restart skipped — instance not running)"),
        "config": validated,
        "restarted": restarted,
    }


@router.get("/instances/{instance_id}/strategy-config")
@limiter.limit(READ_LIMIT)
def get_strategy_config(
    request: Request,
    instance_id: str,
    db: Session = Depends(get_db),
):
    """Return current per-instance strategy config + parameter schema."""
    inst = db.query(Instance).filter(Instance.slug == instance_id).first()
    if not inst:
        return {"ok": False, "message": "Instance not found"}
    from engine.registry import get_strategy
    strategy_cls = get_strategy(inst.strategy_id)
    parameters = strategy_cls.get_parameters() if strategy_cls else []
    return {
        "ok": True,
        "strategy_id": inst.strategy_id,
        "config": inst.strategy_config or {},
        "parameters": parameters,
    }


@router.post("/instances/{instance_id}/start")
@limiter.limit(WRITE_LIMIT)
def start_instance(request: Request, instance_id: str, db: Session = Depends(get_db)):
    inst = db.query(Instance).filter(Instance.slug == instance_id).first()
    if not inst:
        return {"ok": False, "message": "Instance not found"}
    # BUG-8 (P0): enforce kill switch at the API boundary (defense in depth).
    # Block start if the global kill switch is active OR this instance is killed,
    # regardless of manager internals. Returns 409 so callers can't mistake it for success.
    if is_instance_killed(db, instance_id):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"ok": False, "message": f"Instance {inst.name} is killed. Reset the kill before starting."},
        )
    if is_global_killed(db):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"ok": False, "message": f"Global kill switch active — {inst.name} start blocked."},
        )
    ok = manager.start_instance(inst)
    if not ok:
        return {"ok": False, "message": f"Could not start {inst.name} (kill switch active, already running, or instance killed)"}
    return {"ok": True, "message": f"Started {inst.name}"}


@router.post("/instances/{instance_id}/stop")
@limiter.limit(WRITE_LIMIT)
def stop_instance(request: Request, instance_id: str, db: Session = Depends(get_db)):
    """Stop an instance. B7: close any open position on the exchange
    before halting the runner so no position is left dangling."""
    inst = db.query(Instance).filter(Instance.slug == instance_id).first()
    if not inst:
        return {"ok": False, "message": "Instance not found"}
    # B7: close open position first (mirrors kill-switch behavior)
    if inst.position_side and inst.position_side != "FLAT":
        try:
            from core.exchange import get_hyperliquid_client
            client = get_hyperliquid_client(inst)
            client.market_close(inst.token)
        except Exception as e:
            print(f"[STOP] Failed to close position for {instance_id}: {e}")
    ok = manager.stop_instance(instance_id)
    return {"ok": ok, "message": "Stopped and position closed" if ok else "Instance not running"}


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
def get_trades(request: Request, instance_id: str, limit: int = 50, dry_run: bool = None, db: Session = Depends(get_db)):
    """Get trade history for an instance, most recent first. Filter by dry_run if provided."""
    from instances.models import Trade
    q = db.query(Trade).filter(Trade.instance_id == instance_id)
    if dry_run is not None:
        q = q.filter(Trade.dry_run == dry_run)
    rows = q.order_by(Trade.timestamp.desc()).limit(limit).all()
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
                "dry_run": t.dry_run,
                "timestamp": t.timestamp.isoformat() if t.timestamp else None,
            }
            for t in rows
        ],
    }


@router.get("/trades")
@limiter.limit(READ_LIMIT)
def get_all_trades(request: Request, limit: int = 50, dry_run: bool = None, db: Session = Depends(get_db)):
    """Get recent trades across all instances, most recent first. Filter by dry_run if provided."""
    from instances.models import Trade
    q = db.query(Trade)
    if dry_run is not None:
        q = q.filter(Trade.dry_run == dry_run)
    rows = q.order_by(Trade.timestamp.desc()).limit(limit).all()
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
                "dry_run": t.dry_run,
                "timestamp": t.timestamp.isoformat() if t.timestamp else None,
            }
            for t in rows
        ],
    }


@router.post("/instances/{instance_id}/leverage")
@limiter.limit(WRITE_LIMIT)
def set_leverage(
    request: Request,
    instance_id: str,
    leverage: int,
    db: Session = Depends(get_db),
):
    """Set leverage on the exchange and update the instance record."""
    inst = db.query(Instance).filter(Instance.slug == instance_id).first()
    if not inst:
        return {"ok": False, "message": "Instance not found"}
    if leverage < 1 or leverage > 50:
        return {"ok": False, "message": "Leverage must be 1-50"}
    from core.exchange import get_hyperliquid_client
    client = get_hyperliquid_client(inst)
    result = client.set_leverage(inst.token, leverage)
    if result is None:
        return {"ok": False, "message": "Exchange rejected leverage change - check logs"}
    # HL returns {"status": "err", "response": "..."} on failure
    if isinstance(result, dict) and result.get("status") == "err":
        return {"ok": False, "message": f"Exchange error: {result.get('response', 'unknown')}"}
    inst.leverage = leverage
    db.commit()
    return {"ok": True, "message": f"Set {inst.slug} leverage to {leverage}x", "result": result}


class SetBalanceRequest(BaseModel):
    start_balance: float = Field(..., ge=0)
    balance_mode: str = Field(default="manual", pattern="^(live|manual)$")


@router.post("/instances/{instance_id}/balance")
@limiter.limit(WRITE_LIMIT)
def set_balance(
    request: Request,
    instance_id: str,
    payload: SetBalanceRequest,
    db: Session = Depends(get_db),
):
    """Set manual start balance for PnL tracking."""
    inst = db.query(Instance).filter(Instance.slug == instance_id).first()
    if not inst:
        return {"ok": False, "message": "Instance not found"}
    inst.start_balance = payload.start_balance
    inst.balance_mode = payload.balance_mode
    db.commit()
    return {"ok": True, "message": f"Set {inst.slug} balance: {payload.balance_mode} ${payload.start_balance}"}


@router.get("/instances/{instance_id}/balance")
@limiter.limit(READ_LIMIT)
def get_balance(
    request: Request,
    instance_id: str,
    db: Session = Depends(get_db),
):
    """Get balance info: start_balance, balance_mode, live account value, tracked PnL.
    
    For paper instances (dry_run=True), uses the latest AccountSnapshot instead
    of querying the live HL account — paper must never touch real money APIs.
    """
    inst = db.query(Instance).filter(Instance.slug == instance_id).first()
    if not inst:
        return {"ok": False, "message": "Instance not found"}
    
    if inst.dry_run:
        # Paper instance: use simulated equity from snapshots, never touch HL API
        from instances.models import AccountSnapshot as Snap
        latest_snap = (
            db.query(Snap)
            .filter(Snap.instance_id == inst.slug, Snap.dry_run == True)
            .order_by(Snap.timestamp.desc())
            .first()
        )
        simulated_value = latest_snap.account_value if latest_snap else (inst.start_balance or 0.0)
        start = inst.start_balance if inst.balance_mode == "manual" and inst.start_balance > 0 else simulated_value
        tracked_pnl = simulated_value - start if start > 0 else 0.0
        return {
            "ok": True,
            "balance_mode": inst.balance_mode,
            "start_balance": inst.start_balance or 0.0,
            "live_account_value": simulated_value,  # simulated, not live
            "tracked_pnl": tracked_pnl,
            "baseline": start,
            "dry_run": True,  # P14: client knows this is simulated
        }
    
    # Live instance: query real HL account
    from core.exchange import get_hyperliquid_client
    client = get_hyperliquid_client(inst)
    live_value = client.get_account_value() if not inst.dry_run else 0.0
    start = inst.start_balance if inst.balance_mode == "manual" and inst.start_balance > 0 else live_value
    tracked_pnl = live_value - start if start > 0 else 0.0
    return {
        "ok": True,
        "balance_mode": inst.balance_mode,
        "start_balance": inst.start_balance,
        "live_account_value": live_value,
        "tracked_pnl": tracked_pnl,
        "baseline": start,
        "dry_run": False,  # P14: live instance
    }


@router.post("/instances/{instance_id}/restart")
@limiter.limit(WRITE_LIMIT)
def restart_instance(request: Request, instance_id: str, db: Session = Depends(get_db)):
    ok = manager.restart_instance(instance_id)
    return {"ok": ok, "message": "Restarted" if ok else "Instance not found"}


@router.delete("/instances/{instance_id}")
@limiter.limit(WRITE_LIMIT)
def delete_instance(
    request: Request,
    instance_id: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    """Delete an instance and all associated data (trades, signals, backtests, snapshots).

    PER-USER ISOLATION: only the owning user may delete. Lookup is scoped by
    user_id — a non-owner gets 404 (instance not found), never another user's engine.
    """
    user_id = _current_user_id(db, request)
    manager.stop_instance(instance_id)
    inst = db.query(Instance).filter(Instance.slug == instance_id, Instance.user_id == user_id).first()
    if not inst:
        return {"ok": False, "message": f"Instance {instance_id} not found"}
    # BUG #15: check for open exchange position before deleting.
    # If a position is still open on the exchange, force-close it first
    # so we don't orphan a live position with no local record.
    if inst.position_side and inst.position_side != "FLAT":
        try:
            from core.exchange import get_hyperliquid_client
            client = get_hyperliquid_client(inst)
            client.market_close(inst.token)
            print(f"[DELETE] Force-closed {inst.token} position before deleting {inst.slug}")
        except Exception as e:
            return {"ok": False, "message": f"Cannot delete — open position on exchange ({e}). Close manually first."}
    # Clean up all related records to prevent orphaned data
    from instances.models import Trade, Signal, Backtest, PositionSnapshot, AccountSnapshot
    db.query(Trade).filter(Trade.instance_id == instance_id).delete()
    db.query(Signal).filter(Signal.instance_id == instance_id).delete()
    db.query(Backtest).filter(Backtest.instance_slug == instance_id).delete()
    db.query(PositionSnapshot).filter(PositionSnapshot.instance_id == instance_id).delete()
    db.query(AccountSnapshot).filter(AccountSnapshot.instance_id == instance_id).delete()
    db.delete(inst)
    db.commit()
    return {"ok": True, "message": f"Deleted {instance_id} and all associated data"}


@router.get("/candles/{token}")
def candle_data_api(token: str, request: Request, timeframe: str = "15m", bars: int = 200):
    """Return OHLCV candle data for a token from HyperLiquid."""
    from core.market_data import HyperLiquidMarketData
    md = HyperLiquidMarketData()
    df = md.get_candles(symbol=token.upper(), timeframe=timeframe, bars=min(int(bars), 500))
    if df is None or df.empty:
        return {"ok": True, "token": token.upper(), "candles": []}
    candles = []
    for _, row in df.iterrows():
        candles.append({
            "time": int(row["timestamp"].timestamp()) if hasattr(row["timestamp"], "timestamp") else int(row["timestamp"]),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
        })
    return {"ok": True, "token": token.upper(), "timeframe": timeframe, "candles": candles}
