# Full Project UI/UX Redesign — Expanded Plan

**Author:** Aetheris · **Date:** 2026-07-16 · **Session:** e3f7461df4ce
**Operator directive:** "whole project refactor and proper UI/UX redesign, starting with paper trading, use lightweight-charts"
**Skills applied:** ui-ux-pro-max, trading-dashboard-patterns, backup-versioning, AEE, Karpathy
**Backup protocol:** backup-versioning skill (tar.gz STABLE, exclude venv/.env/db, one per phase)

---

## 0. Project Context (verified)

| Layer | Count | LOC |
|---|---|---|
| Python | ~40 files | 32,132 |
| HTML templates | 25 files | 7,183 |
| CSS | 3 files | 1,404 |
| JS | 4 files | 377 |
| Pine source | 3 files | 1,342 |
| Markdown docs | many | 8,325 |
| **Routes** | **114** | — |
| Design system | `tokens.css` (3-layer) + `style.css` (legacy, has shim) | 1,299 |

**Page inventory (25 templates):**
- Public: landing, error
- Auth app: dashboard, engines, engine_detail, trades, strategies, strategy_detail, strategy_studio, strategy_upload
- Testing: testing_index, testing_historical, testing_paper
- Account: account, account_overview, account_secrets, settings
- System: spec, logout, instances/new
- Assistant: assistant, chat_widget
- Other: live_paper, withdrawals, layout (shared shell), backtests (legacy)

**Current visual state (post-DS5):**
- Chart cards now have visible bg + border (DS5 fix)
- 30+ legacy CSS vars resolved via shim
- Input focus ring now renders (DS2 fix)
- ToggleAppMode cleaned (DS3 fix)
- All 19 pages render at 200 OK

**Current functional state:**
- Paper trading: **display-only** (no action buttons, no live refresh, no SSE)
- Engine detail: working (Start/Stop/Close/Restart/⚙ modal), but JS `parseFloat || 0` bug fixed (DS-2.0) and HTML5 validation removed (commit 0db2ed5)
- live_paper.html: **display-only** (same problem)
- account.html: display-only fleet cards
- Strategies: working, but Strategy Studio convert feature unknown
- Backtest: working but only has form, no comparison features

---

## 1. The Expanded Plan — 4 Sprints, ~25 hours total

### Sprint A — Foundation (~4h)

Solidify the base. No UI changes — just stable ground for what comes after.

| Phase | Change | Files | Backup slug |
|---|---|---|---|
| A.1 | Token audit: ensure all 5+ modes (dark/light × css var resolution) work | `app/static/tokens.css` | `v200_a1-token-audit_2026-07-16_1500` |
| A.2 | Add `lightweight-charts` library (CDN) to `layout.html` `<head>` | `app/templates/layout.html` | `v201_a2-add-lightweight-charts_2026-07-16_1510` |
| A.3 | Create reusable `chart.js` wrapper module: `createEquityChart(containerId, theme)` | `app/static/chart.js` (NEW) | `v202_a3-chart-wrapper_2026-07-16_1520` |
| A.4 | Add per-instance equity endpoint `/api/v2/instances/{slug}/equity` | `api/instances.py` | `v203_a4-per-instance-equity-api_2026-07-16_1530` |
| A.5 | Add `equity_series` to per-instance dashboard payload | `app/routes.py` | `v204_a5-route-context-equity_2026-07-16_1540` |
| A.6 | Live test: charts render on empty page with skeleton loader | browser | (no backup — verify only) |
| A.7 | Write `docs/charts-usage.md` for the new chart module | docs | `v205_a7-chart-docs_2026-07-16_1550` |

### Sprint B — Paper Trading Pilot (~6h)

The operator's pilot page. Make it beautiful + functional + live.

| Phase | Change | Files | Backup slug |
|---|---|---|---|
| B.1 | **Apply Part 1.1** (already in working tree, uncommitted): clickable fleet cards + sparkline container | `app/templates/testing_paper.html` | `v206_b1-fleet-clickable_2026-07-16_1600` |
| B.2 | Add per-engine action buttons (Start/Stop/Close/Restart/⚙) + `event.stopPropagation()` | `app/templates/testing_paper.html` | `v207_b2-action-buttons_2026-07-16_1610` |
| B.3 | Bump button heights to 36px desktop / 44px mobile | `app/templates/testing_paper.html` | `v208_b3-touch-targets_2026-07-16_1620` |
| B.4 | Add aria-labels to all icon-only buttons | `app/templates/testing_paper.html` | `v209_b4-aria-labels_2026-07-16_1630` |
| B.5 | Add live API refresh loop (3s poll) | `app/templates/testing_paper.html` | `v210_b5-live-refresh_2026-07-16_1640` |
| B.6 | Add SSE runner console (live signal/trade stream) | `app/templates/testing_paper.html` | `v211_b6-sse-console_2026-07-16_1650` |
| B.7 | Fix PnL color: use `--color-profit`/`--color-loss` (was brand teal) | `app/templates/testing_paper.html` | `v212_b7-pnl-color_2026-07-16_1700` |
| B.8 | **Replace canvas with lightweight-charts** for portfolio-total equity curve | `app/templates/testing_paper.html` | `v213_b8-lwc-portfolio_2026-07-16_1710` |
| B.9 | Add per-engine equity chart (lightweight-charts, one per fleet card) | `app/templates/testing_paper.html` | `v214_b9-lwc-per-engine_2026-07-16_1720` |
| B.10 | Empty state: "No paper engines" → add CTA button + brief explainer | `app/templates/testing_paper.html` | `v215_b10-empty-state_2026-07-16_1730` |
| B.11 | Live test end-to-end: open page, click engine, start, watch chart update | browser | (verify only) |
| B.12 | Commit "feat: paper trading panel — fleet cards + live charts" | git | — |

### Sprint C — Replicate to Other Pages (~6h)

The same panel pattern on `live_paper.html`, `account.html`, and add missing actions on other pages.

| Phase | Change | Files | Backup slug |
|---|---|---|---|
| C.1 | Apply full panel pattern to `live_paper.html` (currently display-only) | `app/templates/live_paper.html` | `v216_c1-live-paper-panel_2026-07-16_1800` |
| C.2 | Apply to `account.html` (currently display-only) | `app/templates/account.html` | `v217_c2-account-panel_2026-07-16_1810` |
| C.3 | Add per-engine lightweight-charts to `engine_detail.html` (in addition to existing sparkline + histogram) | `app/templates/engine_detail.html` | `v218_c3-engine-detail-lwc_2026-07-16_1820` |
| C.4 | Add per-engine lightweight-charts to `engines.html` fleet cards | `app/templates/engines.html` | `v219_c4-engines-lwc_2026-07-16_1830` |
| C.5 | Add lightweight-charts to `dashboard.html` Pulse Graph (replaces current SVG) | `app/templates/dashboard.html` | `v220_c5-dashboard-lwc_2026-07-16_1840` |
| C.6 | Add tab pills to `testing_paper.html` (All / Live / Paper / Per-engine) for trades view | `app/templates/testing_paper.html` | `v221_c6-tabbed-trades_2026-07-16_1850` |
| C.7 | Add trade history filters (side, status, date range) to `trades.html` | `app/templates/trades.html` | `v222_c7-trades-filters_2026-07-16_1900` |
| C.8 | Add inline validation feedback + loading states to engine settings modal | `app/templates/engine_detail.html` | `v223_c8-settings-ux_2026-07-16_1910` |

### Sprint D — Polish & Security (~5h)

The quality + safety work. Already partially identified in DS4 audit.

| Phase | Change | Files | Backup slug |
|---|---|---|---|
| D.1 | Replace SHA256 password with bcrypt (operator security) | `app/routes.py` + `requirements.txt` | `v224_d1-bcrypt-passwords_2026-07-16_2000` |
| D.2 | Whitelist allowed fields in `update_instance` PUT (security) | `api/instances.py` | `v225_d2-put-whitelist_2026-07-16_2010` |
| D.3 | Add server-side validation: leverage (1-50), max_position_pct (0-1), token (valid HL) | `api/instances.py` | `v226_d3-server-validation_2026-07-16_2020` |
| D.4 | Add success banner to `settings.html` for `{saved: True}` | `app/templates/settings.html` | `v227_d4-settings-banner_2026-07-16_2030` |
| D.5 | Add aria-labels to 16 avatar emoji radios in Settings | `app/templates/settings.html` | `v228_d5-avatar-aria_2026-07-16_2040` |
| D.6 | Fix `$0.0` → `$0.00` number format drift on Account Overview | `app/templates/account_overview.html` | `v229_d6-money-format_2026-07-16_2050` |
| D.7 | Remove legacy 301 redirects (`/app/backtests`, `/app/paper`) | `app/routes.py` | `v230_d7-remove-301_2026-07-16_2100` |
| D.8 | WCAG AA contrast audit (per DS6): compute all text/bg ratios, fix any <4.5:1 | `app/static/tokens.css` | `v231_d8-wcag-audit_2026-07-16_2110` |
| D.9 | Add "Promote to Live" button on paper trading cards (operator explicitly mentioned as needed) | `app/templates/testing_paper.html` + new endpoint | `v232_d9-promote-to-live_2026-07-16_2120` |
| D.10 | Final live test: walk every page light + dark, screenshot, document | browser + docs | (verify + commit only) |

---

## 2. Per-Phase AEE Cycle (strict)

Every phase follows this loop. No exceptions. No batching.

```
1. THINK    — what is the exact change? what files? what success criterion?
2. PLAN     — slug, what to tar, what to read first
3. BACKUP   — tar czf backups/v{N}_{slug}.tar.gz --exclude=... <files>
            + append to backups/VERSIONING.md
4. EXECUTE  — ONE patch (find/replace, unique context)
5. VERIFY   — wc -l + git diff --stat + curl 200 + browser_console computed style
6. DOUBLE   — read file post-edit, check for regressions, edge cases
7. COMMIT   — git add specific files + commit with phase slug
```

---

## 3. Execution order

**This session, starting now:**
1. Commit Part 1.1 (the in-progress change, backed up to v104)
2. Sprint A: A.1 → A.7 (foundation, ~4h)
3. Sprint B: B.1 → B.12 (paper trading pilot, ~6h)

**Next session, after operator reviews:**
4. Sprint C: C.1 → C.8 (replicate pattern, ~6h)
5. Sprint D: D.1 → D.10 (polish + security, ~5h)

**Total: ~21h of focused work over ~4-5 sessions.**

If operator wants faster: parallel sprints where independent (e.g., Sprint A backend + Sprint B frontend can overlap). Otherwise sequential, one phase per turn, one backup per phase.

---

## 4. What "done" looks like for each sprint

**Sprint A done when:**
- lightweight-charts loads in browser, no console errors
- `/api/v2/instances/{slug}/equity` returns `{ok: true, equity: [...]}`
- Chart wrapper reusable from any page via `createEquityChart('id', 'dark')`
- `docs/charts-usage.md` exists with examples

**Sprint B done when:**
- Paper trading page: click engine card → navigate; click ▶/⏹ → action; click ⚙ → modal; fleet card has 44px touch targets; aria-labels on all icon buttons; live refresh works; SSE console streams; PnL renders emerald/coral; portfolio chart + per-engine charts render with lightweight-charts and update every 3s; empty state has CTA
- Operator can demo it: "Look, paper trading now actually works"

**Sprint C done when:**
- live_paper.html, account.html, engine_detail.html, engines.html, dashboard.html all use the same panel pattern
- All charts use lightweight-charts (no more hand-rolled SVG/canvas)
- Trades page has filters
- Tab pills work on paper trading

**Sprint D done when:**
- Password is bcrypt-hashed
- update_instance has whitelist
- Server-side validation in place
- WCAG AA passes on all text combos
- No legacy 301 redirects
- Every page tested light + dark

---

## 5. Out of scope (deferred)

- "Compare to Live" feature (paper vs live side-by-side) — needs backend support
- Strategy Studio LLM-powered Pine→Python converter — already exists, just needs UX polish
- New API endpoints (everything uses existing routes)
- Mobile-first redesign (44px touch targets in 1.3 cover critical case; full mobile redesign is separate)
- Real-time SSE for charts (using 3s polling is simpler and proven; SSE later if needed)
- Backups of the live trade data (DB only — not source)

---

## 6. Risk register

| Risk | Mitigation |
|---|---|
| lightweight-charts CDN goes down | Vendor locally as fallback (`app/static/lightweight-charts.standalone.production.js`) |
| Backups bloat with many small files | 1 backup per phase only, prune v0-v99 periodically |
| Operator runs out of patience with many small phases | Optional: batch 2-3 small related phases per turn if they touch same file |
| Existing design audit (DS4) findings conflict with new plan | DS4 findings already in `docs/design-audit-findings-v1.md`; integrate D.1-D.8 |
| `instances/runner.py` doesn't populate per-instance equity snapshots | A.4/A.5 may need runner.py changes; defer to discovery in A.4 |
| Browser cache hides UI updates | Each phase uses fresh navigation with cache-bust `?ts=...` query |

---

## 7. Backup-versioning skill — execution rules

- **One backup per phase**, before any live edit
- **tar.gz form** with explicit excludes: `backups venv __pycache__ *.pyc data/*.db* .env`
- **Update `backups/VERSIONING.md`** after each tar (one section per phase)
- **Mark STABLE only after live verification** confirms the change works
- **If a change breaks**: revert to last STABLE, investigate, increment from there
- **Timestamp in slug** is local time, format `YYYY-MM-DD_HHMM`

---

## 8. Operator approval gates

Per AEE: explicit go before each major change. The following need operator confirmation:
- Sprint A complete → review before Sprint B
- Sprint B (paper trading) complete → operator demos it before Sprint C
- Sprint C complete → review before Sprint D
- Sprint D complete → final sign-off

Within a sprint: per-phase commits are auto-approved, no per-phase pause.
