# PULS·R Strategy Engine — Session Handover

> **Date:** 2026-07-16 ~05:35 WITA
> **Session:** 75a13148be04
> **Status:** PINE FIDELITY REFACTOR Phases 1-8 COMPLETE. 61/61 tests PASS. Clean slate — no servers running, fresh DB from template. Ready for Phase 9+ (Studio clone, Python upload, multi-tenant, live test).

---

## ⚡ Quick Start (Read This First)

**No servers running.** Clean slate. To start:

```bash
# Dev UI (paper mode, port 8792)
cd /workspace/projects/strategy-engine
source venv/bin/activate
export $(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' .env | head -20)
export DATABASE_URL="sqlite:////workspace/projects/strategy-engine/data/dev_test.db"
export DRY_RUN=true
python3 -m uvicorn main:app --host 0.0.0.0 --port 8792

# Worker (port 9999) — start only when ready for live/paper trading
cd /workspace/projects/strategy-engine
source venv/bin/activate
export $(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' .env | head -20)
export DATABASE_URL="sqlite:////workspace/projects/strategy-engine/data/worker.db"
export DRY_RUN=true
python3 scripts/worker.py --port 9999
```

⚠️ **App entrypoint is `main:app`, NOT `app.main:app`.**
⚠️ **Use `export $(grep -E '^[A-Za-z_]' .env | head -20)` — NOT `export $(cat .env | xargs)` (comments break it).**
⚠️ **Dev = `DRY_RUN=true` (paper). Never flip to live without operator consent.**

Then read: `CONTEXT.md` → `HANDOVER-PROMPT.md` → `NOTES.md` → Load `/adix` + `/backup-versioning` + `/karpathy-guidelines`.

---

## 🔧 Current State

| Item | Status |
|------|--------|
| Dev server (8792) | ⏹ Stopped (clean slate) |
| Worker (9999) | ⏹ Stopped (clean slate) |
| HL positions | ✅ Zero open ($5.10 USDC spot) |
| DB | Fresh from `template_empty_STABLE.db` (20 tables, 1 operator, 0 instances) |
| Template DB | `data/template_empty_STABLE.db` (290KB) — for multi-tenant spawning |

---

## ✅ Completed This Session (Pine Fidelity Refactor, Phases 1-8)

### Phase 1: `engine/base.py` — Parameter Declaration System
- `get_parameters()` classmethod: returns parameter schema for UI rendering
- `get_default_config()` classmethod: returns default values
- `__init__` accepts `**kwargs` for per-instance config overrides

### Phase 2: `engine/v1_3.py` — Dual-Mode Restored
- **Swing + Scalp** modes restored (was hardcoded Scalp only). Pine default = Swing.
- **6 risk profiles** restored (was hardcoded 8/3 only): Swing Sniper (36/12), Swing Trend (36/18), Swing Conservative (48/18), Scalp Default (10/4), Scalp Aggressive (8/3), Scalp Conservative (12/5)
- Mode-aware: EMA lengths (6/18/50 vs 4/9/25), ATR base (1.8 vs 1.3), momentum thresh (18 vs 28), pin bar ratios (0.66/0.34 vs 0.70/0.30), volume multiplier (1.0 vs 1.3)
- `trail_exit_grace_seconds` removed (not in Pine — was fabricated)
- `get_parameters()` declares 15 configurable params

### Phase 3: `scripts/worker.py` — Pine Fidelity Fixes
- **Equity history**: per-tick append removed. Now appends only on trade close (matches Pine `strategy.closedtrades`). Cap 100 (was 500).
- **Trail grace**: removed. Trail active immediately after activation (matches Pine `strategy.exit`).
- **One-entry-per-bar**: `last_entry_bar_time` guard added (matches Pine `bar_index > lastEntryBar`)

### Phase 4: `instances/runner.py` — Same Fixes + Config Application
- Same 3 fixes as worker (grace, equity_history, one-entry-per-bar)
- `strategy_config` from DB applied via `strategy_class(**config)` at instantiation

### Phase 5: `instances/models.py` — New Columns
- `strategy_config` (JSON): per-instance strategy parameter overrides
- `snapshot_data` (JSON): latest state snapshot
- `snapshot_image_url` (String): snapshot image path/URL
- `snapshot_at` (DateTime): when last snapshot taken
- All 4 added to migration spec. Instance table now has 34 columns.

### Phase 6: API Endpoints (3 new, all live-verified)
- `GET /api/v2/strategies/{id}/parameters` — returns 15-param schema
- `GET /api/v2/instances/{slug}/strategy-config` — returns current config + parameter schema
- `PUT /api/v2/instances/{slug}/strategy-config` — saves per-instance config to DB

### Phase 7: `app/routes.py` — Template Wiring
- `get_strategy` imported at module level
- `engine_detail_page` passes `strategy_config` + `strategy_parameters` to template

### Phase 8: `engine_detail.html` — Dynamic Settings Panel
- Settings modal renders 15 strategy params from `get_parameters()`
- Typed fields: select, bool, int, float — all with correct defaults
- `saveSettings()` sends both instance PUT + strategy-config PUT
- Browser-verified: 15 `data-param` fields in DOM

### Full-Scope Test: 61/61 PASS
See NOTES.md for full breakdown (12 test groups, 61 individual tests).

---

## 🧠 Three-Port Architecture

Each strategy script is standalone and declares three ports:

1. **strategy_config** (Port 1): Static per-instance params, stored in DB, editable via UI. Pine `input.*` equivalent. Applied via `__init__(**config)`.
2. **entry_config** (Port 2): Per-signal output — direction, signal strength, metadata. Consumer reads to decide entry. Frontend reads for display.
3. **exit_config** (Port 3): Per-signal exit declaration — stop_loss, take_profit, trail, time_exit, EMA values. Consumer is neutral.

**Key principle:** Strategy script is the single source of truth. PWA is a generic host. New strategies just implement `get_parameters()` + `generate_signals()`.

---

## 📦 Backups

| Version | Description | Size |
|---------|------------|------|
| v90 | Pre-refactor snapshot | 62KB |
| v91 STABLE | Phases 1-5 complete, pre-API endpoints | 680KB |

---

## 🎯 What's Next (Operator Decides)

1. **Phase 9: Strategy Studio clone** — user-named, versioning (e.g. `v1.3-cust-1`)
2. **Phase 10: Python upload tab** — paste Python directly, not just Pine
3. **v1 + v6.1 `get_parameters()`** — add parameter declaration to other strategies
4. **Worker: apply `strategy_config`** — worker reads config from state, not just runner
5. **Aetheris user account** — own strategies, engines, sandbox
6. **Multi-tenant DB spawn** — `cp template_empty_STABLE.db data/tenant_{user_id}.db`
7. **Snapshot capture system** — image + state per instance (columns ready)
8. **Live trade test** — restart worker with new Pine-faithful params, observe
9. **Backtest runner review** — verify equity_history matches Pine (trade-close only)

---

*End of handover. Next session: read CONTEXT.md → HANDOVER-PROMPT.md → NOTES.md → load /adix + /backup-versioning + /karpathy-guidelines → pulse.*

Both servers are running. If you need to restart:

```bash
# Dev UI (paper mode, port 8792)
cd /workspace/projects/strategy-engine
source venv/bin/activate
export $(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' .env | head -20)
export DATABASE_URL="sqlite:////workspace/projects/strategy-engine/data/dev_test.db"
export DRY_RUN=true
python3 -m uvicorn main:app --host 0.0.0.0 --port 8792

# Worker (paper mode, port 9999) — currently on FARTCOIN 15m
cd /workspace/projects/strategy-engine
source venv/bin/activate
export $(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' .env | head -20)
export DATABASE_URL="sqlite:////workspace/projects/strategy-engine/data/worker.db"
export DRY_RUN=true
python3 scripts/worker.py --port 9999
```

⚠️ **DO NOT use `${VAR}` shell expansion in `terminal(background=true)` for secrets — they resolve to empty strings.** Hardcode values or `source .env`.

⚠️ **Dev = `DRY_RUN=true` (paper). Worker = currently `DRY_RUN=true` too (paper testing).** Never flip to live without operator consent.

⚠️ **App entrypoint is `main:app`, NOT `app.main:app`.**

⚠️ **Worker API auth is Basic Auth `operator:operator`. Dev API uses `X-API-Key: goodgirl999` header.**

⚠️ **Background processes (uvicorn/worker) get SIGKILL'd after ~5 minutes in this environment. Use `nohup` or a process manager (systemd, tmux) for persistent uptime. For quick testing: `fuser -k PORT/tcp; sleep 1; cd /workspace/projects/strategy-engine && source venv/bin/activate && export $(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' .env | head -20) && export DATABASE_URL="sqlite:////workspace/projects/strategy-engine/data/dev_test.db" && export DRY_RUN=true && nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8792 > /tmp/dev.log 2>&1 &`**

⚠️ **SQLite WAL/SHM files can corrupt after unclean shutdowns. If `PRAGMA journal_mode=WAL` fails with "database disk image is malformed", delete the DB file and all `-wal/-shm/-journal` files, then restart — SQLAlchemy will recreate the schema.**

Then read: `CONTEXT.md` → `HANDOVER-PROMPT.md` → `NOTES.md` → Load `/adix` skill.

---

## 🔧 Current Server State

| Server | Port | Mode | Status | Details |
|--------|------|------|--------|---------|
| Dev UI | 8792 | `DRY_RUN=true` (paper) | ✅ Running | FARTCOIN engine-1 started, all pages functional |
| Worker | 9999 | `DRY_RUN=true` (paper) | ✅ Running | FARTCOIN 15m 3x leverage, $7.12 equity |

**Worker API state:** `curl -u operator:operator http://localhost:9999/api/state`
**Dev API:** `curl -H "X-API-Key: goodgirl999" http://localhost:8792/api/v2/instances`
**Health:** `curl http://localhost:8792/health`
**HL credentials:** In `.env` file.

---

## ✅ Completed This Session (Phases 1–10B + Audit + UX Overhaul)

### Audit Fixes (P1–P14)

| ID | Bug | Fix | File |
|----|-----|-----|------|
| P2 | Adopted positions missing `size`, `stop_loss`, `take_profit`, `mintick` | Added fields from current signal's `exit_config` | `runner.py` |
| P4 | No same-tick re-entry on reversal | Added reversal re-entry block after close | `runner.py` |
| P5 | Password/API-key comparison used `==` (timing attack) | `secrets.compare_digest` for all 5 comparisons | `api/auth.py` |
| P5b | `detect_mintick` `UnboundLocalError` in adoption code (crashed runner on restart) | Moved import to module level; removed duplicate local import at line 251 | `runner.py` |
| P11 | Anomalous equity snapshots (97% fake drawdowns) | >50% swing filter in `_record_account` | `runner.py` |
| P12 | TP was `None` in `exit_config` when `use_fixed_tp=False` | Always populate ATR-based TP values | `engine/v1_3.py` |
| P14 | Dashboard KPIs had no tooltips, no accessibility | `tip-i` tooltips, `:focus-visible`, skip-link | `dashboard.html`, `style.css`, `layout.html` |

### Worker Fixes (P16 — Previously Deferred, NOW FIXED)

| Fix | File |
|-----|------|
| `equity_history` now appends every signal cycle + trade close | `scripts/worker.py` |
| Adoption dicts now include `size`, `stop_loss`, `take_profit`, `mintick` | `scripts/worker.py` |
| Exit cost estimation from `close_result` (no more `exit_cost=0`) | `scripts/worker.py` |
| Anomalous equity snapshot filter (>50% swing) | `scripts/worker.py` |
| New API endpoints: `GET /api/settings`, `GET /api/state` with equity_history | `scripts/worker.py` |

### Frontend Phase 10B (F1–F11)

| Phase | Component | File |
|-------|-----------|------|
| F1 | Trades page: filter bar, sortable columns, P&L coloring, tooltips, SSE | `trades.html` (rewrite) |
| F2 | Strategies page: tooltips, descriptions, running/idle badges | `strategies.html` (rewrite) |
| F3 | Paper testing: KPI tooltips | `testing_paper.html` |
| F4 | Engine histogram fade-up animations | `engines.html`, `style.css` |
| F5 | Engine detail fade-up animations (histogram, waterfall, streak, comparison) | `engine_detail.html`, `style.css` |
| F6 | Skeleton loading system (shimmer pulse) | `style.css` |
| F7 | Settings tooltips (Display Name, Email) | `settings.html` |
| F8 | Secrets tooltip (Private Key) | `account_secrets.html` |
| F9 | Landing page logged-in state (shows "Go to Dashboard") | `landing.html` |
| F10 | Signup page logic (Coming Soon kept as-is) | — |
| F11 | Docsync (CONTEXT.md, NOTES.md updated) | — |
| F12 | Sticky save bar on Settings page | `settings.html` |
| F13 | ARIA roles on sidebar and main | `layout.html` |

### UX Overhaul (G1–G3 + Logout + Mobile)

| Item | What | Files Changed |
|------|------|---------------|
| G1 | Account value always shows (live exchange fallback + HL connection prompt) | `api/instances.py`, `app/routes.py`, `dashboard.html` |
| G2 | AI assistant = floating bubble everywhere (removed `chat-dashboard` variant) | `chat_widget.html`, `chat_widget.css` |
| G3 | Mobile burger menu (≤768px slide-out nav with all items + logout) | `layout.html`, `style.css` |
| LOGOUT | Full logout flow: progress bar → splash screen with account summary | `logout.html` (new), `main.py`, `app/routes.py` |
| LOGIN | Fixed `doLogin()` to use XMLHttpRequest Basic Auth (no more URL-embedded credentials) | `landing.html` |
| DARK/LIGHT | Mode toggle in topbar with localStorage persistence | `layout.html` |
| ASSISTANT | Full chat UI (sessions sidebar, model selector, thinking animation, mobile input bar) | `assistant.html` (rewrite, 538 lines) |
| SESSION DELETE | `DELETE /api/v2/chat/session/{id}` endpoint + `×` buttons | `app/routes.py` |
| SETTINGS UX | ⚙ Settings button moved to top of engine detail page (brand-colored, 44px) | `engine_detail.html` |
| MODAL | Settings modal: flex column, body scrolls, header/actions pinned, full-screen on mobile | `engine_detail.html` |
| MOBILE | 44px touch targets, KPI grid 2-col, controls wrap | `engine_detail.html` |

---

## 🗂 Key Files Modified (All Sessions Combined)

| File | Key Changes |
|------|-------------|
| `instances/runner.py` | P2: adoption dict fields; P4: reversal re-entry; P11: anomalous snapshot filter |
| `engine/v1_3.py` | P12: TP always populated in exit_config |
| `api/auth.py` | P5: `secrets.compare_digest` for all 5 comparisons |
| `scripts/worker.py` | P16: equity_history, adoption dicts, exit cost, API endpoints, anomalous filter |
| `api/instances.py` | `/summary` live exchange fallback, `has_hl_credentials`, `get_summary_data()` standalone |
| `main.py` | Public `/logout` route with server-side account data rendering |
| `app/routes.py` | Dashboard live exchange fallback, `DELETE /api/v2/chat/session/{id}`, removed old `/logout` |
| `app/templates/dashboard.html` | Connect-wallet prompt, `has_hl_credentials` flag |
| `app/templates/engine_detail.html` | ⚙ Edit Settings button at top, flex column modal, mobile controls |
| `app/templates/engines.html` | Fade-up animations on histogram bars |
| `app/templates/trades.html` | Full rewrite: filter bar, sortable columns, P&L, tooltips, SSE |
| `app/templates/strategies.html` | Full rewrite: tooltips, badges, descriptions |
| `app/templates/assistant.html` | Full rewrite: chat UI, sessions, model selector, thinking animation |
| `app/templates/landing.html` | Logged-in state detection, `doLogin()` XMLHttpRequest fix |
| `app/templates/logout.html` | New: progress bar → splash screen with server-side account data |
| `app/templates/layout.html` | ARIA roles, burger menu, dark/light mode toggle, `{% block head %}` |
| `app/templates/chat_widget.html` | Removed `chat-dashboard` variant, always floating bubble |
| `app/templates/settings.html` | Tooltips on labels, sticky save bar with toast |
| `app/templates/account_secrets.html` | Tooltip on Private Key label |
| `app/templates/testing_paper.html` | KPI tooltips |
| `app/static/style.css` | Chart entrance animations, skeleton loading, burger menu CSS |
| `app/static/chat_widget.css` | Removed dashboard variant, mobile sizing |

---

## 🧠 Strategy v1.3 Behavior

- **Entry:** 3-way AND: `fan_up_trend AND bull_pierce AND valid_trigger_bull`
- **TP is LIVE** — P12 fix: `take_profit_long/short` always populated in `exit_config`
- **Reversal re-entry** — P4 fix: after "Trend Change"/"Reversal Signal" exit, runner re-enters opposite direction same tick
- **PENDING sentinel** prevents double-entry (BUG-001 fix, still in place)
- **Anomalous snapshots filtered** — P11: >50% account value swings are skipped

---

## ⚠️ Known Issues / Watchouts

| Issue | Severity | Notes |
|-------|----------|-------|
| K6: Hardcoded API keys in `config.py` | Medium | API_KEY and API_SECRET still in source. Not yet moved to env-only. |
| Worker-only trade log | Low | No CSV-based trade persistence for live P&L tracking yet |
| `.env` has comments that break `export $(cat .env \| xargs)` | Low | Use `export $(grep -E '^[A-Za-z_]' .env \| head -20)` instead |

### ADIX Pitfalls to Watch

- **#38:** `.py` edits need server restart; `.html`/`.css`/`.js` do NOT
- **#62:** Orphaned child process port binding — verify port free before relaunch
- **#73:** Shell `${VAR}` expansion in `terminal(background=true)` resolves to empty — hardcode or source `.env`
- **#15:** Purge test DBs before validation runs
- **#17:** Test from browser, not just curl
- **#28:** Three live-money footguns (cloid double-fill [FIXED], exit_cost=0 [FIXED], TP never checked [FIXED])
- **#69:** Wrong entrypoint (`app.main:app` vs `main:app`)
- **#70:** Context hint must be read live in handler, not cached at init
- **#NEW:** Settings modal uses flex column — if adding fields, make sure they go inside `.modal-body` not after `.modal-actions`
- **#NEW:** `detect_mintick` must be imported at module level (not locally inside `_execute_open`) — P5b fix for `UnboundLocalError` crash
- **#NEW:** Background uvicorn/worker processes get SIGKILL'd after ~5 min in this environment — use `nohup` or tmux for persistence
- **#NEW:** SQLite WAL/SHM corruption after unclean shutdown — delete DB + WAL/SHM files, let SQLAlchemy recreate

---

## 🎯 What's Next (Operator Decides)

1. **Live trading readiness** — switch worker to `DRY_RUN=false` with operator approval
2. **Worker-only trade log** — CSV-based trade persistence for live P&L tracking
3. **K6: Move API keys to env-only** — remove hardcoded secrets from `config.py`
4. **24h live test analysis** — after worker runs 24h, check `data/logs/worker_2026-07-15.log`
5. **M6: OHLC persistence** — >60d backtests need accumulated candle cache
6. **M7: Worker trade log** — CSV-based trade persistence for live P&L tracking
7. **Polish** — landing logged-in state redirect, signup flow, settings save animation
8. **Backup versioning** — no `.backup` directory or script yet (using `backups/` tar.gz)

---

## 📦 Backups

| Version | Tag | Size | What |
|---------|-----|------|------|
| v85 | audit-pre-phase1 | 654KB | Before audit fixes |
| v86 | audit-fixes-phase1-12 | 655KB | After P1-P12 |
| v87 | worker-fixes | 658KB | After worker equity/exit/cost fixes |
| v88 | pre-F1-trades | 659KB | Before frontend Phase 10B |
| v89 | engine-settings-mobile | 708KB | After settings UX + modal scroll fix |

---

*End of handover. Next session: read CONTEXT.md → HANDOVER-PROMPT.md → NOTES.md → load /adix → pulse.*