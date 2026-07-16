"""
Withdrawal calculator for strategy-engine.
"""

from datetime import datetime, timedelta, timezone
from typing import Tuple, Optional

from sqlalchemy.orm import Session

from instances.models import (
    CapitalBaseline,
    WithdrawalConfig,
    WithdrawalRecord,
    AccountSnapshot,
)


DEFAULT_PHASED_RULES = [
    {"min": 0, "max": 100000, "withdrawal_rate": 0.0, "compound_rate": 1.0},
    {"min": 100000, "max": 500000, "withdrawal_rate": 0.25, "compound_rate": 0.75},
    {"min": 500000, "max": 1000000, "withdrawal_rate": 0.50, "compound_rate": 0.50},
    {"min": 1000000, "max": None, "withdrawal_rate": 0.55, "compound_rate": 0.45},
]


def get_or_create_config(db: Session) -> WithdrawalConfig:
    config = db.query(WithdrawalConfig).first()
    if not config:
        config = WithdrawalConfig(
            cycle_days=30,
            auto_withdraw_enabled=False,
            withdrawal_rate=0.50,
            compound_rate=0.50,
            min_capital=10000.0,
            phased_rules_json=DEFAULT_PHASED_RULES,
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def get_current_baseline(db: Session) -> Optional[CapitalBaseline]:
    return (
        db.query(CapitalBaseline)
        .order_by(CapitalBaseline.created_at.desc())
        .first()
    )


def set_baseline(db: Session, value: float, note: str = "") -> CapitalBaseline:
    baseline = CapitalBaseline(baseline_value=value, note=note)
    db.add(baseline)
    db.commit()
    db.refresh(baseline)
    return baseline


def profit_since_baseline(db: Session, current_balance: float) -> float:
    baseline = get_current_baseline(db)
    if not baseline:
        return 0.0
    return max(0.0, current_balance - baseline.baseline_value)


def get_effective_rate(db: Session, balance: float, config: WithdrawalConfig) -> float:
    rules = config.phased_rules_json or DEFAULT_PHASED_RULES
    if not isinstance(rules, list):
        return config.withdrawal_rate
    for rule in rules:
        max_val = rule["max"]
        if max_val is None:
            if balance >= rule["min"]:
                return rule["withdrawal_rate"]
        elif rule["min"] <= balance < max_val:
            return rule["withdrawal_rate"]
    return config.withdrawal_rate


def calculate_withdrawal(
    balance: float,
    profit: float,
    config: WithdrawalConfig,
    force_rate: Optional[float] = None,
) -> Tuple[float, str]:
    if balance < config.min_capital:
        return 0.0, "Balance below minimum capital threshold"
    if profit <= 0:
        return 0.0, "No profit to withdraw"

    rate = force_rate if force_rate is not None else get_effective_rate(db=None, balance=balance, config=config)
    withdrawal = profit * rate
    max_safe = balance - config.min_capital
    withdrawal = min(withdrawal, max_safe)

    if withdrawal <= 0:
        return 0.0, "No safe withdrawal amount available"
    return withdrawal, "Approved"


def calculate_manual_50(
    db: Session,
    balance: float,
    config: WithdrawalConfig = None,
) -> Tuple[float, str]:
    if config is None:
        config = get_or_create_config(db)
    profit = profit_since_baseline(db, balance)
    return calculate_withdrawal(balance, profit, config, force_rate=config.withdrawal_rate)


def calculate_manual_all(
    db: Session,
    balance: float,
    config: WithdrawalConfig = None,
) -> Tuple[float, str]:
    if config is None:
        config = get_or_create_config(db)
    if balance <= config.min_capital:
        return 0.0, "No available profit above minimum"
    withdrawal = balance - config.min_capital
    return withdrawal, "Complete"


def get_next_withdrawal_date(last_withdrawal_at: Optional[datetime], cycle_days: int) -> Optional[datetime]:
    if not last_withdrawal_at:
        return datetime.now(timezone.utc) + timedelta(days=cycle_days)
    return last_withdrawal_at + timedelta(days=cycle_days)


def days_until_next_withdrawal(config: WithdrawalConfig, last_record: Optional[WithdrawalRecord]) -> int:
    last_at = last_record.timestamp if last_record else None
    next_at = get_next_withdrawal_date(last_at, config.cycle_days)
    if not next_at:
        return config.cycle_days
    delta = next_at - datetime.now(timezone.utc)
    return max(0, delta.days)


def generate_projection(
    start_capital: float,
    monthly_return: float = 0.30,
    withdrawal_rate: float = 0.50,
    months: int = 24,
) -> list:
    rows = []
    balance = start_capital
    cumulative_withdrawn = 0.0
    for month in range(1, months + 1):
        profit = balance * monthly_return
        withdrawal = profit * withdrawal_rate
        compound = profit - withdrawal
        balance += compound
        cumulative_withdrawn += withdrawal
        rows.append(
            {
                "month": month,
                "start_capital": balance - compound,
                "profit": profit,
                "withdrawal": withdrawal,
                "compound": compound,
                "end_capital": balance,
                "cumulative_withdrawn": cumulative_withdrawn,
            }
        )
    return rows
