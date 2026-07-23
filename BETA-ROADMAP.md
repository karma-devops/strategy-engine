# BETA-ROADMAP.md — strategy-engine (PULS·R) Beta Readiness Plan

> **THE PLAN.** Forward action items for a beta version bump (target: v2.0-beta or v2.1-beta).
> Pairs with: CONTEXT.md (MAP), NOTES.md (LOG), TASK-LIST.md (WORK).
> Status 2026-07-23: Z1–Z7 + X1–X4 + A4 + B7 + D1 + D2 code-complete + live-verified. 2026-07-22/23 added entry-gate UNIVERSAL repair, BUG-A/B, TDZ fix, version sync to v2.02, PR#1 merge, trailing-stop PineScript parity, paper-route 404 fix, backtest-import 500 fix, perp-account-value UI, test-drift fixes. **NOT STABLE / NOT BETA** — systematic bughunt + full `tests/` run still pending (next phase).
> Live state: engine-1 LIVE (FARTCOIN, liq enriched via A4, auto-resumed via D2), engine-2 stopped (paper), worker 9999 down (standalone). Version **v2.02**.

---

## 0. Beta Gate (definition of "beta-ready")

Beta = operator can invite external testers to trade paper + view live, with no **live-safety gaps** and **no 500-errors on any UI route**.

**Hard gates (all must pass):**
1. All tests in `tests/` green (`phase1_hard_test`, `phase2_killswitch_test`, `phase5_auth_test`, `idempotency_runner_test`, `monitoring_api_test`).
2. PAPER/LIVE separation verified end-to-end (engine-2 paper → NEUTRAL; engine-1 live → records `dry_run=false` trades).
3. Kill switch closes open positions before stopping (B7).
4. Server survives restart (D2 — systemd/supervisor).
5. Every UI route returns 200 (the deferred `routes.py` `_safe_tojson` fix deployed — D0).
6. `main.py` version string corrected to v2.02 (`metadata.py` reads VERSION file — `041d83e`/`529a3b2`).
7. **Live frontend practical test passes** — operator/tester actually uses the UI in browser: Dashboard `#pos-grid` renders live position card (HL spine), engine_detail shows correct LIVE/PAPER tag, Backtest form submits + renders results, Paper flow runs dry-run, no 404s in menu. (TASK-LIST §BUGHUNT BUG-1→BUG-5)
8. **Visual verification complete** — position-card.js output matches `design-system/position-card-spec.md` via browser screenshot; console error sweep clean on all authenticated pages (BUG-1, BUG-2, BUG-9).

> **Operator directive (2026-07-18):** "It's not stable yet! We need to actually front end practical testing live with it before we can assume that." → Gates 7-8 are HARD blockers. Code-complete ≠ stable. No beta bump until BUGHUNT group closed.

---

## 1. Verification Group (V — gate blockers)

| ID | Action | Verify | Blocker |
|----|--------|--------|---------|
| V1 | Run full `tests/` suite | `pytest tests/ -q` exit 0 | YES |
| V2 | Paper/live separation live test | engine-2 (dry_run=true) generates NEUTRAL; engine-1 trade row has `dry_run=false` | YES |
| V3 | Per-instance dry_run toggle E2E | UI toggle → API PUT → runner respects on next tick | YES |
| V4 | Hard-test deferred `routes.py` fix on test instance | `/app/engines/{slug}` returns 200 with `paper_trades` | YES (precedes D0) |

---

## 2. Hardening Group (H — live-safety, must close for beta)

| ID | Severity | Item | Plan | Verify |
|----|----------|------|------|--------|
| H1 | MED | B7 kill switch closes positions | DONE 2026-07-18 (`stop_instance` + `killswitch.py` call `market_close()` before halt; kill-switch closes all). Live-verified (FARTCOIN flattened on HL). | N/A — closed |
| H2 | MED | B9 drawdown spike filter | Confirm >50% swing filter holds on running engine-1 (no fake 97% DD) | AccountSnapshot max swing < 50% over 24h |
| H3 | MED | B3 per-user log persistence | Write `data/logs/{user_id}.jsonl`, rotate >200 lines, load on startup | Log file exists post-restart, user-scoped |
| H4 | MED | D2 auto-restart | systemd unit or supervisor conf for `main:app` on 8792 | `kill -9` uvicorn → auto-respawn, engine-1 reconnects |
| H5 | LOW | Schema hardening (B5/B6) | `_migrate_columns` NOT NULL defaults + `ON DELETE CASCADE` FKs | Migration runs clean on dev_test.db; delete cascade verified |

---

## 3. UI/UX Group (U — operator-requested polish)

| ID | Item | From | Status |
|----|------|------|--------|
| U1 | A1 dashboard `#pos-grid` visible (flip `display:none`) | operator | OPEN (backend done) |
| U2 | A2/A6 real-time position via SSE `position` event | audit | OPEN |
| U3 | A3 engine detail live card + A4 running-position liq enrichment | audit | PARTIAL |
| U4 | C1 account dropdown larger (mobile near-fullscreen) | operator | OPEN |
| U5 | C2 mobile fullscreen per-page | operator | OPEN |
| U6 | C3 centered engine carousel + profile card | DESIGN-SPEC-V2 | OPEN |
| U7 | C4 engine detail popup (one-click modal) | DESIGN-SPEC-V2 | OPEN |
| U8 | C5 bento masonry grid utilities | DESIGN-SPEC-V2 | OPEN |
| U9 | C6 polish pass (skeletons, contrast, typography, hover) | DESIGN-SPEC-V2 | OPEN (partial) |
| U10 | C7 assistant per-user model prefs + context | operator | OPEN (widget exists) |
| U11 | C8 strategy studio Pine→Python converter | STRATEGY_CONVERTER | OPEN (form exists) |
| U12 | C9 secrets page 4-tab | IA-SPEC | OPEN (route exists) |
| U13 | C10 historical backtests UI (equity canvas, metrics, runs) | operator | OPEN (route exists) |

---

## 4. Deploy Group (D — release mechanics)

| ID | Item | Note | Risk |
|----|------|------|------|
| D0 | Deploy deferred `app/routes.py` `_safe_tojson` + `paper_trades` fix | Requires clean server restart → engine-1 flips running→stopped briefly (position stays open) | Disrupts live engine-1 — COORDINATE |
| D1 | Fix `main.py` version `0.095` → `1.98` + sweep all version refs (`grep -rn`) | Quick, low risk | None |
| D2 | Worker (9999) decision: KEEP standalone (operator) — document, no integration | No code | None |
| D3 | Tag release `v1.99-beta` + `VERSIONING.md` entry + `backups/v1xx_beta-gate_STABLE_*.tar.gz` | Follows backup-versioning | None |

---

## 5. Execution Order (recommended)

1. **V1–V4** verification gate (no restart yet)
2. **D1** version string (safe, no restart)
3. **H4** auto-restart (enables safe restarts going forward)
4. **D0** deploy routes.py fix (now safe — H4 covers restart)
5. **H1** B7 kill-close (live-safety)
6. **H2/H3/H5** remaining hardening
7. **U1** dashboard visibility (highest operator value)
8. **U2–U13** UI/UX polish
9. **D3** tag beta

---

## 6. Out of Scope (post-beta / backlog)

Bar-replay endpoint, intra-bar tick UI, backtest date picker, local candle cache >60d, signup flow, smart-contract payment, multi-user roles, Postgres migration, backup-restore RTO test, NTP clock-drift enforcement, Fernet rotation runbook. See TASK-LIST.md Section E + ROAST index in NOTES.md.

---

## 7. Separation Group (Z — 3-way strict separation, beta-blocker)

> Architecture: CONTEXT §11 (Three-Way Strict Separation, SOLID/DDD). Code: TASK-LIST §Z. Goal: paper/backtest can NEVER bleed into Live Dashboard / Live Engine Stats. Isolation at repository layer.

| ID | Item | Notes | Blocker |
|----|------|-------|---------|
| Z1 | Route split — LIVE only in `app/routes.py`; paper/backtest handlers → `paper_routes.py` / `backtest_routes.py`; `main.py` registers 3 routers | Code phase needs D0 restart coordination | YES (structural) |
| Z2 | Menu restructure — drop "Testing"; top-level **Paper** + **Backtesting**; Trades = LIVE only | layout.html nav rewrite | YES (UX clarity) |
| Z3 | Instances single-page dynamic schema — `engine_detail.html` title LIVE/PAPER from `dry_run`, mode tag, `get_parameters()` settings, dry_run toggle | resolves "Paper Trading" hardcoded title | NO (post-doc) |
| Z4 | Design-system theme/glow files — `theme-glow.md`+`.css`, `components.md`, `position-card-spec.md`; reconcile `tokens.css` + CONTEXT §6 to MASTER (`#34D399`/`#FB7185`/`#15100B`) | MASTER.md wins | NO |
| Z5 | Position card HL replication + populate `#pos-grid` — `position-card.js` (left-edge spine, long=`--color-profit`/short=`--color-loss`), wire to live summary | closes A1 empty-grid gap | YES (largest UX gap) |
| Z6 | Paper isolation — `PaperRepository` appends `dry_run=True` unconditionally; `testing/runner.py --mode paper` (dry-run HL, no orders); paper results page = paper history only | absorbs `backtests/runner.py` paper path | YES |
| Z7 | Backtest isolated store — `testing/backtest_store.py` → separate `backtest.db`, distinct models; `BacktestRepository` points at it; `testing/runner.py --mode backtest` (no HL client) | zero live-bleed guarantee | YES |

**Z-gate addition to §0 hard gates:**
7. Route separation complete: `routes.py` contains zero paper/backtest handlers; `Trades` page renders LIVE only.
8. Backtest store is a separate SQLite file with no reference to live models.

**Updated execution order note:** Z1/Z2/Z5/Z6/Z7 are beta-blockers (code phase, after D0 restart safety). Z3/Z4 may land post-beta as polish. Phase B (code) is a SEPARATE go from Phase A (docs) and requires the D0/D1/H4 restart sequence to protect engine-1.

**Design-system note:** HL open-position card VISUALLY VERIFIED 2026-07-18 — replicate HL *layout* (left-edge spine, no row fill, symbol+size colored) with OUR MASTER tokens. See NOTES 2026-07-18 (2nd) entry.

---

## 8. BugHunt & Stability Phase (NEXT — pre-beta, HARD gate 7-8)

> **Status:** Code-complete through 2026-07-23 (Z1–Z7, X1–X4, A4, B7, D1, D2, entry-gate universal repair, BUG-A/B, TDZ, trailing-stop parity, PR#1, paper/backtest fixes). **Systematic bughunting (UI + wiring + data flow) still PENDING** — the next phase after the 2026-07-23 doc sync. NOT STABLE until BUGHUNT group + full `tests/` run close.
> Operator directive: "We need to actually front end practical testing live with it before we can assume that."

### 8.1 Live Frontend Practical Test (gate 7)
| Bug | Target | Verify |
|-----|--------|--------|
| BUG-1 | Dashboard `#pos-grid` renders live position card (HL spine, long=profit, fields from `window.POSITIONS_DATA`) | browser_vision screenshot vs `design-system/position-card-spec.md` |
| BUG-2 | engine_detail LIVE/PAPER mode tag correct | screenshot both LIVE + paper engine |
| BUG-3 | Backtest form submit renders results from `backtest.db` | submit in browser, check console |
| BUG-4 | Paper page forward-test flow (dry_run, no HL orders) | start paper engine, confirm dry-run |
| BUG-5 | Menu nav integrity (no 404, "Testing" gone) | click all top-level items |

### 8.2 Correctness Proof (gate 1)
| Bug | Target | Verify |
|-----|--------|--------|
| BUG-8 | Run `tests/` suite (20 files) | pytest exit 0; fix failures |

### 8.3 Separation Integrity (gate 2)
| Bug | Target | Verify |
|-----|--------|--------|
| BUG-6 | PAPER/LIVE badge on trades | live trades LIVE, paper trades PAPER, no bleed |
| BUG-7 | Dry-run toggle E2E | UI toggle to API to runner respects |

### 8.4 UI Robustness (gate 8)
| Bug | Target | Verify |
|-----|--------|--------|
| BUG-9 | Console error sweep (all authenticated pages) | browser_console clean |

### Exit criteria for "stable" claim
- All BUG-1 to BUG-9 CLOSED
- tests suite green
- No 500s / no console errors on any authenticated route
- Position card visually matches spec
- PAPER/LIVE separation proven in browser

**Only after all above:** bump version to v1.99-beta, update CONTEXT section 13 to BETA, notify operator.

