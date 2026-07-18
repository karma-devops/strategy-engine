# PULS·R Strategy Engine — Roadmap

> **Current Version:** v0.095
> **Status:** Pine fidelity refactor complete. Three-port architecture live. 61/61 tests PASS.
> **Next milestone:** v0.1 — Live trading ready (Phases 9-12)
> **Repository:** Local only (not pushed to GitHub yet)

---

## Version History

### v0.095 — Pine Fidelity Refactor (2026-07-16)

**State:** Strategy layer matches PineScript v1.3 exactly. Dual-mode restored. Three-port architecture confirmed. Dynamic settings panel in UI. Clean slate protocol established.

**Completed:**
- [x] Phase 1: `engine/base.py` — `get_parameters()` + `get_default_config()` + kwargs support
- [x] Phase 2: `engine/v1_3.py` — Dual-mode (Swing+Scalp), 6 risk profiles, mode-aware params, `trail_exit_grace_seconds` removed, `get_parameters()` (15 params)
- [x] Phase 3: `scripts/worker.py` — Equity history trade-close only, grace removed, one-entry-per-bar
- [x] Phase 4: `instances/runner.py` — Same 3 fixes + `strategy_config` applied at instantiation
- [x] Phase 5: `instances/models.py` — `strategy_config` JSON + `snapshot_data`/`snapshot_image_url`/`snapshot_at` columns + migration
- [x] Phase 6: API endpoints — GET parameters, GET/PUT strategy-config (3 endpoints, live-verified)
- [x] Phase 7: `app/routes.py` — `strategy_config` + `strategy_parameters` passed to engine detail template
- [x] Phase 8: `engine_detail.html` — Dynamic settings panel (15 params from `get_parameters()`)
- [x] Full-scope test: 61/61 PASS
- [x] Clean slate: `template_empty_STABLE.db` saved, all processes killed, HL positions closed
- [x] Documentation: FAQ.md + DOCUMENTATION.md + Roadmap.md created

**Not yet:**
- [ ] Phase 9: Strategy Studio clone (user-named, versioning)
- [ ] Phase 10: Python upload tab
- [ ] v1 + v6.1 `get_parameters()` implementation
- [ ] Worker: apply `strategy_config` from state
- [ ] Aetheris user account
- [ ] Multi-tenant DB spawn on signup
- [ ] Snapshot capture system (image + state per instance)
- [ ] Live trade test with new Pine-faithful params
- [ ] Backtest runner equity_history review

---

### v0.09 — UX Overhaul + Worker Fixes (2026-07-15)

**State:** Frontend fully functional. Worker autonomous. Settings accessible and mobile-friendly.

**Completed:**
- [x] Audit fixes P1-P14 (adoption dict, reversal re-entry, compare_digest, anomalous snapshots, TP fix, tooltips)
- [x] Worker P16 fixes (equity_history, adoption dicts, exit cost, API endpoints)
- [x] Frontend Phase 10B (F1-F13): Trades rewrite, strategies rewrite, tooltips, animations, skeleton loading, landing logged-in state, sticky save bar, ARIA roles
- [x] UX Overhaul (G1-G3 + Logout + Mobile): Account value always shows, floating AI bubble, mobile burger menu, full logout flow, login fix, dark/light mode, session delete, settings UX, modal scroll fix, mobile touch targets
- [x] Worker verified autonomous (enters/exits via 7-exit logic, position reconciliation, reversal re-entry)

---

### v0.08 — Strategy Studio + Account Section (2026-07-14)

**State:** Full strategy lifecycle (upload, convert, backtest, deploy). Account management with credential storage.

**Completed:**
- [x] Phase 6: Strategy Studio (Pine→Python converter, save & activate)
- [x] Phase 7: Testing section (historical backtest form + results, paper trading, OHLC persistence)
- [x] Phase 8: Account section (overview, settings, secrets with 4 tabs, credential manager)
- [x] Phase 8A: Per-engine HL credential selector
- [x] Phase 8B: Multi-wallet / multi-HL UI
- [x] Phase 9: Chat backend (per-user model selection, chat sessions, context-awareness)
- [x] Phase 10: Chat widget restyle (brand tokens, user dropdown, logout, session reload)
- [x] Receptacle pattern: Unified exit config, neutral receivers, removed fabricated exits
- [x] Fidelity check: All 3 PineScripts read (1,342 lines), 5 mismatches found, 2 fixed
- [x] Mintick fix: HL API markPx precision (authoritative)
- [x] Poll interval: 3s (was 30s)
- [x] Full live verification: API matrix (17 GET, 4 POST/PUT), browser UI (19 routes), HL bidirectional, backtest

---

### v0.07 — Multi-Tenant + DDD Build (2026-07-13)

**State:** User aggregate, per-instance dry_run, account settings, live/paper separation.

**Completed:**
- [x] Phase A1: User aggregate (User model, get_or_seed_operator)
- [x] Phase A2: user_id on instances, snapshots, backtests, trades + kind/is_paper
- [x] Phase A3: Per-instance dry_run overrides env
- [x] Phase A4: Settings page + account KPIs
- [x] Phase A5: Live/Paper separation routes
- [x] Phase A6: Rich trade log
- [x] Phase A7: Engines page + detail
- [x] Bento dashboard: Pulse Graph, Open Positions, Active Trades
- [x] SVG Pulse Graph (replaced lightweight-charts)
- [x] Densify: tighter layout, more data density
- [x] Swagger enhancement: title, version, description, contact
- [x] PWA wiring: manifest.json, service worker, theme-color
- [x] Full API test matrix: 51/52 PASS
- [x] Browser UI bidirectional verify
- [x] tojson|safe fix (critical JS bug)
- [x] ADIX docsync: HANDOVER, IA-SPEC, CONTEXT, SPECSHEET, NAMING updated

---

### v0.06 — UI Architecture Decision: Option B (2026-07-13)

**State:** Server-rendered Jinja2 + lightweight-charts. No SPA. Auth unified.

**Completed:**
- [x] Phase 0: Backup UI files, auth unification
- [x] Phase 1: Dashboard — real /app/dashboard route, Python KPIs, equity curve
- [x] Phase 2: Backtests — Python-rendered results table, correct metrics
- [x] Phase 3: Trades / Engines / Monitoring / Assistant / Settings — server-rendered
- [x] Phase 4: Retire SPA — delete app-shell router JS
- [x] Phase 5: Landing logged-in state
- [x] Lightweight-charts integration (CDN)
- [x] Code audit: 10 bugs found (2 critical, 2 high, 6 medium)
- [x] Worker repair: cloid hex fix, DRY_RUN=false, 7-exit logic, position reconciliation

---

### v0.05 — Phase 4B: UI Overhaul (2026-07-12)

**State:** Full dashboard with fleet cards, toast system, monitoring gauges, add engine modal, loading skeletons, empty states, dark/light mode, mobile responsive.

**Completed:**
- [x] Delete cascade bugfix
- [x] Token selector with search (232 HL tokens)
- [x] Leverage from HL maxLeverage
- [x] System info panel
- [x] Kill switch UI (Global, Withdrawal, Per-Engine)
- [x] Withdrawals page
- [x] AI Assistant page
- [x] Dark/light theme toggle
- [x] Mobile bottom nav
- [x] Fleet cards with PnL hero, status dot, running glow
- [x] Toast system (4 types, slide-in, auto-dismiss)
- [x] Monitoring gauges (SVG ring gauge)
- [x] Add Engine modal
- [x] Loading skeletons
- [x] Empty states
- [x] Path-based routing (History API)
- [x] Login/logout flow
- [x] Backtest API fixes (standalone mode, activation as float)
- [x] Strategy dropdown bugfix

---

### v0.04 — Phase 3: Dashboard + Engines + Backtest (2026-07-12)

**State:** SPA router, dashboard with equity curve, engine detail, backtest page with bar-replay.

**Completed:**
- [x] SPA hash router (9 routes)
- [x] Dashboard: equity curve SVG, fleet grid, activity log, SSE
- [x] Engines page: per-engine tabs, detail cards, signals, trades, backtests
- [x] Engine detail page (direct hash route)
- [x] Trades page: full-width table
- [x] Backtests page: saved results table
- [x] Monitoring page: scores grid + alerts
- [x] Settings modal + start_balance
- [x] Bar-replay endpoint (POST /api/v2/backtests/replay)
- [x] Tick simulation (4-tick O/H/L/C, 28-tick Brownian bridge)
- [x] Leverage API + UI stepper
- [x] Sidebar icons fix
- [x] Live engine start (FARTCOIN 5x, DRY_RUN=false)

---

### v0.03 — Pre-Live Blocker Phase (2026-07-11)

**State:** All critical blockers resolved. Auth, rate limiting, idempotency, kill switches.

**Completed:**
- [x] Stable slugs + per-engine credentials (Fernet encryption)
- [x] Default 6-engine fleet
- [x] Position limit 97% default
- [x] Kill switch system (global, per-instance, withdrawals)
- [x] API rate limiting (slowapi)
- [x] Safe backoff/retry on HL SDK calls
- [x] Trade idempotency
- [x] Auth: HTTP Basic Auth (UI) + X-API-Key (API)
- [x] Hard test pass (8 sections, all green)
- [x] Live credential smoke test ($15.85 USDC)
- [x] UI retheme: sienna dark palette (#1a1410)
- [x] Logo: PULS-R (animated stroke-dasharray)
- [x] Backtest runner repair (equity compounding, fees, trailing stop)
- [x] v1.3 fidelity fixes (ATR Wilder's RMA, 1x leverage default, risk-based sizing)
- [x] Trailing stop simulation
- [x] Accuracy audit (fee 0.045%, mintick 0.00001)
- [x] Git repo created (private, github.com/karma-devops/strategy-engine)
- [x] Dynamic mintick detection
- [x] Live execution test (FARTCOIN LONG executed on HL)

---

### v0.02 — Scaffold + Core (2026-07-11)

**State:** Project structure, core services, basic dashboard.

**Completed:**
- [x] Directory structure
- [x] FastAPI service
- [x] Exchange client (HL SDK)
- [x] Signal monitor
- [x] Dashboard HTML/JS/CSS
- [x] Strategy loader (dynamic class detection)
- [x] Withdrawal system (calculator, scheduler, manual executor)
- [x] Presets (v1, v1.3, v6.1)
- [x] 6-engine default fleet
- [x] py_compile passes for all Python files
- [x] PineScripts archived in pinescript-tv/

---

### v0.01 — Project Init (2026-07-11)

**State:** Initial scaffold.

**Completed:**
- [x] Project directory created
- [x] CONTEXT.md created
- [x] SPECSHEET.md created
- [x] Design locked
- [x] Backup v0 created

---

## Milestone Roadmap

### v0.1 — Live Trading Ready (Next)

| # | Item | Priority | Est. Effort | Dependencies |
|---|------|----------|-------------|--------------|
| 9 | Strategy Studio clone endpoint + versioning (user-named, auto-increment) | High | 3h | ✅ Done |
| 10 | Strategy Studio Python upload tab | High | 2h | ✅ Done |
| 11 | v1 + v6.1 `get_parameters()` implementation | Medium | 1h | ✅ Done |
| 12 | Worker `strategy_config` application + UI | Medium | 1.5h | ✅ Done |
| 13 | Live trade test with Pine-faithful params | High | 2h | Phases 9-12 |
| 14 | Backtest runner equity_history review | Medium | 1h | None |

### v0.2 — Multi-Tenant + Accounts

| # | Item | Priority | Est. Effort | Dependencies |
|---|------|----------|-------------|--------------|
| 15 | Aetheris user account | Medium | 1h | None |
| 16 | Multi-tenant DB spawn on signup | High | 2h | None |
| 17 | Signup flow (form, validation, DB creation) | High | 2h | #16 |
| 18 | Per-user venv (isolated Python) | Low | 4h | #16 |

### v0.3 — Monitoring + Polish

| # | Item | Priority | Est. Effort | Dependencies |
|---|------|----------|-------------|--------------|
| 19 | Snapshot capture system (image + state) | Medium | 3h | None |
| 20 | 24h live test analysis | High | 1h | #13 |
| 21 | Worker CSV trade log | Medium | 2h | None |
| 22 | K6: Move API keys to env-only | Medium | 1h | None |
| 23 | OHLC persistence for >60d backtests | Low | 2h | None |

### v0.3 — Monitoring + Polish (same as roadmap)

### v0.4 — GitHub Release (same as roadmap)

### v0.5 — Eval + Model Comparison

| # | Item | Priority | Est. Effort | Dependencies |
|---|------|----------|-------------|--------------|
| 14 | `/eval` page + panel (run multiple models/engines/scripts against each other) | High | 4h | None |
| 15 | `eval_runs` + `eval_results` DB tables | High | 2h | #14 |
| 16 | HL `userFills` trade ID reconciliation for eval | Medium | 2h | #15 |
| 17 | Eval history browser (per-user, stored in DB) | Medium | 2h | #15 |

### v0.6 — Multi-Tenant User Accounts + Tokens

| # | Item | Priority | Est. Effort | Dependencies |
|---|------|----------|-------------|--------------|
| 18 | Per-user PULS-R API key on signup (UUID, API key, token verification) | High | 3h | None |
| 19 | Favourite coins per user (bubble/info display, stored in user DB) | High | 2h | #18 |
| 20 | Available tokens list from HL API (only valid USDC perps) | High | 2h | None |
| 21 | Documentation prompt template with copy-able API, frontend, strategy code | Medium | 2h | None |

### v0.4 — GitHub Release

| # | Item | Priority | Est. Effort | Dependencies |
|---|------|----------|-------------|--------------|
| 24 | Clean repo (remove secrets, local paths, .env) | High | 1h | All above |
| 25 | Public README.md | High | 2h | #24 |
| 26 | GitHub release v0.1 | High | 1h | #24-25 |
| 27 | CI/CD pipeline (tests on push) | Medium | 3h | #24 |

---

## Versioning Convention

```
v{Major}.{Minor}{Patch}
```

- **Major:** Breaking changes (0 = pre-release)
- **Minor:** Feature releases (0.01 → 0.02 → ... → 0.095 → 0.1)
- **Patch:** Bug fixes (0.095 → 0.095.1)

**Current:** v0.095 — Pine fidelity refactor complete. Next: v0.1 (live trading ready).

**Version file:** `VERSION` at project root (contains just the version string).
**Version reference:** All docs reference this file for the current version.

---

## How to Bump the Version

```bash
# 1. Update VERSION file
echo "v0.1" > VERSION

# 2. Update this file (add new version entry above)
# 3. Update DOCUMENTATION.md version header
# 4. Update main.py FastAPI title version
# 5. Commit
```
