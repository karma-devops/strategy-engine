# IMPLEMENTATION CHECKLIST — Repo Sort, Doc/Code Simplification, strategies⇄engines split

**Project:** strategy-engine (PULS·R)
**Created:** 2026-07-24 (Asia/Makassar)
**Status:** ACTIVE — execution in progress, one phase per turn
**Discipline:** ADIX + Karpathy + backup-versioning (tar.gz STABLE before every structural edit). Zero autonomous deletion. Consent gate on destructive.
**Supersedes:** `docs/PLANNED-EDITS-24-7-2026.md` — its Phases A–G (live repair) are COMPLETE as of 2026-07-24 (A–F applied + committed; G = live-testing, operator-marked done). That file is retained read-only as repair history; this file is the active cleanup agenda.

---

## Scope boundary (inviolable)

This is a **structure + docs cleanup workstream**, distinct from:
- The live repair (Phases A–G) — DONE.
- The attached debug-stabilization plan (auth/route/test contracts, Tier 0–1). Its doc-cleanup sections (Tier 3.5) are cross-referenced here, NOT duplicated.

The `strategies/` split touches the same source files the repair touched — so paths below are written against the **post-repair** tree (`engine/` still holds strategy logic; executor daemon is `instances/runner.py` + `core/`).

---

## Track 1 — `strategies/` clearly separate from `engines/`  (operator core ask)

**Problem:** `engine/` holds *strategy logic* (`base.py`, `registry.py`, `v1.py`, `v1_3.py`, `v6_1.py`), NOT the executor. The executor daemon is `instances/runner.py` + `core/`. The word "engine" is overloaded (`EngineV1_3Strategy` = a strategy class; `instances/runner.py` = the engine daemon). This overload IS the confusion.

**Split boundary (decided):**
- `strategies/` = trading logic only: `base.py` (BaseStrategy), `registry.py`, `v1.py`, `v1_3.py`, `v6_1.py`.
- Runtime stays put: `instances/` (runner, manager, models, events) + `core/` (exchange, market_data, llm, position_sizer).

| # | Step | Type | Gate | Status |
|---|------|------|------|--------|
| 1.1 | Document vocabulary: "strategy" (logic in `strategies/`) vs "engine daemon" (runtime in `instances/`). Update CONTEXT.md §2 + README to use correct terms | doc | agreed vocab | ☐ |
| 1.2 | Create `strategies/` dir; `git mv` the 5 files from `engine/` → `strategies/` | structural | files moved, no content change | ☐ |
| 1.3 | Add `strategies/__init__.py` if namespace import needs it (check if `from strategies.registry import ...` resolves without it) | structural | import resolves | ☐ |
| 1.4 | Re-point all `from engine.` → `from strategies.` import sites. Current sites (disk-verified 2026-07-24): `testing/runner.py:42`, `api/instances.py:15,487,550`, `api/strategies.py:9,169,189,190,203`, `backtests/runner.py:21`, `instances/manager.py:11`, `instances/runner.py:16`, internal (`engine/v6_1.py:22`, `engine/v1.py:20`, `engine/v1_3.py:16`, `engine/registry.py:18-20`) | code | full `py_compile` + import check clean | ☐ |
| 1.5 | Boot smoke: `uvicorn main:app --port 8792` + `curl /api/v2/strategies` returns 200 with strategy list | verify | green | ☐ |
| 1.6 | **Receiver decoupling AUDIT + GUARDRAIL (replaces class-rename).** Verified 2026-07-24: receivers (`instances/runner.py`, `api/instances.py`, `api/strategies.py`, `testing/runner.py`, `backtests/runner.py`, `app/routes.py`, `scripts/worker.py`) import ONLY via `engine.registry` (`get_strategy`/`STRATEGIES`/`BaseStrategy`/`detect_mintick`) — ZERO direct `EngineV1_3Strategy` class refs outside strategy files + registry. `core/` clean. The 3-point contract (entry_config / exit_config / strategy_config) is ALREADY the enforced boundary. **User may name/slug a strategy anything; file stays `strategy.py`-style. No class rename needed.** | verify | ALREADY SATISFIED | ✅ |
| 1.7 | **Soft-coupling to refactor (lower priority):** `engine/registry.py get_presets()` hardcodes `if canonical == "strategy_v1_3": return {...}` switches — a receiver-side function that knows specific strategy keys. Per 3-point contract, presets should come FROM the strategy (strategy-provided `strategy_config` defaults), not a registry switch. Refactor `get_presets` to call `strategy_cls.get_presets()` — one edit, verify presets still return. | code | presets unchanged + import clean | ☐ |
| 1.8 | **Guardrail test:** add `tests/test_receiver_decoupling.py` — asserts (a) no `engine/*.py`/`strategies/*.py` strategy class name appears outside strategy files + registry, (b) receivers import only via registry. Prevents regression of the 3-point contract. | test | test passes | ☐ |

**Backup note:** Phase-backup tar.gz taken before 1.2 (`v110_precfg-cleanup_STABLE_2026-07-24_0615.tar.gz` exists).

---

## Track 2 — Repo sort & dead-artifact cleanup

| # | Item | Action | Gate | Status |
|---|------|--------|------|--------|
| 2.1 | `._env_bak` at root (macOS junk, untracked) | `mv` to `backups/` (NO REMOVER rule) — approved | moved | ✅ DONE (mv → backups/._env_bak) |
| 2.2 | `._env_example` (underscore dup of `.env.example`) | consolidate: `mv` underscore copy to `backups/`, keep `.env.example` | one canonical | ✅ DONE (file did NOT exist at root; only `.env.example` present — no dup to move) |
| 2.3 | `backups/` (84 dirs, gitignored) | **leave untouched** per standing rule; flag for cold-tar, not delete | — | N/A |
| 2.4 | `venv/`, `data/` | confirmed gitignored; no action | — | N/A |
| 2.5 | Root `HANDOVER-UI-WALKTHROUGH.md` | consider `mv` to `docs/` (CONTEXT references it as companion) | operator call | ☐ |

---

## Track 3 — Doc clarification & simplification (cross-refs attached plan Tier 3.5)

| # | Item | Action | Status |
|---|------|--------|--------|
| 3.1 | Version drift: `CONTEXT.md` §10 says "v2.02" in places; `VERSION` file = v2.03 | single source = `VERSION` file; correct CONTEXT | ☐ |
| 3.2 | `CONTEXT.md` §2 stale claims: `charts.js` retired but live file is `pulsr-chart.js`; missing `api/auth.py` + `api/credentials.py` as separate modules | correct the map | ☐ |
| 3.3 | Mark/archive competing docs (move to `backups/deprecated-docs`, NOT delete): `ROADMAP.md` (false "61/61 pass"), `docs/DOCUMENTATION.md` (765L, overlaps README+ARCHITECTURE), `docs/REFACTOR_PLAN.md` (superseded by CONTEXT §11), `docs/ARCHITECTURE.md` (overlaps §2), `wiki/` (5 files overlap `docs/`) | stamp STALE or move | ☐ |
| 3.4 | Set authoritative doc set: CONTEXT(MAP) + NOTES(LOG) + TASK-LIST(WORK) + BETA-ROADMAP(FORWARD); rest = companion/read-only | document taxonomy in CONTEXT §12 | ☐ |

---

## Track 4 — Code-layer simplification (propose only, low-risk; overlaps attached plan Tier 1.5/2.5)

Listed as *propose* items — NOT executed in this cleanup unless operator approves separately:
- Root `/` public-vs-auth drift (CONTEXT says `/` public landing; `app/routes.py` serves auth dashboard) — product decision needed.
- Withdrawals route `/app/withdrawals` (current) vs legacy `/withdrawals` (old tests/docs).
- Test split-brain: `phase1/2/5_*` stale contract tests vs `test_hardening.py` hitting live port 8792. Repair per attached Tier 0 (convert to in-process ASGI or classify external-only).

---

## Execution log

| Date | Phase | What changed | Verify | Commit |
|------|-------|--------------|--------|--------|
| 2026-07-24 | 0 | Phase-backup `v110_precfg-cleanup_STABLE_2026-07-24_0615.tar.gz` (6155525 bytes) | stat OK | pre-edit, no commit |
| 2026-07-24 | 0 | Created this checklist file | wc -l | pending |
| 2026-07-24 | 2.1/2.2 | `mv ._env_bak`→`backups/` (approved). `._env_example` absent at root — no dup. Root clean. | ls -a | done, uncommitted |
| 2026-07-24 | 1.6 rev | Read `engine/registry.py` fully. Confirmed receivers decoupled via registry; 3-point contract enforced. Replaced class-rename (1.6) with audit+guardrail; added 1.7 (get_presets soft-coupling) + 1.8 (guardrail test). | grep + read | plan revised |

---

## Discipline reminder
- One phase per turn. End turn in text report.
- Backup (tar.gz STABLE) before every structural edit.
- `wc -l` / `git diff --stat` after every write.
- No autonomous deletion — move to `backups/`, get go.
