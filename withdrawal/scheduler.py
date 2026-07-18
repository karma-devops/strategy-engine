"""
Withdrawal scheduler for strategy-engine.
"""

import threading
import time
from datetime import datetime, timezone

from sqlalchemy.orm import sessionmaker

from instances.models import engine, WithdrawalRecord, AccountSnapshot
from withdrawal.calculator import (
    get_or_create_config,
    calculate_withdrawal,
    get_next_withdrawal_date,
    set_baseline,
)
from core.exchange import HyperLiquidClient
from instances.events import add_log
from api.killswitch import is_withdrawal_killed

Session = sessionmaker(bind=engine)


class WithdrawalScheduler:
    def __init__(self):
        self._thread = None
        self._stop_event = threading.Event()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self):
        add_log("[WITHDRAWAL] Scheduler started", "info")
        while not self._stop_event.is_set():
            try:
                self._check_and_execute()
            except Exception as e:
                add_log(f"[WITHDRAWAL] Scheduler error: {e}", "error")
            self._stop_event.wait(3600)  # check every hour
        add_log("[WITHDRAWAL] Scheduler stopped", "info")

    def _check_and_execute(self):
        db = Session()
        try:
            # BUG #2: kill-switch must block auto-withdrawals entirely
            if is_withdrawal_killed(db):
                add_log("[WITHDRAWAL] Auto-withdraw skipped — kill switch active", "info")
                return

            config = get_or_create_config(db)
            if not config.auto_withdraw_enabled:
                return

            last_record = (
                db.query(WithdrawalRecord)
                .filter(WithdrawalRecord.status == "completed")
                .order_by(WithdrawalRecord.timestamp.desc())
                .first()
            )

            next_due = get_next_withdrawal_date(
                last_record.timestamp if last_record else None,
                config.cycle_days,
            )
            # BUG #19: persist the computed next-scheduled date so the API
            # doesn't always return null. Write it regardless of whether we
            # act this tick (it's the planned next run).
            config.next_scheduled_at = next_due
            db.commit()
            if not next_due or datetime.now(timezone.utc) < next_due:
                return

            hl = HyperLiquidClient()
            balance = hl.get_account_value()
            account_snap = AccountSnapshot(
                account_value=balance,
                withdrawable=hl.get_withdrawable(),
            )
            db.add(account_snap)

            amount, reason = calculate_withdrawal(
                balance,
                balance - (get_current_baseline_value(db) or balance),
                config,
            )
            if amount <= 0:
                add_log(f"[WITHDRAWAL] Auto-withdraw skipped: {reason}", "info")
                return

            record = WithdrawalRecord(
                amount=amount,
                withdrawal_type="auto",
                status="pending",
                balance_before=balance,
            )
            db.add(record)
            db.commit()

            result = hl.withdraw_to_wallet(amount)
            # BUG #3: dry_run returns truthy dict {"status":"dry_run",...}
            # — must NOT mark completed or reset baseline in dry-run mode
            if result and result.get("status") != "dry_run":
                record.status = "completed"
                record.balance_after = balance - amount
                record.note = reason
                db.commit()
                set_baseline(db, balance - amount, "Post-auto-withdrawal baseline")
                add_log(f"[WITHDRAWAL] Auto-withdraw {amount:.2f} completed", "trade")
            elif result and result.get("status") == "dry_run":
                record.status = "dry_run"
                record.balance_after = balance
                record.note = f"DRY_RUN: {reason}"
                db.commit()
                add_log(f"[WITHDRAWAL] Auto-withdraw {amount:.2f} DRY_RUN (no baseline reset)", "info")
            else:
                record.status = "failed"
                db.commit()
                add_log(f"[WITHDRAWAL] Auto-withdraw {amount:.2f} failed", "error")
        finally:
            db.close()


def get_current_baseline_value(db):
    from withdrawal.calculator import get_current_baseline

    baseline = get_current_baseline(db)
    return baseline.baseline_value if baseline else None


scheduler = WithdrawalScheduler()
