# AEE.md — Engine Page UI Bug-Hunt (2026-07-19)

**Author:** Aetheris (assisted by operator's senior-dev direction)
**Project:** strategy-engine (`/workspace/projects/strategy-engine/main`)
**Scope:** Engine detail page (`/app/engines/{slug}`) — graph render, Open Positions render, Settings edit persist.
**Method:** ADIX one-step verification; ui-ux-pro-max trading-dashboard-patterns reference; evidence from live server (proc_c91db601bb9e, :8792).

---

## TL;DR (operator-facing)

The engine page was rebuilt from scratch but two render paths were wired to code/classes that don't exist on that page, and a third issue (LIVE toggle reverting) was a backend runner bug now fixed. Three concrete defects, all reproduced:

1. **Pulse graph does not render** — engine page calls `buildPulse()` but that function is defined ONLY inside `dashboard.html` (inline). On the engine page `typeof buildPulse === 'function'` is `false`, so the guard silently skips. The `#pulse-svg` SVG never gets a path. (Confirmed: `grep buildPulse` → only `dashboard.html` + `engine_detail.html` call sites; `pulsr-chart.js` has 0 occurrences.)
2. **Open Positions cards render unstyled / broken** — engine page builds an inline card using classes `pos-head`, `pos-symbol-size`, `pos-side-badge`, `pos-fields`, `pos-field-item`, `pos-field-label`, `pos-field-value`, `pos-close-btn`, `pos-card-long/short`. **None of these have CSS** (0 definitions in `style.css`). Only bare `.pos-card` (3 defs) exists. So cards show as raw unstyled HTML. (Confirmed: grep each class in `style.css` → 0 defs.)
3. **Settings "don't persist" / "can't edit properly"** — root cause was the running engine re-merging its stale in-memory `dry_run` every tick (backend `instances/runner.py`). Fixed in commit `3e7d2fa` and proven via API (running engine-1 set LIVE stays LIVE across 12s). The API PUT/edit path itself works (tested: leverage + timeframe persist on engine-2). Remaining UX risk: the modal's edit flow needs a live browser confirmation pass.

---

## Defect 1 — Pulse graph empty

### Evidence
- `app/templates/engine_detail.html` calls `buildPulse()` at lines 241, 262 (guarded by `typeof buildPulse === 'function'`).
- `buildPulse` is defined ONLY at `dashboard.html:285` (inline, not global).
- `app/static/pulsr-chart.js` defines `window.PulsRChart.createEquityChart` (Lightweight Charts canvas wrapper), NOT `buildPulse`.
- Served engine page loads `pulsr-chart.js` + `lightweight-charts` (confirmed via curl), but `buildPulse` is undefined there → guard skips → `#pulse-svg` stays empty.

### Canonical pattern (ui-ux-pro-max / trading-dashboard-patterns.md)
- Live/streaming charts MUST use `PulsRChart.createEquityChart` (Lightweight Charts, vendored locally). The hand-built `buildPulse` SVG is legacy (used only by dashboard). Operator mandate 2026-07-16: "integrate lightweight-charts into the project. serve from us."
- Engine page should render into a `<div id="equityChart">` container (not an `<svg>`), with an empty-data overlay (animated PULS-R logo) per the reference.

### Fix (planned)
- Replace the `<svg id="pulse-svg">` block on engine page with a `<div id="equityChart-wrap"><div id="equityChart"></div><div id="equity-empty">…</div></div>` matching the reference pattern.
- Replace the `buildPulse()` call with `PulsRChart.createEquityChart('equityChart', {height: 280})` + `setData(equityData)` + live poll update.
- Reuse `equityData` array (already populated via `/summary` + SSE in the engine page script).
- Sign-aware line color (emerald/coral) per the NON-NEGOTIABLE rule.

---

## Defect 2 — Open Positions unstyled

### Evidence
- Engine page `renderEnginePosition()` (inline) builds card with classes: `pos-card pos-card-${sideClass}`, `pos-head`, `pos-symbol-size`, `pos-side-badge`, `pos-fields`, `pos-field-item`, `pos-field-label`, `pos-field-value`, `pos-close-btn`.
- `style.css` defines: `.pos-card` (3), `.pos-card:hover`, responsive `.pos-card`. **0 defs** for every other class above.
- `position-card.js` (already loaded on engine page via `layout.html`) has `renderEngineDetailPosition()` that renders into `#pos-card` using the CORRECT styled classes (`.pos-side-badge`, `.pos-fields`, `.pos-field-item`, `.pos-close-btn` — all styled in `style.css`). The engine page currently uses `#pos-grid` + a hand-rolled (unstyled) card instead.

### Canonical pattern (trading-dashboard-patterns.md "Open Positions")
- Each position card: left-edge spine, sign-colored long/short, field grid (Market, Size, Value, Entry, Mark, PnL, Liq, Margin, Funding), inline Close + Chart buttons. `position-card.js` already implements exactly this and is styled.

### Fix (planned)
- Change engine page container `#pos-grid` → `#pos-card` (what `position-card.js` expects for engine detail).
- Replace inline `renderEnginePosition()` with a call to `renderEngineDetailPosition()` on each refresh (it reads `window.ENGINE_INSTANCE_DATA`, already updated from `/summary`).
- Remove the unstyled inline card builder. Reuse the proven styled component.
- Confirm live position shows (engine-1 has a real FARTCOIN position when LIVE + polled).

---

## Defect 3 — Settings edit / persist

### Evidence
- API PUT `/api/v2/instances/{slug}` works: tested leverage 5→3 and timeframe 15m→5m on engine-2, both persisted, then restored. (ok=True)
- `/api/v2/strategies` returns 3 strategies; `/api/v2/instances/engine-2/strategy-config` returns 15 params. Modal dropdowns/params CAN populate.
- Backend revert bug (running engine re-merging stale `dry_run`) — ROOT CAUSE OF "settings don't persist" — fixed in `instances/runner.py` (commit `3e7d2fa`) and proven (running engine-1 LIVE stays LIVE 12s).
- Remaining: browser-side confirmation that the modal's full edit+safe+reload flow works on the engine page (esp. LIVE toggle confirm + `__refreshEngine` reload).

### Fix (planned)
- Browser pass: open Settings on engine-1, change a non-destructive field (e.g. leverage), save, confirm reload shows new value.
- Confirm LIVE toggle in modal persists (uses same PUT path as the proven fix).
- If the Strategy select options don't match backend `strategy_id` values, fix the option `value` mapping.

---

## Execution plan (one verified piece at a time, ADIX)

1. **Fix graph** (Defect 1): rewrite engine page pulse container + JS to use `PulsRChart.createEquityChart`. Verify canvas renders + empty overlay. Commit `engine-detail-graph-lwc`.
2. **Fix positions** (Defect 2): switch to `#pos-card` + `renderEngineDetailPosition()`. Verify styled card + live position. Commit `engine-detail-positions-styled`.
3. **Verify settings edit** (Defect 3): browser pass on engine-1. If modal mapping bug found, fix + commit.
4. **Doc-sync** AEE.md → NOTES.md entry; update AEE.md with verification results.

## What is NOT broken (verified)
- Server health, routing, Basic-Auth, shared Settings modal open (dashboard + engine page).
- API edit/persist path (PUT works).
- Runner dry_run revert (fixed + proven).

## Risks / open questions for operator
- **engine-1 is currently LIVE** (real funds) from the proof test. Leave or flip to Paper?
- Open Positions on engine-1 will only show a card when engine-1 reports a position (needs LIVE + polled, or the operator's real FARTCOIN position to be reflected). If engine-1 is PAPER with FLAT, the card correctly shows empty state.
- "Rearrange dashboard" still pending (no spec given).
