"""
Kill switch API routes and helpers.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from api.ratelimit import limiter, READ_LIMIT, WRITE_LIMIT
from instances.models import get_db, Instance, KillSwitchState
from instances.manager import manager

router = APIRouter()


def get_or_create_kill_state(db: Session, scope: str) -> KillSwitchState:
    state = db.query(KillSwitchState).filter(KillSwitchState.scope == scope).first()
    if not state:
        state = KillSwitchState(scope=scope, active=False)
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


def is_global_killed(db: Session) -> bool:
    return get_or_create_kill_state(db, "global").active


def is_withdrawal_killed(db: Session) -> bool:
    return get_or_create_kill_state(db, "withdrawals").active


def is_instance_killed(db: Session, slug: str) -> bool:
    inst = db.query(Instance).filter(Instance.slug == slug).first()
    return bool(inst and inst.status == "killed")


@router.post("/kill/global")
@limiter.limit(WRITE_LIMIT)
def kill_global(request: Request, reason: Optional[str] = None, db: Session = Depends(get_db)):
    state = get_or_create_kill_state(db, "global")
    state.active = True
    state.reason = reason or "manual"
    db.commit()
    # Stop every running engine
    manager.stop_all()
    return {"ok": True, "message": "Global kill switch engaged. All engines stopped."}


@router.post("/kill/global/reset")
@limiter.limit(WRITE_LIMIT)
def reset_global_kill(request: Request, db: Session = Depends(get_db)):
    state = get_or_create_kill_state(db, "global")
    state.active = False
    state.reason = None
    db.commit()
    return {"ok": True, "message": "Global kill switch reset."}


@router.post("/kill/{slug}")
@limiter.limit(WRITE_LIMIT)
def kill_instance(request: Request, slug: str, reason: Optional[str] = None, db: Session = Depends(get_db)):
    inst = db.query(Instance).filter(Instance.slug == slug).first()
    if not inst:
        return {"ok": False, "message": f"Instance {slug} not found"}
    manager.stop_instance_by_slug(slug)
    inst.status = "killed"
    db.commit()
    return {"ok": True, "message": f"Instance {slug} killed."}


@router.post("/kill/{slug}/reset")
@limiter.limit(WRITE_LIMIT)
def reset_instance_kill(request: Request, slug: str, db: Session = Depends(get_db)):
    inst = db.query(Instance).filter(Instance.slug == slug).first()
    if not inst:
        return {"ok": False, "message": f"Instance {slug} not found"}
    if inst.status != "killed":
        return {"ok": False, "message": f"Instance {slug} is not killed"}
    inst.status = "stopped"
    db.commit()
    return {"ok": True, "message": f"Instance {slug} reset to stopped."}


@router.post("/kill/withdrawals")
@limiter.limit(WRITE_LIMIT)
def kill_withdrawals(request: Request, reason: Optional[str] = None, db: Session = Depends(get_db)):
    state = get_or_create_kill_state(db, "withdrawals")
    state.active = True
    state.reason = reason or "manual"
    db.commit()
    return {"ok": True, "message": "Withdrawal kill switch engaged."}


@router.post("/kill/withdrawals/reset")
@limiter.limit(WRITE_LIMIT)
def reset_withdrawal_kill(request: Request, db: Session = Depends(get_db)):
    state = get_or_create_kill_state(db, "withdrawals")
    state.active = False
    state.reason = None
    db.commit()
    return {"ok": True, "message": "Withdrawal kill switch reset."}


@router.get("/kill/status")
@limiter.limit(READ_LIMIT)
def kill_status(request: Request, db: Session = Depends(get_db)):
    return {
        "ok": True,
        "global": get_or_create_kill_state(db, "global").active,
        "withdrawals": get_or_create_kill_state(db, "withdrawals").active,
    }
