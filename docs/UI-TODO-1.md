# UI-TODO.md — strategy-engine frontend cleanup
**Compiled:** 2026-07-19 · **Verified against:** `github.com/karma-devops/strategy-engine`, `main` @ `6d7c4f1`
**Scope:** you specifically flagged broken bar charts and the pulse graph. Both are traced to root cause below, plus everything else found doing a full pass over the chart/widget layer.

---

## 🔴 The broken bar charts — root cause found

**`app/static/pulsr-chart.js:createEquityBarChart()`** — used for the Trade PnL histogram on Paper Trading and Backtesting pages — is missing two things every one of its three sibling functions (`createEquityChart`, `createSparkline`, `createCandleChart`) has:

1. **No call to `normalizeSeries()`.** The other three functions all run incoming data through a shared helper that converts timestamps to LWC's expected Unix-seconds format, sorts ascending, and dedupes same-timestamp points before handing it to the chart library. `createEquityBarChart` skips this entirely — it passes `equityData` and `trades` straight through to `lineSeries.setData()` / `barSeries.setData()`.
2. **No try/catch around `setData()`.** The other three wrap the call: `try { this.series.setData(norm); } catch (e) { /* ignore time-order errors */ }`. `createEquityBarChart` has neither.

TradingView Lightweight Charts throws a **hard, uncaught exception** if data isn't strictly ascending by time or contains duplicate timestamps. Trade PnL data is exactly the kind of data likely to violate this — multiple trades closing in the same time bucket, scalp strategies firing several times per candle. The chart doesn't render "wrong," it **throws and never renders**, which is what "broken bar chart" looks like from the outside: blank space where the chart should be.

**Fix:** in `createEquityBarChart`'s `setData(equityData, trades)`, run both arrays through `normalizeSeries()` before calling `lineSeries.setData()` / `barSeries.setData()`, and wrap both calls in the same try/catch pattern the other three functions use.

---

## 🔴 Pulse Graph — theme toggle is a no-op

`pulsr-chart.js`'s own comment says it plainly:
```js
// Re-read theme after a data-mode change (operator toggles dark/light).
// Charts using this must call refresh() and pass their handle in.
themeVersion: 0,
bumpTheme() { this.themeVersion += 1; },
```
`bumpTheme()` increments a counter — nothing else. **There is no `refresh()` method anywhere in `PulsRChart`.** The `MutationObserver` watching `data-mode` correctly fires `bumpTheme()` on every dark/light toggle, but nothing then goes back and reapplies `getTheme()` to already-rendered chart instances. If the Pulse Graph (or any chart) is on screen when the operator flips the theme, it keeps rendering in the old theme's colors — background, grid lines, text — until the page is reloaded.

**Fix:** either implement the promised `refresh(handle)` method (re-run `chart.applyOptions(getTheme())` on the stored `chart` reference) and call it from each page's theme-toggle handler, or — simpler — have `bumpTheme()` itself walk a registry of live chart handles and reapply the theme directly, if `PulsRChart` tracks its own instances.

---

## 🟠 Position card — wrong-variable bug, silent (not a crash, but a real display bug)

**`app/static/position-card.js:88`**:
```js
const sideClass = isLongPos ? 'long' : (isShortPos ? 'short' : 'flat');
```
`isShortPos` here is a **reference to the function declared later in the same file** (line 164), not a boolean check. Function declarations hoist in JS, so this doesn't throw — but a function reference is always truthy, so `sideClass` is **never** `'flat'`. Any position where `isLongPos` is false gets classified as `'short'` regardless of its actual side — including genuinely flat positions, which shouldn't reach this branch at all normally, but also anything with an unexpected `side` string value.

Knock-on effect: the close button's flat-check (`if (sideClass !== 'flat')`, line 136) is also permanently broken as a result, since the flat branch is unreachable.

There's also a **duplicate function pair** doing the same thing: `isShort(position)` at line 49 and `isShortPos(position)` at line 164 — nearly identical, and the one actually needed at line 88 isn't being called at all.

**Fix:** line 88 should read `(isShortPos(instance) ? 'short' : 'flat')` — and delete one of the two duplicate functions, they're redundant.

---

## 🟡 Duplicate SSE connections on 3+ pages

`position-card.js`'s `init()` unconditionally calls `initSSEPositionListener()`, which opens `new EventSource('/stream')` on every page that loads the script. Dashboard, engines, and engine-detail **each already open their own separate `EventSource('/stream')`** inline (for the console/log widget). That's two independent SSE connections to the same endpoint per page load — not a functional bug (both are correctly guarded with try/catch around `JSON.parse`), but it's wasted server connections and duplicate event handling for no benefit. Worth consolidating into one shared connection, especially since `position-card.js` is loaded on 5 pages per the BUG-9-A investigation notes.

**Fix:** either have `position-card.js` reuse an existing page-level `EventSource` if one's already open (expose it on `window`), or centralize SSE connection management in one place instead of each script opening its own.

---

## 🟡 BUG-9-A (still open, being actively narrowed by the dev)

I did not find a hard, reproducible `ReferenceError`/`TypeError` in `position-card.js` on this pass — the two top-level render functions (`renderPositions`, `renderEngineDetailPosition`) both have safe fallbacks (`window.POSITIONS_DATA || []`, `window.ENGINE_INSTANCE_DATA || null`), and the SSE handlers I checked are all correctly try/catch-guarded. Given the dev's own notes already isolated this to `position-card.js` or the console widget across exactly the 5 pages that load both, and I've now found two concrete, real bugs in `position-card.js` (the `isShortPos` reference bug and the duplicate-SSE issue above) — **worth testing whether fixing those two clears BUG-9-A as a side effect** before spending more time hunting for a third cause in the same file. Add `window.onerror` capture (as the dev's notes already planned) if it's still reproducing after those fixes.

---

## ✅ Not bugs — ruled out on this pass

- **Two competing design-token systems** (flagged in an earlier session) — resolved. `tokens.css` (primitives) and `style.css` (components) are a properly layered two-file system now, both loaded together via `layout.html`, and `style.css`'s own header documents the intended architecture ("Do NOT redefine token values here"). Not a conflict.
- **`lightweight-charts.standalone.production.js`** — legitimate, complete, correctly-minified TradingView Lightweight Charts v5.2.0 bundle (196KB). Initially looked truncated at a glance; it isn't.
- **`createEquityChart`, `createSparkline`, `createCandleChart`** — all three correctly normalize and guard their data. Only `createEquityBarChart` is missing this.

---

## Priority order

1. **`createEquityBarChart` normalization + try/catch** — this is "the broken bar charts," directly, confirmed root cause.
2. **`isShortPos` reference bug** in `position-card.js:88` — one-line fix, likely also closes BUG-9-A.
3. **Theme refresh no-op** — Pulse Graph and every other chart silently ignores dark/light toggles.
4. Consolidate the duplicate SSE connections.
5. Re-test BUG-9-A after #2; only continue hunting if it's still reproducing.
