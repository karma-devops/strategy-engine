# PLANNED-EDITS-24-7-2026 — Live UI Repair Plan (Pulse · Positions · Trades · KPI)

**Project:** strategy-engine · **Status:** APPROVED for hotfix (operator go, 2026-07-24)
**Engines:** RUNNING — operator is ~10h into a 24h live test (engine-1 LIVE). This plan is **DEFERRED** until the live test completes. Do NOT execute while engines are live (mutations touch runner + DB + restart). Status: drafted, pending post-test execution.
**Principle (operator directive):** HL is the source of truth for *rendering*. DB is the *historical record*. No mismatch between KPI, Pulse, and HL.

---

## 0. VERIFIED GROUND TRUTH (from source read)

| Mechanism | Location | Finding |
|---|---|---|
| `get_account_value()` | `core/exchange.py:134` | perps `accountValue` + available spot USDC = **total portfolio** |
| `get_perp_account_value()` | `core/exchange.py:151` | HL-native perp-only `marginSummary.accountValue` (excludes idle spot) — **the consistent figure** |
| Positions render | `dashboard.html:680` `renderPositions(d.instances)`; `engine_detail.html:337` | reads DB `Instance.position_side` column, NOT HL live |
| HL-live positions exist | `api/positions.py` (`/api/v2/positions`) | correct, but only fetched once at boot by `position-card.js:265 hydratePositions()` |
| Runner writes `position_side` | `instances/runner.py:707/736` | only when HL `position` truthy; sets `None` on stale-None ticks (line 712) |
| Pulse seed | `dashboard.html:682-692` | `equityData` seeded from `/summary` `equity_series` (1h) ONLY if empty |
| Pulse live push | `dashboard.html:755-762` + `stream.py:55` | SSE pushes `get_account_value()` (full) into `equityData` **capped 60-pt rolling window** → evicts 1h history → scale jump |
| Anomaly filter | `instances/runner.py:1076-1089` `_record_account` | **drops snapshot if swing >50%** from last-good → gaps in `account_snapshots` at transitions |
| KPI account_value | `api/instances.py:280-290` | `/summary` returns `account_value`; for operator it's overridden with LIVE `get_account_value()` (full perps+spot) — but pulse history uses `account_snapshots.account_value` (same full figure) → *should* match, but the 60-cap eviction + gaps break visual continuity |
| Trades pricing | `instances/runner.py:946-947` `_close_active_trade` | `exit_price=mark_px`; HL `user_fills` override only on `position is None` branch (line 923) → `pnl_usd`/`exit_price` wrong on normal closes |
| AccountSnapshot model | `instances/models.py:373-382` | `account_value`, `withdrawable`, `dry_run`, `timestamp` — no `source` column |
| PositionSnapshot model | `instances/models.py:359-370` | `side`,`size`,`entry_price`,`mark_price`,`unrealized_pnl_*` |

---

## 1. DESIGN DECISIONS (operator-approved)

1. **Positions** → always rendered from **HL live** (`/api/v2/positions`), never the stale DB column.
2. **Pulse** → a **pure `balance_history` array** that always appends the latest value; seeded from DB history on load, then live-appended (no fixed cap that evicts history; append-only, trim from front only to a generous max e.g. 2000).
3. **Live KPI** → fetched **directly from `get_account_value()` / `get_perp_account_value()`** (same source as the pulse), so KPI ≡ pulse tail ≡ HL. No cross-source mismatch.
4. **Trades** → corrected from HL `user_fills` at close (both branches); open legs recorded; backfill script post-fix.

---

## 2. PHASES

### PHASE A — Positions: HL-live render (JS + 1 read endpoint)
**Safe to run with engines stopped or running. No DB schema change.**

- **A1.** `api/instances.py` `/summary` (lines 237-245 A4 block): extend the live HL enrichment to ALL running instances — for each, call `get_hyperliquid_client(i).get_position(i.token)`; if open, override `position_side` / `position_size` / `entry_price` / `mark_price` / `unrealized_pnl` from HL (already imports `get_hyperliquid_client`). Keep DB as fallback when HL fails.
  - *Verify:* `curl /api/v2/summary` (operator per-user key) → engine with open pos shows correct `position_side` + `entry_price`.
- **A2.** `app/static/position-card.js` `hydratePositions()` (line 265): change from one-time boot fetch to a **3s interval** that re-fetches `/api/v2/positions` and re-renders `window.POSITIONS_DATA` (so it never reverts to stale). Gate on `window.API_KEY` being set on dashboard (currently `dashboard.html:448` sets it — confirm both pages set it).
  - *Verify:* open a position on HL (paper engine), dashboard shows it persistently across 10s, no flash-vanish.
- **A3.** `engine_detail.html` (line 337): already reads `inst.position_side` from `/summary` → inherits A1. Confirm `renderEngineDetailPosition()` uses the same. No change unless mismatch found.

**Gate A:** positions visible & stable on both dashboard + engine page for 1 min against a live HL position.

---

### PHASE B — Pulse: pure appending balance_history (JS + runner filter + 1 model col)
**Engines stopped → can restart after. Includes model migration.**

- **B1.** `instances/models.py` `AccountSnapshot` (line 373): add `source = Column(String(16), default="perp")` to distinguish `perp` (HL-native perp-only) vs `total` (perps+spot). Generates Alembic/SQLAlchemy `ALTER TABLE` on next `Base.metadata.create_all`.
  - *Verify:* `python -c "from instances.models import AccountSnapshot; print(AccountSnapshot.__table__.columns)"` shows `source`.
- **B2.** `instances/runner.py` `_record_account` (line 1076-1089): **remove the >50% drop**. Record every tick. Use `get_perp_account_value()` (HL-native, consistent with KPI) as the `account_value` written to `account_snapshots`, stamped `source="perp"`. If a swing is suspicious, set a flag column (or just keep it — visual gaps were the real bug, not a few bad points).
  - *Verify:* after restart + 1 tick, `account_snapshots` has a contiguous row (no gaps) for the window; `source='perp'`.
- **B3.** `dashboard.html` pulse JS (lines 682-762): replace the 60-cap rolling window with **append-only `balance_history`**:
  - Seed `balance_history` from `/summary.equity_series` (DB history, `source` filtered) on load (if empty).
  - On SSE `metrics` (line 745-762): `balance_history.push({time: Date.now()/1000, value: m.portfolio_value})`; trim from front only if `length > 2000`. **Never shift out the DB history.**
  - `buildPulse()` reads `balance_history` (rename from `equityData` or alias). Scale to its own min/max → stable, no jump.
  - *Verify:* reload page → 1h history shows; live point appends at the tail continuously for 60s+ without the line "jumping" or history disappearing.
- **B4.** `api/instances.py` `/summary` `equity_series` (line 257): filter `AccountSnapshot` by `source="perp"` (so pulse + KPI use the same HL-native figure). Default `hours` handling unchanged.

**Gate B:** pulse renders continuous 1h+ history; live tail appends smoothly; reload shows no discontinuity; `account_snapshots` has no gaps.

---

### PHASE C — Live KPI from HL directly (backend + JS align)
**Ensures KPI ≡ pulse tail ≡ HL. No schema change.**

- **C1.** `api/instances.py` `/summary` (lines 280-290): the operator live override already calls `hl.get_account_value()`. Change it to `hl.get_perp_account_value()` so the KPI figure **equals** the pulse's `source="perp"` history. (Perp-only is the consistent, non-jumpy figure; full perps+spot can jump when spot USDC moves.)
  - *Verify:* KPI `account_value` == last `account_snapshots` (`source='perp'`) value == HL dashboard perp account value.
- **C2.** `dashboard.html` KPI render (lines 202/206, 664, 934): ensure `kpi-account` + ticker show the `/summary.account_value` (now perp-consistent). No separate live fetch needed — `/summary` already live for operator. If a faster KPI is wanted, add a 1s SSE-driven `portfolio_value` text update (already at line 745-757) but **label it clearly as the same perp figure**.
  - *Verify:* KPI number matches pulse tail exactly.

**Gate C:** KPI, pulse tail, and HL perp dashboard all show the same number within rounding.

---

### PHASE D — Trades: HL-accurate pricing (DB mutation — post-restart)
**Engines stopped → safe now. Mutates `trades` table.**

- **D1.** `instances/runner.py` `_close_active_trade` (lines 914-947): on **both** branches (position present / None), correlate HL `user_fills` for the token by `(side, px, timestamp±30s)`; use the real `closedPnl` + fill `px` for `pnl_usd` / `exit_price`. Fallback to `mark_px` only if no fill found.
  - *Verify:* close a paper trade; `trades` row `exit_price` == HL fill `px`, `pnl_usd` == HL `closedPnl`.
- **D2.** `instances/runner.py` entry path (around line 765 `_execute_open`): write a `Trade` row on OPEN (side=entry, size, entry_px, `pnl_usd=0`), so open legs are recorded, not just closes. (Or reconcile at close — operator preference: record-on-open is cleaner.)
  - *Verify:* open a position → `trades` has an open row; on close it updates in place (match by `signal_id` / open timestamp).
- **D3.** Backfill script `scripts/backfill_trades_hl.py` (new, read-only against HL, write to DB): re-pull `user_fills` for the test window, correct/replace `trades` rows. Run once, backup DB first.
  - *Verify:* `trades` count + sums match HL `user_fills` for the window (operator's audit method: scope recent window, match by timestamp/coin/side/price).

**Gate D:** `trades` table mirrors HL `user_fills` for open + closed; backfill reconciles history.

---

### PHASE E — Restart & Full Verify
- **E1.** Kill all runner processes; confirm port 8792 free (`grep -qi ':2268' /proc/net/tcp`).
- **E2.** Restart: `DATABASE_URL=dev_test.db STRATEGY_ENGINE_PORT=8792 ./venv/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8792`.
- **E3.** Health: `curl -o /dev/null -w "%{http_code}" http://127.0.0.1:8792/` (landing 200) + `/app/dashboard` (200) + `/api/v2/summary` (200 with per-user key).
- **E4.** Functional: open a paper position on HL → dashboard shows it (A), pulse appends (B), KPI matches (C), close it → trades row correct (D).

---

## 3. EXECUTION DISCIPLINE
- ADIX: **one verified file change per turn**, commit + push each (`git add -p` style, not bulk).
- Backup DB before any Phase D mutation: `cp data/dev_test.db /tmp/dev_test.db.bak.$(date +%s)`.
- Each phase has a **Gate** — do not advance until the gate verifies green.
- No autonomous deletion; cleanup candidates listed, not executed.

## 4. FILE TOUCH MAP
| Phase | File | Type |
|---|------|------|
| A1 | `api/instances.py` | read-endpoint enrich |
| A2 | `app/static/position-card.js` | JS poll |
| A3 | `app/templates/engine_detail.html` | verify only |
| B1 | `instances/models.py` | +1 column |
| B2 | `instances/runner.py` | filter removal + perp source |
| B3 | `app/templates/dashboard.html` | JS pulse rewrite |
| B4 | `api/instances.py` | equity_series filter |
| C1 | `api/instances.py` | perp KPI |
| C2 | `app/templates/dashboard.html` | KPI label |
| D1 | `instances/runner.py` | trades pricing |
| D2 | `instances/runner.py` | trades open row |
| D3 | `scripts/backfill_trades_hl.py` | new script |
| E | shell | restart + verify |

## 5. OPEN DECISIONS (resolved by operator directive)
- Pulse figure = **perp-only** (`get_perp_account_value`) for consistency. ✅
- KPI = same perp figure. ✅
- Trades = record-on-open + correct-on-close from HL. ✅
- Anomaly filter = **removed** (gaps were the bug). ✅
