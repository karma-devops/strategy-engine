# CONTEXT.md — strategy-engine (PULS·R) — THE MAP

> **Single structural reference.** All architecture, product, deployment, naming, pipe/IA design, strategy contract, and design-system specs live here.
> Companion docs (consolidated 2026-07-19, REFRESHED 2026-07-24): **NOTES.md** (session log + audits + ROAST), **docs/TASK-LIST.md** (SINGLE consolidated work inventory — TIER 0/1/2 priority), **BETA-ROADMAP.md** (forward plan). Read-only evidence: **docs/HANDOVER-UI-WALKTHROUGH.md**. Living PWA docs: **docs/DOCUMENTATION.md**, **docs/FAQ.md**, **docs/VOCABULARY.md**. (All other historical docs archived to `backups/deprecated-docs_2026-07-24/` — see Track 2.6.)
> Rollback index: `backups/VERSIONING.md`. Pre-consolidation docs moved to `backups/deprecated-docs_2026-07-18/`.
> Do not commit to GitHub (local-only). Version: **v2.03** (synced 2026-07-24; `VERSION` file = v2.03, `api/metadata.py` reads it; `/api/v2/metadata` reports v2.03). Prior doc freeze v2.02 @ 2026-07-23; v1.98 @ 2026-07-19.

---

## 1. Project Identity

`strategy-engine` (PULS·R) is the canonical strategy-only trading executor for HyperLiquid perpetuals.

- **Runtime:** Python FastAPI + SSE.
- **Exchange:** HyperLiquid perpetuals.
- **Decision maker:** Engine strategy only. No LLM for execution.
- **Scope:** Up to 6 engine instances (`engine-1`..`engine-6`), each with its own token, strategy, credentials, risk settings.
- **Goal:** Instant execution on engine signals, full per-engine monitoring, backtest-first validation, PWA UI with public landing + authenticated dashboard.

---

## 2. Directory Map

```
strategy-engine/
├── main.py                 # FastAPI app, route registration, lifespan (REPORTS version from VERSION file — see §10)
├── config.py              # Env config: port, DB, global creds, LLM defaults
├── requirements.txt
├── Dockerfile / docker-compose.yml
├── CONTEXT.md             # This file — THE MAP
├── NOTES.md               # Session log + audits + ROAST findings
├── docs/TASK-LIST.md      # SINGLE consolidated work inventory (TIER 0/1/2) — see §companion line
├── BETA-ROADMAP.md        # Beta readiness action plan
├── api/                   # REST routes (11 modules, /api/v2)
│   ├── instances.py       # CRUD + start/stop/close/leverage + delete cascade
│   ├── signals.py positions.py metrics.py withdrawals.py
│   ├── stream.py          # SSE event stream (emits `trade`, not `position`)
│   ├── strategies.py backtests.py monitoring.py killswitch.py metadata.py
├── app/                   # Jinja2 UI (Option B: per-route server-rendered, NO SPA)
│   ├── routes.py          # UI routes (Basic Auth) — per-page
│   ├── templates/
│   │   ├── layout.html    # Shared shell (sidebar, topbar, PWA, toast, tooltip JS)
│   │   ├── engine_detail.html  # ★ ENGINE DETAIL SURFACE — the per-instance "map":
│   │   │                     KPI row, performance hero, live position card + strategy card,
│   │   │                     trade/signal tables, runner console, controls bar. Served at
│   │   │                     /app/engines/{slug}. This template is the canonical reference
│   │   │                     for what a single engine instance exposes to the operator.
│   │   ├── dashboard.html engines.html trades.html strategies.html strategy_detail.html
│   │   ├── strategy_studio.html testing_historical.html assistant.html chat_widget.html
│   │   ├── instance_form.html error.html (404 splash)
│   │   └── backtests.html withdrawals.html settings.html  # legacy redirects
│   ├── static/  tokens.css (design tokens) style.css chat_widget.* manifest.json sw.js
│   │           pulsr-chart.js (SVG+JS charts — lightweight-charts RETIRED)
│   └── charts.js          # REMOVED — retired; charts now in app/static/pulsr-chart.js
├── core/                  # HyperLiquid layer: exchange.py, llm.py, market_data.py, position_sizer.py
├── instances/             # models.py, manager.py, runner.py, events.py
├── withdrawal/            # calculator.py, scheduler.py, manual.py
├── monitoring/            # tracker.py, rotator.py, testing_pool.py, alerts.py
├── backtests/             # runner.py (bar-by-bar sim, trailing stop, tick simulation)
├── scripts/worker.py      # Live strategy worker — port 9999, STANDALONE tester, no DB.
│                          #   Operator directive: KEEP as standalone testing wrapper, NOT integrated.
├── pinescript-tv/         # Original PineScript source-of-truth
├── strategies/            # strategy.catalog: base.py (BaseStrategy + detect_mintick), registry.py (strategy.registry: STRATEGIES dict + get_strategy/get_presets), v1.py, v1_3.py, v6_1.py
└── data/                  # SQLite DBs + backups (template_empty_STABLE.db, dev_test.db, backups/)
```

---

## 2b. Vocabulary — strategy vs engine daemon (authoritative)

These two words are deliberately distinct. Confusing them is the root cause of the
repo's historical structure drift.

| Term | Means | Lives in | Registry |
|------|-------|----------|----------|
| **Strategy** | The trading logic — signal generation, params, presets. User may name/slug it anything (e.g. `v1_3`, `my_scalp`); a strategy file is just `strategy.py`-style logic. | `engine/` today → `strategies/` after the split (Track 1) | **strategy.registry** — the catalog of available strategy classes. New strategies register here and become selectable by any engine. |
| **Engine (daemon)** | A running Instance that executes a Strategy against HyperLiquid. Own token, creds, risk, mode. | `instances/` (runner, manager, models, events) + `core/` (exchange, market_data) | **engine.registry** — per-engine instance config: which `strategy_id`, plus its params/vars (activation, offset, profile, mode, timeframe, leverage, max_position_pct, poll_interval). |

**Receiver contract (inviolable):** the engine daemon is a *universal receiver*. It never
references a strategy's class or file name. It consumes a strategy only through the
3-point contract returned by `generate_signals()`:
- `entry_config` — clear entry signal → open trade (param values are log-only).
- `exit_config` — clear exit of an open trade → close it (param values are log-only).
- `strategy_config` — manual settings / params (editable in UI, stored per instance).

The strategy.registry exposes strategies by slug; the engine.registry wires a chosen
slug + its params into a running instance. Neither registry imports the other's logic
by name — they meet only through the 3-point contract. (Full registry design: Track 5.)

---

## 3. URL Structure

### Public (no auth)
| URL | Serves |
|-----|--------|
| `/` | Landing page | 
| `/faq` `/about` | Info pages |
| `/login` `/signup` | Auth forms (signup = placeholder) |
| `/health` | Health check (`{"status":"ok","dry_run":...}`) |
| `/stream` | SSE event stream |

### Authenticated (Basic Auth)
| URL | Serves |
|-----|--------|
| `/app` → `/app/dashboard` | Fleet overview, pulse graph, console |
| `/app/engines` | Fleet grid |
| `/app/engines/{slug}` | **Engine detail** (see engine_detail.html note in §2) |
| `/app/trades` | All trades + Active Positions section |
| `/app/strategies` `/app/strategies/{id}` `/app/strategies/upload` | Strategy registry + detail (4 tabs) + upload |
| `/app/testing/historical` | Backtest form + results (replaces `/app/backtests`) |
| `/app/monitoring` | Scores + alerts |
| `/app/account/*` | Overview, Settings, Secrets, Wallet, API Keys |
| `/app/assistant` | AI chat (full page + shared widget) |
| `/app/*` (unknown) | `error.html` 404 splash |

### Live Worker (port 9999, Basic Auth operator:operator) — standalone tester
`/` worker UI · `/api/state` · `/api/config` POST · `/api/start` `/api/stop` POST · `/stream` SSE

### API (X-API-Key header, `/api/v2/*`)

---

## 4. Configuration (env vars)

| Var | Default | Description |
|-----|---------|-------------|
| `STRATEGY_ENGINE_PORT` | `8888` (running on `8792` dev / `9999` worker) | HTTP port |
| `DATABASE_URL` | `sqlite:///data/strategy_engine.db` | SQLite local |
| `DRY_RUN` | `false` | Global default; per-instance override via DB |
| `HYPER_LIQUID_ETH_PRIVATE_KEY` | required | Global HL signing key |
| `ACCOUNT_ADDRESS` | required | Global wallet |
| `INSTANCE_SECRET_KEY` | required | Fernet key for per-instance private keys |
| `DASHBOARD_USERNAME` / `DASHBOARD_PASSWORD` | required | UI login |
| `FLASK_SECRET_KEY` | required | UI session |
| `AGENT_API_KEY` | optional | API route protection |
| `AI_PROVIDER` | `ollama` | Chat provider |
| `AI_MODEL` | `glm-5.1` | Chat model |
| `AI_API_KEY` | optional | Chat auth |

Per-engine overrides in DB: `hyperliquid_private_key` (encrypted), `account_address`, `withdrawal_address`, `hl_credential_id`.
Per-user model prefs: `User.assistant_model`, `User.coder_model` (default `glm-5.1`).

---

## 5. API Surface (`/api/v2/*`, X-API-Key unless noted)

**Instances:** `GET/POST /instances` · `PUT/DELETE /instances/{slug}` (cascade) · `POST /instances/{slug}/{start|stop|restart|close}` · `GET /instances/{slug}/{signals|trades|position|balance}`.
**Metadata:** `GET /metadata` (232 tokens) · `?query=` · `?token=` · `GET /stats`.
**Backtests:** `POST /backtests/run` · `GET /backtests` · `POST /backtests/replay` (tick sim).
**Metrics/Account:** `GET /metrics` · `GET /metrics/account` · `GET /account`.
**Withdrawals:** `GET/PUT /withdrawals/config` · `GET /withdrawals/history` · `GET /withdrawals/projection`.
**Kill:** `GET /kill/status` · `POST /kill/global` · `POST /kill/withdrawals`.
**Monitoring:** `GET /monitoring/scores` · `GET /alerts`.
**Chat:** `POST /chat` (Basic Auth) · `GET /chat/sessions` (Basic Auth).
**Strategies:** `GET /strategies`. **Stream:** `GET /stream` (SSE, no prefix).

---

## 6. UI & Design System

- **Palette:** brown neutrals (`#0f0a08` bg → `#f5f1ed` text) + electric teal brand `#06d6a0` + semantic positive `#10b981` / negative `#ef4444` / warning `#f59e0b`. Light mode inverted (localStorage).
- **Type:** Space Grotesk (display) / Inter (body) / JetBrains Mono (code). 8-step scale, 1.15x ratio.
- **Anti-slop (DESIGN-SPEC-V2 dials):** variance 6.5, motion 5.5, density 7.5. Asymmetric 2fr/1fr grids, border-top KPI dividers (not boxes), brown-tinted shadows, teal-tinted glass, skeleton/empty/success states, status-dot pulse 2s.
- **Breakpoints:** asymmetric grid → 1fr @1024px; sidebar 220→56px; KPI 4→2→1 col.
- **PWA:** manifest.json + sw.js. Path-based routing (no hash).
- **Mobile:** bottom nav, burger ≤768px, 44px touch targets, stacked grids.

### 📁 `design-system/MASTER.md` — AUTHORITATIVE DESIGN SYSTEM SPEC (pointer)
**Do NOT absorb — kept as a live subdirectory doc.** This is the canonical source for:
- **Token architecture** (3-layer: Primitive → Semantic → Component) in `app/static/tokens.css`
- **Typography scale**, **spacing scale (4pt)**, **component specs** (button/card/tag/input/tab/trade-row/chat-widget)
- **Layout system** (breakpoints, grid, content width), **navigation patterns**
- **Animation guidelines**, **accessibility checklist (WCAG AA)**, **Gestalt audit protocol** (blur isolation / color erasure / boundary strike)
- **PWA config** (manifest, service worker, routes)

The legacy `DESIGN-SPEC.md` / `DESIGN-SPEC-V2.md` content was folded into §6 above for the MAP, but `design-system/MASTER.md` remains the maintained reference for any token/component change. When editing UI, read it first. If it drifts from `tokens.css`, flag in NOTES.md (see "Spec Drift" entries).

### `design-system/` file map (authoritative, internal docs)
| File | Role | Status |
|------|------|--------|
| `MASTER.md` | Authoritative token/component/layout/a11y/PWA spec. **Palette wins.** | maintained |
| `theme-glow.md` + `theme-glow.css` | Glow/aura spectrum extension (broadens MASTER palette for effects — does NOT override MASTER base tokens). | NEW (Z4) |
| `components.md` | Component specs (card/tag/button/input/tab/trade-row/**position-side-spine**/pulse) reconciled to MASTER. | NEW (Z4) |
| `position-card-spec.md` | HL open-position replication: left-edge spine overlay + field set + token mapping (long=`--color-profit` `#34D399`, short=`--color-loss` `#FB7185`). | NEW (Z4) |

**Palette authority:** `MASTER.md` wins (`#34D399` profit / `#FB7185` loss / `#15100B` surface-card). `tokens.css` + this §6's old `#10b981`/`#ef4444` are OUTDATED — reconcile via Z4. Position side-color uses MASTER tokens (not HL's `#00C08B`/`#FF4D4D`); **layout style follows HL** (left-edge spine, no row fill, symbol+size colored).

---

## 7. Backtest Runner (`backtests/runner.py`)

- Bar-by-bar inline signal gen; `equity_history` feeds back to strategy.
- Risk sizing: `qty = min(riskAmount/riskPerShare, equity*0.97/close)`.
- SL via candle high/low; trailing stop (HL mintick); trend-reversal close (EMA cross); signal-reversal close.
- HL taker fee 0.045%; default 1x lev, $100 capital.
- Standalone mode (token+strategy+timeframe+days, no instance). Activation = float.
- Tick modes: 1=OHLC, 4=basic O/H/L/C, 28=Brownian bridge. **No HL orders sent.**

---

## 8. Strategy Contract (`STRATEGY_CONVERTER.md` absorbed)

**Golden rule:** Strategy declares, receiver consumes. Receivers (worker/runner/backtests) are universal — they never import strategy classes or hardcode activation/offset/mode.

`generate_signals()` returns: `{token, signal (±1|0), direction (BUY|SELL|NEUTRAL), metadata{}, exit_config{}}`.
Receiver exit order: 1) Stop Loss → 2) Trailing (with `trail_exit_grace_seconds`) → 3) Take Profit → 4) Trend Change (EMA cross) → 5) Time Exit.
Removed fabricated exits: Reversal Signal, Full Fan Alignment, Signal Reverses.
Three-port architecture: `strategy_config` (DB params, UI-editable) · `entry_config` (per-signal) · `exit_config` (per-signal, receiver-neutral).

---

## 9. Pipe Architecture & Information Architecture

**Pipe (data flow):** `main.py` scheduler (30s) → `signal_monitor.run_once()` → `data_fetcher` → `engine.generate_signals()` → position/account update → `exchange_client` open/close → SSE/REST to dashboard. Position sizing: `notional = free_balance * MAX_POSITION_PCT * LEVERAGE`.
**IA (navigation) — TARGET STATE (Z2, beta-blocker):** Sidebar = Dashboard / Engines (dynamic children) / Strategies (incl. Studio) / **Paper** / **Backtesting** / Trades / Account (Overview/Settings/Secrets/Wallet/API Keys) / Assistant. The legacy "Testing" collapsible is **removed**; Historical→Backtesting, Paper Trading→**Paper**. 
- **Paper** = live forward-testing simulation (dry-run only, no executions — evaluate your strategy scripts). Top-level.
- **Backtesting** = historical tick/replay simulation, isolated store. Top-level.
- **Trades** = LIVE trades ONLY (`dry_run=False`). Paper trade history lives only on the Paper results page.

**Naming:** routes `/app/{section}/{id}/{subsection}` (kebab); APIs `/api/v2/{resource}/{id}/{action}` (snake in practice); templates `{section}.html`/`{section}_detail.html` (snake_case); models PascalCase class / snake_case plural table / UUID or slug PK.

---

## 10. Version & Audit State (reconciled 2026-07-18, end-of-day)

### Version
- **Actual: v2.03** (VERSION file, bumped 2026-07-24 post-sprint; `metadata.py` reads VERSION file so `/api/v2/metadata`/`/stats` report v2.03).
- **✅ FIXED (D1):** `main.py` now reads `version=VERSION` (was hardcoded `"0.095"`). `/openapi.json` correctly reports the version. Resolved 2026-07-18; version-sync hardened 2026-07-22.
- **Entry-gate UNIVERSAL repair (2026-07-22, `5cfcbf5` + `3805b2e`):** v1_3 now emits a strategy-agnostic `entry_config` (`.trigger = valid_trigger_bull` for LONG / `valid_trigger_bear` for SHORT). `instances/runner.py` gates entry on `entry_config.trigger` (neutral receiver) instead of strategy-internal signal names; legacy `valid_trigger_*` kept as fallback. Fixes the persistent `"ENTRY skipped - no bullish pin/trigger"` despite `pin=bull`+`pierce=bull`. Verified: entries now execute.
- **BUG-A / BUG-B (2026-07-22, `ad2180b` + `fa9bac9`):** `notional` assigned before entry active-trade dict (NameError had blocked ALL entries); `AccountSnapshot.user_id` set so dashboard Pulse Graph seed is scoped (was always NULL → empty graph).
- **TDZ fix (2026-07-22, `d9ef794`):** `dashboard.html` moved `fmtUsd`/`fmtPct`/`sideClass` consts above first `buildPulse()` call — resolved TDZ ReferenceError that aborted the page script before SSE/Console init.
- **Trailing-stop PineScript parity (2026-07-23, `6a0d4e0`):** `_evaluate_exit` rewritten to match original PineScript `strategy.exit` semantics (trail_points = distance, trail_offset = activation move, track best_price from entry). Preserves original intent; closes P1 exit-audit (positions held too long / exits not firing).
- **Paper route + backtest-import fixes (2026-07-23, `37701b1` + `ce645be`):** added missing `/app/testing/paper` route (paper UI 404); resolved 500 on `POST /api/v2/backtests/run` (ImportError `_trade_to_dict` in `api/backtests.py` → corrected symbol in `testing/backtest_store.py`).
- **PR #1 merged (2026-07-23, `7b7ee11`):** `karma-devops/fix-strategies-and-paper-trading-simulation` — strategy execution engine fix, config standardization, paper-trading simulation fix. Local `main` == `origin/main`.
- **Perp-account value UI (2026-07-23, `c9d630a`):** dashboard + account overview now show HL perp-only account value alongside total portfolio.

### Live State (confirmed 2026-07-23, end-of-day)
- Server 8792 UP, `dry_run=false`.
- engine-1: FARTCOIN Scalp v1.3, RUNNING LIVE, LONG ~390 @ ~$0.1296 (re-adopted from HL), liq=0.1228 (A4 live-enriched), account ~$5.1.
- engine-2: HYPE Paper v1.3, STOPPED, FLAT, dry_run=true.
- Worker 9999 DOWN (kept as standalone tester).

### Audit — Fixed (verified in code + live)
| ID | Finding | Fix | Verified |
|----|---------|-----|----------|
| B1 | Stale HL client (position=None) | `f66dffe` `_refresh_hl_client()` + retry | code |
| B2 | Password hash missing on fresh DB | seed `hash_password('operator')` | code |
| B8 / #2 | Plaintext API keys | P12 `60f039a` Fernet | code |
| #1 | Trade not persisted | P9 `9350609` | code |
| #3/#4/#7 | Auth info leak / min-order / LOG_BUFFER O(n) | P11 `21da5e5` | code |
| #10 / P14 | Dry-run/live trade separation | `e6ac56d`→`14f21e5` | code |
| D1 | `main.py` version hardcoded 0.095 | reads `VERSION` now | **live** (`/openapi.json` → v1.98) |
| D3 | equity_history to strategy | verified in `runner._tick()` | code |
| A1/A4 | Position card + API enrichment | `f0bbf90`; **A4 extended** — summary now pulls live `liquidationPx` from HL for running positions (liq no longer 0.0) | **live** (liq=0.1228) |
| B7 | Kill switch stops thread but doesn't `market_close()` | `stop_instance()` + `stop_instance_by_slug()` now call `market_close()` before halt; kill-switch already closed all | **live** (FARTCOIN position closed on HL) |
| D2 | No auto-restart (engine dies on host reboot) | runner `_loop` auto-restarts on crash (5× exp backoff); manager `load_instances(auto_resume=True)` resumes running instances on boot | **live** (engine-1 auto-resumed after server restart) |
| X1 | Duplicate entry on short poll interval | `PENDING` sentinel set synchronously before `_execute_open`; blocks re-entry on next poll | code + lint |
| X2 | Entry without pin-bar condition | entry requires `valid_trigger_bull/bear` flag from strategy result; skips otherwise | code + lint |
| X3 | Backtest form: start-balance + timeframes | form now has 30m/3h/1d options, start-balance field (default 100), HL token registry link; payload wired | live (form renders) |
| X4 | ExecutionCostModel (slippage/maker/taker) | `backtests/cost_model.py` + wired into `backtests/runner.py` (replaces hardcoded TAKER_FEE) | **live** (entry $0.13/exit $0.10 per $100) |
| Z1–Z7 | 3-way separation + unified runner | `app/_common.py`, `paper_routes.py`, `backtest_routes.py`, `testing/runner.py`, `testing/backtest_store.py`, design-system/* , `position-card.js` | **live** (all routes 200, Z7 backtest executed) |

### Audit — OPEN (pre-beta, not live-safety blockers)
| ID | Severity | Finding | Plan |
|----|----------|---------|------|
| B9 | MED | Anomalous drawdown spikes (>50% filter exists, verify on live) | H2 |
| B3 | MED | Per-user log persistence (LOG_BUFFER in-memory only) | H3 |
| B5/B6 | LOW | NOT NULL defaults + cascade deletes | H5 |
| D0 | DEPLOY | Deferred `app/routes.py` `_safe_tojson` fix — now absorbed into `_common.py` + live; verify no 500s remain | D0 |
| D4/D5 | OPEN | Trade PAPER/LIVE badge; dry_run toggle end-to-end verify | V3/D4 |

### Dry-Run Architecture (verified)
Global `.env` DRY_RUN=false → live-connected. Per-instance `dry_run=true` → paper (signals, no orders). `get_hyperliquid_client()` always passes `instance.dry_run`. UI toggle reflects instantly.

### Auth Architecture (verified P6)
`require_ui_or_api` accepts Basic Auth / global X-API-Key / PULS-R per-user key. Router-level `verify_ui_credentials` no longer blocks API-key-only requests.

---

## 13. Stability Status (synced 2026-07-23)

**⚠️ NOT STABLE. NOT BETA.** Code-complete + live-verified at route/import level through 2026-07-23:
- 2026-07-18: Z1–Z7 (route split, menu, engine detail, design-system, position card, backtest store, unified runner) + X1–X4 + D2 (auto-restart) + A4 (liq enrichment) + B7 (kill-switch close).
- 2026-07-22: entry-gate UNIVERSAL repair (`entry_config.trigger`), BUG-A/B (notional NameError + AccountSnapshot.user_id), TDZ dashboard fix, version sync to v2.01/v2.02.
- 2026-07-23: PR #1 merged, trailing-stop PineScript parity, paper route 404 fix, backtest-import 500 fix, perp-account-value UI, test-drift fixes (phase1/2/5).

Outstanding before any beta claim:
- **No `tests/` suite executed recently** — correctness asserted via live probes + import checks, not unit/integration runs. Phase1/2/5 test-drift fixed (07-23) but full suite not run green.
- **UI wiring only partially verified** — `#pos-grid` population not visually confirmed with a live position; engine_detail mode tag not visually checked.
- **Bug surface unknown** — systematic bughunting (UI + wiring + data flow) still pending (next phase after this doc sync).
- **Open live-safety items:** BUG-11/BUG-12 withdrawal/deposit round-trip DEFERRED (live funds, explicit go required); D5 dry_run toggle end-to-end verify; B9 drawdown >50% spike filter; B3 per-user log persistence; B5/B6 schema hardening.

**Next phase:** bughunting + UI frontend improvement + wiring verification. See docs/TASK-LIST.md (TIER 0/1/2 + BUGHUNT group) and BETA-ROADMAP.md.

---

## 11. Three-Way Strict Separation (SOLID / DDD) — beta-blocker (Z1–Z7)

**Goal:** theoretical tools (paper/backtest) can NEVER bleed into the Live Dashboard or Live Engine Stats. Isolation is enforced at the **repository layer**, not just routing.

### Bounded contexts (inviolable)
| Domain | Data scope | Menu | Router file | Store |
|--------|-----------|------|-------------|-------|
| **LIVE** | `dry_run=False` only | Dashboard · Engines · Trades(live) | `app/routes.py` | `strategy_engine.db` |
| **PAPER** | `dry_run=True` only (no executions) | **Paper** (top-level) | `app/paper_routes.py` | `strategy_engine.db` (filtered) |
| **BACKTEST** | isolated, zero live access | **Backtesting** (top-level) | `app/backtest_routes.py` | **`backtest.db` (separate file)** |
| **STRATEGY** | code + params (shared kernel) | Strategies · Studio | `app/routes.py` | `strategy_engine.db` |

### No-bleed guarantees
- Each repository **appends its filter unconditionally** — router never passes a mode flag down. `LiveRepository` physically cannot return `dry_run=True` rows.
- `BacktestRepository` points at a **different SQLite file** with different models → impossible to read/write live data.
- **Shared kernel:** only the strategy contract (`generate_signals()`) + receiver exit order are reused by both `instances/runner.py` (live daemon) and `testing/runner.py` (`--mode paper|backtest`). That reuse is intended, not a bleed.
- Withdrawals stay in `routes.py` (live-only). Strategies (Studio/upload) stay in `routes.py` as a shared kernel, NOT a 4th router.

### SOLID mapping
- **S**ingle: one router per domain; `testing/runner.py` handles one mode per invocation.
- **O**pen/Closed: receivers consume the strategy contract without importing strategy classes.
- **L**iskov: paper/backtest runners satisfy the same `Runner` port.
- **I**nterface Segregation: `LiveReadService` / `PaperReadService` / `BacktestReadService` ports; Dashboard depends on `LiveReadService` only (DIP).
- **D**ependency Inversion: routes depend on repository ports, not live SQLAlchemy sessions.

### File tree (target)
```
strategy-engine/
├── main.py                      # include_router(live_) + paper_ + backtest_ ; injects correct repo per router
├── app/
│   ├── routes.py                # LIVE: dashboard, engines, trades(LIVE), account, settings, strategies, assistant, live, withdrawals
│   ├── paper_routes.py          # Paper page + paper results/trades history
│   ├── backtest_routes.py       # Backtesting page + backtest runs/results
│   ├── _common.py               # pure helpers (_safe_tojson, auth deps, theme inject) — ZERO DB access
│   ├── templates/  layout.html (menu: Dashboard|Engines|Strategies|Paper|Backtesting|Trades|Account|Assistant)
│   │              paper.html · backtesting.html · trades.html (LIVE-only) · engine_detail.html (dynamic LIVE/PAPER title)
│   └── static/    position-card.js (HL spine, populates #pos-grid) · design tokens
├── instances/
│   ├── models.py                # shared schema (dry_run column)
│   ├── runner.py                # LIVE daemon (engine-1)
│   └── repositories.py          # LiveRepository / PaperRepository (DIP ports + filters)
├── testing/
│   ├── runner.py                # UNIFIED: --mode paper|backtest  (absorbs backtests/runner.py)
│   └── backtest_store.py        # isolated SQLite models + store
├── design-system/  MASTER.md · theme-glow.md/.css · components.md · position-card-spec.md
└── backtests/runner.py          # → backups/deprecated (absorbed by testing/runner.py)
```
**Note:** `scripts/worker.py` (port 9999) stays standalone per operator directive — not absorbed into `testing/runner.py`.

---

## 12. Rules of Engagement
- No code execution without operator approval.
- Backup before structural changes (ADIX phase-backup; tar.gz STABLE form).
- One change per cycle; verify before next.
- Secrets in env vars only; never committed.
- ADIX: filesystem is the state machine; every directory is a processing node.
- Keep worker (9999) standalone — do not integrate into main app.

## Doc pointer (REFRESHED 2026-07-24 — Track 2.6)
- `docs/TASK-LIST.md` is the single consolidated work/status tracker (TIER 0/1/2). ROOT `TASK-LIST.md` no longer exists — all work now lives in `docs/`.
- `docs/` KEEP set (authoritative, living): `TASK-LIST.md`, `IMPLEMENTATION-CHECKLIST-cleanup.md`, `PLANNED-EDITS-24-7-2026.md`, `HANDOVER-UI-WALKTHROUGH.md`, `DOCUMENTATION.md`, `FAQ.md`, `VOCABULARY.md`. All others (ARCHITECTURE, ROADMAP, REFACTOR_PLAN, bugreport, DECISIONS, STYLEGUIDE, AI_RULES, UI-TODO-1, etc.) archived to `backups/deprecated-docs_2026-07-24/`. `wiki/` removed (overlapped docs/).
- `DOCUMENTATION.md` / `FAQ.md` / `VOCABULARY.md` = living PWA docs; must reflect ACTUAL implemented frontend (LIVE+STABLE). Refresh pending (Track 2.7).
- `BACKLOG.md` (root) = bugreport tracking ledger.

## Known deferred features (operator-flagged, do NOT implement without explicit go)
- **Withdrawal/Deposit round-trip (BUG-11 + BUG-12, TASK-LIST.md BUGHUNT):** withdrawal is
  BROKEN at `core/exchange.py:429` (`self._exchange.withdraw` → should be
  `withdraw_from_bridge(amount, destination)`, SDK `withdraw3` action, mainnet already set).
  Deposit has NO code path at all. Both deferred 2026-07-19 (live funds, not urgent).
  T1-5 idempotency guard already in place. Full scope + verification plan in TASK-LIST BUGHUNT
  and NOTES.md (2026-07-19 DEFERRED entry). Reuse T1-5 pattern when built. Explicit operator
  re-open required before any live fund movement.
