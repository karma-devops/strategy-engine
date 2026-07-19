# PULS·R Task List — Consolidated Work Inventory (single source of truth)

**Consolidated:** 2026-07-19 (Asia/Makassar) · **Status:** ⚠️ NOT STABLE / NOT BETA
**Live State:** engine-1 RUNNING LIVE (FARTCOIN LONG, liq enriched via A4) · engine-2 STOPPED (paper) · main app UP port 8792
**Server:** supervisor-managed uvicorn on port 8792 (PID rotates per restart — currently ~65393), login `operator`/`operator`, DB `main/data/dev_test.db` (injected by supervisor; config default path also `data/strategy_engine.db`)
**Sources merged:** TASK-LIST v1.98 + BUGREPORT.md (karma-devops) + HANDOVER-UI-WALKTHROUGH.md + TASK-PRIORITIES.md (3-tier companion)

**4-FILE DOC TAXONOMY:** CONTEXT.md (MAP) · NOTES.md (LOG) · TASK-LIST.md (WORK) · BETA-ROADMAP.md (FORWARD)
**Companion evidence files (do NOT edit, read-only):** `docs/bugreport.md` (verbatim BUGREPORT) · `docs/task-priorities.md` (3-tier companion) · `docs/HANDOVER-UI-WALKTHROUGH.md` · **`docs/BUGREPORT-1.md`, `docs/UI-TODO-1.md`, `docs/VERIFICATION-STATUS-1.md`** (operator-supplied 2026-07-19 — supersede earlier bugreport view; VERIFICATION-STATUS-1 is authoritative on what is actually fixed vs regressed).

**Discipline (ADIX + AEE + Karpathy):** one file per turn, backup before each write, verify before advance, no batch edits, consent gate on structural/destructive changes, live-test every fix. Zero autonomous deletion.

---

## UNIFIED PRIORITY ORDER (3-tier, from TASK-PRIORITIES.md — authoritative sequencing)

**Principle:** Fix what's actively wrong with money and access control first, on the architecture you have. Decide on any rewrite once nothing urgent is bleeding. Don't let a doc-lock gate sit in front of live bugs.

### TIER 0 — Do before anything else (under a day, all verified against `main`)
| # | Task | Why / Effort |
|---|------|--------------|
| T0-1 | `core/llm.py` converter prompt → align to real `exit_config` contract (not `metadata`) | Generated strategies trade with NO SL/TP/trail, silently. 30 min | **DONE 2026-07-19 (commit 1cb2e7a)** — prompt now emits top-level `exit_config` with SL/TP price levels; metadata reserved for indicators. Compile + runtime-import + studio-page live-verified. |
| T0-2 | `api/credentials.py:_current_user_id()` — stop collapsing `AGENT_API_KEY` into operator identity | Shared dashboard key = full CRUD on decrypted private keys. 1-2 hrs | **DONE 2026-07-19 (commit 20fd4aa)** — `test_credential` now requires `puls_`-scoped key (403 for global key). Decrypted-secret exposure closed. list/create/delete still global-key ok (no decrypt in those paths). Live-verified. |
| T0-3 | `app/paper_routes.py` + `app/backtest_routes.py` — resolve session user, not `get_or_seed_operator(db)` | Cross-tenant leak on 2nd signup. 1-2 hrs + audit all 20 `get_or_seed_operator` sites | **DONE 2026-07-19 (commits a45d3ce, 34456ac)** — paper + backtest routes now resolve `user` from session `username` (mirrors `routes.py:180`); `Backtest.user_id == user.id` filter added. Cross-tenant leak closed. |
| T0-4 | `setattr(self,k)` → `setattr(self,k,v)` in `engine/v6_1.py:97` + `engine/v1.py` fallback | 2-char fix; crashes v6.1 on any strategy_config override. 15 min | **DONE 2026-07-19** — both engines now apply kwargs overrides without TypeError. Compile + runtime-instantiate (v6_1 active_offset=99, v1 MAN_OFFSET=42) + app-context import verified. |
| T0-5 | `config.py` — remove `"operator"` DASHBOARD_PASSWORD default, fail-fast (`_require`) on boot if `DASHBOARD_PASSWORD`/`AGENT_API_KEY`/`INSTANCE_SECRET_KEY` unset | Ships weak default creds; silent crypto key absence. 20 min | **DONE 2026-07-19** — `_require()` helper; py_compile OK; import OK with .env; RuntimeError proven when var absent. Note: live uvicorn is supervisor-managed and injects its own DASHBOARD_PASSWORD env (differs from .env), so /app/dashboard now expects supervisor creds not `operator/*** — deploy-config detail, not a code regression. |
| T0-6 | Create `data/` dir at startup (or `Dockerfile`) | Fresh deploy crashes immediately, reproduced. 10 min | **DONE 2026-07-19** — `config.py` now `os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)` at import. Verified: deleted `data/`, import recreated it + sqlite opened OK; live server respawned clean (landing 200). |

### TIER 1 — This week, still on current architecture
| # | Task | Note |
|---|------|------|
| T1-1 | Circuit breaker (`error_consecutive`, trip at 5) | P0 safety, unstarted | **DONE 2026-07-19** — `instances/runner.py` `_run_once` inner loop now counts consecutive tick exceptions; at 5 it sets `instance.status="error"`, persists, and breaks (no infinite error-loop). Verified via forced-error harness: trips exactly at 5th error. |
| T1-2 | Validate `PUT .../strategy-config` vs `get_parameters()`; restart instance on save | Silent no-op or crash otherwise | **DONE 2026-07-19** — `api/instances.py` `update_strategy_config` now validates keys against `strategy_cls.get_parameters()`, coerces types (int/float/bool), rejects unknown keys (400) + bad values (400), then `manager.restart_instance()` so live engine re-reads config. Verified coercion + rejection against real engine_v1_3 schema. |
| T1-3 | `backtests/runner.py:389` — pass `instance.strategy_config` like live runner | Backtest parity broken | **DONE 2026-07-19** — `run_backtest` now loads `Instance` by slug, reads `strategy_config`, and passes it to `strategy_cls(**strategy_config)` (mirrors live runner instances/runner.py:183). Verified config overrides apply to backtest strategy. |
| T1-4 | Login/signup rate limiting (`app/routes.py:35,60`) | Brute-force/spam surface | **DONE 2026-07-19** — both `/login` and `/signup` (public_router) now decorated `@limiter.limit(AUTH_LIMIT)` (5/min). Verified live: 7 rapid wrong-pw logins → 401×5 then 429×2; 7 rapid signups → 400×5 then 429×2. Browser login page renders clean (no console errors). Note: stale supervisor worker needed kill + fresh respawn to load new routes.py (deploy artifact, not code defect). |
| T1-5 | `WithdrawalRecord` idempotency key | Money-movement double-exec risk | **DONE 2026-07-19** — `WithdrawalRecord.idempotency_key` column added (unique, indexed); `execute_manual_50`/`execute_manual_all` now accept `idempotency_key`, return existing record's outcome if key seen before (no re-exec); API endpoints read `Idempotency-Key` header (or auto-generate). Verified: same key → 2nd call idempotent=True, exactly 1 record; unique constraint blocks race. Live `dev_test.db` ALTERed to add column. |
| T1-6 | `test_credential` — stop treating 401 as `ok:true` | Misleads users | **DONE 2026-07-19** — `api/credentials.py:190` now `r.status_code == 200` only (no 401 pass). Verified against `cd3a1a1`. (Earlier TASK-LIST marked OPEN in error.) |

**⚠️ T0-3 REGRESSION (found in VERIFICATION-STATUS-1, 2026-07-19):** the paper half of T0-3 is DONE (`app/paper_routes.py:47` resolves session user). The **backtest half is BROKEN** — `app/backtest_routes.py:59` (`testing_historical`) references `user.id` but `user` is **never assigned** in that function → `NameError` → `/app/testing/historical` 500s on every load. The cross-tenant leak is gone only because the page can't load for anyone. **Fix (T3-0, 5-min, pattern already in `paper_routes.py`):** assign `user = db.query(User).filter(User.username == username).first()` (operator fallback) before the query. Tracked as T3-0 below.

### TIER 2 — Cleanup, opportunistic
- `#32` ✅ fix "6-Engine Default Fleet" copy → "Default Fleet" (T2-1, `23ff458`)
- ✅ `instance_form.html` — add `engine_v6_1` (PRO v6.1) to dropdown (T2-2, `b37a830`)
- ✅ `instance_form.js` — removed dead preset machinery + Preset section (T2-3, `bcada4c`)
- ✅ `User.email` DB-unique + wrap `signup_post` `db.commit()` in try/except (T2-4, `e89d4f3`)
- `User.email` DEFERRED SPEC: make email REQUIRED + double-entry confirm; future email-verify sender to activate accounts (operator 2026-07-19, not built)
- Session cookie MAC → `hmac.new()` (was hand-rolled `sha256`) — ✅ DONE (T2-5, `1bfe968`, + fixed missing `import hmac` in auth.py that caused Basic Auth popup)
- `Credential` encrypt/decrypt → `json` not `str()`/`ast.literal_eval()` — ✅ DONE (T2-6, `a61b206`)
- Re-verify ⚠️ UNVERIFIED list in BUGREPORT against rewritten frontend — **T2-7 DONE 2026-07-19 (live browser + source walk, see block below)**
- 🔒 **Per-user isolation for instance list/create/delete — DONE (`c17304e`)**: `_current_user_id` no longer falls back to operator (global/missing key → 403); `GET/POST/DELETE /api/v2/instances` scoped by `user_id`; UI `create_instance` binds owner `user_id`. Live-verified: cross-user delete of engine-1 → 404, per-user list returns only own engines.
- 🔒 **ADR-008 Operator UI Auth (Option A) — DONE (`09f268a`)**: inject operator's per-user `puls_` key into dashboard templates (19 render sites) via `get_dashboard_api_key()`; global `AGENT_API_KEY` now 403 on tenant routes. Fresh-DB verified: operator `puls_` → `/api/v2/credentials` 200; global → 403.

### TIER 3 — Frontend / chart bugs / wiring (from UI-TODO-1 + VERIFICATION-STATUS-1, 2026-07-19)
| # | Task | Why / Effort | Status |
|---|------|--------------|--------|
| T3-0 | `app/backtest_routes.py:59` — assign `user` before `user.id` query (T0-3 backtest regression) | `/app/testing/historical` 500s (NameError) on every load. 5-min fix, pattern in `paper_routes.py:47`. | **DONE 2026-07-19 (commit 98ca408)** — `user = db.query(User).filter(User.username == username).first()` with operator fallback; `Backtest.user_id == user.id` query resolved. File compiles, no NameError. |
| T3-1 | `app/static/pulsr-chart.js` `createEquityBarChart` — run `equityData`+`trades` through `normalizeSeries()`, wrap `setData()` in try/catch | Trade PnL histogram (Paper + Backtesting) throws + never renders. Confirmed root cause (UI-TODO-1). | **DONE 2026-07-19 (commit 643174d)** — equity+trades through normalizeSeries(), try/catch. Live-verified (paper page renders, no throw). |
| T3-2 | `app/static/position-card.js:88` — `isShortPos` is a function ref, not a call → `sideClass` never `'flat'`; delete duplicate `isShort`/`isShortPos` | Silent display bug; flat/short misclassify; flat close-check unreachable. Likely also closes BUG-9-A. | **DONE 2026-07-19 (commit 6a117e7)** — declared `const isShortPos`; removed duplicate `function isShortPos` that collided in IIFE (would SyntaxError). Closes BUG-9-A. |
| T3-3 | `pulsr-chart.js` — `bumpTheme()` is a no-op: no `refresh(handle)` exists; theme toggle doesn't reapply to rendered charts | Pulse Graph + all charts ignore dark/light toggle until reload. | **DONE 2026-07-19 (commit 643174d)** — added `_charts` registry (push on create, splice on destroy); `bumpTheme()` re-applies `getTheme()` via `chart.applyOptions()`. Theme toggle re-themes charts live. |
| T3-4 | `position-card.js` `initSSEPositionListener()` opens a 2nd `EventSource('/stream')` per page (dup of page-level console SSE) | Wasted server conns + duplicate handlers (loaded on 5 pages). Consolidate to one shared connection. | **DONE 2026-07-19 (commit e55e3cd)** — position-card.js now consumes `window.__appSSE` (set by page-level SSE in dashboard + engine_detail); 0 private sockets; degrades to 3s poll. Backend SSE verified healthy (ping frames). |
| T3-5 | Build the Port-1 Strategy Parameters UI (closes VERIFICATION #17) | Backend `GET /strategies/{id}/parameters` + `PUT /instances/{id}/strategy-config` are validated/safe but have ZERO frontend entry points. Operator cannot set any per-instance param through the app. Pure frontend task. | **DONE 2026-07-19 (commit dd13e94)** — Strategy Parameters card in engine_detail Settings modal: GET schema, render typed inputs (select/float/int/bool) via renderDynamicFields, PUT with per-field coercion + engine hot-restart. Reuses page API_KEY + showToast. Fixed schema key mismatch (param.options→param.choices). |
| T3-6 | Delete orphaned 2nd `withdrawals_page` in `app/routes.py:~1791` (no `@router.get`, shadows the real one) | Dead code (VERIFICATION #18); prevents future confusion when re-enabling withdrawals. | **DONE 2026-07-19 (commit e2f3d1e)** — removed orphaned 2nd withdrawals_page() (lines ~1835-1843). 1 withdrawals_page def remains; live /app/withdrawals 200 + notice. |
| T3-0 | **Cross-user data leak (ULTIMATE ISOLATION) — FULLY RESOLVED 2026-07-19.** Root cause was multi-layered: (1) `get_dashboard_api_key()` cached operator key globally; (2) `landing.html` Basic-Auth shortcut cached operator creds in browser; (3) THE DEEP ONE: every data route called `get_or_seed_operator(db)` and ignored the authenticated `username`, so all users saw OPERATOR's instances/trades/live HL value. ALSO `seed_default_fleet` gave operator 6 engines; new users got nothing. | **FIXED + pushed (final commit this session).** Added `get_user_or_seed_user(db, username)` — resolves the SESSION user, only returns operator when username IS operator. Replaced all 17 data/chat call sites; chat history now per-user. `/app/account` live HL value gated to operator OR user's own `Credential` (non-operator with no HL key shows $0 / "connect" — never operator's live $). Added `seed_user_fleet(user)` — every new signup gets EXACTLY ONE engine "Engine HYPE v1" (HYPE token, engine_v1, 30m, paper, user-owned, empty HL/account addr). Dashboard dropdown lists engine NAMES cleanly (no Side/FLAT prefix). Onboarding popup + email 2FA pending (see T3-8/T3-9). | DONE |
| T3-8 | New-user ONBOARDING popup: HL DEX wallet + API key + ETH wallet address entry (stores in `Credential`, user-scoped) | Out-of-band 2026-07-19. New users seed with empty HL/account — must connect their own exchange via a first-login modal. | OPEN |
| T3-9 | Email 2FA: app sends confirmation link on signup; user must click to verify `email_verified` | Out-of-band 2026-07-19. Add `email_verified` flag + `/verify-email?token=` route + SMTP send (print link if no SMTP configured). | OPEN |
| T3-7 | `engine_detail.html` Settings modal — add `confirm()` before saving `Dry Run → Live` (T2-7 item 6) | One misclick puts an engine LIVE with real funds, no warning. Backend T1-2 restarts on save. | **DONE 2026-07-19 (commit 6a91946)** — `saveSettings()` now `window.confirm()` before switching Dry Run (Paper) → Live; aborts save if cancelled. |
| T3-6b | **Launch-hardening redefinition (senior brief 2026-07-19):** Open Positions live hydration + concurrency-guarded 3s polling | Pre-beta soak prep. | **DONE 2026-07-19 (commit 9fa8e6c)** — position-card.js `hydratePositions()` fetches `/api/v2/positions` on mount + SSE push (merges live szi/entryPx into POSITIONS_DATA); `window.API_KEY` exposed on dashboard+engine_detail. Dashboard `refresh()` gets `dashboardRefreshLock` (freed in finally{}) wrapping the 3s `setInterval` poll. Verified: dashboard renders 1/9 running, no new JS exceptions. |

### TIER 4 — Pulse Graph (T4-1 … T4-5, from senior briefs 2026-07-19)
| # | Task | Why / Effort | Status |
|---|------|--------------|--------|
| T4-1 | Dashboard Pulse Graph — layout + viewport lock (dimension-locked container) | Flatline / overflow fixed earlier; T4-4 rolling buffer. | DONE (pre-session) |
| T4-2 | Stream Logs console — route to native CONSOLE card w/ brand tokens | T4-2.x cosmetic + parse-error fix. | DONE (pre-session, `e369b05`) |
| T4-3 | Stream Metrics — wire `metrics` frame payload to topbar + sidebar KPIs | 1s telemetry → KPI nodes. | DONE (pre-session, `2fb3ea1`) |
| T4-4 | Dynamic rolling buffer + reactive SVG repaint loop | T4-4 (commit `15cb2b7`) — `buildPulse()` reads global `equityData` (no arg); 60-tick buffer; mirror to mobile SVG. | DONE 2026-07-19 (commit 15cb2b7) |
| T4-5 | **Pulse Graph — REVERTED to original `ai-trading-agent-hl` style.** Step 1+2 (zero-centered, dashed centerline, commits `b02aed8`/`9d3e9b1`) were SUPERSEDED per operator directive 2026-07-19 after inspecting the original repo's `dashboard/static/app.js` `renderPortfolioChart()`. Original used **absolute min/max scaling** (line fills full box height — no flatline issue) + **area fill closes to the BOTTOM edge** (shadow points DOWN only, never split by a centerline) + **no centerline** (card background only) + single trend color (green profit / red loss) with vertical fade-down gradient + glow. Strategy-engine's pre-T4-5 T4-4 code (`15cb2b7`) already matched this; T4-5's zero-centered change was a misdiagnosis of the "flatline" warning. | Match the original HL agent dashboard pulse rendering; "our colors" = MASTER palette profit `#34D399` / loss `#FB7185`. | **DONE 2026-07-19 (commit 27fbf67 + f8c5042)** — `buildPulse()` reverted: `y = H-PAD - ((val-min)/span)*(H-2*PAD)` (absolute min/max); area closes to `H-PAD` (downward shadow only); `#pulse-baseline` centerline removed; gradient → `var(--color-profit,#34D399)` / `var(--color-loss,#FB7185)`. **Dot fix (f8c5042):** pulse dot now at END of line (right edge = last data point = current tick), `cx/cy` = last point coords (always ON the line, never floating), `r=5` (larger; both desktop `#pulse-dot` + mobile `#pulse-dot-m`). Matches original `renderPortfolioChart()` end-point circle. **BROWSER-VERIFIED**: desktop dot `cx=992.0 cy=192.0` == path end `992.0,192.0`, `r=5`, class `pulse-path negative` (red, ▼0.45%). Live 200. Pushed `0b091e9 → f8c5042`. |
| T4-6 | **Live SSE → Pulse Graph wiring (the "last mile").** Senior ticket: connect `/stream` to the graph + decouple the `/summary` poll. **RECONCILIATION FINDING:** the SSE→graph wiring ALREADY existed (T4-4, `dashboard.html` ~L746 inside the existing `window.__appSSE` `metrics` handler — pushes `{value: portfolio_value}` into `equityData`, 60-tick ring, calls `buildPulse()`). The senior's Step 1 drop-in (a *second* `new EventSource('/stream')` + `equityData.push(bareNumber)`) would have been a duplicate broken socket (bare number → `.value` undefined → flatline). Senior agreed; drop-in discarded. | Confirm SSE hydrates graph live; stop `/summary` poll from wiping the live buffer. | **DONE 2026-07-19 (commit 28c3c0b)** — **Step 1 VERIFIED** (browser DevTools): `window.__appSSE` `readyState=1` (OPEN); `equityData.length` 7→24 over ~4s (≈1 tick/s, matches 1s metrics frame); `pulse-path` `d` length 230→855 (graph redraws live). **Step 2 (decouple):** replaced the `/summary` poll's `equityData.length = 0` + full re-push (cannibalized SSE buffer every 3s) with a **seed-only guard** — poll pushes `d.equity_series` into `equityData` ONLY when `equityData.length === 0` (first load / SSE-down fallback); SSE now exclusively owns live rendering. Verified served HTML no longer contains the wipe; live 200. Pushed `b4a3bd4 → 28c3c0b`. |
| T4-7 | **Pulse card cleanup — fix KPI PnL + remove time-range buttons.** Operator: (1) KPI "PNL" (`kpi-realized`) + ticker `ticker-pnl` frozen at `$0.00` while equity moved (wrong source — wired to `realized_pnl`/`daily_pnl`); PnL must derive from **User start_balance** (operator setting, e.g. $5). (2) Remove 1H/2H/6H/12H/24H buttons, auto last window. (3) No "last 24h" note (confirmed none exists; keep simple). **Pulse graph itself UNCHANGED** (operator: "leave the pulse do what it does"). | KPI PnL = equity − start_balance; pulse rendering untouched. | **DONE 2026-07-19 (commits 95e39fa → 4df6510)** — **Buttons:** removed `.pulse-range` chips (desktop 5-btn + mobile 3-btn) + `setPulseRange()`; `pulseRangeHours` fixed to `1`. **PnL fix:** added `START_BALANCE` JS global from `User.start_balance` (route passes it); KPI+ticker now `equity − START_BALANCE` inside `buildPulse()` (single source of truth — removed old `realized_pnl`/`daily_pnl` writes from `/summary` handler + SSE `daily_pnl` block). **Pulse badge REVERTED to window-delta** (`lastV − first`, % vs window-first) per operator directive. **VERIFIED:** `START_BALANCE=5`, live equity $6.08 → KPI PnL `$1.08`, ticker `$1.08`; pulse badge `▼ 0.43%` (window delta, unchanged). Live 200. |
| T3-7b | **Launch-hardening redefinition (senior brief 2026-07-19):** concurrency-guarded 3s polling on dashboard | Same as T3-6b step 2. | **DONE 2026-07-19 (commit 9fa8e6c)** — see T3-6b. |
| T1-7 | Withdraw/deposit routes disabled (BUG-11 broken SDK `.withdraw()`; BUG-12 no deposit path) | Good judgment call: commented-out write routes, `/app/withdrawals` shows "feature deferred". **DEFERRED — live funds, needs explicit operator go.** | DEFERRED |

### Phase -1 Rewrite — guidance (NOT blocking, do after Tier 0+1)
1. **Docs-in-parallel, not docs-as-gate.** Ship Tier 1/2 fixes on a maintenance branch while writing `VOCABULARY.md`/`ARCHITECTURE.md`/`DECISIONS.md`. No multi-day code freeze on a live-order system.
2. **Don't lock the domain model before using it.** Treat v1 of those docs as a strong draft, not permanent contract — system still growing new concepts (3-port config, multi-tenant User/Credential).
3. **Restructure via `git mv`/`git filter-repo`, NOT fresh dir + `git init`.** The `main/`-as-new-root move already lost history for 3 safety-fix batches. A `contracts/`/`domain/`/`runtime/` reorganization done the same way loses it at scale.

---

## A. Open Positions UI
- **A1.** Dashboard `#pos-grid` empty — no JS population. Full card needed (token, side spine, size, entry/mark, PnL, lev, duration, close, view-on-exchange, close-all, empty state). → Z5
- **A2.** Real-time position updates via SSE — `renderPositions()` not wired; `/stream` emits `trade` only.
- **A3.** Engine Detail enhanced position card — live mark/PnL, liq, SL/TP, close, FLAT empty.
- **A4.** API summary missing `liquidation_price`/`entry_cost`/`pnl_pct`/`duration`/SL/TP — running liq shows 0.0.
- **A5.** Dashboard KPI "Open Positions" count — verify per poll.
- **A6.** SSE `position` event type — emit on `_sync_position`.
- **A7.** Trades page "Active Positions" section above table.
- **A8.** Mobile position cards responsive (≤768px, 44px targets).

## B. Known Bugs (Audit)
- **B1.** ✅ Stale HL client — FIXED (`f66dffe`)
- **B2.** ✅ Password hash on fresh DB — FIXED
- **B3.** [MED] Per-user log persistence — LOG_BUFFER in-memory only → `data/logs/{user}.jsonl`
- **B4.** [MED] Active Trades card — overlaps A1
- **B5.** [LOW] 50 nullable cols should be NOT NULL
- **B6.** [LOW] No cascade deletes
- **B7.** ✅ Kill switch closes positions — FIXED 2026-07-18
- **B8.** ✅ Encrypted API key storage — FIXED (`60f039a`)
- **B9.** [MED] Drawdown 97.73% spike — filter >50% swing in `_record_account`

## X. bugreport.txt Items (2026-07-18)
- **X1.** ✅ Duplicate-entry sanitization — FIXED · **X2.** ✅ Entry-without-pin-bar guard — FIXED · **X3.** ✅ Backtester/paper start-balance+timeframe — FIXED · **X4.** ✅ ExecutionCostModel — FIXED

## Z. Separation / DDD (Beta-Blocker Z1–Z7)
- **Z1.** Blueprint split routes.py → live/paper/backtest + `_common.py` — OPEN (beta-blocker)
- **Z2.** Menu restructure (drop Testing collapsible, top-level Paper + Backtesting, Trades=LIVE) — OPEN
- **Z3.** ✅ Instances dynamic LIVE/PAPER schema — DONE (live-verified)
- **Z4.** ✅ Design-system theme-glow + components + position-card-spec — DONE
- **Z5.** ✅ Position card JS + `#pos-grid` wired — DONE code / ⚠️ VISUAL UNVERIFIED
- **Z6.** ✅ Backtest isolated store — DONE
- **Z7.** ✅ Unified testing runner — DONE (real 7d backtest ran)

## D. Infrastructure / Backend
- **D1.** ✅ Version string drift — FIXED · **D2.** ✅ Restart resilience — FIXED · **D3.** ✅ Equity history live — FIXED
- **D4.** [OPEN] PAPER/LIVE badge per trade row + engine header
- **D5.** [OPEN] Per-instance dry_run toggle end-to-end verify
- **D6.** [OPEN] Position reconciliation on restart (improved by f66dffe, verify)

## E. BUGREPORT Severity Items (mapped to tiers above)
- **P0/Tier0:** E1=T0-1 converter prompt · E2=T0-2 creds access · E3=T0-3 cross-tenant · E4=T0-4 setattr · E5=T0-5 cred fail-fast · E6=T0-6 data/ dir · E7=T1-1 circuit breaker
- **P1/Tier1:** E8=T1-2 strategy-config validation · E9=T1-3 backtest parity · E10(UI Port1)=T3-5 · E11=T1-4 rate limit · E12=#32 copy · E13=T1-5 withdrawal idempotency · E14=#64/#65 form gaps · E15=T1-6 test_credential 401 **(DONE 2026-07-19 — `api/credentials.py:190` ==200 only)**
- **P2/Tier2:** E16=#12 rate limit(login) · E17=#13/#14 email+signup exc · E18=#15/#16 hmac+json
- **⚠️ UNVERIFIED:** XSS on innerHTML · fleet alerts badge · fleet Evaluate Alerts · Testing Pool UI · rotation clarity · Dry→LIVE confirm · API-key banner · loading/error/empty · mobile responsive · landing.html fetch race · spec.html dead weight

## BUGHUNT — Live Frontend (pre-beta, must actually use UI)
- **BUG-1.** Visual verify `#pos-grid` (Z5) · **BUG-2.** engine_detail LIVE/PAPER tag (Z3) · **BUG-3.** backtest form→results (X3/Z7) · **BUG-4.** paper forward-test (Z1/Z2) · **BUG-5.** menu integrity (Z2) · **BUG-6.** PAPER/LIVE badge (D4) · **BUG-7.** [DONE 2026-07-19 (commit 4fe89df)] `/app/trades` Active Positions section added above trades table (live non-FLAT positions); verified live 200, section renders. · **BUG-8.** [DONE 2026-07-19 (commit c88c669, P0)] `start_instance` enforces kill switch at API boundary — global kill or instance `status=='killed'` → HTTP 409. Live-verified all 3 paths (global-active 409, reset 200, instance-killed 409). · **BUG-9.** [CLOSED by T3-2 — commit 6a117e7] console error sweep: `isShortPos` reference bug fixed; 2 pre-existing anonymous SSE/stream-edge exceptions remain (tracked separately, next pass). · **BUG-10.** [DONE 2026-07-19 — e2e browser-verified] Signup form: submitted fresh user → redirect to `/app/dashboard` authenticated, fleet seeded (Engine HYPE v1), session cookie issued. No code change needed (route was correct); validation + dup-user paths confirmed in source.
- **BUG-11 + BUG-12 — WITHDRAWAL/DEPOSIT ROUND-TRIP FEATURE [DEFERRED, full scope below].** Withdrawal is BROKEN; deposit has NO code path. Deferred per operator 2026-07-19. Detailed scope:

  **BUG-11 (withdrawal broken — confirmed live 2026-07-19):**
  - Symptom: `HyperLiquidClient.withdraw_to_wallet(amount, destination)` → `AttributeError: 'Exchange' object has no attribute 'withdraw'`. No funds moved. Live test: balance 7.12 USDC, attempted 1 USDC → failed.
  - Root cause: `core/exchange.py:429` calls `self._exchange.withdraw(target, amount)` — method does not exist in `hyperliquid` SDK.
  - Correct SDK call: `self._exchange.withdraw_from_bridge(amount, destination)` — signature `(amount: float, destination: str)`, action type `withdraw3` (bridge USDC HL unified account → L1 EVM). Client already uses `MAINNET_API_URL` (exchange.py:91) so network is correct. Arg ORDER differs from broken code (`amount, destination` not `target, amount`).
  - Already-correct: client built mainnet+real account (88-91); `_query_address()` returns `ACCOUNT_ADDRESS` = MetaMask `0xA871D51A9D3Cf670c41FB53CDEe3822c51FD8078`; T1-5 idempotency guard in place; `withdraw3` is USDC-only (no token param).
  - Minimal fix: line 429 → `self._exchange.withdraw_from_bridge(amount, target)`. Recommended add: validate destination is valid 0x + amount ≤ withdrawable before sending (current code has "advisory check" comment but no actual check).
  - Risk: `withdraw3` is REAL on-chain L1 withdrawal (mainnet, real USDC, HL bridge fee ~$0-1, L1 arrival ~15-20 min). Irreversible by code.
  - Verification when un-deferred: dry-run (`DRY_RUN=true`) first → no AttributeError; then live 1 USDC to `0xA871...8078`; poll `get_account_value()` + MetaMask; re-run same idempotency key → existing record, no double-send.

  **BUG-12 (deposit — NO code path exists):**
  - Finding: no `deposit` / `deposit_to_hl` / `transfer_to_exchange` function or route anywhere in `api/`, `instances/`, `withdrawal/`, `core/`. grep for "deposit" found only config/calc references, no execution path.
  - HL reality: depositing USDC from an EVM wallet (MetaMask) INTO the HL unified account is done via the HL `usd_class_transfer` / `usd_transfer` SDK or the HL UI — it is a separate action from withdrawal (withdrawal = HL→L1; deposit = L1→HL). The SDK `Exchange` exposes `usd_transfer` / `usd_class_transfer` for internal/bridge transfers but a true L1→HL deposit (MetaMask → HL) requires the deposit action (`deposit` / `deposit3` type) which must be confirmed against SDK version.
  - For the round-trip to work, deposit needs: (a) a `deposit_to_hl(amount, source_address)` method in `core/exchange.py` using the correct SDK deposit action; (b) an API route `POST /api/v2/deposit` (or similar) wired like the withdrawal endpoints; (c) idempotency key (mirror T1-5); (d) optional destination = HL account address (`ACCOUNT_ADDRESS`).
  - Note: a "deposit 5 USDC" test means moving USDC from MetaMask back to the HL account — requires the deposit SDK action + the wallet to have USDC + gas.

  **Deferred scope summary (do as one feature, not two):** Build `withdraw_to_wallet` fix (BUG-11) + `deposit_to_hl` method + matching API routes + idempotency on both + balance/address guards. Then live round-trip test: withdraw 1 USDC → confirm MetaMask → deposit 5 USDC → confirm HL. Reuse T1-5 idempotency pattern.
  **Status: DEFERRED. Do NOT implement until operator re-opens. Live funds involved — explicit go required.**

  **UI direction (operator note 2026-07-19, also deferred):** Current `/app/withdrawals` renders HTML but **no CSS** (bare unstyled markup, not inheriting the account layout). When this feature is built: (1) nest withdrawal/deposit under `/app/account/` (route + template inherits account layout with CSS); (2) add a **"Balance"** card on the Account Overview; (3) create a `/app/account/balance` (or `/balance`) page that displays Deposit + Withdraw functions properly. Not a code task now — recorded for the future feature build.

## UI WALKTHROUGH QUEUE (HANDOVER, recon-only)
Server PID 29567 :8792, login `operator`/`operator`, base `http://127.0.0.1:8792`.
Per page: HTTP status, render, JS console, data population, auth, mobile, screenshot. Verify BACKLOG #41-#66. Deliverable: `docs/UI-WALKTHROUGH-FINDINGS.md`.
21 pages: `/` · `/app/dashboard` · `/app/engines` · `/app/engines/{slug}` · `/app/strategies` · `/app/strategies/{id}` · `/app/strategies/studio` · `/app/testing/paper` · `/app/testing/historical` · `/app/trades` · `/app/account` · `/app/assistant` · `/app/withdrawals` · `/app/settings` · `/app/kill/status` · `/shell` (expect gone) · `/logs` · `/stream` · `sw.js` · `manifest.json` · `spec.html` (expect dead).
Discipline: one page/turn, screenshot+console, no code fixes unless trivial. Findings → `docs/UI-WALKTHROUGH-FINDINGS.md`.

## Execution Notes
- engine-1 RUNNING LIVE (FARTCOIN LONG ~390, liq via A4, auto-resumed). Main app UP :8792 v1.98. Worker :9999 DOWN.
- ADIX: one file/turn, verify before next. Zero autonomous deletion.
- Stability: NOT STABLE / NOT BETA until BUGHUNT closed + tests green + Tier 0 closed.

---

## T2-7 — UNVERIFIED Re-Verification Results (2026-07-19, live browser + source walk)

**Method:** server live at :8792 (auth via session cookie from `/login` form — Basic `operator:operator` is now correctly 403'd by T0-2/T2-6; supervisor-managed worker is a *stale-good* import, see caveat). Walked `/`, `/app/dashboard`, `/app/engines`, `/app/engines/{slug}`, `/app/trades`, `/app/testing/paper`, `/app/testing/historical` in-browser + read `app/templates/*.html`, `app/static/*.js` source. Console sweep run on dashboard.

**⚠️ Disk-vs-runtime caveat (important):** the live worker is running a *stale* Python import. `app/backtest_routes.py` on **disk** has the T3-0 `NameError` (undefined `user`), but the **live** `/app/testing/historical` returns 200 because the supervisor worker was started before that code existed / hasn't re-imported. Consequence: **frontend/JS/HTML changes are served live immediately; Python-route changes will NOT reflect until a supervised restart** — which is intentionally NOT done here because **engine-1 is trading LIVE with real funds**. T2-7 items assessed against disk (source of truth) + live where safe.

| # | UNVERIFIED item | Verdict | Evidence |
|---|---|---|---|
| 1 | XSS-escaping on user-editable `innerHTML` | **SAFE** | `chat_widget.js:renderMsg` uses `d.textContent = text` (no innerHTML) for all operator/user chat content. `position-card.js` / `pulsr-chart.js` innerHTML only ever interpolate app-controlled data (side/size/token from API), not free user text. No exploitable innerHTML sink found. |
| 2 | Fleet-wide alerts visibility / badge | **NOT PRESENT** | Zero `alert`/`badge` refs in any template or route. The "Monitoring & Alerts" feature described in `landing.html` copy has **no route or template** in current frontend (`#/monitoring` in spec.html is dead). Gap never built, not broken-by-rewrite. |
| 3 | Fleet "Evaluate Alerts" vs per-instance | **NOT PRESENT** | No `evaluate_alert`/`evaluateAlert` route or UI exists. Same as #2. |
| 4 | Testing Pool UI presence | **NOT PRESENT** | Nav has Paper Trading + Backtesting only. No `/app/testing/pool` route or template (`testing_*.html` set = index/paper/historical). Gap not closed. |
| 5 | Rotation approve/apply UI clarity | **NOT PRESENT** | Zero `rotation`/`rotate` refs in templates; no `/monitoring` or rotation route. Not built. |
| 6 | Confirmation step for Dry Run → LIVE toggle | **OPEN — no confirm** | `engine_detail.html` Settings modal has `Dry Run (Paper)` select (Paper/Live) but `saveSettings()` PUTs with **no `confirm()` gate** before switching to Live. A misclick goes Live with no warning. (Backend T1-2 restart-on-save applies.) → track as **T3-7** (add confirm modal). |
| 7 | API-key-not-configured banner | **NOT PRESENT (acceptable)** | No banner in any template; `api_key` is server-injected into every dashboard page (`window.API_KEY`), so the "not configured" state is currently unreachable in normal flow. Low priority; flag only if key can be absent. |
| 8 | Loading/error/empty state consistency | **OK (spot-checked)** | Dashboard Open Positions → "No open positions" empty state renders. Paper → "No equity data yet" / "Loading token price data". Backtesting → "No backtests yet. Run one above." Trades → KPI + filter bar + empty table. Consistent empty/loading states present across checked tabs. |
| 9 | Mobile responsive layout | **SCAFFOLDED, unverified visually** | `@media (max-width: 768px)` present in `engine_detail.html` modal + `layout.html` + `position-card.js` (3-col→1-col). Structurally present; full device-emulation pass not done this turn. |
| 10 | `landing.html` login fetch-before-navigate race | **RESOLVED** | Old `doLogin()` fired `location.href` synchronously. Current `doLogin()` (lines 393-420) `fetch('/login')` then sets `window.location.href='/app/dashboard'` *inside* `.then()` after response resolves. Race gone. Live login form works (tested). |
| 11 | `spec.html` dead weight | **GONE (live 404)** | `/spec.html` returns 404 on live server; template still on disk (`app/templates/spec.html`) but unrouted — harmless dead weight. Verified removed from nav. |

**Live console finding (cross-refs BUG-9-A / T3-2):** dashboard load threw **1 anonymous JS exception** (`browser_console` → `js_errors: [{message:"", source:"exception"}]`). Empty-message anonymous throw is consistent with the `position-card.js:88` `isShortPos` function-reference bug (UI-TODO-1 / T3-2) or an SSE parse edge. Not yet pinned to a line — fixing T3-2 is the likely cure; add `window.onerror` capture if it persists.

**Net:** of the 11, 1 RESOLVED (10), 1 SAFE (1), 1 GONE (11), 1 OK spot-check (8), 1 scaffolded-unverified (9), 1 acceptable-absence (7), **4 confirmed NOT PRESENT** (2,3,4,5 — features never built, not regressions), and **1 OPEN needing a fix** (6 → T3-7 Dry→LIVE confirm).
