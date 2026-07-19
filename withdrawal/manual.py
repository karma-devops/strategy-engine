"""
Manual withdrawal execution for strategy-engine.
"""

from sqlalchemy.orm import Session

from instances.models import WithdrawalRecord, AccountSnapshot
from instances.events import add_log
from core.exchange import HyperLiquidClient
from withdrawal.calculator import (
    get_or_create_config,
    calculate_manual_50,
    calculate_manual_all,
    set_baseline,
)


def execute_manual_50(db: Session, hl: HyperLiquidClient = None, idempotency_key: str = None) -> dict:
    # Idempotency: if a record with this key already exists (any terminal or
    # in-flight state), return its stored outcome instead of re-executing.
    if idempotency_key:
        existing = (
            db.query(WithdrawalRecord)
            .filter(WithdrawalRecord.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            return {
                "ok": existing.status in ("completed", "dry_run"),
                "idempotent": True,
                "amount": existing.amount,
                "message": f"Already processed (status={existing.status})",
                "balance_after": existing.balance_after,
                "status": existing.status,
            }

    if hl is None:
        hl = HyperLiquidClient()

    config = get_or_create_config(db)
    balance = hl.get_account_value()
    available = hl.get_withdrawable()

    snap = AccountSnapshot(account_value=balance, withdrawable=available)
    db.add(snap)
    db.commit()

    amount, reason = calculate_manual_50(db, balance, config)
    if amount <= 0:
        return {"ok": False, "message": reason, "amount": 0}

    record = WithdrawalRecord(
        amount=amount,
        withdrawal_type="manual_50",
        status="pending",
        balance_before=balance,
        idempotency_key=idempotency_key,
    )
    db.add(record)
    db.commit()

    result = hl.withdraw_to_wallet(amount)
    # BUG #3: dry_run returns truthy dict — must NOT mark completed
    if result and result.get("status") != "dry_run":
        record.status = "completed"
        record.balance_after = balance - amount
        record.note = reason
        db.commit()
        set_baseline(db, balance - amount, "Post-manual-50 baseline")
        add_log(f"[WITHDRAWAL] Manual 50% withdrew ${amount:.2f}", "trade")
        return {"ok": True, "amount": amount, "message": reason, "balance_after": balance - amount}
    elif result and result.get("status") == "dry_run":
        record.status = "dry_run"
        record.balance_after = balance
        record.note = f"DRY_RUN: {reason}"
        db.commit()
        add_log(f"[WITHDRAWAL] Manual 50% DRY_RUN (no baseline reset)", "info")
        return {"ok": True, "amount": amount, "message": "DRY_RUN — no funds moved", "balance_after": balance}
    else:
        record.status = "failed"
        db.commit()
        add_log(f"[WITHDRAWAL] Manual 50% failed for ${amount:.2f}", "error")
        return {"ok": False, "amount": amount, "message": "Withdrawal execution failed"}


def execute_manual_all(db: Session, hl: HyperLiquidClient = None, idempotency_key: str = None) -> dict:
    # Idempotency: if a record with this key already exists, return its
    # stored outcome instead of re-executing (prevents double on-chain send).
    if idempotency_key:
        existing = (
            db.query(WithdrawalRecord)
            .filter(WithdrawalRecord.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            return {
                "ok": existing.status in ("completed", "dry_run"),
                "idempotent": True,
                "amount": existing.amount,
                "message": f"Already processed (status={existing.status})",
                "balance_after": existing.balance_after,
                "status": existing.status,
            }

    if hl is None:
        hl = HyperLiquidClient()

    config = get_or_create_config(db)
    balance = hl.get_account_value()
    available = hl.get_withdrawable()

    snap = AccountSnapshot(account_value=balance, withdrawable=available)
    db.add(snap)
    db.commit()

    amount, reason = calculate_manual_all(db, balance, config)
    if amount <= 0:
        return {"ok": False, "message": reason, "amount": 0}

    record = WithdrawalRecord(
        amount=amount,
        withdrawal_type="manual_all",
        status="pending",
        balance_before=balance,
        idempotency_key=idempotency_key,
    )
    db.add(record)
    db.commit()

    result = hl.withdraw_to_wallet(amount)
    # BUG #3: dry_run returns truthy dict — must NOT mark completed
    if result and result.get("status") != "dry_run":
        record.status = "completed"
        record.balance_after = balance - amount
        record.note = reason
        db.commit()
        set_baseline(db, balance - amount, "Post-manual-all baseline")
        add_log(f"[WITHDRAWAL] Manual ALL withdrew ${amount:.2f}", "trade")
        return {"ok": True, "amount": amount, "message": reason, "balance_after": balance - amount}
    else:
        record.status = "failed"
        db.commit()
        add_log(f"[WITHDRAWAL] Manual ALL failed for ${amount:.2f}", "error")
        return {"ok": False, "amount": amount, "message": "Withdrawal execution failed"}


def get_withdrawal_history(db: Session, limit: int = 50) -> list:
    records = (
        db.query(WithdrawalRecord)
        .order_by(WithdrawalRecord.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "amount": r.amount,
            "type": r.withdrawal_type,
            "status": r.status,
            "balance_before": r.balance_before,
            "balance_after": r.balance_after,
            "note": r.note,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
        }
        for r in records
    ]
