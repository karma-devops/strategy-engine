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

---

## Deep-Dive: Settings Page + Engine Settings Edit

Operator reported an issue editing engine settings previously. This section goes deeper than the per-page walk above.

### A. `/app/settings` — Account Settings (POST handler analysis)

**File:** `app/routes.py` lines 868-923

#### Functional Findings

| # | Severity | Issue | Location | Fix |
|---|----------|-------|----------|-----|
| 1 | **🔴 CRITICAL** | Password stored as `hashlib.sha256(new_pw.encode()).hexdigest()` — no salt, no bcrypt, no argon2. Rainbow-table crack in seconds. | line 891-892 | Use `bcrypt` or `argon2-cffi`. Library not in `requirements.txt` — needs install. |
| 2 | **🟡 MED** | `form.get("default_dry_run") in ("on", "true", "1", True)` — `True` is a Python bool, never matches a form string. Dead check. | line 881, 893 | Simplify to `in ("on", "true", "1")` |
| 3 | **🟡 MED** | `saved: True` flag is set in template context (line 919) but the `settings.html` template does NOT check for it — no success toast or banner on save. | template | Add `{% if saved %}<div class="toast success">Settings saved</div>{% endif %}` |
| 4 | **🟡 MED** | `start_balance = float(form.get(...))` silently catches `ValueError` (line 877-880). If operator types `abc`, nothing happens, no error feedback. | line 877-880 | Validate explicitly: try/except → return 400 with message |
| 5 | **🟢 LOW** | Email field accepts any string (line 884). No format validation. | line 884 | Add `@` check |
| 6 | **🟢 LOW** | `withdrawal_eth_address` accepts any string (line 895). No 0x prefix check. | line 895 | Validate `^0x[a-fA-F0-9]{40}$` |
| 7 | **🟢 LOW** | 2FA checkbox is a boolean but no 2FA flow is implemented anywhere. Setting it to `True` does nothing functional. | line 893 | Either implement 2FA or remove the field |

#### Design Findings

- **Form sections (PROFILE, SECURITY, TRADING, WALLET, PLAN & BILLING) are h2s without card containers** — same `.chart-card` bug applies. Form will be visually flat.
- **16-emoji avatar radio grid has no `aria-label`** — accessibility fail. Each radio should have `aria-label="Avatar {emoji}"`.
- **Save Settings button is at the bottom of a long form** — no "sticky save bar" (F12 mentioned in CONTEXT §"UX Overhaul" but not visible here).
- **No "Cancel" or "Discard" button** — operator can't back out without refreshing the page.
- **No visual feedback that the password field is being updated** — operator can't tell if their password was actually changed.

### B. `/app/engines/{slug}` — Engine Settings Modal

**File:** `app/templates/engine_detail.html` lines 304-757 (form + JS) · `api/instances.py` lines 318-337 (PUT handler)

#### Modal Design (lines 6-20 inline CSS)

- ✅ Clean modal overlay (rgba black 0.55)
- ✅ Card surface uses `var(--surface-card)` + border + radius
- ✅ Input height: 36px (matches spec)
- ✅ Focus ring: `outline: 2px solid var(--brand)` (uses brand, not broken --input-focus)
- ✅ Read-only fields in `.modal-readonly` block (Activation/Offset/Poll/Mode) — good UX
- ⚠️ `.modal-field label` uses `--text-xs` 10px uppercase — readable but very small
- ⚠️ No validation feedback inline — operator types a value, hits Save, no preview of "this is what'll change"

#### Save Flow (lines 705-757)

```
saveSettings(e)
  → PUT /api/v2/instances/{slug} with body
  → if ok: PUT /api/v2/instances/{slug}/strategy-config with collected [data-param] values
  → toast success → closeSettings() → refresh()
```

**Functional bugs in the JS:**

| # | Severity | Issue | Line | Fix |
|---|----------|-------|------|-----|
| 1 | **🟡 MED** | `parseInt(...) \|\| 1` for leverage — typing `0` silently becomes `1`. No min/max validation. | 712 | Add min/max attrs + check: `const v = parseInt(...); if (isNaN(v) \|\| v < 1 \|\| v > 50) { showToast('Leverage 1-50', 'error'); return; }` |
| 2 | **🟡 MED** | `max_position_pct: ... / 100` — assumes operator enters 97 for 97%. Unit not documented in label. | 713 | Update label: `Max Position (% of account, e.g. 97)` |
| 3 | **🟡 MED** | `dry_run` toggle sends immediately even if engine is `running`. The change saves to DB but **the running runner doesn't pick it up** without restart. Operator gets false feedback. | 714 | If `inst.status === "running" && dry_run changed`: `showToast('Stop engine to change dry_run', 'warning'); return;` |
| 4 | **🟢 LOW** | If PUT 1 fails AND strategy_config had values, the operator sees "Save error" but the form is still populated with old values. No clear retry path. | 740-755 | Disable form, show "Retrying…" spinner |
| 5 | **🟢 LOW** | No loading state on Save button — operator can click Save multiple times, firing duplicate PUTs. | — | `button.disabled = true` while in flight |

#### PUT Handler (`api/instances.py:318-337`)

```python
@router.put("/instances/{instance_id}")
def update_instance(...):
    inst = db.query(Instance).filter(Instance.slug == instance_id).first()
    if not inst:
        return {"ok": False, "message": "Instance not found"}
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key == "hyperliquid_private_key" and value:
            inst.set_private_key(value)
        elif key in {"account_address", "withdrawal_address"} and value:
            setattr(inst, key, value)
        elif hasattr(inst, key):
            setattr(inst, key, value)
    db.commit()
    return {"ok": True, "message": f"Updated {inst.slug}"}
```

| # | Severity | Issue | Fix |
|---|----------|-------|-----|
| 1 | **🔴 HIGH** | `hasattr(inst, key)` lets through ANY attribute — `user_id`, `id`, `created_at`, `api_key`, etc. Auth bypass risk if operator sends the right payload. | Whitelist allowed fields: `{"name", "token", "strategy_id", "timeframe", "leverage", "max_position_pct", "dry_run", "start_balance", "activation", "offset", "hl_credential_id", "hyperliquid_private_key", "account_address", "withdrawal_address", "poll_interval"}` |
| 2 | **🟡 MED** | No validation of `leverage` (can be 0, negative, or 1000) | Add `1 <= payload.leverage <= 50` check |
| 3 | **🟡 MED** | No validation of `max_position_pct` (can be > 1.0 = 100%) | Add `0 < payload.max_position_pct <= 1.0` |
| 4 | **🟡 MED** | No validation of `token` (must be valid HL token, not random string) | Verify against `meta_and_asset_ctxs` or `/api/v2/metadata` |
| 5 | **🟢 LOW** | Returns `{"ok": True}` — no payload of what was actually saved. UI can't show "Saved: leverage=3x, dry_run=false" | Return `{ok: True, saved: {field: value, ...}}` |
| 6 | **🟢 LOW** | No audit log — operator changes dry_run on running engine, no record in DB | Add `AuditLog` row on every PUT |

#### Strategy Config PUT (`api/instances.py:340`)

Different endpoint (`/strategy-config`), likely has its own validation. **Not audited this pass** — would need a separate review.

### C. Recommended Fix Sequence (Settings + Engine Edit)

| Phase | Fix | Effort | Risk |
|---|---|---|---|
| **DS15** | Whitelist allowed fields in `update_instance` (security) | 15 min | low — additive guard |
| **DS16** | Add `leverage` and `max_position_pct` validation in `update_instance` | 15 min | low |
| **DS17** | Replace SHA256 password with bcrypt in `settings_app_save` | 30 min | medium — needs `bcrypt` install, migration of existing hash |
| **DS18** | Add `saved: True` success banner to `settings.html` | 10 min | low |
| **DS19** | Fix `saveSettings()` JS — add min/max validation, dry-run-stop-first guard, disable-during-save | 30 min | low |
| **DS20** | Add `aria-label` to 16 avatar emojis in Settings | 5 min | low |
| **DS21** | Add `is_running` check in `update_instance` PUT for dry_run changes | 15 min | low |

**Total: ~2 hours** to bring both Settings and Engine Edit to a safe + clear state.

### D. Why the operator hit an issue editing engine settings

Based on the code, the most likely failure mode is:
1. Operator opens engine settings modal
2. Changes `dry_run` toggle
3. Clicks Save
4. PUT to `/api/v2/instances/{slug}` succeeds (DB updated)
5. PUT to `/strategy-config` succeeds (no values, returns ok)
6. Toast: "Settings saved" ✓
7. Modal closes, page refreshes
8. **But the engine is still running with the OLD dry_run** — runner doesn't read DB dynamically for dry_run; it has the value at instantiation
9. Operator sees the **same status** (running) and **same behavior** → thinks "Save didn't work"

**This is a real UX bug.** The fix is either (a) auto-stop+restart on dry_run change, or (b) clear warning "Dry run changes take effect on next engine restart."
