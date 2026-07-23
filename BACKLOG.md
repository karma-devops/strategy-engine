# BACKLOG.md — Bugreport Tracking Ledger

> Consolidated tracking of all bug reports reviewed for the strategy-engine project.
> Last updated: 2026-07-23 (Asia/Makassar) — synced with CONTEXT.md / TASK-LIST.md / NOTES.md.
> Maintained so we don't re-do or lose track of applied vs. open items.

## Legend
- ✅ Fixed & committed
- ⚠️ Partial / documented / mitigated / needs decision
- ❌ Open (not yet done)
- N/A — not applicable to this repo (file doesn't exist, etc.)

---

## Report 1 — 28 bugs (#1–#28)

| # | File | Status | Commit | Note |
|---|------|--------|--------|------|
| 1 | main.py `/logs`+`/stream` auth | ✅ Fixed & live-verified (401/200) | `9387cfc` | |
| 2 | withdrawal/scheduler kill-check | ✅ Fixed | `9387cfc` | |
| 3 | dry-run withdrawal → `dry_run` status | ✅ Fixed | `9387cfc` | |
| 4 | start_instance bool propagation | ✅ Already correct in code | — | verified, no change needed |
| 5 | restart_instance kill guard | ✅ Fixed | `74b5a0e` | |
| 6 | runner._tick kill-check | ✅ Fixed | `9387cfc` | lazy import avoids circular |
| 7 | EventBus thread lock | ✅ Fixed | `74b5a0e` | `threading.Lock` |
| 8 | LOG_BUFFER thread lock | ✅ Fixed | `74b5a0e` | `threading.Lock` |
| 9 | alert dedup | ✅ Fixed | `74b5a0e` | `create_alert` checks existing |
| 10 | snapshot order_by | ✅ Fixed | `74b5a0e` | |
| 11 | dead portfolio_value | ✅ Removed | `74b5a0e` | |
| 12 | rotator applies max_position_pct | ✅ Fixed | `74b5a0e` | |
| 13 | testing_pool no-op explicit | ✅ Fixed | `74b5a0e` | `persisted: false` in response |
| 14 | ratelimit key_func | ✅ Fixed (was NameError) | `74b5a0e` | `key_func=api_key_or_ip` |
| 15 | delete_instance position check | ✅ Fixed | `74b5a0e` | force-close before delete |
| 16 | create_instance dry_run default True | ✅ Fixed | `74b5a0e` | paper by default |
| 17 | create_instance slug validation | ✅ Fixed | `74b5a0e` | regex `^[a-z0-9-]{1,32}$` |
| 18 | market_data startTime from bars | ✅ Fixed | `74b5a0e` | dropped unsupported `limit` key |
| 19 | next_scheduled_at persisted | ✅ Fixed | `74b5a0e` | scheduler writes it |
| 20 | metrics snapshot ordering | ✅ Fixed | `74b5a0e` | desc+limit+reverse |
| 21 | shared-wallet snapshot pollution | ⚠️ Documented | `74b5a0e` | TODO per-instance PnL from Trade rows |
| 22 | calculator boundary documented | ✅ Clarified | `74b5a0e` | comment on inclusivity |
| 23 | _persist_status blind merge | ✅ Already uses fresh-query | — | no change needed |
| 24 | withdrawals.js X-API-Key | ✅ Fixed & live-verified | `74b5a0e` | |
| 25 | routes pass api_key to withdrawals | ✅ Fixed & live-verified | `74b5a0e` | `window.API_KEY` set |
| 26 | bt.sharpe vs sharpe_ratio | ✅ Already correct | — | template uses `sharpe_ratio` |
| 27 | XSS in app.js | N/A | — | no `app.js` in repo |
| 28 | drawPulse inherits #20 | ✅ Resolved by #20 | — | backend fix sufficient |

---

## Report 2 — Codebase Review (P0–P3)

| Item | Priority | Status | Note |
|------|----------|--------|------|
| Kill switch closes positions | P0 | ✅ Already done | `kill_global` → `manager.close_all_positions()` verified |
| Idempotency on signals | P0 | ✅ Done | X1 PENDING sentinel + 60s cooldown (`_last_entry_attempt_ts`, `0122757`) |
| Circuit breaker | P0 | ✅ Done | `instances/runner.py` trips at 5 consecutive tick errors (T1-1) |
| Withdrawal method exists | P1 | ✅ Already done | `withdraw_to_wallet` at exchange.py:413 |
| Clock drift check | P1 | ❌ Open | optional NTP sync on startup + hourly |
| Thread-unsafe DB sessions | P1 | ⚠️ Mitigated | per-tick sessions + D2 retry/backoff |
| Liquidation detection | P2 | ❌ Open | add exit-reason tracking |
| Exchange client refresh | P2 | ✅ Done | `f66dffe` `_refresh_hl_client` on stale |
| Position size validation | P2 | ⚠️ Exists | `position_sizer.py` present; explicit pre-order check pending |
| Alerting system | P3 | ❌ Open | infra (webhook), out of scope |

---

## Report 3 — New Bugs (#32–#66)

| # | Item | Status | Decision / Note |
|---|------|--------|-----------------|
| 32 | 6-engine fleet is actually 1 | ⚠️ **DECIDED: seed engine-1 only** | fix "6-Engine" copy/labels to accurate wording |
| 41 | No kill-switch UI | ✅ Done | dashboard.html:543-550 EMERGENCY STOP → /api/v2/kill?reset=false |
| 42/43 | Two competing dashboards (/shell vs dashboard.html) | ✅ Resolved | No /shell route or shell.html exists; only / and /app/dashboard, both dashboard.html (stale backlog) |
| 44 | /dashboard 404 after login | 🟡 Stale | route is /app/dashboard, works; no 404 on real path |
| 46 | monitoring.py redundant dep | ⚠️ Harmless | optional cleanup |
| 48 | alerts helper unused | ❌ Open | minor |
| 53 | DEFAULT_FLEET docstring mismatch | ⚠️ Tied to #32 | fix with #32 |
| 54 | WithdrawalRecord idempotency | ✅ Done | unique `idempotency_key` column (T1-5) |
| 59 | landing.html auth broken | ✅ Resolved | T3-0 removed dangerous sessionStorage→Basic-Auth link; doLogin() correct |
| 60 | sessionStorage dead code | ✅ Resolved | dead `pulsr_auth` removeItem removed (`cf6a1d4`) |
| 61 | fake wallet-connect CTAs | ✅ Resolved | only legit HL-site wallet link remains (account_secrets.html) |
| 62 | sw.js dead /static/pages.js | ✅ Resolved | T3-0 sw.js caches static only, never /app/* HTML |
| 63 | sw.js cache-first on / | ✅ Resolved | T3-0 sw.js network-fetches authenticated HTML |
| 64 | instance_form missing engine_v6_1 | ✅ Done | v6_1 present in dropdown (renamed strategy_v6_1) |
| 65 | instance_form.js presets unwired | ❌ Open | dead code |
| 66 | spec.html dead weight | ⚠️ Move out of templates | minor |
| — | No fleet alerts badge | ❌ Open | UX backlog |
| — | No fleet-wide evaluate trigger | ❌ Open | UX backlog |
| — | Rotation approve/apply unclear | ❌ Open | UX (compounds #12) |
| — | Testing Pool zero UI | ❌ Open | API-only |
| — | No live-confirm on Dry Run→LIVE | ❌ Open | ROAST 3.6 |
| — | No API-key config banner | ❌ Open | UX |
| — | Withdrawals link easy to miss | ❌ Open | UX |
| — | Inconsistent loading/error states | ❌ Open | UX |
| — | No mobile layout on dashboard | ❌ Open | UX |

---

## Commits This Session
- `de71482` — Z1-Z7 refactor + A4/B7/D2/X1-X4
- `9387cfc` — Bugreport batch 1: safety-critical #1/#2/#3/#6
- `74b5a0e` — Bugreport batch 2: high+medium #4-#23

## Open Work (not yet scheduled) — reconciled 2026-07-23 (post-investigation)
1. #32 copy fix (seed engine-1 only, correct "6-Engine" labels) — ✅ DONE (T2-1 `23ff458`)
2. #41 kill-switch UI button (topbar) — ✅ DONE (dashboard.html:543-550 EMERGENCY STOP → /api/v2/kill?reset=false)
3. Circuit breaker (P0) — ✅ DONE (T1-1 `instances/runner.py`, trips at 5 consecutive errors)
4. Idempotency full window-check (P0) — ✅ DONE (2026-07-23 `0122757` — 60s entry cooldown via `_last_entry_attempt_ts` on both entry paths; X1 sentinel + bar gate retained)
5. Liquidation detection (P2) — ❌ OPEN (exit-reason tracking)
6. Clock drift (P1, optional) — ❌ OPEN (NTP sync; low priority)
7. #42/#43 two competing dashboards — ✅ RESOLVED (only / → dashboard() and /app/dashboard → dashboard_app(), both render dashboard.html; no /shell route or shell.html exists — was stale backlog)
8. #44 /dashboard 404 after login — 🟡 STALE (route is /app/dashboard, works; minor doc error, no 404 on the real path)
9. #54 WithdrawalRecord idempotency — ✅ DONE (T1-5, unique idempotency_key column)
10. T3-0 backtest `user` NameError — ✅ DONE (`98ca408`)
11. BUG-7 `/app/trades` Active Positions — ✅ DONE (`4fe89df`)
12. BUG-8 kill-switch API boundary — ✅ DONE (P0, `c88c669`, live-verified)
13. BUG-10 signup e2e — ✅ DONE (browser-verified)
14. BUG-11/BUG-12 withdrawal/deposit round-trip — ❌ DEFERRED (live funds, explicit go required)
15. T3-8 onboarding popup — ❌ OPEN
16. T3-9 email 2FA — ❌ OPEN (parked, no SMTP)
17. D4 PAPER/LIVE badge per trade row — ✅ DONE (dashboard.html:83 renders `paper` span when dry_run)
18. D5 dry_run toggle end-to-end verify — ❌ OPEN
19. B3 per-user log persistence — ❌ OPEN
20. B9 drawdown >50% spike filter — ❌ OPEN
21. B5/B6 schema hardening (NOT NULL + cascade) — ❌ OPEN
22. #59 landing.html auth broken — ✅ RESOLVED (T3-0 removed dangerous sessionStorage→Basic-Auth link; doLogin() correct; was stale backlog)
23. #60–#66 sessionStorage dead code / fake wallet CTAs / sw.js PWA — ✅ RESOLVED (T3-0; dead `pulsr_auth` removeItem removed 2026-07-23 `cf6a1d4`; only legit HL-site wallet link remains; sw.js caches static only, never /app/*)

## Decisions Locked
- **#32:** No default fleet. Seed engine-1 only. Fix misleading copy.
- All applied fixes committed; working tree clean between batches.
- Cookies, `.env`, `*.db` excluded via `.gitignore` (never committed).
- **Note (2026-07-23):** `engine/registry.py` carries an UNCOMMITTED labeling-prep diff (terminology block + dual-namespace keys) — operator decision pending, not part of committed batches.
