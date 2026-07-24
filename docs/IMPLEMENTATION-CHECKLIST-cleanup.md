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

## Track 5 — Three-registry architecture + strategy lifecycle (scope expansion 2026-07-24)

**Operator model (verbatim intent):**
- An **instance** = 1 engine + 1 strategy + 1 config-parameter set.
- An **engine** = execution code + log/db entry from a strategy, driven by configs.
- A **strategy** = trading logic; each gets its own subdir with python + pine + doc + originals.

**Three registries (confirmed 2026-07-24):**
| Registry | Path | Role |
|----------|------|------|
| `strategies/registry.py` | catalog of available strategies; manage/create/edit/delete a `strategy.py`; stores pine + python originals; translation via `pynescript` | strategy catalog |
| `engines/registry.py` | created/saved engine definitions; persist; later copy-able for the user | engine catalog |
| `instances/registry.py` | created instances; manage/create/delete an "engine instance" (engine + strategy + config bound) | instance catalog |

**⚠️ Naming collision to resolve (singular vs plural):** current `engine/` (singular) holds the *strategy* classes (`v1.py`, `v1_3.py`, `v6_1.py`). After Track 1 it becomes `strategies/`. The NEW `engines/` (plural) dir is for engine definitions. No clash because singular≠plural, but the split order matters: Track 1 (`engine/`→`strategies/`) runs FIRST, then `engines/` is created.

**Strategy subdir layout (per slug):**
```
strategies/{slug}/
  strategy-name.py        # executable strategy python script
  strategy-name.pine      # exported pine script of latest strategy (optional)
  strategy-name-doc.md    # doc: what it does + technical terms + FIDELITY SCORE vs original
  strategy-origin.py      # if origin was python
  strategy-origin.pine    # if origin was pine
```

**Translation + fidelity:** `pynescript` (https://pypi.org/project/pynescript/) authors pine→python more accurately. Each strategy's `strategy-name-doc.md` carries a fidelity score (translated python vs origin script) shown on the front end.

**Binding model (authoritative — corrected 2026-07-24):**
- **Strategy owns the KEYS** (param schema). It populates the fields shown in the engine settings panel UI.
- **Engine `config.yaml` is written from the UI** on create / edit / save. User sets values in the panel → persisted to `config.yaml`. **Always overrides.**
- Strategy defaults' only job: pre-fill the input box at first render. At save, the engine owns the value. There is NO runtime "strategy default backfills" — the saved `config.yaml` is always complete + authoritative.
- **Runtime binding:** engine reads its own `config.yaml`, passes those values into the strategy. The strategy file is never mutated.
- **Schema drift:** if a strategy changes its keys, the engine settings panel re-renders from the new strategy; old saved `config.yaml` values for removed keys are ignored by the engine (or flagged stale in UI); new keys seeded from the strategy default on next edit. No execution-layer contradiction — the engine only ever binds what its own file says.

**Loader change (architecture-affecting):** `strategies/registry.py` must DYNAMICALLY discover `strategies/{slug}/strategy-name.py` via `importlib` and introspect for a `BaseStrategy` subclass + metadata (slug, name, doc path, fidelity). This replaces the current hardcoded `STRATEGIES = {...}` dict. `get_strategy/list_strategies/register_uploaded_strategy` keep the same public names so callers (`instances/runner.py`, `api/*`, `app/routes.py`, `testing/runner.py`, `backtests/runner.py`, `scripts/worker.py`) don't break.

**⚠️ Grounded finding (read 2026-07-24 — disk-verified):** The binding model is ALREADY implemented in live code. Track 5 is a RESTRUCTURE/DECOUPLE of working code, not a from-scratch build:
- `engine/base.py:9-14` `BaseStrategy.__init__(**kwargs)` applies config as attributes.
- `engine/base.py:21-34` `get_parameters()` declares KEYS (UI schema); `get_default_config()` derives defaults. = "strategy brings the keys."
- `instances/runner.py:178-188` `strategy = strategy_class(**strategy_config)` — engine reads `Instance.strategy_config` (JSON col, models.py:211) and binds at runtime; strategy file untouched. = "full authoritative binding."
- `api/instances.py:468-534` `PUT /instances/{id}/strategy-config` saves config, validates, restarts engine. = **API-editability (5.12) already exists** behind API-key gate; just needs to also write the `config.yaml`.
- `instances/models.py:485-501` `Strategy` DB model already stores pine_source/python_source/documentation/parameters — strategy catalog exists in DB.

**Implication:** the file-based `strategies/registry.py` + subdirs = source-of-truth for strategy *code*; DB `Strategy` row + `Instance.strategy_config` = runtime catalog. Both coexist. New `engines/registry.py` + per-instance `config.yaml` add the file-based authoritative engine-config layer beside the existing DB column.

| # | Step | Type | Gate | Status |
|---|------|------|------|--------|
| 5.1 | Confirm 3-registry layout + `engine/`→`strategies/` order (this table) | consent | go | ☐ PENDING |
| 5.2 | Track 1 first (`engine/`→`strategies/` via git mv). Then create NEW `engines/` dir + `engines/registry.py` | structural | imports clean | ☐ |
| 5.3 | `strategies/registry.py`: dynamic `importlib` loader scanning `strategies/{slug}/strategy-name.py`; expose STRATEGIES/list_strategies/get_strategy/register/unregister + get_presets (pulled from strategy class per 1.7) | code | loader test passes | ☐ |
| 5.4 | `engines/registry.py`: saved engine definitions (execution-code ref + config schema); persist + copy-able | code | engine list returns | ☐ |
| 5.5 | `instances/registry.py`: instance = engine+strategy+config; create/manage/delete; absorbs `DEFAULT_FLEET` from `instances/manager.py` | code | instance CRUD works | ☐ |
| 5.6 | Seed existing strategies into subdirs: `engine/v1.py`→`strategies/strategy_v1/strategy-name.py`, `v1_3.py`→`strategy_v1_3/`, `v6_1.py`→`strategy_v6_1/`; write `{slug}-doc.md` (fidelity TBD) + origin files | code | 3 subdirs import | ☐ |
| 5.7 | `detect_mintick` → `core/` (strategy helper, not registry concern) | code | import clean | ☐ |
| 5.8 | Add `pynescript` to `requirements.txt`; verify it imports + supports the pine version in use (python 3.12 venv) BEFORE relying on it for translation | verify | pip install + import OK | ☐ |
| 5.9 | Fidelity-score mechanism: decide compare method (AST diff / pynescript round-trip / LLM eval) and implement into doc generation | code | score produced | ☐ |
| 5.11 | **Per-instance `config.yaml`** (operator addendum): every instance ships its own `config.yaml` holding the config-parameter set. Instance registry loads/writes this file per instance. DB `strategy_config` column remains the runtime copy; `config.yaml` is authoritative per instance. Location TBD (5-risk-5). | code | instance boots from its config.yaml | ☐ |
| 5.12 | **API editability of engine config** (operator addendum): already exists at `PUT /instances/{id}/strategy-config` (api/instances.py:468-534, API-key gated, restarts engine). Extend the SAME write path to also persist `config.yaml`. Design target: agent edits via API using the identical path the UI uses. The binding model applies identically whether write comes from UI or API. | design | endpoint writes config.yaml too | ☐ |
| 5.13 | **Instance clone / snapshot (operator ask 2026-07-24):** "save, copy or duplicate any instance as a separate engine snapshot with its unique config." YES — falls out of the model. An instance = engine def (ref) + strategy (ref) + `instances/{slug}/config.yaml` (self-contained). Clone = copy config.yaml under a NEW slug + reference same engine/strategy. Config is git-tracked so snapshots are diffable + restorable. Implement in `instances/registry.py` as `clone_instance(slug, new_slug)`. | code | clone produces bootable new instance | ☐ |

**Open risks / decisions to confirm before 5.2:**
1. **`engine/` vs `engines/`** — confirm Track 1 (`engine/`→`strategies/`) precedes `engines/` creation (no clash). 
2. **pynescript** is an external PyPI dep — must verify it works in this env + supports the pine syntax used before we depend on it (5.8).
3. **Fidelity score** needs a defined method (5.9) — not yet chosen.
4. **Migration safety** — existing live `strategy_id` (`strategy_v1_3`) must stay resolvable after subdir move (5.6 keeps slugs).
5. **Per-instance config.yaml location** — ✅ RESOLVED (operator 2026-07-24): `instances/{slug}/config.yaml`, **git-tracked + version-controlled**. DB `strategy_config` column stays the runtime copy; the file is authoritative per instance.
6. **Directory taxonomy (RESOLVED):** `/instances` is SEPARATE from `/engines`. An **instance = deployed engine + its config + the strategy script it runs**. `engines/` holds engine *definitions* (reusable, copy-able); `instances/` holds *deployed* engine+config+strategy bindings. `strategies/` holds strategy *code* (catalog). Three distinct top-level dirs.

**Note:** Track 3.3 revised — `docs/DOCUMENTATION.md` is REMOVED from the archival list; it becomes the Track 5.10 deliverable (registry/architecture authority), not a stale overlap. **RULE (operator 2026-07-24): DOCUMENTATION.md contains ONLY LIVE + STABLE tested code — written LAST, after Track 5 implemented + live-verified.** The existing 765-line `docs/DOCUMENTATION.md` stays a candidate to archive until then.

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
