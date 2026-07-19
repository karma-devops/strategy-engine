"""
Withdrawal API routes.
"""

from fastapi import APIRouter, Depends, Form, Request
import uuid
from sqlalchemy.orm import Session

from api.ratelimit import limiter, READ_LIMIT, WRITE_LIMIT
from instances.models import get_db, AccountSnapshot, WithdrawalRecord
from api.killswitch import is_withdrawal_killed
from core.exchange import HyperLiquidClient
from withdrawal.calculator import (
    get_or_create_config,
    calculate_manual_50,
    calculate_manual_all,
    generate_projection,
    days_until_next_withdrawal,
)
from withdrawal.manual import (
    execute_manual_50,
    execute_manual_all,
    get_withdrawal_history,
)

router = APIRouter()


def _check_withdrawal_kill(db: Session):
    if is_withdrawal_killed(db):
        return {"ok": False, "message": "Withdrawal kill switch is active"}
    return None


@router.get("/account")
@limiter.limit(READ_LIMIT)
def get_account(request: Request):
    hl = HyperLiquidClient()
    if not hl.has_credentials:
        return {
            "ok": True,
            "account_value": 0.0,
            "withdrawable": 0.0,
            "credentials_present": False,
        }
    return {
        "ok": True,
        "account_value": hl.get_account_value(),
        "withdrawable": hl.get_withdrawable(),
        "credentials_present": True,
    }


@router.get("/withdrawals/config")
@limiter.limit(READ_LIMIT)
def get_withdrawal_config(request: Request, db: Session = Depends(get_db)):
    config = get_or_create_config(db)
    last_record = (
        db.query(WithdrawalRecord)
        .filter(WithdrawalRecord.status == "completed")
        .order_by(WithdrawalRecord.timestamp.desc())
        .first()
    )
    return {
        "ok": True,
        "config": {
            "cycle_days": config.cycle_days,
            "auto_withdraw_enabled": config.auto_withdraw_enabled,
            "withdrawal_rate": config.withdrawal_rate,
            "compound_rate": config.compound_rate,
            "min_capital": config.min_capital,
            "phased_rules": config.phased_rules_json,
            "days_until_next": days_until_next_withdrawal(config, last_record),
            "next_scheduled_at": config.next_scheduled_at.isoformat() if config.next_scheduled_at else None,
        },
    }


# === T1-7 DEFERRED: comment out config-write + calculate (fund-touching) ===
# @router.put("/withdrawals/config")
# @limiter.limit(WRITE_LIMIT)
# def update_withdrawal_config(
#     request: Request,
#     cycle_days: int = Form(30),
#     auto_withdraw_enabled: bool = Form(False),
#     withdrawal_rate: float = Form(0.50),
#     compound_rate: float = Form(0.50),
#     min_capital: float = Form(10000.0),
#     db: Session = Depends(get_db),
# ):
#     config = get_or_create_config(db)
#     config.cycle_days = cycle_days
#     config.auto_withdraw_enabled = auto_withdraw_enabled
#     config.withdrawal_rate = withdrawal_rate
#     config.compound_rate = compound_rate
#     config.min_capital = min_capital
#     db.commit()
#     return {"ok": True, "message": "Withdrawal config updated"}
#
#
# @router.get("/withdrawals/calculate")
# @limiter.limit(READ_LIMIT)
# def calculate_withdrawal_endpoint(request: Request, db: Session = Depends(get_db)):
#     hl = HyperLiquidClient()
#     if not hl.has_credentials:
#         return {
#             "ok": True,
#             "balance": 0.0,
#             "manual_50": {"amount": 0.0, "reason": "No HyperLiquid credentials configured"},
#             "manual_all": {"amount": 0.0, "reason": "No HyperLiquid credentials configured"},
#             "credentials_present": False,
#         }
#     config = get_or_create_config(db)
#     balance = hl.get_account_value()
#     amount_50, reason_50 = calculate_manual_50(db, balance, config)
#     amount_all, reason_all = calculate_manual_all(db, balance, config)
#     return {
#         "ok": True,
#         "balance": balance,
#         "manual_50": {"amount": amount_50, "reason": reason_50},
#         "manual_all": {"amount": amount_all, "reason": reason_all},
#         "credentials_present": True,
#     }


# === T1-7 DEFERRED 2026-07-19: withdraw/deposit round-trip feature ===
# Withdrawal is BROKEN (BUG-11: SDK missing .withdraw) and deposit has NO
# code path (BUG-12). Operator deferred the feature. Comment out fund-moving
# routes so the broken flow is unreachable. Re-enable when BUG-11/12 are built.
# Idempotency logic (T1-5) preserved in withdrawal/manual.py for reuse.
#
# @router.post("/withdrawals/manual/50")
# @limiter.limit(WRITE_LIMIT)
# def withdraw_50_percent(request: Request, db: Session = Depends(get_db)):
#     blocked = _check_withdrawal_kill(db)
#     if blocked:
#         return blocked
#     idem_key = request.headers.get("Idempotency-Key") or str(uuid.uuid4().hex)
#     result = execute_manual_50(db, idempotency_key=idem_key)
#     return {"ok": result["ok"], "idempotency_key": idem_key, **result}
#
#
# @router.post("/withdrawals/manual/all")
# @limiter.limit(WRITE_LIMIT)
# def withdraw_all(request: Request, db: Session = Depends(get_db)):
#     blocked = _check_withdrawal_kill(db)
#     if blocked:
#         return blocked
#     idem_key = request.headers.get("Idempotency-Key") or str(uuid.uuid4().hex)
#     result = execute_manual_all(db, idempotency_key=idem_key)
#     return {"ok": result["ok"], "idempotency_key": idem_key, **result}


@router.get("/withdrawals/history")
@limiter.limit(READ_LIMIT)
def withdrawal_history(request: Request, limit: int = 50, db: Session = Depends(get_db)):
    return {"ok": True, "history": get_withdrawal_history(db, limit)}


@router.get("/withdrawals/projection")
@limiter.limit(READ_LIMIT)
def withdrawal_projection(
    request: Request,
    start_capital: float = 10000.0,
    monthly_return: float = 0.30,
    withdrawal_rate: float = 0.50,
    months: int = 24,
):
    return {
        "ok": True,
        "projection": generate_projection(start_capital, monthly_return, withdrawal_rate, months),
    }
