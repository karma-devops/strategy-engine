# PULS·R Task List — Consolidated Work Inventory (single source of truth)

**Consolidated:** 2026-07-19 (Asia/Makassar) · **Status:** ⚠️ NOT STABLE / NOT BETA
**Live State:** engine-1 RUNNING LIVE (FARTCOIN LONG, liq enriched via A4) · engine-2 STOPPED (paper) · main app UP port 8792
**Server:** supervisor-managed uvicorn on port 8792 (PID rotates per restart — currently ~65393), login `operator`/`operator`, DB `main/data/dev_test.db` (injected by supervisor; config default path also `data/strategy_engine.db`)
**Sources merged:** TASK-LIST v1.98 + BUGREPORT.md (karma-devops) + HANDOVER-UI-WALKTHROUGH.md + TASK-PRIORITIES.md (3-tier companion)

**4-FILE DOC TAXONOMY:** CONTEXT.md (MAP) · NOTES.md (LOG) · TASK-LIST.md (WORK) · BETA-ROADMAP.md (FORWARD)
**Companion evidence files (do NOT edit, read-only):** `docs/bugreport.md` (verbatim BUGREPORT) · `docs/task-priorities.md` (3-tier companion) · `docs/HANDOVER-UI-WALKTHROUGH.md`

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
| T1-3 | `backtests/runner.py:389` — pass `instance.strategy_config` like live runner | Backtest parity broken |
| T1-4 | Login/signup rate limiting (`app/routes.py:35,60`) | Brute-force/spam surface |
| T1-5 | `WithdrawalRecord` idempotency key | Money-movement double-exec risk |
| T1-6 | `test_credential` — stop treating 401 as `ok:true` | Misleads users |

### TIER 2 — Cleanup, opportunistic
- `#32` fix "6-Engine Default Fleet" copy (decision locked: 1 engine, fix label)
- `instance_form.html` — add `engine_v6_1` to dropdown
- `instance_form.js` — wire or remove unused per-strategy presets endpoint
- `User.email` DB-unique + wrap `signup_post` `db.commit()` in try/except
- Session cookie MAC → `hmac.new()` (was hand-rolled `sha256`)
- `Credential` encrypt/decrypt → `json` not `str()`/`ast.literal_eval()`
- Re-verify ⚠️ UNVERIFIED list in BUGREPORT against rewritten frontend

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
- **P1/Tier1:** E8=T1-2 strategy-config validation · E9=T1-3 backtest parity · E10(UI Port1)=Tier2 · E11=T1-4 rate limit · E12=#32 copy · E13=T1-5 withdrawal idempotency · E14=#64/#65 form gaps · E15=T1-6 test_credential 401
- **P2/Tier2:** E16=#12 rate limit(login) · E17=#13/#14 email+signup exc · E18=#15/#16 hmac+json
- **⚠️ UNVERIFIED:** XSS on innerHTML · fleet alerts badge · fleet Evaluate Alerts · Testing Pool UI · rotation clarity · Dry→LIVE confirm · API-key banner · loading/error/empty · mobile responsive · landing.html fetch race · spec.html dead weight

## BUGHUNT — Live Frontend (pre-beta, must actually use UI)
- **BUG-1.** Visual verify `#pos-grid` (Z5) · **BUG-2.** engine_detail LIVE/PAPER tag (Z3) · **BUG-3.** backtest form→results (X3/Z7) · **BUG-4.** paper forward-test (Z1/Z2) · **BUG-5.** menu integrity (Z2) · **BUG-6.** PAPER/LIVE badge (D4) · **BUG-7.** dry-run toggle (D5) · **BUG-8.** `pytest tests/` pass/fail · **BUG-9.** console error sweep · **BUG-10.** [OPEN] Signup form end-to-end verify — `/signup` (`app/routes.py:60`) creates user + hashes password but never browser-tested. Verify: success→`/app/dashboard`, session cookie issued, login with new creds works, dup-user/email handled, pw<6 rejected. Note: `/login` form was broken until operator `password_hash` seeded 2026-07-19 (`get_or_seed_operator` now sets `hash_password("operator")`); signup path itself still unverified — test after Tier 0.

## UI WALKTHROUGH QUEUE (HANDOVER, recon-only)
Server PID 29567 :8792, login `operator`/`operator`, base `http://127.0.0.1:8792`.
Per page: HTTP status, render, JS console, data population, auth, mobile, screenshot. Verify BACKLOG #41-#66. Deliverable: `docs/UI-WALKTHROUGH-FINDINGS.md`.
21 pages: `/` · `/app/dashboard` · `/app/engines` · `/app/engines/{slug}` · `/app/strategies` · `/app/strategies/{id}` · `/app/strategies/studio` · `/app/testing/paper` · `/app/testing/historical` · `/app/trades` · `/app/account` · `/app/assistant` · `/app/withdrawals` · `/app/settings` · `/app/kill/status` · `/shell` (expect gone) · `/logs` · `/stream` · `sw.js` · `manifest.json` · `spec.html` (expect dead).
Discipline: one page/turn, screenshot+console, no code fixes unless trivial. Findings → `docs/UI-WALKTHROUGH-FINDINGS.md`.

## Execution Notes
- engine-1 RUNNING LIVE (FARTCOIN LONG ~390, liq via A4, auto-resumed). Main app UP :8792 v1.98. Worker :9999 DOWN.
- ADIX: one file/turn, verify before next. Zero autonomous deletion.
- Stability: NOT STABLE / NOT BETA until BUGHUNT closed + tests green + Tier 0 closed.
