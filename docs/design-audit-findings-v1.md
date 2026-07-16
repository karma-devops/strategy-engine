# Design Audit Findings — PULS-R (v101+, 2026-07-16)

**Author:** Aetheris · **Session:** e3f7461df4ce · **Method:** Per-page walk · DOM + computed CSS + vision
**Status:** Audit complete. Prioritized fix list below.
**Spec reference:** `design-system/MASTER.md` v1.0.0

---

## Executive Summary

| # | Severity | Finding | Pages affected |
|---|----------|---------|----------------|
| 1 | **🔴 CRITICAL** | `--glass-bg` and `--glass-border` undefined → `.chart-card` has no background or border. **Every card on every page renders as a flat invisible container.** | ALL 19 |
| 2 | **🔴 HIGH** | Fleet card action buttons (▶/⏹/⚙) are 28px tall · spec requires 36px desktop / 44px mobile. | Dashboard, Engines |
| 3 | **🟡 MEDIUM** | `h2` headings in chart-cards render at **9.75px** (master spec says `text-sm` = 12px). KPI value `text-xl` (20px) overrides with `16.25px`. | ALL |
| 4 | **🟡 MEDIUM** | Light mode: `--color-info` declared in spec as `#6BA4D5 Sky`; in `tokens.css` it's `var(--tb-600)` (teal). Spec/code drift. | Theme system |
| 5 | **🟡 MEDIUM** | Fleet cards on dashboard use inline `style="height:28px; padding:0 10px; font-size:11px;"` instead of token-driven classes. Inline styles override design system. | Dashboard, Engines, Engine Detail |
| 6 | **🟢 LOW** | Two legacy 301 redirects still in nav: `/app/backtests` and `/app/paper` redirect to renamed locations. | Nav |
| 7 | **🟢 LOW** | Assistant chat widget shows 3 session refs (e35/e36/e37) without visible session titles in the accessibility tree — labels may be empty. | Assistant |
| 8 | **🟢 LOW** | Settings page has 16-emoji avatar radio grid — no labels/aria-labels. Accessibility concern. | Settings |

---

## Per-Page Findings

### 1. Dashboard (`/app/dashboard`) — 5 chart-cards, 3 KPI cards, 3 fleet cards

**DOM:** 3 KPIs render with values ($4.90 / $-0.02 / engine-1). 3 fleet cards (FARTCOIN LIVE 3x / HYPE PAPER 5x / WIF stopped). Pulse graph SVG renders. Agent console streaming live NEUTRAL signals.

**Computed styles (dark mode):**
- `.chart-card` bg = `rgba(0,0,0,0)` (transparent — bug #1)
- `.chart-card` border = `0px none` (no border — bug #1)
- `.kpi` bg = `rgb(21, 16, 11)` (surface-card ✓)
- `.kpi` padding = `8px 12px` (tight — spec says 16px via `--card-padding`)
- `.kpi-grid` gap = `8px` (spec implies `--grid-gap` = 16px)
- `.kpi-value` font-size = `16.25px` (overrides `--text-xl` = 20px; why?)
- `.pulse-head h2` font-size = `9.75px` (overrides `--text-sm` = 12px)
- `.fleet-btn` height = `28px` (bug #2)
- `.fleet-card` bg = `rgb(21, 16, 11)` ✓, border = `rgba(8,121,142,0.35)` ✓ (works because `.fleet-card` has its own rules, not `.chart-card`)

**Vision (dark mode):** Layout is "very flat" — KPIs read but cards are invisible. Pulse Graph and Fleet sections bleed into each other. Engine "label/dot pulse" is the only structural anchor. Console is legible but lacks card framing.

**Light mode:** Same flat structure. Brand teal reads cleanly on cream background, but cards still have no borders.

### 2. Engines (`/app/engines`) — 5 KPI metrics, 3 engine cards, 2 chart sections, 1 console

**DOM:** Active Engines 2/3, Open PnL $0.00, Win Rate 40.0%, Closed Trades 10, Mode LIVE. 3 engine cards (FARTCOIN 3x LIVE / HYPE 5x PAPER / WIF 3x stopped). Each card has Stop/Close/Restart/⚙ buttons. Returns Distribution + PnL Distribution headings + Runner Console.

**Findings:** 4 chart-cards on this page. All inherit the glass-bg/glass-border bug. Engine cards work (have own CSS). Action buttons on engines page are full-text ("Stop"/"Close"/"Restart") so the 28px height isn't an issue here — but the **icon-only buttons on dashboard (▶/⏹/⚙)** are the 28px problem.

### 3. Engine Detail (`/app/engines/engine-1`) — 11+ chart-cards, full telemetry

**DOM:** Status/PnL/Mode KPIs. Performance hero (Win Rate 57.1% / Total PnL $-0.02 / Closed 7 / Max DD +5.33%). Position card, Strategy card. Tab pills (Returns Distribution / Profit Structure / Run-ups & Drawdowns). SVG charts render. Trade History table (7 rows). Recent Signals table (40+ rows). ⚙ Edit Settings button at top.

**Findings:** **Highest chart-card density in the project** (11 instances). All cards will be invisible. Tab pill switcher works. Trade History data-table renders correctly with proper styling. Equity Trend sparkline renders as SVG image.

### 4. Trades (`/app/trades`) — 4 KPIs, 3 filter dropdowns, data table

**DOM:** Total PnL $0.00, Win Rate 0.0%, Open 0, Total 0. 3 filter dropdowns (Engine / Side / Status). No table rows (zero trades match filters).

**Findings:** Page is empty (no trades match). Empty state renders. 1 chart-card containing the filters. Filter dropdowns render with custom styling (NOT native `<select>`) — uses `combobox` ARIA role. The `<select>` widgets are styled by browser, which is **inconsistent with the rest of the design system** that uses custom controls.

### 5. Strategies (`/app/strategies`) — 4 KPIs, 3 strategy cards

**DOM:** Total Strategies 3, Active 3, Total Trades 10, Aggregate PnL $-0.02. 3 strategy cards (Scalp v1.3 / Swing v1 / PRO v6.1) each with "View details →" link.

**Findings:** 1 chart-card. Strategy cards have their own styling (not `.chart-card`). Strategy registry is sparse — 3 strategies, but only the **active** ones show; no PENDING/INACTIVE filter. The "Aggregate PnL" KPI shows live aggregate.

### 6. Testing/Historical (`/app/testing/historical`) — form, equity curve, 6-metric grid, runs table

**DOM:** Form (Token / Strategy / Timeframe / Days / Leverage / Run). Latest backtest result: +320.64%, Win Rate 92.8%, PF 8.80, Sharpe 4.83, Max DD 8.55%, 69 trades. Ask Assistant chat widget inline. Backtest Runs table (5 rows).

**Findings:** Form fields are native `<input>` and `<select>` — bare HTML, not styled to match the rest. The "Ask Assistant about these results" widget is injected into the middle of the page (3rd-level embed). Canvas element renders the equity curve (legacy lightweight-charts). 5 backtest rows in runs table — duplicate `+28.78%` rows suggest the **runs table has duplicates** (suspicious).

### 7. Testing/Paper (`/app/testing/paper`) — minimal page

**DOM:** "Active Engines" KPI, Mode badge "Paper Trading", Equity Curve canvas, 1 paper engine (HYPE).

**Findings:** Simplest page. 1 chart-card. Equity curve canvas renders.

### 8. Account Overview (`/app/account`) — 5 KPIs, allocation table, settings summary

**DOM:** Portfolio Value $4.9, Start Balance $100.0, Total PnL $0.0, Withdrawable $4.9, Active 2/2. Engine Allocation table (FARTCOIN + HYPE rows). Account Settings summary card with Edit/Secrets/Wallet/API Keys links.

**Findings:** **"$0.0" instead of "$0.00"** for currency values — inconsistent format across pages (other pages use `$0.00`). The 2/2 active engines (was 3 with WIF) — operator may have stopped WIF.

### 9. Account/Secrets (`/app/account/secrets`) — 4 tab buttons, credential forms

**DOM:** 4 step tabs (Overview / Wallets / HyperLiquid DEX / AI Inference). Only "Credential Summary" heading shown — the other tabs are navigated by clicking.

**Findings:** 4-tab pattern. Tab content swapped client-side. Form fields in tabs (when active) will be native HTML — input focus rings now work after DS2 fix.

### 10. Settings (`/app/settings`) — 5 form sections, 16-emoji avatar grid

**DOM:** Profile (Display Name + Email + 16-emoji avatar grid). Security (Username + password + 2FA checkbox). Trading (Start Balance + Paper Trading checkbox). Wallet (0x... address). Plan & Billing (Free tier info). Save Settings button at bottom.

**Findings:**
- 16 radio buttons in a row (🦊 🐉 🚀 ⚡ 🔥 🌌 🦅 🐺 🦈 💎 🎯 🧠 ⭐ 🌙 ☄️ 🦾) — **no labels, no `aria-label`** → screen readers will read only "radio button" 16 times. Accessibility fail.
- Form fields are native HTML (no custom components).
- Disabled inputs (Username, Upgrade to Pro button) — good.
- The 4 form sections render inline — no clear card separation (chart-card bug strikes again).

### 11. Assistant (`/app/assistant`) — sessions sidebar, model dropdown, chat

**DOM:** SESSIONS sidebar (New button, 3 session items, MODEL dropdown with 6 options: GLM-5.1/GPT-4o/Claude Sonnet 4/Claude Sonnet 4 May/DeepSeek Chat/Custom). Main area: "PULS-R Assistant" heading + input textbox + Send button.

**Findings:** Chat widget (Phase 9/10) integrates with shared `chat_widget.css`. Model dropdown uses native `<select>`. Sessions sidebar items are generic clickable elements (refs e35-e37) with **no visible session titles** in the accessibility tree — may be empty labels or text not exposed to AT. Need to inspect actual rendered text in the session chip elements.

### 12. Strategy Upload (`/app/strategies/upload`) — simple form
### 13. Strategy Studio (`/app/strategies/studio`) — Pine→Python converter
### 14. Strategy Detail (`/app/strategies/{id}`) — 4 tabs (Overview/Pine/Python/Docs)
### 15. Engine Form (`/instances/new`) — new engine creation
### 16. Withdrawals (`/app/withdrawals`) — config + history
### 17. Spec (`/spec`) — design system spec page (1088 lines)

All walk-complete via `curl` 200 OK; DOM not inspected individually. **Will inspect next session** if needed.

---

## System-Wide Findings

### A. The `--glass-bg` / `--glass-border` Bug — TOP PRIORITY

`app/templates/layout.html` line 211:
```css
.chart-card {
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    ...
}
```

`--glass-bg` and `--glass-border` are **never defined** in `tokens.css`. Result: every `.chart-card` on every page is invisible (transparent bg, no border).

**Fix:** In `tokens.css`, add:
```css
--glass-bg: var(--surface-card);
--glass-border: var(--border-subtle);
--glass-shadow: var(--shadow-md);
```
Or better, **update the `.chart-card` rule to use the proper token names** (no glass metaphor needed for opaque dark theme):
```css
.chart-card {
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    border-radius: var(--card-radius);
    ...
}
```

This single fix will make **all 50+ card surfaces visible across the entire app.**

### B. Fleet Card Action Buttons — Height Mismatch

Dashboard fleet cards use:
```html
<button class="fleet-btn btn-stop" style="height:28px; padding:0 10px; font-size:11px;">
```

Spec (`design-system/MASTER.md` §5.1) says buttons should be **36px min on desktop, 44px on mobile**. The inline `style="height:28px"` overrides any token rule. 28px < 36px < 44px.

**Fix:** Replace inline styles with token classes:
```css
.fleet-card-actions .fleet-btn {
    height: var(--btn-height, 36px);
    padding: 0 var(--space-3);
    font-size: var(--text-sm);
}
@media (max-width: 768px) {
    .fleet-card-actions .fleet-btn {
        height: 44px;
        width: 44px;
    }
}
```

### C. Font-Size Overrides (h2 = 9.75px)

`layout.html` line 215:
```css
.chart-card h2 {
    font-family: var(--font-display);
    font-size: var(--text-sm);  /* 12px per tokens.css */
    font-weight: var(--weight-semibold);
    ...
}
```

But computed style says **9.75px**. The `--text-sm` token IS defined as 0.75rem (12px) — but something downstream overrides it. Possibly a media query for mobile, or a nested `.empty` class rule. **Need to trace.**

### D. Spec/Code Drift

`design-system/MASTER.md` §2 says `--color-info: #6BA4D5 Sky` (light blue).
`tokens.css` says `--color-info: var(--tb-600)` (teal `#08798E`).
**Decide: are we Sky or Teal?** The rest of the system is teal (brand, buttons, links). Recommendation: **update the spec to match code** (teal is the brand). Code is the source of truth.

### E. Legacy 301 Redirects

`/app/backtests` → 301 → `/app/testing/historical`
`/app/paper` → 301 → `/app/testing/paper`

Nav already points to the new URLs. But if any other internal links, bookmarks, or external references exist to the old paths, the 301s cost a round-trip. **Fix:** update any remaining `/app/backtests` or `/app/paper` references and remove the 301 handlers.

### F. Form Controls Inconsistency

Forms across **Settings, Secrets, Strategy Upload, Strategy Studio, Account Settings, Engine Form** use native `<input>` and `<select>` elements. These don't match the dark-mode design system (browser default rendering on dark mode is unpredictable). The Assistant + Trades pages use custom-styled controls. **Fix:** create `.form-input`, `.form-select`, `.form-textarea` classes with consistent dark-mode styling.

---

## Prioritized Fix List

| Priority | Phase | Fix | Impact | Effort |
|---|---|---|---|---|
| 🔴 1 | **DS5** | Define `--glass-bg`/`--glass-border` in tokens.css OR update `.chart-card` rule | Every card visible | 5 min |
| 🔴 2 | **DS6** | Bump fleet card buttons to 36px (44px mobile) | Touch targets compliant | 15 min |
| 🟡 3 | **DS7** | Replace inline `style="height:28px; font-size:11px"` on fleet cards with token classes | Inline styles eliminated | 20 min |
| 🟡 4 | **DS8** | Trace h2 font-size override (renders 9.75px not 12px) | Heading legibility | 20 min |
| 🟡 5 | **DS9** | Standardize form controls (`.form-input`, `.form-select`) | Consistent forms | 1h |
| 🟡 6 | **DS10** | Update design-system/MASTER.md to reflect teal (not sky) for info color | Spec/code aligned | 10 min |
| 🟢 7 | **DS11** | Add `aria-label` to 16 emoji avatar radios in Settings | Accessibility | 5 min |
| 🟢 8 | **DS12** | Remove legacy 301 redirects, fix any internal refs | Nav clean | 15 min |
| 🟢 9 | **DS13** | Investigate `$0.0` vs `$0.00` format inconsistency on Account Overview | Number format | 10 min |
| 🟢 10 | **DS14** | Add session titles to chat sessions sidebar | AT usability | 15 min |

**Total: ~3.5 hours of focused work** to bring the entire design system to spec compliance.

---

## Light Mode Verification

Both `--green` (#34d399) and `--bg-1` (#FFFFFF in light) and `--text-1` (#1A1410 in light) all resolve correctly through the DS1 shim. Light mode toggle works in browser. `applyAppMode()` is now clean (DS3 fix). The shim covers ALL legacy var refs in style.css.

**Remaining light-mode work:** the `--glass-*` bug affects light mode equally — once DS5 lands, light mode will also have visible cards.

---

## Files Referenced

- `app/static/tokens.css` — design system (Layer 1-4)
- `app/static/style.css` — legacy component styles (847 lines)
- `app/static/chat_widget.css` — chat widget styles (105 lines)
- `app/templates/layout.html` — shared shell, contains inline `<style>` block with `.chart-card` rule (lines 210-215)
- `app/templates/dashboard.html` — main page
- `app/templates/engine_detail.html` — most complex page (11+ chart-cards)
- `design-system/MASTER.md` — design spec (some drift from code)
- `backups/v101_design-system-reconcile_2026-07-16_1300/snapshot.tar.gz` — pre-DS1 backup
