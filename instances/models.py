"""
SQLAlchemy models for strategy-engine instances.
"""

import os
import json
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


class User(Base):
    """Multi-tenant account aggregate root.

    Owns global settings: portfolio start balance and default execution mode.
    Instances and backtests reference a user via user_id. Currently a single
    operator ("operator") is seeded; the model is tenant-ready (unique username).
    """
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(64), nullable=False, unique=True, index=True)
    display_name = Column(String(128), nullable=True)
    # Global portfolio baseline for equity-curve / drawdown math
    start_balance = Column(Float, default=1000.0)
    # Default execution mode for new instances (True = Paper Trading)
    default_dry_run = Column(Boolean, default=True)
    # Account settings (Phase 8b)
    email = Column(String(256), nullable=True, unique=True, index=True)  # for 2FA / notifications; unique per T2-4
    password_hash = Column(String(256), nullable=True)       # for login auth (future)
    withdrawal_eth_address = Column(String(64), nullable=True)  # same as metamask env
    avatar_emoji = Column(String(16), nullable=True)         # emoji icon selector
    avatar_url = Column(String(512), nullable=True)          # uploaded image (future)
    plan = Column(String(32), default="free")                # billing: free/pro/enterprise
    twofa_enabled = Column(Boolean, default=False)           # 2FA status
    email_verified = Column(Boolean, default=False)           # email confirmation status
    email_verify_token = Column(String(128), nullable=True, index=True)  # email verify token
    # Phase 9: per-user model selection
    assistant_model = Column(String(64), default="glm-5.1")  # chat model (Assistant + dashboard)
    coder_model = Column(String(64), default="glm-5.1")      # Pine->Python conversion model (Studio)
    # Phase 18: per-user API key (auto-generated on signup)
    # api_key stores Fernet-encrypted key; api_key_hash stores SHA256 for O(1) lookup
    api_key = Column(Text, nullable=True)  # Fernet-encrypted puls_<uuid4>_key
    api_key_hash = Column(String(64), nullable=True, unique=True, index=True)  # SHA256 hex digest
    # Per-user display timezone (IANA name, e.g. "GMT", "Asia/Jakarta"). Defaults to GMT.
    timezone = Column(String(64), default="GMT")
    # Theme preference (pulsr, hyperfluid, portrait)
    theme = Column(String(32), default="pulsr")
    created_at = Column(DateTime, default=_now_utc)
    updated_at = Column(DateTime, default=_now_utc, onupdate=_now_utc)


class Credential(Base):
    """Multi-tenant encrypted credential store.

    One table for all secret types (eth_wallet, hl_api, ai_provider, app_api_key).
    encrypted_data is a Fernet-encrypted JSON blob. masked_preview stores a safe
    display string (e.g. "0xA871...8078") so the frontend never sees raw secrets.
    Multi-tenant: every row is scoped by user_id. Operator (user 1) gets env-var
    fallback via config.get_credential(); other tenants must store in DB.
    """
    __tablename__ = "credentials"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False, index=True)
    type = Column(String(32), nullable=False, index=True)  # eth_wallet | hl_api | ai_provider | app_api_key
    label = Column(String(128), nullable=False)
    priority = Column(Integer, default=0)  # 0=primary, 1=secondary, 2=tertiary
    encrypted_data = Column(Text, nullable=False)  # Fernet-encrypted JSON
    masked_preview = Column(String(128), nullable=True)  # safe display value
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_now_utc)
    updated_at = Column(DateTime, default=_now_utc, onupdate=_now_utc)

    @staticmethod
    def _mask(value: str, head: int = 6, tail: int = 4) -> str:
        if not value:
            return ""
        if len(value) <= head + tail + 1:
            return value
        return value[:head] + "..." + value[-tail:]

    def encrypt_and_store(self, data: dict, user_id: str, password: str = None):
        """Encrypt a dict into encrypted_data. password=raw secret for masking."""
        fernet = _get_fernet()
        if not fernet:
            raise RuntimeError("INSTANCE_SECRET_KEY not configured; cannot encrypt credential")
        self.user_id = user_id
        self.encrypted_data = fernet.encrypt(json.dumps(data).encode()).decode()
        # masked_preview derived from type-specific field
        if self.type == "eth_wallet":
            self.masked_preview = self._mask(data.get("address", ""))
        elif self.type == "hl_api":
            self.masked_preview = self._mask(data.get("account_address", ""))
        elif self.type == "ai_provider":
            self.masked_preview = self._mask(data.get("api_key", ""), head=8, tail=0)
        elif self.type == "app_api_key":
            self.masked_preview = self._mask(data.get("key", ""), head=6, tail=0)
        else:
            self.masked_preview = "[encrypted]"

    def decrypt(self) -> dict:
        fernet = _get_fernet()
        if not fernet:
            raise RuntimeError("INSTANCE_SECRET_KEY not configured; cannot decrypt credential")
        raw = fernet.decrypt(self.encrypted_data.encode()).decode()
        # New credentials are stored as JSON; legacy blobs used Python repr.
        # Try JSON first, fall back to ast.literal_eval for pre-migration data.
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            import ast
            return ast.literal_eval(raw)


class ChatSession(Base):
    """Per-user assistant chat session. Cap 10 per user (oldest pruned on create)."""
    __tablename__ = "chat_sessions"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False, index=True)
    title = Column(String(128), default="New chat")
    context = Column(String(32), default="assistant")  # assistant | studio | backtester | dashboard
    created_at = Column(DateTime, default=_now_utc)
    updated_at = Column(DateTime, default=_now_utc, onupdate=_now_utc)


class ChatMessage(Base):
    """A single turn in a chat session."""
    __tablename__ = "chat_messages"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    role = Column(String(16), nullable=False)  # user | assistant
    content = Column(Text, nullable=False)
    model = Column(String(64), nullable=True)  # model used for assistant reply
    created_at = Column(DateTime, default=_now_utc)


class Instance(Base):
    __tablename__ = "instances"

    slug = Column(String(32), primary_key=True)
    user_id = Column(String(36), nullable=True, index=True)  # owning User (multi-tenant)
    hl_credential_id = Column(String(36), nullable=True, index=True)  # FK → credentials.id (per-engine HL key)
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
    # Manual start balance for PnL tracking (independent of HL account value)
    start_balance = Column(Float, default=0.0)
    balance_mode = Column(String(16), default="live")  # "live" or "manual"
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
    liquidation_price = Column(Float, default=0.0)   # HL liquidation price (risk metric)
    stop_loss = Column(Float, nullable=True)           # strategy stop-loss price (from _active_trade)
    take_profit = Column(Float, nullable=True)         # strategy take-profit price (from _active_trade)

    # Per-instance strategy parameter overrides (Pine input.* equivalent)
    # JSON dict: {"engine_mode": "Scalp", "risk_profile": "Scalp Aggressive (8/3)", ...}
    # Applied via strategy_class(**config) at instantiation.
    strategy_config = Column(JSON, default=dict, nullable=True)

    # Snapshot + image capture (per-instance visual + state snapshots)
    snapshot_data = Column(JSON, default=dict, nullable=True)  # latest state snapshot
    snapshot_image_url = Column(String(512), nullable=True)  # URL or path to snapshot image
    snapshot_at = Column(DateTime, nullable=True)  # when last snapshot was taken

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

    def get_resolved_hl_credentials(self) -> tuple[str | None, str | None]:
        """Resolve HL private_key + account_address for this engine.

        Priority:
          1. If hl_credential_id is set, decrypt that Credential row (DB-stored).
          2. Else fall back to this instance's own encrypted key (legacy path).
          3. Else None -> caller falls back to global env client.
        'Global' in the UI = hl_credential_id is NULL -> returns None -> env default.
        """
        if self.hl_credential_id:
            db = SessionLocal()
            try:
                cred = db.query(Credential).filter(Credential.id == self.hl_credential_id).first()
            finally:
                db.close()
            if cred and cred.is_active:
                d = cred.decrypt()
                return d.get("private_key"), d.get("account_address")
        pk = self.get_private_key()
        addr = self.get_account_address()
        if pk or addr:
            return pk, addr
        return None, None


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
    dry_run = Column(Boolean, default=True)  # P14: paper vs live separation
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
    idempotency_key = Column(String(64), nullable=True, unique=True, index=True)
    timestamp = Column(DateTime, default=_now_utc)


class Trade(Base):
    __tablename__ = "trades"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    instance_id = Column(String(32), nullable=False, index=True)
    user_id = Column(String(36), nullable=True, index=True)  # owning User (multi-tenant)
    side = Column(String(8), nullable=False)
    size = Column(Float, default=0.0)
    entry_price = Column(Float, default=0.0)
    exit_price = Column(Float, nullable=True)
    pnl_usd = Column(Float, default=0.0)
    pnl_pct = Column(Float, default=0.0)
    entry_cost = Column(Float, default=0.0)  # estimated exchange fees on entry
    exit_cost = Column(Float, default=0.0)   # estimated exchange fees on exit
    fee = Column(Float, default=0.0)  # total HL fees (maker + taker) for both legs
    price_diff = Column(Float, default=0.0)   # exit - entry
    signal_id = Column(String(36), nullable=True)
    dry_run = Column(Boolean, default=True)  # P14: paper vs live separation
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
    user_id = Column(String(36), nullable=True, index=True)  # owning User (multi-tenant)
    account_value = Column(Float, default=0.0)
    withdrawable = Column(Float, default=0.0)
    dry_run = Column(Boolean, default=True)  # P14: paper vs live separation
    source = Column(String(16), default="perp")  # B1: 'perp' (HL-native perp-only) vs 'total' (perps+spot)
    timestamp = Column(DateTime, default=_now_utc)


class Backtest(Base):
    __tablename__ = "backtests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    instance_slug = Column(String(32), nullable=False, index=True)
    user_id = Column(String(36), nullable=True, index=True)  # owning User (multi-tenant)
    # Distinguishes historical backtests from live Paper-Trading forward tests
    kind = Column(String(16), default="backtest")  # "backtest" | "forward_test"
    is_paper = Column(Boolean, default=False)  # True when produced by a Paper-Trading instance
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



class CandleCache(Base):
    """Cache OHLCV candles from HL to enable longer backtests beyond the 60-day API limit."""
    __tablename__ = "candle_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(64), nullable=False, index=True)
    timeframe = Column(String(16), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)  # candle open time
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, default=0.0)
    fetched_at = Column(DateTime, default=_now_utc)


class Strategy(Base):
    """User-uploaded strategy (PineScript-first, Python conversion via Studio)."""
    __tablename__ = "strategies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=True, index=True)
    name = Column(String(128), nullable=False)
    strategy_id = Column(String(64), nullable=False, unique=True, index=True)
    pine_source = Column(Text, nullable=False)
    python_source = Column(Text, nullable=True)
    documentation = Column(Text, nullable=True)
    status = Column(String(16), default="pending")  # pending, active, error
    parameters = Column(JSON, default=dict)
    # Clone/versioning support
    parent_strategy_id = Column(String(64), nullable=True, index=True)  # FK to parent Strategy.strategy_id
    version = Column(String(16), default="1.0")  # Semantic version (1.0, 1.1, 2.0)
    created_at = Column(DateTime, default=_now_utc)
    updated_at = Column(DateTime, default=_now_utc, onupdate=_now_utc)


class OHLCData(Base):
    """Persisted historical OHLCV candles per token + timeframe.

    Accumulates over time so backtests can use longer history than a single
    live fetch allows. Upserted by token/timeframe/timestamp (idempotent).
    """
    __tablename__ = "ohlc_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(64), nullable=False, index=True)
    timeframe = Column(String(16), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, default=0.0)

    __table_args__ = (
        __import__("sqlalchemy").UniqueConstraint("token", "timeframe", "timestamp", name="uq_ohlc_token_tf_ts"),
    )


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
    Base.metadata.create_all(engine)  # creates new tables; no-op for existing
    # SQLite has no ALTER ADD COLUMN IF NOT EXISTS — apply migration idempotently
    _migrate_columns(engine)
    return engine


def _migrate_columns(engine):
    """Add columns introduced after initial deploy (SQLite-safe, idempotent)."""
    from sqlalchemy import inspect, text
    desired = {
        "instances": [("user_id", "VARCHAR(36)"), ("hl_credential_id", "VARCHAR(36)"), ("strategy_config", "JSON"), ("snapshot_data", "JSON"), ("snapshot_image_url", "VARCHAR(512)"), ("snapshot_at", "DATETIME")],
        "account_snapshots": [("user_id", "VARCHAR(36)"), ("dry_run", "BOOLEAN"), ("source", "VARCHAR(16)")],
        "backtests": [
            ("user_id", "VARCHAR(36)"),
            ("kind", "VARCHAR(16)"),
            ("is_paper", "BOOLEAN"),
        ],
        "strategies": [("parent_strategy_id", "VARCHAR(64)"), ("version", "VARCHAR(16)")],
        "trades": [("user_id", "VARCHAR(36)"), ("dry_run", "BOOLEAN")],
        "signals": [("dry_run", "BOOLEAN")],
        "users": [
            ("api_key", "TEXT"),
            ("api_key_hash", "VARCHAR(64)"),
            ("email", "VARCHAR(256)"),
            ("password_hash", "VARCHAR(256)"),
            ("withdrawal_eth_address", "VARCHAR(64)"),
            ("avatar_emoji", "VARCHAR(16)"),
            ("avatar_url", "VARCHAR(512)"),
            ("plan", "VARCHAR(32)"),
            ("twofa_enabled", "BOOLEAN"),
            ("email_verified", "BOOLEAN"),
            ("email_verify_token", "VARCHAR(128)"),
            ("assistant_model", "VARCHAR(64)"),
            ("coder_model", "VARCHAR(64)"),
            ("timezone", "VARCHAR(64)"),
        ],
        "chat_sessions": [
            ("user_id", "VARCHAR(36)"),
            ("title", "VARCHAR(128)"),
            ("context", "VARCHAR(32)"),
        ],
        "chat_messages": [
            ("session_id", "VARCHAR(36)"),
            ("user_id", "VARCHAR(36)"),
            ("role", "VARCHAR(16)"),
            ("content", "TEXT"),
            ("model", "VARCHAR(64)"),
        ],
    }
    insp = inspect(engine)
    with engine.begin() as conn:
        for table, cols in desired.items():
            existing = {c["name"] for c in insp.get_columns(table)}
            for col, ctype in cols:
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ctype}"))
        # T2-4: enforce unique email on existing DBs (idempotent; SQLite allows
        # multiple NULLs in a unique column, so existing NULL emails are safe).
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)"
        ))


engine = init_db()
SessionLocal = sessionmaker(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def generate_api_key() -> str:
    """Generate a PULS-R API key in the format puls_<uuid4>_key."""
    return f"puls_{uuid.uuid4().hex[:24]}_key"


def hash_api_key(plaintext: str) -> str:
    """SHA256 hash of API key for O(1) DB lookup (no plaintext stored)."""
    import hashlib
    return hashlib.sha256(plaintext.encode()).hexdigest()


def hash_password(plaintext: str) -> str:
    """Scrypt-hash a password for storage. Returns salt:hash (both hex)."""
    import hashlib, os
    salt = os.urandom(16)
    dk = hashlib.scrypt(plaintext.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
    return f"{salt.hex()}:{dk.hex()}"


def verify_password(plaintext: str, stored: str) -> bool:
    """Verify a plaintext password against a stored salt:hash string."""
    import hashlib, hmac
    try:
        salt_hex, hash_hex = stored.split(":")
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.scrypt(plaintext.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


def encrypt_api_key(plaintext: str) -> str:
    """Fernet-encrypt an API key for storage."""
    fernet = _get_fernet()
    return fernet.encrypt(plaintext.encode()).decode()


def decrypt_api_key(encrypted: str) -> str:
    """Fernet-decrypt an API key for display."""
    fernet = _get_fernet()
    return fernet.decrypt(encrypted.encode()).decode()


def store_user_api_key(user, plaintext_key: str, db):
    """Set a user's API key: encrypt for storage, hash for lookup."""
    user.api_key = encrypt_api_key(plaintext_key)
    user.api_key_hash = hash_api_key(plaintext_key)
    db.commit()


def find_user_by_api_key(plaintext_key: str, db):
    """Look up a user by plaintext API key via hash match."""
    key_hash = hash_api_key(plaintext_key)
    return db.query(User).filter(User.api_key_hash == key_hash).first()


def get_user_or_seed_user(db, username: str) -> "User":
    """Resolve the AUTHENTICATED session user (NOT the operator singleton).

    Used by all multi-tenant routes so a logged-in user only ever sees their
    own data. Only returns the operator when the authenticated username is
    literally 'operator' (Basic-auth operator / true admin). Never silently
    returns operator for a normal user — that was the cross-user leak.

    Returns None if the username does not map to a real user (caller 404s).
    """
    if not username or username == "operator":
        return get_or_seed_operator(db)
    return db.query(User).filter(User.username == username).first()


def seed_user_fleet(user: "User") -> list:
    """Seed a NEW user's starter fleet: exactly ONE engine — 'Engine HYPE v1'.

    Engine HYPE v1: token HYPE, strategy strategy_v1 (v1 strategy), 30m timeframe,
    paper (dry_run) by default, owned by the user (user_id). No operator keys,
    no shared credentials. Called once at signup.
    """
    db = SessionLocal()
    try:
        existing = db.query(Instance).filter(Instance.user_id == user.id).first()
        if existing:
            return []  # idempotent — already seeded
        inst = Instance(
            slug=f"engine-hype-v1-{user.id[:8]}",
            user_id=user.id,
            name="Engine HYPE v1",
            token="HYPE",
            strategy_id="strategy_v1",
            mode="Scalp",
            profile="aggressive_8_3",
            timeframe="30m",
            leverage=5,
            max_position_pct=0.97,
            poll_interval_seconds=30,
            dry_run=True,
            enabled=True,
            status="stopped",
        )
        db.add(inst)
        db.commit()
        db.refresh(inst)
        return [inst.slug]
    finally:
        db.close()


def get_or_seed_operator(db=None) -> "User":
    """Return the singleton operator user, seeding it on first run.

    Multi-tenant ready: looks up username "operator"; creates if missing.
    Pass an existing session or a transient one is opened/closed internally.
    """
    own = db is None
    if own:
        db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "operator").first()
        if user is None:
            plaintext_key = generate_api_key()
            user = User(
                username="operator",
                display_name="Operator",
                start_balance=5.0,
                default_dry_run=True,
                password_hash=hash_password("operator"),  # seed so /login form works (Basic Auth + form parity)
                api_key=encrypt_api_key(plaintext_key),
                api_key_hash=hash_api_key(plaintext_key),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        elif not user.api_key:
            # Backfill: generate API key for existing users without one
            plaintext_key = generate_api_key()
            user.api_key = encrypt_api_key(plaintext_key)
            user.api_key_hash = hash_api_key(plaintext_key)
            db.commit()
            db.refresh(user)
        elif not user.password_hash:
            # Backfill: seed operator password so /login form works on existing DBs
            user.password_hash = hash_password("operator")
            db.commit()
            db.refresh(user)
        return user
    finally:
        if own:
            db.close()
