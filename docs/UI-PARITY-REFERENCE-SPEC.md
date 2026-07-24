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
