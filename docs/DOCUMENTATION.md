# PULS·R Strategy Engine — Documentation

> **Version:** v0.095
> **Last updated:** 2026-07-16
> **Status:** Repo cleanup in progress (Track 1–2.6 done 2026-07-24: `engine/` → `strategies/`, stale docs archived). LIVE + STABLE. Verify against running server before trusting any claim.

---

## 1. System Overview

PULS·R is a systematic trading engine for HyperLiquid perpetuals. It runs Python strategies that generate trading signals, manages positions via configurable exit logic (stop-loss, trailing stop, take-profit, trend reversal, time-based exit), and provides a full PWA dashboard for monitoring, configuration, and backtesting.

### 1.1 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     PULS·R Strategy Engine                    │
│                                                              │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐  │
│  │  FastAPI  │   │  Jinja2  │   │  SQLite  │   │  Worker  │  │
│  │  (API)   │   │  (PWA)   │   │   (DB)   │   │  (9999)  │  │
│  └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘  │
│       │              │              │              │         │
│       └──────────────┴──────────────┴──────────────┘         │
│                          │                                    │
│                    ┌──────┴──────┐                            │
│                    │ HyperLiquid │                            │
│                    │    SDK     │                            │
│                    └──────┬──────┘                            │
│                           │                                    │
│                    HyperLiquid DEX                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Components

| Component | Port | Purpose | Persistence |
|-----------|------|---------|-------------|
| Dev server | 8792 | Full PWA + API + instance runner | SQLite DB |
| Worker | 9999 | Standalone strategy loop | None (log files) |
| DB | — | All persistent state | SQLite files |

### 1.3 Key Files

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app entrypoint |
| `config.py` | Environment config |
| `strategies/base.py` | Base strategy class (contract) |
| `strategies/v1_3.py` | Eve Engine v1.3 strategy |
| `strategies/v1.py` | Eve Engine v1 strategy |
| `strategies/v6_1.py` | Engine v6.1 PRO strategy |
| `strategies/registry.py` | Strategy registry + mintick detection (dynamic loader) |
| `instances/runner.py` | Instance runner (managed by dev server) |
| `instances/models.py` | All SQLAlchemy models |
| `instances/manager.py` | Instance lifecycle manager |
| `scripts/worker.py` | Standalone worker process |
| `core/exchange.py` | HyperLiquid client |
| `core/market_data.py` | OHLCV data fetcher + cache |
| `core/llm.py` | AI chat client |
| `api/` | REST API routes (11 modules) |
| `app/routes.py` | UI routes |
| `app/templates/` | Jinja2 templates |
| `app/static/` | CSS, JS, PWA assets |
| `backtests/runner.py` | Backtest engine |
| `data/template_empty_STABLE.db` | Empty DB template for multi-tenant |

---

## 2. Three-Port Architecture

Each strategy script is a standalone module that declares three ports. The host system (runner, worker, PWA) is generic — it reads what the strategy declares and acts accordingly.

### 2.1 Port 1: strategy_config

**Purpose:** Static per-instance parameter overrides. Pine `input.*` equivalent.

**Declaration:** `get_parameters()` classmethod on the strategy class.

```python
@classmethod
def get_parameters(cls) -> list[dict]:
    return [
        {"name": "engine_mode", "label": "Engine Mode", "type": "select",
         "options": ["Swing", "Scalp"], "default": "Swing", "group": "Configuration"},
        {"name": "risk_profile", "label": "Risk Profile", "type": "select",
         "options": ["Swing Sniper (36/12)", "Scalp Default (10/4)", ...],
         "default": "Scalp Default (10/4)", "group": "Risk Management"},
        # ... 13 more parameters
    ]
```

**Storage:** `Instance.strategy_config` JSON column in the DB.

**Application:** Strategy instantiation passes config as kwargs:
```python
strategy = strategy_class(**strategy_config)
```

**UI:** Settings modal on the engine detail page renders fields dynamically from `get_parameters()`. Each field type (select, bool, int, float) maps to the correct HTML input.

**API:**
- `GET /api/v2/strategies/{id}/parameters` — returns parameter schema
- `GET /api/v2/instances/{slug}/strategy-config` — returns current config + schema
- `PUT /api/v2/instances/{slug}/strategy-config` — saves config to DB

### 2.2 Port 2: entry_config

**Purpose:** Per-signal output. Generated fresh every poll cycle.

**Returned by:** `generate_signals()` method.

```python
def generate_signals(self, df, symbol="", equity_history=None) -> dict:
    # ... indicator calculations ...
    return {
        "token": symbol,
        "signal": 1.0,           # 0.0 to 1.0
        "direction": "BUY",       # "BUY", "SELL", or "NEUTRAL"
        "metadata": {
            "engine_mode": "Scalp",
            "fast_ema": 0.15012,
            "medm_ema": 0.15015,
            "slow_sma": 0.15049,
            "adx": 21.1,
            "fan_up_trend": False,
            "fan_dn_trend": True,
            "bullish_pin_bar": False,
            "bearish_pin_bar": False,
            "valid_trigger_bull": False,
            "valid_trigger_bear": False,
            "bull_pierce": False,
            "bear_pierce": False,
            "is_hyper_phase": True,
            "is_strategy_cold": False,
            "in_warmup": False,
            # ... more metadata for UI display
        },
        "exit_config": { ... }   # Port 3
    }
```

**Consumer:** Runner/worker reads `direction` to decide entry. Frontend reads `metadata` for display (tooltips, reasoning).

### 2.3 Port 3: exit_config

**Purpose:** Per-signal exit declaration. Strategy declares what exits exist and their parameters. Consumer is neutral — evaluates only what's declared.

**Returned by:** `generate_signals()` as part of the result dict.

```python
"exit_config": {
    "stop_loss_long": 0.14735,       # Hard stop price for long
    "stop_loss_short": 0.15276,      # Hard stop price for short
    "take_profit_long": 0.15221,     # TP price (None if use_fixed_tp=False)
    "take_profit_short": 0.14763,    # TP price (None if use_fixed_tp=False)
    "trail_activation": 8,           # Ticks to activate trailing stop
    "trail_offset": 3,               # Ticks for trail offset
    "use_time_exit": False,          # Time-based exit enabled?
    "time_exit_bars": None,          # Max bars in trade (if use_time_exit)
    "engine_mode": "Scalp",          # Current mode
    "fan_up_trend": False,           # EMA fan stacked bullish
    "fan_dn_trend": True,            # EMA fan stacked bearish
    "fast_ema": 0.15012,             # Current fast EMA value
    "medm_ema": 0.15015,             # Current medium EMA value
}
```

**Exit evaluation order (consumer follows this):**
1. **Stop Loss** — if stop_loss_long/short is not None and candle H/L touches it
2. **Trailing Stop** — if trail_activation > 0: activates after N ticks profit, trails at M ticks behind best price
3. **Take Profit** — if take_profit_long/short is not None and price reaches it
4. **Trend Change** — EMA crossunder/crossover (always evaluated, bar-to-bar)
5. **Time Exit** — if use_time_exit is True and bars_in_trade >= max_bars_in_trade

**NOT evaluated (removed — not in any PineScript):**
- Full fan alignment against position (fabricated)
- Reversal signal / opposite entry signal (fabricated)

---

## 3. Strategy Reference

### 3.1 BaseStrategy Contract

All strategies must subclass `engine.base.BaseStrategy` and implement:

```python
class BaseStrategy(ABC):
    def __init__(self, name: str, **kwargs):
        """kwargs are per-instance config overrides from strategy_config."""

    @classmethod
    def get_parameters(cls) -> list[dict]:
        """Declare configurable parameters for UI rendering."""
        return []

    @classmethod
    def get_default_config(cls) -> dict:
        """Return default parameter values."""
        return {p["name"]: p["default"] for p in cls.get_parameters()}

    @abstractmethod
    def generate_signals(self, df, symbol="", equity_history=None) -> dict:
        """Generate signal for latest bar. Returns {token, signal, direction, metadata, exit_config}."""
```

### 3.2 Engine v1.3 (Eve Engine v1.3)

**File:** `strategies/v1_3.py`
**Class:** `EngineV1_3Strategy`

Full-fidelity translation of the Pine Script Eve Engine v1.3. Supports both Swing and Scalp modes.

**Mode-aware parameters (auto-switch based on engine_mode):**

| Parameter | Swing | Scalp |
|-----------|-------|-------|
| EMA fast/medm/slow | 6/18/50 | 4/9/25 |
| ATR multiplier base | 1.8 | 1.3 |
| Momentum threshold | 18 | 28 |
| Pin bar wick ratio | 0.66 | 0.70 |
| Pin bar body ratio | 0.34 | 0.30 |
| Volume multiplier | 1.0 | 1.3 |

**Risk profiles (6):**

| Profile | Activation | Offset | Mode |
|---------|-----------|--------|------|
| Swing Sniper (36/12) | 36 | 12 | Swing |
| Swing Trend (36/18) | 36 | 18 | Swing |
| Swing Conservative (48/18) | 48 | 18 | Swing |
| Scalp Default (10/4) | 10 | 4 | Scalp |
| Scalp Aggressive (8/3) | 8 | 3 | Scalp |
| Scalp Conservative (12/5) | 12 | 5 | Scalp |

**Entry conditions (3-way AND):**
- LONG: `fan_up_trend AND bull_pierce AND valid_trigger_bull`
- SHORT: `fan_dn_trend AND bear_pierce AND valid_trigger_bear`

**Hyper-growth protocol:** When equity < initial_capital × 50, momentum triggers are enabled (allows entry on strong ADX without pin bar). Overrides cold state.

**Equity tracking:** `equity_history` is appended only on trade close (matches Pine `strategy.closedtrades`). Cap 100 entries. Used for adaptive compounding (efficiency ratio, SMA, std-dev channel).

### 3.3 Engine v1 (Eve Engine v1)

**File:** `strategies/v1.py`
**Class:** `EngineV1Strategy`

Swing/sniper strategy. Default timeframe 1h. Wider stops (36/12). EMA 50/18/6.

### 3.4 Engine v6.1 (Engine v6.1 PRO)

**File:** `strategies/v6_1.py`
**Class:** `EngineV6_1Strategy`

Scalp strategy with dynamic risk multiplier and drawdown protection. EMA 6/18/50. Trail 18/6.

---

## 4. Runner vs Worker

### 4.1 Instance Runner (`instances/runner.py`)

- Runs inside the dev server process (threaded)
- Managed by `InstanceManager`
- Uses the DB for persistence (trades, signals, snapshots)
- Applies `strategy_config` from DB at instantiation
- Records account snapshots every tick
- Emits SSE events for the UI
- Supports reversal re-entry (PineScript semantics)
- One entry per bar (Pine `bar_index > lastEntryBar`)

### 4.2 Standalone Worker (`scripts/worker.py`)

- Runs as a separate process (port 9999)
- No DB — pure strategy loop
- Has its own minimal web UI (config bar, start/stop, SSE log)
- Uses log files (`data/logs/worker_YYYY-MM-DD.log`)
- Same exit logic as runner (neutral consumer)
- Same Pine fidelity fixes (equity_history on close, no grace, one-entry-per-bar)
- API endpoints: `/api/state`, `/api/settings`, `/api/config`

### 4.3 When to Use Which

| Scenario | Use |
|----------|-----|
| Testing a strategy | Dev server (create engine, start/stop) |
| Backtesting | Dev server (POST /api/v2/backtests/run) |
| Live trading (dedicated) | Worker (port 9999) |
| Paper trading | Dev server (dry_run=true) or Worker (DRY_RUN=true) |
| Multi-strategy | Dev server (multiple engines) |
| Single strategy focus | Worker |

---

## 5. API Reference

All API endpoints are under `/api/v2/` and require `X-API-Key` header.

### 5.1 Instances

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v2/instances` | List all instances |
| GET | `/api/v2/instances/active` | List active (running) instances |
| GET | `/api/v2/summary` | Enriched instance summary with position snapshots |
| POST | `/api/v2/instances` | Create instance |
| PUT | `/api/v2/instances/{slug}` | Update instance |
| DELETE | `/api/v2/instances/{slug}` | Delete instance (cascade: trades, signals, backtests, snapshots) |
| POST | `/api/v2/instances/{slug}/start` | Start engine |
| POST | `/api/v2/instances/{slug}/stop` | Stop engine |
| POST | `/api/v2/instances/{slug}/restart` | Restart engine |
| POST | `/api/v2/instances/{slug}/close` | Close position |
| POST | `/api/v2/instances/{slug}/leverage` | Set leverage |
| GET | `/api/v2/instances/{slug}/trades` | Get trades |
| GET | `/api/v2/instances/{slug}/position` | Get position |
| GET | `/api/v2/instances/{slug}/signals` | Get signals |
| GET | `/api/v2/instances/{slug}/balance` | Get balance config |
| POST | `/api/v2/instances/{slug}/balance` | Set balance config |
| GET | `/api/v2/instances/{slug}/strategy-config` | Get strategy config + parameter schema |
| PUT | `/api/v2/instances/{slug}/strategy-config` | Save strategy config |

### 5.2 Strategies

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v2/strategies` | List available strategies |
| GET | `/api/v2/strategies/{id}/parameters` | Get parameter schema for UI |
| GET | `/api/v2/strategies/{id}/presets` | Get presets |
| GET | `/api/v2/presets/fleet` | Get default fleet presets |

### 5.3 Backtests

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v2/backtests/run` | Run backtest |
| GET | `/api/v2/backtests` | List backtests |
| GET | `/api/v2/backtests/{id}` | Get backtest details |
| POST | `/api/v2/backtests/replay` | Bar-replay with tick simulation |

### 5.4 Market Data

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v2/metadata` | All tokens (232) |
| GET | `/api/v2/metadata?query=X` | Token prefix search |
| GET | `/api/v2/metadata?token=X` | Token info (szDecimals, maxLeverage) |

### 5.5 Account & Withdrawals

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v2/account` | Live HL account value |
| GET | `/api/v2/metrics` | Performance metrics |
| GET | `/api/v2/metrics/account` | Account snapshots + drawdown |
| GET | `/api/v2/stats` | System stats |
| GET | `/api/v2/withdrawals/config` | Withdrawal config |
| PUT | `/api/v2/withdrawals/config` | Update withdrawal config |
| GET | `/api/v2/withdrawals/calculate` | Calculate withdrawal |
| GET | `/api/v2/withdrawals/history` | Withdrawal history |
| GET | `/api/v2/withdrawals/projection` | Withdrawal projection |

### 5.6 Kill Switch

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v2/kill/status` | Kill switch status |
| POST | `/api/v2/kill/global` | Global kill (stop all engines) |
| POST | `/api/v2/kill/withdrawals` | Withdrawal kill |
| POST | `/api/v2/kill/reset` | Reset all kill switches |

### 5.7 Monitoring

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v2/monitoring/scores` | Monitoring scores |
| GET | `/api/v2/alerts` | Alerts |

### 5.8 Chat

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v2/chat` | Send message (context-aware) |
| GET | `/api/v2/chat/sessions` | List chat sessions |
| DELETE | `/api/v2/chat/session/{id}` | Delete session |

### 5.9 Credentials

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v2/credentials` | List credentials (masked) |
| POST | `/api/v2/credentials` | Create credential |
| PUT | `/api/v2/credentials/{id}` | Update credential |
| DELETE | `/api/v2/credentials/{id}` | Soft-delete credential |
| POST | `/api/v2/credentials/{id}/test` | Test credential |

### 5.10 Public

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/docs` | Swagger UI |
| GET | `/redoc` | ReDoc |
| GET | `/openapi.json` | OpenAPI spec |
| GET | `/stream` | SSE event stream |

---

## 6. UI Guide

### 6.1 Pages

| URL | Description | Auth |
|-----|-------------|------|
| `/` | Landing page | Public |
| `/login` | Login form | Public |
| `/faq` | FAQ | Public |
| `/about` | About | Public |
| `/app/dashboard` | Fleet overview, Pulse Graph, console | Basic Auth |
| `/app/engines` | Engine fleet grid | Basic Auth |
| `/app/engines/{slug}` | Engine detail (charts, trades, settings) | Basic Auth |
| `/app/strategies` | Strategy overview | Basic Auth |
| `/app/strategies/{id}` | Strategy detail (Pine/Python/Docs) | Basic Auth |
| `/app/strategies/upload` | Upload new strategy | Basic Auth |
| `/app/strategies/studio` | Pine→Python converter | Basic Auth |
| `/app/testing` | Testing hub | Basic Auth |
| `/app/testing/historical` | Backtest form + results | Basic Auth |
| `/app/testing/paper` | Paper trading | Basic Auth |
| `/app/trades` | All trades | Basic Auth |
| `/app/account` | Account overview | Basic Auth |
| `/app/account/settings` | Account settings | Basic Auth |
| `/app/account/secrets` | Credential management | Basic Auth |
| `/app/assistant` | AI chat assistant | Basic Auth |

### 6.2 Settings Modal

The engine detail page has a settings modal (⚙ Edit Settings) that includes:

1. **Basic settings:** Name, Token, Strategy, Timeframe, Leverage, Max Position %, Dry Run, Start Balance, HL Account
2. **Strategy Parameters:** Dynamic fields rendered from `get_parameters()` — engine_mode, risk_profile, momentum_thresh, etc.
3. **Read-only info:** Activation, Offset, Poll, Mode

Save sends two PUT requests:
1. `PUT /api/v2/instances/{slug}` — basic settings
2. `PUT /api/v2/instances/{slug}/strategy-config` — strategy parameters

### 6.3 Chat Widget

The AI assistant is available as a floating bubble on all pages. It's context-aware:
- **Strategy Studio:** Injects Pine source + strategy name
- **Backtester:** Injects latest backtest stats (return, WR, PF, DD, Sharpe)
- **Dashboard:** General context

---

## 7. Multi-Tenant Architecture

### 7.1 User Isolation

Each user is fully self-contained:

```
User
├── Credentials (encrypted HL keys, AI provider keys, API keys)
├── Strategies (uploaded/cloned, per-user)
├── Instances (engines, per-user)
│   ├── Trades
│   ├── Signals
│   ├── Backtests
│   ├── Position Snapshots
│   ├── Account Snapshots
│   └── Strategy Config (JSON)
└── Chat Sessions
    └── Chat Messages
```

### 7.2 DB Template

`data/template_empty_STABLE.db` is the canonical empty database:
- 20 tables
- 1 operator user (seeded)
- 0 instances
- 0 trades
- 290KB

### 7.3 Tenant Spawn

```bash
cp data/template_empty_STABLE.db data/tenant_{user_id}.db
```

The new DB is pointed to via `DATABASE_URL` env var. The `init_db()` function runs migrations idempotently on startup.

### 7.4 Future: Full Sandbox

Planned but not implemented:
- Per-user venv (isolated Python environment)
- Per-user engine processes (separate worker processes)
- Per-user log files

---

## 8. Clean Slate Protocol

### 8.1 When to Reset

- Before each phase test
- When DB is corrupted
- When starting a new development cycle
- When switching between major feature branches

### 8.2 Reset Steps

```bash
# 1. Kill all processes
for pid in $(ls /proc 2>/dev/null | grep -E '^[0-9]+$'); do
    comm=$(cat /proc/$pid/comm 2>/dev/null)
    if echo "$comm" | grep -q 'python'; then
        cmdline=$(tr '\0' ' ' < /proc/$pid/cmdline 2>/dev/null)
        if echo "$cmdline" | grep -qE '8792|9999|worker|main:app'; then
            kill -9 $pid 2>/dev/null
        fi
    fi
done

# 2. Verify ports free
curl -s http://localhost:8792/health 2>/dev/null || echo "8792 free"
curl -s -u operator:operator http://localhost:9999/api/state 2>/dev/null || echo "9999 free"

# 3. Reset DB
rm -f data/dev_test.db data/dev_test.db-wal data/dev_test.db-shm
cp data/template_empty_STABLE.db data/dev_test.db

# 4. Start fresh
source venv/bin/activate
export $(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' .env | head -20)
export DATABASE_URL="sqlite:////workspace/projects/strategy-engine/data/dev_test.db"
export DRY_RUN=true
python3 -m uvicorn main:app --host 0.0.0.0 --port 8792
```

### 8.3 Close HL Positions

```python
import requests
resp = requests.post("https://api.hyperliquid.xyz/info",
    json={"type": "clearinghouseState", "user": addr})
for p in resp.json().get("assetPositions", []):
    coin = p["position"]["coin"]
    client.market_close(coin)
```

---

## 9. Pine Fidelity Refactor

### 9.1 What Changed

| Gap | Severity | Fix |
|-----|----------|-----|
| Mode hardcoded to Scalp | 🔴 Critical | Restored Swing + Scalp (Pine default = Swing) |
| Risk profile hardcoded to 8/3 | 🔴 Critical | Restored 6 profiles (Sniper, Trend, Conservative, Default, Aggressive) |
| Mode-aware params ignored | 🟠 High | EMA, ATR base, momentum, pin bar, volume all auto-switch with mode |
| `trail_exit_grace_seconds` fabricated | 🟡 Medium | Removed (not in Pine) |
| Equity history appended every tick | 🔴 Critical | Now appends only on trade close (matches Pine `strategy.closedtrades`) |
| Re-entry on same bar | 🟠 High | One-entry-per-bar guard added (Pine `bar_index > lastEntryBar`) |
| `calc_on_every_tick` not simulated | 🟡 Medium | Uses candle H/L for trail eval (acceptable gap — tick data not available) |
| `process_orders_on_close` not simulated | 🟢 Low | Market orders execute immediately (acceptable for live trading) |

### 9.2 Remaining Gaps

| Gap | Impact | Priority |
|-----|--------|----------|
| `calc_on_every_tick` — Pine evaluates trail on every tick, we use candle H/L | Minor accuracy difference | Low |
| `process_orders_on_close` — Pine places orders on bar close, we execute immediately | Minor timing difference | Low |
| Commission — Pine 0.05% vs HL 0.045% | 0.01% difference per side | Low |
| Slippage — Pine models 5 ticks, we don't | Minor | Low |

### 9.3 Verification

61 tests across 12 groups, all PASS:
- Health, Strategy API, Instances API, Strategy Config CRUD
- 12 UI routes, Engine Detail HTML (15 params in DOM)
- Metadata, Stats, Swagger, PWA
- Strategy instantiation (19 tests: all 6 profiles, mode-aware params, no grace, get_parameters)
- DB schema (4 new columns)

---

## 10. How to Port a New PineScript Strategy

### Step 1: Read the PineScript
Read the full Pine file. Identify:
- All `input.*` declarations → these become `get_parameters()`
- All indicator calculations (EMA, SMA, ATR, DMI, etc.)
- Entry conditions (the `if` blocks that call `strategy.entry`)
- Exit conditions (the `strategy.exit` calls and `strategy.close_all` calls)

### Step 2: Create the Python file
```python
# strateges/my_strategy.py
import pandas as pd
import numpy as np
from strateges.base import BaseStrategy

class MyStrategy(BaseStrategy):
    @classmethod
    def get_parameters(cls) -> list[dict]:
        return [
            # Map each Pine input.* to a parameter dict
        ]

    def __init__(self, name="My Strategy", **kwargs):
        # Set Pine defaults
        super().__init__(name, **kwargs)
        # Derived params from kwargs

    def generate_signals(self, df, symbol="", equity_history=None) -> dict:
        # 1. Calculate indicators (EMA, ATR, DMI, etc.)
        # 2. Detect entry conditions
        # 3. Compute stop-loss, take-profit, trail levels
        # 4. Return {token, signal, direction, metadata, exit_config}
```

### Step 3: Register
No manual registration — `strategies/registry.py` auto-discovers `strategies/{slug}/` via `importlib`. Just drop the file in.

```python
STRATEGIES = {
    "engine_v1_3": EngineV1_3Strategy,
    "engine_v1": EngineV1Strategy,
    "engine_v6_1": EngineV6_1Strategy,
    "my_strategy": MyStrategy,  # ADD THIS
}
```

### Step 4: Verify
```python
from strateges.my_strategy import MyStrategy
s = MyStrategy()
params = s.get_parameters()
result = s.generate_signals(df, symbol="TEST", equity_history=[100])
print(result["direction"], result["signal"])
```

### Step 5: Test
- Create an engine with your strategy via the UI or API
- Run a backtest
- Check the engine detail page — your parameters should appear in the settings modal

---

## 11. Backup and Versioning

### 11.1 Convention

```
backups/v{N}_{context}_STABLE_YYYY-MM-DD_HHMM.tar.gz
```

- `N`: Version number (increments per phase)
- `context`: Short hyphenated description
- `STABLE`: Only after live verification
- Timestamp: Local time

### 11.2 Create Backup

```bash
tar czf backups/v{N}_{context}_STABLE_YYYY-MM-DD_HHMM.tar.gz \
  --exclude=backups --exclude=venv --exclude=__pycache__ \
  --exclude='*.pyc' --exclude='data/*.db' --exclude='data/*.db-wal' \
  --exclude='data/*.db-shm' --exclude='data/logs' .
```

### 11.3 Restore

```bash
tar xzf backups/v{N}_{context}_STABLE_YYYY-MM-DD_HHMM.tar.gz
```

### 11.4 Latest STABLE

| Version | Description | Size |
|---------|------------|------|
| v2.03.004 | Track 1–2.6 cleanup: `engine/`→`strategies/`, 25 stale docs + wiki/ archived to `backups/deprecated-docs_2026-07-24/`. Code backups at `v2.03.001–004`. | — |

---

## 12. Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `STRATEGY_ENGINE_PORT` | No | 8888 | HTTP port |
| `DATABASE_URL` | No | `sqlite:///data/strategy_engine.db` | SQLite path |
| `DRY_RUN` | No | false | Paper trading mode |
| `HYPER_LIQUID_ETH_PRIVATE_KEY` | Yes | — | HL signing key |
| `ACCOUNT_ADDRESS` | Yes | — | HL wallet address |
| `INSTANCE_SECRET_KEY` | Yes | — | Fernet key for encrypted credentials |
| `DASHBOARD_USERNAME` | Yes | — | UI login username |
| `DASHBOARD_PASSWORD` | Yes | — | UI login password |
| `FLASK_SECRET_KEY` | Yes | — | UI session key |
| `AGENT_API_KEY` | No | — | API route protection |
| `AI_PROVIDER` | No | ollama | Chat provider |
| `AI_MODEL` | No | glm-5.1 | Chat model |
| `AI_API_KEY` | No | — | Chat auth |

---

## 13. File Map

```
strategy-engine/
├── main.py                 # FastAPI app entrypoint
├── config.py              # Environment config
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── CONTEXT.md             # Structural rails (THE MAP)
├── NOTES.md               # Session memory
├── BETA-ROADMAP.md       # Forward plan
├── docs/                  # KEEP docs only
│   ├── TASK-LIST.md      # Work inventory (TIER 0/1/2)
│   ├── IMPLEMENTATION-CHECKLIST-cleanup.md
│   ├── PLANNED-EDITS-24-7-2026.md
│   ├── HANDOVER-UI-WALKTHROUGH.md
│   ├── FAQ.md             # Quick answers
│   ├── VOCABULARY.md     # Domain terms
│   └── DOCUMENTATION.md  # This file
├── api/                   # REST API routes (11 modules)
├── app/                   # Jinja2 UI
│   ├── routes.py          # UI routes (mounted as ui_routes)
│   ├── templates/         # HTML templates
│   └── static/           # CSS, JS, PWA assets
├── strateges/             # Strategy modules
│   ├── base.py            # Base strategy contract
│   ├── v1_3.py          # Eve Engine v1.3
│   ├── v1.py             # Eve Engine v1
│   ├── v6_1.py          # Engine v6.1 PRO
│   └── registry.py        # Strategy registry (dynamic loader)
├── instances/             # Instance management
│   ├── runner.py          # Instance runner
│   ├── models.py          # SQLAlchemy models
│   ├── manager.py         # Lifecycle manager
│   └── events.py          # Event bus
├── core/                  # Core services
│   ├── exchange.py        # HL client
│   ├── market_data.py     # OHLCV fetcher
│   ├── llm.py             # AI chat
│   └── position_sizer.py # Position sizing
├── scripts/
│   └── worker.py          # Standalone worker
├── backtests/
│   └── runner.py          # Backtest engine
├── monitoring/            # Scoring, rotation, alerts
├── withdrawal/            # Withdrawal system
├── pinescript-tv/         # Original PineScripts
├── data/
│   ├── template_empty_STABLE.db  # Empty DB template
│   ├── dev_test.db               # Dev DB (fresh from template)
│   ├── backups/                  # Old DB backups
│   └── logs/                     # Worker logs
└── backups/               # Code backups
    └── VERSIONING.md       # Backup index
```
