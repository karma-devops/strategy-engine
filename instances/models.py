"""
SQLAlchemy models for strategy-engine instances.
"""

import os
import uuid
from datetime import datetime, timezone

from cryptography.fernet import Fernet
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Float,
    Integer,
    Boolean,
    DateTime,
    Text,
    JSON,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from config import config


Base = declarative_base()


def _now_utc():
    return datetime.now(timezone.utc)


def _get_fernet():
    key = config.INSTANCE_SECRET_KEY
    if not key:
        return None
    return Fernet(key)


class Instance(Base):
    __tablename__ = "instances"

    slug = Column(String(32), primary_key=True)
    name = Column(String(128), nullable=False)
    token = Column(String(64), nullable=False)
    strategy_id = Column(String(64), nullable=False)
    mode = Column(String(32), default="Scalp")
    profile = Column(String(64), default="aggressive_8_3")
    timeframe = Column(String(16), default="15m")
    leverage = Column(Integer, default=10)
    max_position_pct = Column(Float, default=0.97)
    poll_interval_seconds = Column(Integer, default=30)
    activation = Column(Integer, default=8)
    offset = Column(Integer, default=3)
    dry_run = Column(Boolean, default=True)
    enabled = Column(Boolean, default=True)
    status = Column(String(32), default="stopped")  # stopped, running, error, killed
    hyperliquid_private_key_encrypted = Column(Text, nullable=True)
    account_address = Column(String(64), nullable=True)
    withdrawal_address = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=_now_utc)
    updated_at = Column(DateTime, default=_now_utc, onupdate=_now_utc)

    # Live position cache (updated by runner on each tick)
    position_side = Column(String(8), nullable=True)
    position_size = Column(Float, default=0.0)
    entry_price = Column(Float, default=0.0)
    mark_price = Column(Float, default=0.0)
    unrealized_pnl = Column(Float, default=0.0)
    unrealized_pnl_pct = Column(Float, default=0.0)

    def get_private_key(self) -> str | None:
        """Decrypt per-instance private key if present."""
        if not self.hyperliquid_private_key_encrypted:
            return None
        fernet = _get_fernet()
        if not fernet:
            raise RuntimeError("INSTANCE_SECRET_KEY not configured; cannot decrypt per-instance key")
        return fernet.decrypt(self.hyperliquid_private_key_encrypted.encode()).decode()

    def set_private_key(self, private_key: str | None):
        """Encrypt and store per-instance private key. Pass None to clear."""
        if not private_key:
            self.hyperliquid_private_key_encrypted = None
            return
        fernet = _get_fernet()
        if not fernet:
            raise RuntimeError("INSTANCE_SECRET_KEY not configured; cannot encrypt per-instance key")
        self.hyperliquid_private_key_encrypted = fernet.encrypt(private_key.encode()).decode()

    def get_account_address(self) -> str | None:
        return self.account_address or config.ACCOUNT_ADDRESS

    def get_withdrawal_address(self) -> str | None:
        return self.withdrawal_address or self.account_address or config.ACCOUNT_ADDRESS

    def mask_address(self, addr: str | None) -> str:
        if not addr:
            return ""
        if len(addr) <= 10:
            return addr
        return f"{addr[:6]}...{addr[-4:]}"


class KillSwitchState(Base):
    __tablename__ = "kill_switch_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scope = Column(String(32), nullable=False, unique=True)  # global, withdrawals
    active = Column(Boolean, default=False)
    reason = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=_now_utc, onupdate=_now_utc)


class Signal(Base):
    __tablename__ = "signals"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    instance_id = Column(String(32), nullable=False, index=True)
    direction = Column(String(8), nullable=False)  # BUY, SELL, NEUTRAL
    signal = Column(Float, default=0.0)
    trade_active = Column(Boolean, default=False)
    executed = Column(Boolean, default=False)
    metadata_json = Column(JSON, default=dict)
    reasoning_text = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=_now_utc)


class CapitalBaseline(Base):
    __tablename__ = "capital_baselines"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    baseline_value = Column(Float, nullable=False)
    note = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=_now_utc)


class WithdrawalConfig(Base):
    __tablename__ = "withdrawal_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cycle_days = Column(Integer, default=30)
    auto_withdraw_enabled = Column(Boolean, default=False)
    withdrawal_rate = Column(Float, default=0.50)
    compound_rate = Column(Float, default=0.50)
    min_capital = Column(Float, default=10000.0)
    phased_rules_json = Column(JSON, default=dict)
    next_scheduled_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=_now_utc, onupdate=_now_utc)


class WithdrawalRecord(Base):
    __tablename__ = "withdrawal_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    instance_id = Column(String(32), nullable=True, index=True)
    amount = Column(Float, nullable=False)
    withdrawal_type = Column(String(32), nullable=False)
    status = Column(String(32), default="pending")
    balance_before = Column(Float, nullable=True)
    balance_after = Column(Float, nullable=True)
    note = Column(String(255), nullable=True)
    timestamp = Column(DateTime, default=_now_utc)


class Trade(Base):
    __tablename__ = "trades"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    instance_id = Column(String(32), nullable=False, index=True)
    side = Column(String(8), nullable=False)
    size = Column(Float, default=0.0)
    entry_price = Column(Float, default=0.0)
    exit_price = Column(Float, nullable=True)
    pnl_usd = Column(Float, default=0.0)
    pnl_pct = Column(Float, default=0.0)
    entry_cost = Column(Float, default=0.0)  # estimated exchange fees on entry
    exit_cost = Column(Float, default=0.0)   # estimated exchange fees on exit
    price_diff = Column(Float, default=0.0)   # exit - entry
    signal_id = Column(String(36), nullable=True)
    timestamp = Column(DateTime, default=_now_utc)


class PositionSnapshot(Base):
    __tablename__ = "position_snapshots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    instance_id = Column(String(32), nullable=False, index=True)
    side = Column(String(8), nullable=True)
    size = Column(Float, default=0.0)
    entry_price = Column(Float, default=0.0)
    mark_price = Column(Float, default=0.0)
    unrealized_pnl_usd = Column(Float, default=0.0)
    unrealized_pnl_pct = Column(Float, default=0.0)
    timestamp = Column(DateTime, default=_now_utc)


class AccountSnapshot(Base):
    __tablename__ = "account_snapshots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    instance_id = Column(String(32), nullable=True, index=True)
    account_value = Column(Float, default=0.0)
    withdrawable = Column(Float, default=0.0)
    timestamp = Column(DateTime, default=_now_utc)


class Backtest(Base):
    __tablename__ = "backtests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    instance_slug = Column(String(32), nullable=False, index=True)
    token = Column(String(64), nullable=False)
    strategy_id = Column(String(64), nullable=False)
    timeframe = Column(String(16), nullable=False)
    mode = Column(String(32), nullable=False)
    profile = Column(String(64), nullable=False)
    activation = Column(Integer, default=8)
    offset = Column(Integer, default=3)
    leverage = Column(Integer, default=10)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    status = Column(String(32), default="pending")  # pending, running, done, error
    initial_capital = Column(Float, default=1000.0)
    final_capital = Column(Float, nullable=True)
    total_return_pct = Column(Float, default=0.0)
    win_rate = Column(Float, default=0.0)
    profit_factor = Column(Float, default=0.0)
    max_drawdown_pct = Column(Float, default=0.0)
    total_trades = Column(Integer, default=0)
    sharpe_ratio = Column(Float, default=0.0)
    trades_json = Column(JSON, default=list)
    equity_curve_json = Column(JSON, default=list)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_now_utc)
    completed_at = Column(DateTime, nullable=True)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    instance_slug = Column(String(32), nullable=True, index=True)
    level = Column(String(16), nullable=False)  # CRITICAL, WARNING, INFO
    category = Column(String(32), nullable=False)  # drawdown, winrate, profitfactor, notrades, losses, equity_high, withdrawal, system
    message = Column(Text, nullable=False)
    metric_value = Column(Float, nullable=True)
    threshold = Column(Float, nullable=True)
    dismissed = Column(Boolean, default=False)
    internal_note = Column(Text, nullable=True)  # operator-facing/internal context only
    created_at = Column(DateTime, default=_now_utc)
    dismissed_at = Column(DateTime, nullable=True)


class MonitoringScore(Base):
    __tablename__ = "monitoring_scores"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    instance_slug = Column(String(32), nullable=False, index=True)
    period_days = Column(Integer, default=30)
    return_pct = Column(Float, default=0.0)
    win_rate = Column(Float, default=0.0)
    profit_factor = Column(Float, default=0.0)
    max_drawdown_pct = Column(Float, default=0.0)
    total_trades = Column(Integer, default=0)
    consistency = Column(Float, default=0.0)
    score = Column(Float, default=0.0)
    status = Column(String(16), default="HOLD")  # OPTIMAL, HOLD, MONITOR, UNDERPERFORM
    computed_at = Column(DateTime, default=_now_utc)


class RotationRecommendation(Base):
    __tablename__ = "rotation_recommendations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    instance_slug = Column(String(32), nullable=False, index=True)
    action = Column(String(16), nullable=False)  # INCREASE, REDUCE, HOLD
    reason = Column(Text, nullable=False)
    suggested_allocation_pct = Column(Float, nullable=True)
    current_allocation_pct = Column(Float, nullable=True)
    approved = Column(Boolean, nullable=True)  # None = pending, True/False = operator decision
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now_utc)


def get_engine():
    engine = create_engine(
        config.DATABASE_URL,
        connect_args={"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {},
        echo=False,
    )
    if config.DATABASE_URL.startswith("sqlite"):
        with engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL")
    return engine


def init_db():
    engine = get_engine()
    Base.metadata.create_all(engine)
    return engine


engine = init_db()
SessionLocal = sessionmaker(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
