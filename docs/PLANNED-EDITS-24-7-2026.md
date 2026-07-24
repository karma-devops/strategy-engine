# PLANNED-EDITS-24-7-2026 — Consolidated Live Repair Plan

**Project:** strategy-engine
**Status:** APPROVED 2026-07-24 (operator go; all engines halted, 24h live test stopped). Execution authorized with care.
**Discipline:** ADIX — one verified file change per turn, commit+push each; backup DB before any mutation.

---

## 0. RECONCILIATION — dropped / merged stale items

Two external docs were reviewed and verified item-by-item against disk (2026-07-24). Both were partially STALE.

**Sources:**
- Attached `strategy-engine-functional-analysis.md` (dated 2026-07-23)
- `AEE.md` (engine-detail page bug-hunt, 2026-07-19)

**DROPPED (already fixed in code at 2026-07-24):**
| Item | Claim | Disk reality |
|---|---|---|
| F1 `paper_routes.py` missing `instances` | 🔴 broken | FIXED — lines 52-58 query correctly |
| F2 `@dataclass` on `BacktestTrade` | 🔴 broken | FIXED — `@dataclass` at backtests/runner.py:47 |
| F5 entry cost uses `TAKER_FEE` | 🟠 wrong math | FIXED — backtests/runner.py:663 uses `_entry_cost()` |
| AEE Defect 1 (pulse graph empty) | 🔴 broken | FIXED — engine_detail.html:378 uses `PulsRChart.createEquityChart` |
| AEE Defect 2 (positions unstyled) | 🔴 broken | FIXED — engine_detail.html:87 `#pos-card` + :344 `renderEngineDetailPosition` |
| AEE Defect 3 (settings don't persist) | 🔴 broken | FIXED — PUT path engine_detail.html:187-238 works; runner revert bug fixed in 3e7d2fa |

> **AEE.md DELETED per operator instruction** (faulty naming + all defects resolved). Its only useful residue — "engine-detail page already uses PulsRChart + renderEngineDetailPosition + working PUT" — is recorded here so Phase A3 only needs confirmation, not rebuild.

**MERGED as live defects (verified broken on disk):** ROOT-2, ROOT-3, FE-1, FE-2, FE-3, FE-4, FE-5, PINE-1, PINE-2.
**TO-VERIFY-BEFORE-FIX (gates):** F3 (OHLC None-guard), F4 (backtests.html profile), F6 (activation int), F7 (slippage naming).

---

## 1. VERIFIED GROUND TRUTH (disk-confirmed 2026-07-24)

| Mechanism | Location | Finding |
|---|---|---|
| `get_account_value()` | core/exchange.py | perps `accountValue` + spot USDC = total portfolio |
| `get_perp_account_value()` | core/exchange.py | HL-native perp-only = consistent figure |
| Positions render (dash) | dashboard.html:680 `renderPositions` | reads DB `position_side` |
| Positions render (engine) | engine_detail.html:344 `renderEngineDetailPosition` | FIXED (AEE) — uses styled `#pos-card` |
| HL-live positions | api/positions.py `/api/v2/positions` | correct; position-card.js `hydratePositions` (265) polls 3s + SSE |
| Runner writes `position_side` | runner.py:707/736 | only when HL truthy; None on stale-None ticks |
| Pulse seed | dashboard.html:282/686 | `equityData` from `/summary.equity_series` if empty |
| Pulse live push | dashboard.html:758-760 + stream.py:55 | pushes value, **60-cap `shift()` evicts history → scale jump** |
| Anomaly filter | runner.py:1076-1089 `_record_account` | **drops >50% swing → gaps in `account_snapshots`** |
| KPI account_value | api/instances.py:280-295 | operator override calls `get_account_value()` (full perps+spot) |
| Trades pricing | runner.py:879-951 `_close_active_trade` | NO HL `user_fills` correlate; `exit_price=mark_px`; **NO `user_id`** (FE-1) |
| AccountSnapshot model | models.py:373-382 | `account_value`, `withdrawable`, `dry_run`, `timestamp` — **NO `source` column** |
| EMA prev update | runner.py:257-265 | sets `_prev_fast/medm_ema` BEFORE `_evaluate_exit` (~476) → crossunder never fires (ROOT-2) |
| Backtest trail | backtests/runner.py:300-345 | `trail_activation`=activation, `trail_offset`=distance — OPPOSITE of live (ROOT-3) |
| Paper equity | runner.py:1072 | `_record_account` uses `_paper_balance` only → flatlines on open trade (FE-5) |
| v1_3 risk_profile | engine/v1_3.py:644 | hardcoded `"Scalp Aggressive (8/3)"` (PINE-1) |
| v6_1 man_* | engine/v6_1.py:61-62 | `man_activation`/`man_offset` set but NOT wired to `active_*` (PINE-2) |
| position-card.js HTTPS | position-card.js:268 | hardcodes `'http://'` strip → wrong scheme on HTTPS (FE-4) |

**My 4 prior corrections — now verified against disk:**
1. **A1 gate bug CONFIRMED** — api/instances.py:237 requires `i.position_side != "FLAT"` before calling HL, so the HL override never fires for the stale-None case. Real plan gap, fixed in Phase A1.
2. **A1 field mapping UNVERIFIED** — `get_position()` return shape not yet read (only `liquidationPx` consumed). Phase A0 reads it.
3. **B1→B2/B4 ordering CONFIRMED load-bearing** — `AccountSnapshot` has no `source` column; `_record_account` writes none. B2/B4 crash before B1. B1 must land first.
4. **Residual grep-only sections NOW VERIFIED** — dashboard.html pulse JS (682-762), KPI (202/665/747), position-card.js hydratePositions (265) all match plan.

---

## 2. PHASED PLAN

### Phase A — Positions HL-live (API + JS)  [safe with engines stopped/running]
- **A0.** READ `core/exchange.py get_position()` return dict. Verify keys (`entryPx`, `sz`, `unrealizedPnl`, `liquidationPx`).
- **A1.** `api/instances.py:237` relax gate: call HL for all `status==running & dry_run is False`; let HL drive `position_side`/`size`/`entry`/`mark`/`pnl`. Keep DB fallback on HL error. *(Fixes stale-None flash-vanish — verified gate bug.)*
- **A2.** `position-card.js:265` already 3s-poll + SSE (verified). Confirm dashboard sets `window.API_KEY` (975 does). Gate: position stable 1min vs live HL.
- **A3.** `engine_detail.html:344` `renderEngineDetailPosition` already wired (AEE fixed). Confirm A1 override flows in. No rebuild.

### Phase B — Pulse pure-append (model + filter + JS)  [model migration → restart after]
- **B1.** `models.py:373` add `source = Column(String(16), default="perp")`. **MUST land before B2/B4.**
- **B2.** `runner.py:1076-1089` remove >50% filter; write `get_perp_account_value()` stamped `source="perp"`.
- **B3.** `dashboard.html:682-762` replace 60-cap with append-only `balance_history` (trim front >2000); seed from `/summary.equity_series`.
- **B4.** `api/instances.py` `equity_series` filter `source="perp"`. Gate: continuous 1h+ history, smooth tail, no jump.

### Phase C — KPI ≡ pulse ≡ HL  [no schema change]
- **C1.** `api/instances.py:291` operator override `get_account_value()` → `get_perp_account_value()`. Gate: KPI == pulse tail == HL perp dashboard.

### Phase D — Trades HL-accurate (DB mutation)  [backup before writes]
- **D0.** `cp data/dev_test.db /tmp/dev_test.db.bak.$(date +%s)`.
- **D1.** `runner.py:942` add `user_id=self.instance.user_id` (FE-1). Both close branches correlate HL `user_fills` by (side, px, ts±30s) for real `closedPnl`/`exit_price`; fallback `mark_px` only if no fill.
- **D2.** `runner.py:765 _execute_open` write open `Trade` row (`pnl_usd=0`), update in place on close (match by signal_id/open ts).
- **D3.** New `scripts/backfill_trades_hl.py` — re-pull `user_fills`, reconcile window. Gate: `trades` mirrors HL.

### Phase E — Engine correctness (live-behavior)  [engines halted → executable]
- **E1. ROOT-2:** `runner.py:257-265` move `_prev_fast/medm_ema` update to AFTER `_evaluate_exit` (~476). Gate: trend-change exit fires on EMA crossunder.
- **E2. ROOT-3 + F3:** verify live `_evaluate_exit` trail semantics; align `backtests/runner.py:300-345` + OHLC 563-614 so `trail_activation`=distance, `trail_offset`=activation; confirm/add None-guards at OHLC blocks. Gate: backtest trail matches live.
- **E3. PINE-1:** `engine/v1_3.py:644` `"risk_profile": self.risk_profile`.
- **E4. FE-5:** `runner.py:1072` mark paper balance to market during open trade (`_active_trade` stores `current_mark_price`).
- **E5. PINE-2:** `engine/v6_1.py:61-62` wire `active_activation=man_activation`, `active_offset=man_offset`.

### Phase F — Paper/Backtest UI (safe, no engine logic, no restart needed)
- **F1. FE-4:** `position-card.js:268` HTTPS scheme fix (3 lines).
- **F2. FE-2:** verify `testing_paper.html:208` `time_unix` exists in `paper_routes.py` dict; add if missing.
- **F3. FE-3:** verify `paper_routes.py` inst_data `account_value` not aliased to `unrealized_pnl`; fix if present.
- **F4. F4:** `backtests.html` profile payload → valid label + dropdown from `GET /api/v2/strategies`.
- **F5. F6:** `api/backtests.py:37` `activation: int`.
- **F6. F7:** `cost_model.py` `slippage_bps` naming doc (optional cleanup).

### Phase G — Restart & Full Verify
- **G1.** Kill runner processes; confirm port 8792 free.
- **G2.** Relaunch: `DATABASE_URL=dev_test.db STRATEGY_ENGINE_PORT=8792 ./venv/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8792`.
- **G3.** Health: landing 200, `/app/dashboard` 200, `/api/v2/summary` 200 (per-user key).
- **G4.** Functional: open paper pos → shows (A); pulse appends (B); KPI matches (C); close → trades correct (D); EMA exit fires (E1); backtest trail matches (E2).

---

## 3. EXECUTION DISCIPLINE
- ADIX: one verified file change per turn; `git add -p` style, commit+push each.
- Backup DB before Phase D mutations.
- Each phase has a Gate — do not advance until green.
- No autonomous deletion (AEE.md deletion pre-authorized by operator).

## 4. FILE TOUCH MAP
| Phase | File | Type |
|---|---|---|
| A0 | core/exchange.py | read |
| A1 | api/instances.py | gate relax + HL enrich |
| A2 | app/static/position-card.js | confirm only |
| A3 | app/templates/engine_detail.html | confirm only |
| B1 | instances/models.py | +1 column |
| B2 | instances/runner.py | filter removal + perp source |
| B3 | app/templates/dashboard.html | JS pulse rewrite |
| B4 | api/instances.py | equity_series filter |
| C1 | api/instances.py | perp KPI |
| D1 | instances/runner.py | trades user_id + HL pricing |
| D2 | instances/runner.py | trades open row |
| D3 | scripts/backfill_trades_hl.py | new script |
| E1 | instances/runner.py | EMA update order |
| E2 | backtests/runner.py | trail semantics + None-guard |
| E3 | engine/v1_3.py | risk_profile |
| E4 | instances/runner.py | paper mark-to-market |
| E5 | engine/v6_1.py | man_* wiring |
| F1 | app/static/position-card.js | HTTPS scheme |
| F2 | app/paper_routes.py + testing_paper.html | time_unix |
| F3 | app/paper_routes.py | account_value |
| F4 | app/templates/backtests.html | profile payload |
| F5 | api/backtests.py | activation int |
| G | shell | restart + verify |

## 5. OPEN VERIFICATION GATES (verify before fix)
- **F3** OHLC None-guard (backtests/runner.py:563-614)
- **F4** backtests.html profile payload (`"balanced"` invalid)
- **F6** api/backtests.py:37 `activation` type
- **F7** cost_model.py `slippage_bps` naming
