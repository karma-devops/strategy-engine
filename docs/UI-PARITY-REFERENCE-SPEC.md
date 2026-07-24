# UI Parity — Reference Spec (PULS·R dashboard ↔ ai-trading-agent-hl)

**Purpose:** Exact, line-referenced build spec so a future session can be pointed at this
document and implement the dashboard UI parity without re-investigating. Read top-to-bottom,
execute one item at a time, verify per item (see §H).

**Authoritative reference:** `/workspace/projects/ai-trading-agent-hl/dashboard/`
- `templates/index.html` — reference markup
- `static/app.js` — reference logic (positions, pulse chart, console)
- `static/style.css` — reference styling tokens + component CSS

**Live reference (for visual check):** `https://hermes-core-engine-v1.6cdzen.easypanel.host/`
login `operator / operator` (read-only inspection).

---

## STATUS (as of 2026-07-24, session 347db389f0c5 — Turn 15)

**Phase:** Investigation + spec authoring ONLY. **Zero code changes made to the app.**
Repo HEAD at `53633df` (unrelated Track 5.x work). All bugs below are **root-cause
confirmed** by direct live API calls + source inspection, but **none are fixed yet**.

| Item | What it is | Status | Evidence |
|---|---|---|---|
| §A KPI (Equity + Balance) | Collapse to 2 KPIs, brand tokens | 🔍 Confirmed, not built | dashboard.html:198-217 current 4-card layout |
| §B Pulse graph | Match reference SVG curve | 🔍 Confirmed, not built | dashboard.html:289-408 current builder |
| §C Open Positions | De-engine-depend + ref layout | 🔍 Confirmed, not built | position-card.js:69,194 + dashboard.html:462 dup |
| §D Agent Console | Ref level-colored log | 🔍 Confirmed, not built | dashboard.html:264 |
| §E Candles 401 | Backtest chart stuck | 🔍 Confirmed, not built | testing_historical.html:293 missing key |
| §F Portfolio value | Double-count + stale snap | 🔍 Confirmed, not built | exchange.py:134 ; routes.py:358 |
| §G Data plumbing | Engine-independent poller | 🔍 Confirmed, not built | positions.py:37 running-only |
| §H Verify gate | ADIX per-item | ✅ Defined | §H in this doc |
| §I1 Wrong-DB read | Backtest list empty | 🔍 **Confirmed live**, not built | API run returned `done`+673pt curve, but `GET /backtests` → `[]` (api/backtests.py:123 reads main DB; save_run → data/backtest.db) |
| §I2 Candles auth | Token-price stuck | 🔍 Confirmed, not built | 401 without key, 200 with key |
| §I3 Equity renders | Auto after I1+I2 | ⏳ Blocked by I1+I2 | renderer exists testing_historical.html:184-189 |
| §I4 Hard-test | Re-prove fix | ✅ Procedure defined | §I4 in this doc |

**Live environment notes (read this before testing):**
- Prod app: `https://puls-r-engine.6cdzen.easypanel.host/` (external). Login `operator / operator`.
- The repo's `.env` `AGENT_API_KEY` returns **403** on `/api/v2/summary` (key mismatch between
  this checkout and the deploy). This means direct curl comparison of dashboard values isn't
  possible from here — but `POST /api/v2/backtests/run` with that same key returned **HTTP 200 +
  `status: done`** (real run, 76 trades, +199%, 673-pt equity curve). So the backend works; the
  read-path (`list_backtests`) is the only blocker for the UI.
- Backtest run test was **safe** (historical replay, no capital).
- **Next action:** pick an item, build one file at a time, verify per §H, commit+push per step.
  Recommended order: §I1 → §I2 (unblocks the backtest graph fastest, highest visual payoff),
  then §C (positions, your original complaint), then §A/§B/§D (reference parity).

**Our brand tokens (MUST be used instead of reference's raw colors):** see §0.

---

## §0 — BRAND TOKEN RULE (mandatory)

We **follow the reference structure/layout/logic**, but **replace every raw color with our
brand CSS variables**. Reference uses `--accent-green #00ff88`, `--accent-red #ff4757`,
`--accent-blue #2196f3`, `--accent-yellow #ffa502`, `#0d0d0d` console bg. Do NOT copy those.

Map reference color → our token (defined in our `app/templates/layout.html` `:root` /
`design-system/` — grep `--brand` to confirm current values):

| Reference token / value | Use our brand token |
|---|---|
| `--accent-green` `#00ff88` (profit/positive) | `var(--color-profit)` |
| `--accent-red` `#ff4757` (loss/negative/close) | `var(--color-loss)` |
| `--accent-blue` `#2196f3` (chart link / trade) | `var(--brand)` |
| `--accent-yellow` `#ffa502` (warning) | `var(--color-warning)` (or `--amber`) |
| `#0d0d0d` console background | `var(--surface-terminal)` |
| `#00ff88` console base text | `var(--color-profit)` (or keep terminal green if `--surface-terminal` already sets it) |
| `--text-muted` / `--text-secondary` | keep same names (already ours) |
| `--bg-secondary` summary bg | `var(--surface-card)` |
| `--border-color` | `var(--border)` / `var(--border-subtle)` |

Our tokens already in use across `dashboard.html` / `layout.html`:
`--brand`, `--color-profit`, `--color-loss`, `--text-primary`, `--text-secondary`,
`--text-muted`, `--surface-card`, `--surface-terminal`, `--border`, `--border-subtle`,
`--emerald-500`, `--coral-500`, `--font-mono`, `--font-display`, `--radius-lg`, `--space-*`.
Grep `:root` in `app/templates/layout.html` to confirm before editing.

---

## §A — KPI / Account Summary (Total Equity + Available USDC)

**Reference markup:** `ai-trading-agent-hl/dashboard/templates/index.html:59-81`
(`account-summary` → 4 `summary-item`: Equity/Total, Balance/USDC, P&L, Exchange/Connected).
**Reference logic:** `app.js:152-155` `updateBalance(available, equity)`.

**Target KPIs (collapse current 4+ cards into this):**
1. **Equity / Total** = HL `marginSummary.accountValue` (perp equity).
2. **Balance / USDC** = available/withdrawable spot USDC (NOT summed — see §F).
3. **P&L** = equity − start_balance (already in `dashboard.html` `buildPulse`).
4. **Exchange** = small "HyperLiquid · Connected" sublabel chip (not a KPI card).

**Our files to edit:**
- `app/templates/dashboard.html:198-217` — replace the KPI `kpi-card` block (PORTFOLIO /
  PERP ACCT (HL) / PNL / ENGINES) with TWO primary KPIs (Equity/Total, Balance/USDC) + P&L +
  exchange chip. Use `.summary-item` structure from reference index.html:60-81 but our tokens
  (§0). KPI grid already styled via `.kpi-compact` / `.kpi-label` / `.kpi-value`.
- `app/templates/dashboard.html:202` (`kpi-account`) and `:206` (`kpi-perp-account`) →
  rename/repoint: `kpi-account` = Total Equity, add `kpi-balance` = Available USDC.
- `app/routes.py:358-374` — ensure `account_value` (Equity) and a NEW `available_usdc`
  (Balance) are passed to the template. Pull `available_usdc` from
  `core/exchange.py:get_withdrawable()` (line 214) or `_spot_usdc_available` (line 107).
- `app/templates/dashboard.html:282-385` (`buildPulse` + ticker) — P&L already derived from
  `START_BALANCE`; keep. Re-point KPI ids after markup change.

---

## §B — Pulse Graph (match reference shape, keep our LIVE badge + stats)

**Reference logic:** `app.js:1455-1544` `updatePortfolioChart` + `renderPortfolioChart`
(600×120 SVG, quadratic-bezier smooth line, vertical gradient fill, color by
`values[last] >= values[0]`).
**Reference markup:** `index.html:88-98` (card + `#portfolio-chart` + `#portfolio-change` badge).

**Changes:**
- `app/templates/dashboard.html:289-408` (`buildPulse`) — replace absolute-min/max scaling
  with reference's **min/max-normalized smooth SVG** + gradient area fill (port `renderPortfolioChart`
  app.js:1482-1544). Adopt reference color logic: green when `last >= first`, red otherwise
  (currently uses net-window sign — keep our `--color-profit` / `--color-loss` per §0).
- KEEP our extras (they are upgrades): **LIVE badge** (`#mode-toggle`, dashboard.html:223),
  **stat strip** Last/High/Low/PeakΔ (`#pulse-stats`, dashboard.html:242-247), and the
  mobile mirror (`mirrorPulseToMobile`, dashboard.html:414-444). Layer reference styling onto them.
- Data source: already `equity_series` (dashboard.html:282). Fix the underlying value at
  source (§F) so the graph stops jumping. Reference pulls `/api/history` → map to our
  `equity_series` shape `{time, value}`.

---

## §C — Open Positions card (reference layout + de-engine-depend)

**Reference markup:** `index.html:100-115` (card + `#positions` + `#position-count` + footer
`Close All`).
**Reference logic:** `app.js:243-301` `updatePositions` (per-position block: SYMBOL tag,
SIZE, VALUE, ENTRY, MARK, P&L(+%), Close(red X) + Chart(blue→hyperliquid.xyz) buttons).
**Reference CSS:** `style.css:456-641` (`.position`, `.position-row`, `.position-label`,
`.position-value`, `.position-actions-row`, `.btn-close-all`).

**Sub-items:**
- **C1 — De-engine-depend (Bug 1):**
  - `api/positions.py:37-50` `get_all_positions` — currently iterates
    `manager.list_runners()` (running only). Change to query HL `user_state` for ALL configured
    tokens (use `core/exchange.py:get_position` / `user_state`), so stopped engines with live
    positions still appear. Return per-coin `{slug, coin, szi, entryPx, markPx, side, pnl}`.
  - `app/static/position-card.js:69` `buildPositionCard` — remove `if (!instance || instance.status !== 'running') return null;`.
  - `app/static/position-card.js:194-196` `renderPositions` — remove `inst.status === 'running'` filter.
- **C2 — Single renderer (Bug 2):** delete the DUPLICATE `renderPositions` at
  `app/templates/dashboard.html:462-471` (inline). Keep ONE renderer = reference-style field
  grid. Point `dashboard.html:680` (`renderPositions(d.instances)`) and
  `position-card.js:179/325/331` at the single kept function.
- **C3 — Adopt reference card markup:** symbol tag (green/red by side via our `--color-profit`
  / `--color-loss`), size, value (`size×mark`), entry, mark, P&L `(+$0.28 +5.28%)`,
  Close + Chart buttons, "Close All" footer (`index.html:109-114`, `app.js:288-297`,
  `style.css:611-641`). Chart button links to `https://app.hyperliquid.xyz/trade/{SYMBOL}`.
- **C4 — Empty state:** "No open positions" placeholder (reference `app.js:249`; our
  dashboard.html:153 already has one — keep, restyle to match).
- **C5 — `window.POSITIONS_DATA` source:** `app/templates/dashboard.html:975` currently
  server-renders `instances` with position fields only for running engines. After C1, the
  `/api/v2/positions` hydrate (`position-card.js:265-291`) becomes the source of truth; ensure
  it runs on every authed page (see §G2).

---

## §D — Agent Console (reference visualization)

**Reference markup:** `index.html:121-134` (console card + `#console` + Copy/Clear).
**Reference logic:** `app.js:391-423` `updateConsole` (last 50, **newest-first**,
`[HH:MM:SS] message`, level classes, selective emoji).
**Reference CSS:** `style.css:646-688` (`.console-output` `#0d0d0d`/mono/`#00ff88`,
`.console-line.success/error/warning/trade/info` colors).

**Changes:**
- **D1 — Restyle:** `app/templates/dashboard.html:264` (`#console-log`, class
  `console-log`) → use reference `.console-output` styling but OUR tokens (§0): bg
  `var(--surface-terminal)`, mono `var(--font-mono)`, base text `var(--color-profit)`.
- **D2 — Line format:** wrap each runner-log line with `[HH:MM:SS]` prefix +
  level class. Our runner console already emits `[09:04:51] [HYPE] ...`
  (seen live on Engines page). Add level detection: contains "Trade closed"/"closed" →
  `trade` (our `--brand`); "error"/"fail" → `error` (`--color-loss`); "warn" → `warning`;
  else `info` (`--text-secondary`). Emoji: ✅ on success, ❌ on error (reference
  `getLogEmoji` app.js:426-440).
- **D3 — Copy/Clear:** already exist (`dashboard.html:260-261` `copyConsole()` /
  `clearConsole()`). Restyle to reference small rounded grey buttons.

---

## §E — Candles 401 (Backtesting chart stuck)

**Root cause:** `/api/v2/candles/{token}` requires `X-API-Key` (mounted with
`Depends(verify_api_key)` at `main.py:205`; route defined `api/instances.py:835`).
The chart fetch omits the header.

**Fix (one of two, pick A):**
- **E1 (preferred):** add `X-API-Key` header to the fetch in
  `app/templates/testing_historical.html:293` and `app/templates/live_paper.html:131`.
  Pattern already correct at `app/templates/backtests.html:99` (`headers: { 'X-API-Key': API_KEY }`).
  Use `API_KEY` already defined in those templates (testing_historical.html injects it like
  backtests.html:79).
- **E2 (alt):** relax the candles route to `require_ui_or_api` (auth.py:111) instead of
  `verify_api_key` so Basic-auth sessions work — edit `main.py:205` router dependency for
  `instances.router` OR move only the candles route out. More invasive; prefer E1.

**Verify:** unauthenticated → 401 (current); with key → HTTP 200 + candles (confirmed live).

---

## §F — Portfolio value correctness (feeds §A + §B)

- **F1 — Double-count fix:** `core/exchange.py:134` `get_account_value()` adds
  `perps_value + spot_available`. On unified HL accounts `marginSummary.accountValue`
  already nets idle spot USDC → **double count**. Fix: Equity = `get_perp_account_value()`
  (exchange.py:151, uses only `accountValue`); Balance = `get_withdrawable()`
  (exchange.py:214) or `_spot_usdc_available` (exchange.py:107). Update BOTH
  `app/routes.py:358-374` and `api/instances.py:154-167` / `:299-313` to use the split.
- **F2 — Stale snapshot:** `app/routes.py:358-374` overwrites `account_value` only if
  `live_val > 0`; when HL creds absent it silently keeps the last `AccountSnapshot` (hours old).
  Change: if no HL creds, set Equity/Balance to `"—"` (or last known with a stale flag),
  never present a stale number as live.

---

## §G — Engine-independent data plumbing (cross-cutting for §C/§F)

- **G1 — Non-runner poller:** add a dashboard data path that reads HL `user_state` /
  `get_position` for all configured tokens WITHOUT requiring a running runner (mirrors
  reference `/api/data` + `/api/positions/stream` which has no engine concept). Backs §C1
  and §F so the dashboard is correct with 0 engines running.
- **G2 — `window.API_KEY` on every authed page:** reference shows it was only injected on
  dashboard + engine_detail in commit 9fa8e6c. Ensure `layout.html` (or each route) sets
  `window.API_KEY` globally so `position-card.js:265` `hydratePositions` works everywhere.
  Check `app/templates/layout.html` for the `api_key` context var pass-through from
  `app/routes.py`.

---

## §H — Verification gate (ADIX — per item)

After EACH item (not at the end):
1. `python3 -m py_compile` the touched `.py` files (or just restart — import errors surface fast).
2. Restart server per `NOTES.md` runbook (port `:8792`, venv at project root).
3. Curl checks:
   - `curl -s -u operator:operator http://127.0.0.1:8792/api/v2/summary` → Equity + Balance present, sane.
   - `curl -s -H "X-API-Key: $KEY" http://127.0.0.1:8792/api/v2/positions` → shows live positions even with stopped engines.
   - `curl -s -H "X-API-Key: $KEY" "http://127.0.0.1:8792/api/v2/candles/FARTCOIN?tf=15m&bars=200"` → 200 + candles.
4. Browser verify (logged in `operator/operator`): dashboard KPIs, pulse graph shape,
   open-positions card (start/stop an engine OR hold a live position to confirm it shows
   regardless of engine state), Agent Console line format/colors.
5. Commit + push per verified step (git discipline: verified live step → commit LOCAL +
   push remote as one motion).

---

## Source line index (quick jump)

| Concern | File:lines |
|---|---|
| Candles route (auth-required) | `api/instances.py:835` ; `main.py:205` |
| Candle fetch missing auth | `app/templates/testing_historical.html:293` ; `app/templates/live_paper.html:131` |
| Positions API (running-only) | `api/positions.py:37-50` |
| position-card engine filter | `app/static/position-card.js:69, 194-196` |
| Duplicate renderer | `app/templates/dashboard.html:462-471` vs `app/static/position-card.js:179` |
| POSITIONS_DATA source | `app/templates/dashboard.html:975` |
| KPI block | `app/templates/dashboard.html:198-217` |
| Pulse graph builder | `app/templates/dashboard.html:289-408` |
| Console element | `app/templates/dashboard.html:264` ; Copy/Clear `:260-261` |
| Equity/balance fallback | `app/routes.py:358-374` |
| account_value double-count | `core/exchange.py:134` ; perp-only `:151` ; withdrawable `:214` ; spot-available `:107` |
| Reference account-summary | `ai-trading-agent-hl/.../index.html:59-81` |
| Reference positions | `ai-trading-agent-hl/.../index.html:100-115` ; `app.js:243-301` ; `style.css:456-641` |
| Reference pulse | `ai-trading-agent-hl/.../app.js:1455-1544` |
| Reference console | `ai-trading-agent-hl/.../index.html:121-134` ; `app.js:391-423` ; `style.css:646-688` |
| Backtest list reads wrong DB | `api/backtests.py:21,123-140,143-154` (uses `instances.models.Backtest`/`get_db`) vs `testing/backtest_store.py:28,87,101` (writes `data/backtest.db`) |
| Backtest save path | `api/backtests.py:86-114` (`save_run`) ; `testing/backtest_store.py:101-106` |
| Equity chart renderer (exists, starved) | `app/templates/testing_historical.html:184-189` (`PulsRChart.createEquityBarChart` on `#equityChart`) |
| Token-price candles fetch (401) | `app/templates/testing_historical.html:293` (no `X-API-Key`) |
| Run endpoint returns equity_curve | `api/backtests.py:110,116-120` (`equity_curve_json` in response) |

---

## §I — Backtest graph does not render (HARD-TESTED, root cause confirmed)

**Context (verified live 2026-07-24):** Ran a real backtest via API
(`FARTCOIN / strategy_v1_3 / 15m / 7d / 5x`) → `status: done`, 76 trades, +199% return,
`equity_curve` = **673 points** `{time, equity}`. The backend is correct. The FRONT END
shows **nothing**: "No backtests yet", empty equity box, stuck token-price loader.
Two independent bugs, both confirmed by direct inspection + API calls.

### I1 — `list_backtests` / `get_backtest` read the WRONG database (primary killer)

**Symptom:** `GET /api/v2/backtests` always returns `{"backtests":[]}` even after a successful
run. The "Backtest Runs" table is permanently empty and the equity chart never gets data.

**Root cause:**
- `api/backtests.py:21` imports `from instances.models import Backtest, get_db, Instance`.
- `api/backtests.py:123-140` `list_backtests` does `db.query(Backtest)` with `db = Depends(get_db)`
  → the **main `strategy_engine.db`**.
- But the run endpoint saves to the **isolated `data/backtest.db`**:
  `api/backtests.py:86,114` calls `save_run(record)` from `testing/backtest_store.py`,
  where `_DB_PATH = data/backtest.db` (`testing/backtest_store.py:28`) and `save_run` commits
  via that engine's `Session()` (`testing/backtest_store.py:101-106`).
- The main DB has **no backtest tables** (verified: `data/backtest.db` has `backtest_runs`/
  `backtest_trades`; `strategy_engine.db` has neither). So reads return empty.

**Fix (one import + session swap, no logic change):**
- In `api/backtests.py`, stop using `instances.models.Backtest` / `get_db` for the read paths.
- Import the isolated store: `from testing.backtest_store import BacktestRun, list_runs, get_run`
  (functions already exist at `testing/backtest_store.py:128-141` `get_run`, `:134-140` `list_runs`).
- Rewrite `list_backtests` (`:123-140`) to call `list_runs(mode=instance_slug or None, limit=limit)`
  and `get_backtest` (`:143-154`) to call `get_run(backtest_id)`, returning their dicts.
- Keep `_row_to_dict` or switch the response to the store's `_run_to_dict` shape
  (`testing/backtest_store.py:143+`) — the front end consumes `equity_curve`, `total_return_pct`,
  `total_trades`, etc., which both dicts already expose.
- **Do NOT** change `run_backtest_endpoint` (`:43-120`) — its `save_run` path is correct.

**Verify (per §H):**
- `curl -s -H "X-API-Key: $KEY" http://127.0.0.1:8792/api/v2/backtests` → now returns the run
  (count ≥ 1), with `equity_curve` array of 673+ points.
- `curl -s -H "X-API-Key: $KEY" http://127.0.0.1:8792/api/v2/backtests/<id>` → 200 + full dict.

### I2 — Token-price candle fetch missing auth (stuck loader)

**Symptom:** "TOKEN PRICE CHART" shows "Loading token price data / Fetching candles from
HyperLiquid…" forever.

**Root cause:** `app/templates/testing_historical.html:293` fetches `/api/v2/candles/{token}`
with **no `X-API-Key` header**. That route requires it (`api/instances.py:835` mounted under
`Depends(verify_api_key)` at `main.py:205`). Unauthenticated → 401 → loader never clears.
(Confirmed: with key → HTTP 200 + candles; without → 401.)

**Fix (two options, pick A):**
- **A (preferred):** add `headers: { 'X-API-Key': API_KEY }` to the fetch at
  `app/templates/testing_historical.html:293` (pattern already correct at
  `app/templates/backtests.html:99`). `API_KEY` is injected on this page
  (see dashboard.html `window.API_KEY` wiring / `app/routes.py` context).
- **B (alt):** relax the candles route to `require_ui_or_api` (`api/auth.py:111`) so Basic-auth
  sessions work — edit the router dependency at `main.py:205`. More invasive; prefer A.

**Verify:** browser reload of `/app/testing/historical` → token-price chart draws candles (no
longer stuck). Cross-check: `curl -s -H "X-API-Key: $KEY" "http://127.0.0.1:8792/api/v2/candles/FARTCOIN?tf=15m&bars=200"` → 200.

### I3 — After I1+I2, the equity graph renders automatically

The renderer already exists and is correct: `app/templates/testing_historical.html:184-189`
`const btChart = PulsRChart.createEquityBarChart('equityChart', { height: 280 })` fed by
`latestEquity` / the run's `equity_curve`. Once I1 supplies the curve and I2 unblocks the page,
the "beautiful" equity graph (the one referenced in the operator's early memory) will draw
with **no further chart code changes**. If the operator wants the *early* styling exactly, port
the reference pulse-graph SVG treatment (§B) onto `#equityChart` — but functionally it works as-is.

**Note on the "early beautiful graph":** the early commit `7bbb4ec` was backend/engine-only
(zero HTML templates). The equity-graph code has always lived in `testing_historical.html`;
it was never removed — it was just starved of data by bug I1. No historical recovery needed.

### I5 — Strategy Studio: user-selectable model + provider (operator directive 2026-07-24)

**Current state:** `app/routes.py` `/api/v2/strategies/{id}/convert` resolves the AI
provider from `config.get_credential("ai_provider", user_id)` (DB, then env fallback).
The **frontend Strategy Studio** (`/app/strategy-studio`, the "PINE → PYTHON CONVERTER"
panel) currently *reads* the backend default (Provider: ollama · Model: glm-5.1) and
offers no selector — the user cannot set model/provider from the UI.

**Required (operator: "user should be able to set model + provider from the frontend"):**
1. Add a **Provider** + **Model** dropdown (or free-text model) to the Strategy Studio
   convert panel, pre-filled from the operator's stored `ai_provider` credential.
2. On Convert, POST the selected provider/model alongside `pine_source` + `save_slug`
   so `core/llm.convert_pine_to_python` receives `model_override` (already supported)
   + a provider URL/key override that writes to `Account > Secrets` (ai_provider cred).
3. The `/convert` route must accept + persist the selection (currently `user_id` resolves the
   DB cred; the UI should let the user *edit* that cred, not just send per-call overrides).
4. GATES (system prompt + `_gate_check`/`_smoke_test` loop in `core/llm.py`) stay
   scoped to `convert_pine_to_python` only — unaffected by this UI change.

**Verify:** screenshot the Studio panel showing the provider/model selectors populated from
the operator's Secrets; confirm a Convert with a non-default model reaches `core/llm.chat`
with the chosen `model_override`.


1. Login `operator/operator` at the app, open `/app/testing/historical`.
2. Fill: TOKEN=FARTCOIN, STRATEGY=translation-test, TF=15m, START BALANCE=100, DAYS=7, LEVERAGE=5.
3. Click **Run Backtest** (button `e25`). Wait ~5-15s (page reloads on success per
   `backtests.html:106` `setTimeout(()=>location.reload(),1500)`).
4. Expect: "Backtest Runs" table shows the row; EQUITY & TRADES draws the curve; token-price
   chart shows candles; LATEST RETURN etc. populate (≠ "—").
5. API cross-check: `curl -s -H "X-API-Key: $KEY" .../api/v2/backtests` returns the run with
   `equity_curve` length > 0.
