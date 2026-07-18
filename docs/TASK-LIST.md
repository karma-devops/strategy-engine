# PULS·R Task List — Beta Readiness Inventory

**Created:** 2026-07-17  
**Last reconciled:** 2026-07-18 (end-of-day execution + stability reality)  
**Version:** v1.98  
**Status:** ⚠️ NOT STABLE / NOT BETA — code-complete, needs live frontend testing + bughunt  
**Live State:** engine-1 RUNNING LIVE (FARTCOIN LONG, liq enriched via A4) · engine-2 STOPPED (paper) · main app UP port 8792

**4-FILE DOC TAXONOMY (CONFIRMED):**
- CONTEXT.md: The MAP — architecture, product spec, deployment, naming, pipe/IA design, strategy-converter ref
- NOTES.md: The LOG — session handovers, audit tables, ROAST findings, live-state snapshots, decisions
- TASK-LIST.md: The WORK — all open tasks/bugs/UI/UX/infra/backlog
- BETA-ROADMAP.md: The FORWARD PLAN — beta gate, verification, hardening, UI, deploy action items

**DEPRECATED (MOVED TO BACKUPS - NO REMOVER):**
- SPECSHEET.md, DEPLOYMENT.md, NAMING.md, PIPE-ARCHITECTURE.md, IA-SPEC.md, DESIGN-SPEC.md, DESIGN-SPEC-V2.md, STRATEGY_CONVERTER.md
- HANDOVER.md, HANDOVER-PROMPT.md, ROAST.md, REFACTOR_PLAN.md

**4-WAY STRICT SEPARATION (SOLID / DDD) — beta-blocker (Z1–Z7):**
- LIVE: Dashboard/Engines/Trades (dry_run=False) — LIVE state only
- PAPER: Paper Trading (new top-level menu, dry_run=True)
- BACKTEST: Isolated store (backtest.db), never touches live/paper data
- STRATEGY: Code + params — pure execution (shared kernel)

**MENU RESTRUCTURE (Z2):**
- DROP "Testing" collapsible
- Paper Trading and Backtesting become top-level siblings
- Trades page = LIVE only (dry_run=False)

**PALETTE AUTHORITY (MASTER.md WINS):**
- #34D399 profit / #FB7185 loss / #15100B surface-card — authoritative
- CONTEXT §6 (#10b981/#ef4444) and tokens.css values are outdated — reconcile via Z4

---

## A. Open Positions UI (Primary Focus)

### A1. Dashboard — Visible Open Positions Card
- **Current state:** `#pos-grid` exists in dashboard.html as CSS grid, **visible but empty** — no JS population logic (grep confirmed zero renderPos/pos-grid refs in app/static/).
- **Needed:** Make `#pos-grid` functional with:
  - Per-position card: token, side (LONG/SHORT tag + HL-style left-edge spine), size, entry price, mark price, unrealized PnL, leverage, duration
  - Close Position button (calls `/api/v2/instances/{slug}/close`)
  - "View on Exchange" link (hyperliquid.xyz)
  - Close All / Emergency Stop actions
  - Empty state: "No open positions" with SVG icon
- **CSS:** `.pos-card`, `.pos-row`, `.pos-head` styles in layout.html (lines 583-589) minimal. Expand with proper card styling, side-specific accent borders (green=LONG, red=SHORT), responsive grid.
- **Status:** OPEN (Z5 will implement)

### A2. Dashboard — Real-Time Position Updates via SSE
- **Current state:** Dashboard polls `/api/v2/summary` every 3s but `renderPositions()` isn't connected to polling loop.
- **Needed:** Wire `refresh()` function to update `#pos-grid` on each poll. SSE `/stream` should push `position` events (currently emits `trade` only).
- **Status:** OPEN (Z5 extension)

### A3. Engine Detail — Enhanced Position Card
- **Current state:** `engine_detail.html` has static `#pos-card` with side/size/entry/mark/pnl/leverage (lines 140-153). No real-time update.
- **Needed:** Live-updating mark price + PnL, liquidation price, duration, entry cost/notional, PnL %, stop-loss/take-profit levels, Close button, FLAT empty state.
- **Status:** OPEN (Z5 extension)

### A4. API — Add Liquidation Price + Position Metadata to Summary
- **Current state:** `/api/v2/summary` returns position_side, position_size, entry_price, mark_price, unrealized_pnl per instance. Missing: liquidation_price, entry_cost, pnl_pct, duration, stop_loss, take_profit.
- **Gap:** Running-position `liquidation_price` shows 0.0 (runner only populates on adopt/close, not tick).
- **Needed:** Enrich summary endpoint with liquidation_price from HL position.liquidationPx, entry_cost, pnl_pct, duration, stop_loss/take_profit from _active_trade metadata, margin_used.
- **Status:** OPEN (A4-gap, U3)

### A5. Dashboard — KPI "Open Positions" Count
- **Current state:** Dashboard has "Positions" KPI (line 628) counting instances with position_side !== 'FLAT'. Works via JS polling.
- **Needed:** Ensure KPI updates on every poll, matches visible position cards.
- **Status:** OPEN (verify after Z5)

### A6. Dashboard — Position Change SSE Event
- **Current state:** SSE `/stream` emits `trade` events (open/close) but no `position` event type.
- **Needed:** Add `position` event to SSE stream (instances/events.py or api/stream.py). Emit on every _sync_position call. Frontend updates cards without 3s poll wait.
- **Status:** OPEN

### A7. Trades Page — Open Positions Section
- **Current state:** /app/trades has "Open Positions" KPI but no dedicated open positions section.
- **Needed:** Add "Active Positions" section above trades table with real-time PnL (mirrors dashboard pos cards).
- **Status:** OPEN

### A8. Mobile — Position Cards Responsive Layout
- **Current state:** `.pos-card` styles minimal (layout.html lines 583-589), no mobile breakpoint handling.
- **Needed:** Mobile (≤768px): cards stack full-width, 44px touch targets, prominent side tag + PnL, 44px Close button.
- **Status:** OPEN

---

## B. Known Bugs (From Audit, NOTES)

### B1. [FIXED] Stale HL Client — position=None despite live position
- **Status:** ✅ FIXED (commit `f66dffe` — `_refresh_hl_client()` + retry counter + _sync_position guard)

### B2. [FIXED] Password hash missing on fresh DB
- **Status:** ✅ FIXED (seed `hash_password('operator')` on fresh DB)

### B3. [MEDIUM] Per-user log persistence (#5 from audit)
- **Status:** OPEN
- **Issue:** LOG_BUFFER is in-memory only, max 200, global. No per-user disk persistence.
- **Plan:** Write per-user logs to `data/logs/{user_id}.jsonl`, rotate on size

### B4. [MEDIUM] Active Trades Card on Dashboard (#6 from audit)
- **Status:** OPEN (overlaps with A1)
- **Plan:** Covered by A1 task

### B5. [LOW] 50 nullable columns that should be NOT NULL (#8 from audit)
- **Status:** OPEN
- **Plan:** Add NOT NULL constraints with sensible defaults via migration

### B6. [LOW] No explicit cascade deletes (#9 from audit)
- **Status:** OPEN
- **Plan:** Add cascade delete constraints to foreign keys

### B7. [MEDIUM] Kill switch doesn't close open positions (#8 from original audit)
- **Status:** ✅ FIXED (2026-07-18) — `stop_instance()` in `api/instances.py` now calls `market_close()` before halting; kill-switch already closed all. Verified: FARTCOIN position closed on HL.

### B8. [FIXED] Per-user encrypted API key storage (#2 from audit)
- **Status:** ✅ FIXED (P12 commit `60f039a` — Fernet encryption)

### B9. [MEDIUM] Drawdown 97.73% bug — anomalous account snapshots
- **Status:** OPEN
- **Issue:** HL API returns inconsistent values during position transitions, causing fake drawdown spikes
- **Plan:** Filter snapshots with >50% swing in `_record_account`

---

## X. bugreport.txt Items (2026-07-18 attachment review)

### X1. Duplicate-entry sanitization
- **Status:** ✅ FIXED (2026-07-18) — `instances/runner.py` sets synchronous `PENDING` sentinel before `_execute_open`; blocks re-entry on next 3s poll. Imports clean.

### X2. Entry-without-pin-bar guard
- **Status:** ✅ FIXED (2026-07-18) — entry requires `valid_trigger_bull/bear` flag from strategy result; skips otherwise. Imports clean.

### X3. Backtester/paper start-balance default + timeframe options
- **Status:** ✅ FIXED (2026-07-18) — `testing_historical.html` form: 30m/3h/1d timeframes + start-balance field (default 100) + HL token registry link; payload wired to `initial_capital`. Live form renders.

### X4. ExecutionCostModel proposal
- **Status:** ✅ FIXED (2026-07-18) — `backtests/cost_model.py` (maker/taker/slippage/spread) created + wired into `backtests/runner.py` (replaces hardcoded TAKER_FEE). Verified: entry $0.13 / exit $0.10 per $100.

---

## D. Infrastructure / Backend

### D1. Version string drift
- **Status:** ✅ FIXED (2026-07-18) — `main.py` now reads `version=VERSION` (was hardcoded "0.095"). `/openapi.json` → "v1.98" live-verified.

### D2. Server Restart Resilience
- **Status:** ✅ FIXED (2026-07-18) — runner `_loop` auto-restarts on crash (5× exp backoff); manager `load_instances(auto_resume=True)` resumes running instances on boot. Verified: engine-1 auto-resumed after server restart. (Note: required a restore+re-apply cycle due to class-structure corruption during patch — see NOTES.)

### D3. [FIXED] Equity History for Live Runner
- **Status:** ✅ FIXED (verified in runner._tick() — equity_history passed to strategy)

### D4. P14e — Engine Detail PAPER/LIVE Badge
- **Status:** OPEN
- **Plan:** Add PAPER/LIVE badge on each trade row + engine_detail header

### D5. Per-Instance Dry_Run Toggle in UI
- **Status:** OPEN
- **Plan:** Verify toggle works end-to-end (toggle → API → runner respects change)

### D6. Position Reconciliation on Restart
- **Status:** OPEN (improved by f66dffe, verify fully)
- **Plan:** Verify _refresh_hl_client() fix resolves stale data fully on restart

---

## Z. Separation / DDD Group (Beta-Blocker — Z1–Z7)

### Z1. Blueprint Split — routes.py → live_bp / paper_bp / backtest_bp
- **Status:** OPEN (beta-blocker)
- **Plan:** Split monolithic routes.py into three routers:
  - `app/routes.py` → LIVE only (dashboard, engines, trades(LIVE), account, settings, strategies, assistant, withdrawals)
  - `app/paper_routes.py` → Paper page + paper results/trades history
  - `app/backtest_routes.py` → Backtesting page + backtest runs/results
  - `app/_common.py` → pure helpers (_safe_tojson, auth deps, theme inject) — ZERO DB access
- **No-bleed guarantee:** Each router injects correct repository; repositories append filters unconditionally

### Z2. Menu HTML Restructure
- **Status:** OPEN (beta-blocker)
- **Plan:** Update `app/templates/layout.html` nav:
  - DROP "Testing" collapsible
  - ADD top-level "Paper" (forward-testing simulation, dry-run only, no executions)
  - ADD top-level "Backtesting" (historical simulation, isolated store)
  - "Trades" = LIVE only

### Z3. Instances Page — Dynamic LIVE/PAPER Schema
- **Status:** ✅ DONE (2026-07-18) — `engine_detail.html` restored (was corrupted with Paper Trading markup), wired `window.ENGINE_INSTANCE_DATA`, added LIVE/PAPER mode tag, included `position-card.js`. Live-verified: `/app/engines/engine-1` → 200 "FARTCOIN Scalp", shows LIVE tag.

### Z4. Design-System Extension — theme-glow + components + position-card-spec
- **Status:** ✅ DONE (2026-07-18) — `design-system/theme-glow.md` + `theme-glow.css`, `components.md`, `position-card-spec.md` created (MASTER.md authority preserved).

### Z5. Position Card — HL Replication + #pos-grid Population
- **Status:** ✅ DONE (code) / ⚠️ VISUAL UNVERIFIED (2026-07-18) — `app/static/position-card.js` created + wired to dashboard (`#pos-grid`) + engine_detail (`#pos-card`). JS included + `window.POSITIONS_DATA` injected. **NOT yet visually confirmed in browser with a live position render** — see BUGHUNT group.

### Z6. Backtest — Isolated Store (backtest.db)
- **Status:** ✅ DONE (2026-07-18) — `testing/backtest_store.py` created (isolated SQLite, no FK to live/paper). Imports clean.

### Z7. Unified Testing Runner — testing/runner.py (--mode paper|backtest)
- **Status:** ✅ DONE (2026-07-18) — `testing/runner.py` created, `--mode paper|backtest` CLI, wired to `run_backtest`, **executed a real 7-day FARTCOIN backtest end-to-end** (pipeline works, 0 trades in window). Imports + CLI verified.

---

## BUGHUNT — Live Frontend + Wiring Verification (NEXT PHASE, pre-beta)

**⚠️ NOT STABLE / NOT BETA.** Operator directive: "we need to actually front end practical testing live with it before we can assume that." Code is complete; bugs unknown until used.

### BUG-1. Visual verify #pos-grid population (Z5)
- **Status:** OPEN (blocker for "stable")
- **Plan:** Open Dashboard in browser with engine-1 LIVE + position open. Confirm `#pos-grid` renders position-card.js output (HL spine, long=profit color, fields populated from `window.POSITIONS_DATA`). Screenshot + compare to `design-system/position-card-spec.md`.
- **Verify:** browser_vision screenshot of `/app/dashboard` with live position.

### BUG-2. Visual verify engine_detail LIVE/PAPER mode tag (Z3)
- **Status:** OPEN
- **Plan:** Open `/app/engines/engine-1` (LIVE) — confirm header shows "LIVE" tag + correct title. Open a paper engine — confirm "PAPER" tag. Screenshot both.

### BUG-3. Backtest form submit → results render (X3/Z7)
- **Status:** OPEN
- **Plan:** In browser, fill backtest form (FARTCOIN, 15m, 100 balance, 7d), submit. Confirm results table/chart renders from `backtest.db`. Check console for JS errors.

### BUG-4. Paper page forward-test flow (Z1/Z2)
- **Status:** OPEN
- **Plan:** Open `/app/testing/paper`. Confirm paper instances list + "New Paper Engine" flow works. Start a paper engine, confirm it runs dry_run (no HL orders) + shows in Paper results.

### BUG-5. Menu navigation integrity (Z2)
- **Status:** OPEN
- **Plan:** Click through all top-level menu items (Dashboard / Engines / Strategies / Paper / Backtesting / Trades / Account / Assistant). Confirm no 404 / no broken layout. Confirm "Testing" collapsible is GONE.

### BUG-6. Trade PAPER/LIVE badge (D4)
- **Status:** OPEN
- **Plan:** Confirm trades page shows LIVE badge on live trades; paper trades show PAPER badge on Paper results page. No bleed (live trades never show paper badge).

### BUG-7. Dry-run toggle end-to-end (D5)
- **Status:** OPEN
- **Plan:** Toggle an engine dry_run in UI → confirm API receives → runner respects (no HL orders when dry_run=True).

### BUG-8. Run actual test suite (if any exist)
- **Status:** OPEN
- **Plan:** `tests/` has 20 files (~2.4k LOC). Execute `pytest tests/` (or project's runner). Report pass/fail. Fix any failures before beta.

### BUG-9. Console error sweep (all pages)
- **Status:** OPEN
- **Plan:** Load each authenticated page, capture browser console errors (browser_console). Fix JS exceptions.

---

## Priority Order (Updated 2026-07-18 end-of-day)

1. **BUG-1 → BUG-5** — Live frontend practical testing (operator directive: must actually use the UI)
2. **BUG-8** — Run test suite (correctness proof)
3. **BUG-6 / BUG-7** — PAPER/LIVE badge + dry-run toggle (separation integrity)
4. **BUG-9** — Console error sweep (UI robustness)
5. **B3 / B9** — Remaining backend audits (per-user logs, drawdown filter)
6. **D0** — Confirm no 500s remain from old routes.py (absorbed into _common.py)

---

## Execution Notes

- **engine-1:** RUNNING LIVE (FARTCOIN LONG ~390, liq=0.1228 via A4, auto-resumed after D2 restart test)
- **Main app:** UP port 8792, healthy, version v1.98
- **Worker (9999):** DOWN (standalone tester per directive)
- **Backup chain:** TASK-LIST-pre-beta_0910 → stub → Z+X rebuild → pre-eod_1504 (this update)
- **ADIX:** One file per turn, verify before next
- **Stability:** NOT STABLE / NOT BETA until BUGHUNT group closed + test suite green

