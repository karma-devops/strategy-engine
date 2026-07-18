# BACKLOG.md — Bugreport Tracking Ledger

> Consolidated tracking of all bug reports reviewed for the strategy-engine project.
> Last updated: 2026-07-18 (Asia/Makassar)
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
| Idempotency on signals | P0 | ⚠️ Partial | X1 PENDING sentinel blocks re-entry; full 60s window-check pending |
| Circuit breaker | P0 | ❌ Open | add `error_consecutive` counter, trip at 5 |
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
| 41 | No kill-switch UI | ❌ Open | Safety UX — recommend topbar STOP ALL |
| 42/43 | Two competing dashboards (/shell vs dashboard.html) | ⚠️ **Pending your call** | finish /shell OR delete it |
| 44 | /dashboard 404 after login | ❌ Open | verify route (may be served at `/`) |
| 46 | monitoring.py redundant dep | ⚠️ Harmless | optional cleanup |
| 48 | alerts helper unused | ❌ Open | minor |
| 53 | DEFAULT_FLEET docstring mismatch | ⚠️ Tied to #32 | fix with #32 |
| 54 | WithdrawalRecord idempotency | ❌ Open | money-movement safety |
| 59 | landing.html auth broken | ❌ Open | concrete frontend bug |
| 60 | sessionStorage dead code | ❌ Open | minor |
| 61 | fake wallet-connect CTAs | ❌ Open | UX honesty |
| 62 | sw.js dead /static/pages.js | ❌ Open | breaks PWA install (all-or-nothing cache) |
| 63 | sw.js cache-first on / | ❌ Open | stale shell after deploy |
| 64 | instance_form missing engine_v6_1 | ❌ Open | concrete |
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

## Open Work (not yet scheduled)
1. #32 copy fix (seed engine-1 only, correct "6-Engine" labels)
2. #41 kill-switch UI button (topbar)
3. Circuit breaker (P0)
4. Idempotency full window-check (P0)
5. Liquidation detection (P2)
6. Clock drift (P1, optional)
7. Report 3 frontend bugs #44, #59-#66
8. #42/#43 architectural decision (finish /shell or delete)
9. #54 WithdrawalRecord idempotency

## Decisions Locked
- **#32:** No default fleet. Seed engine-1 only. Fix misleading copy.
- All applied fixes committed; working tree clean between batches.
- Cookies, `.env`, `*.db` excluded via `.gitignore` (never committed).
