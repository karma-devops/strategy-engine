# VOCABULARY

Domain terms for the PULS·R strategy engine, as **actually implemented in this repo** (LIVE + STABLE, verified 2026-07-24). Where an older concept was renamed, the live name is used.

## Strategy
A pure trading algorithm that produces signals from market data. Owns trading logic + parameters. Immutable at runtime — the engine passes config IN; the strategy file is never mutated.
- Live location: `strategies/{slug}/strategy-name.py` (subclass of `BaseStrategy`).
- Declares 3 ports (see below).

## The three ports (strategy contract)
1. **strategy_config** (Port 1): static per-instance parameters. The strategy exposes its schema via `get_parameters()`; the engine settings panel renders these fields. Applied at runtime via `strategy_class(**strategy_config)`.
2. **entry_config** (Port 2): per-signal output — direction (BUY/SELL/NEUTRAL), signal strength (0–1), metadata. Consumer reads to decide entry.
3. **exit_config** (Port 3): per-signal exit declaration — stop_loss, take_profit, trail_activation/offset, time_exit. Consumer is neutral — reads only what the strategy declares.

## Strategy Package (subdir)
`strategies/{slug}/` holds:
- `strategy-name.py` — executable strategy
- `strategy-name.pine` — exported PineScript (optional)
- `strategy-name-doc.md` — what it does + FIDELITY SCORE vs original
- `strategy-origin.py` / `strategy-origin.pine` — source if ported

## Engine (runtime executor)
The deployed trading loop for ONE strategy + ONE config on ONE token. Driven by `instances/runner.py` + `core/`. Knows its own state. Does NOT contain strategy logic (strategy is imported, not embedded).

## Instance
= 1 engine + 1 strategy + 1 config parameter set, deployed and running. Created via UI (`/app/engines` → Add Engine) or API (`POST /api/v2/instances`).
- Live model: `instances/{slug}/` holds `config.yaml` (authoritative, git-tracked) + the running process.
- `Instance.strategy_config` (DB JSON column) is the runtime copy; `config.yaml` is the source of truth per instance.

## Strategy Registry (`strategies/registry.py`)
Catalog of available strategies. Public API kept stable: `STRATEGIES`, `list_strategies()`, `get_strategy()`, `register_uploaded_strategy()`, `get_presets()`. Loads `strategies/{slug}/` dynamically via `importlib`. Receivers (runner, API, UI) import ONLY through this — never by strategy class name.

## Engine/Instance Registry (`instances/registry.py`)
Manages instance lifecycle (create / manage / delete / clone). Absorbs `DEFAULT_FLEET`. Clone = copy `config.yaml` under a new slug (see `clone_instance`).

## Signal
A decision from a Strategy: direction, strength, metadata. Consumed by the engine to open/adjust a position.

## Position / Trade / Order
- **Position:** current exposure (LONG/SHORT/FLAT), size, entry, mark, PnL.
- **Trade:** completed open+close transaction (immutable once closed).
- **Order:** instruction to exchange (idempotency-keyed).

## Account
HyperLiquid account state (value, equity, margin, leverage), fetched from exchange. All engine instances share wallet `0xA871…8078` (global `ACCOUNT_ADDRESS`); engine fills + manual fills co-mingle in `user_fills`.

## Core service layer (`core/`)
- `exchange.py` — HyperLiquid SDK wrapper (order/cancel, position/account query, candle fetch).
- `llm.py` — strategy Pine→Python translation helper.
- `risk`, `execution`, `market`, `event_bus`, `logger`, `metrics` — injected services the runner depends on.

## PWA
Progressive Web App: `app/static/manifest.json` + `app/static/sw.js` (service worker). Server-rendered Jinja2 templates + vanilla JS. Installable, offline-shell capable.

## Authentication
- **UI:** HTTP Basic Auth (`operator:operator` default). Verified by `verify_ui_credentials`.
- **API:** `X-API-Key` header (per `.env` `AGENT_API_KEY`). Verified by `verify_api_key`. All `/api/v2/*` routes are API-key gated.

## Backup (versioned)
`backups/v{N}_{context}_STABLE_YYYY-MM-DD_HHMM.tar.gz`. Index in `backups/VERSIONING.md`. NO deletions — relocate stale artifacts to `backups/deprecated-docs_*/`.
