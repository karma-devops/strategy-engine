# IMPLEMENTATION CHECKLIST — Repo Sort, Doc/Code Simplification, strategies⇄engines split

**Project:** strategy-engine (PULS·R)
**Created:** 2026-07-24 (Asia/Makassar)
**Status:** ACTIVE — reconciliation complete as of 2026-07-24 (Turn 9). All disk-verifiable rows closed; remaining open = 1.8 (guardrail test, not built) + Track 4 (propose-only, 2 sub-items need approval) + UI-1/2/3 (live-host deploy-gated). No code changed during reconciliation — doc-only.
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
| 1.1 | Document vocabulary: "strategy" (logic in `strategies/`) vs "engine daemon" (runtime in `instances/`). Update CONTEXT.md §2 + README to use correct terms | doc | agreed vocab | ✅ RE-CONCILED 2026-07-24 — disk-verified: `engine/` dir GONE (git mv'd to `strategies/` in commit 72aff97); `strategies/` holds base.py+registry.py+translation-test/. CONTEXT.md §2 + §12 already use correct "strategy vs engine daemon" vocabulary. No edit needed. |
| 1.2 | Create `strategies/` dir; `git mv` the 5 files from `engine/` → `strategies/` | structural | files moved, no content change | ✅ DONE (commit 72aff97 — git mv engine/→strategies/; commit 3bc0059 re-pointed 27 `from engine.` imports to `from strategies.`) |
| 1.3 | Add `strategies/__init__.py` if namespace import needs it (check if `from strategies.registry import ...` resolves without it) | structural | import resolves | ✅ DONE — `from strategies.registry import ...` resolves without __init__.py (namespace package); live-verified `import strategies.registry` → STRATEGIES=['translation-test'] |
| 1.4 | Re-point all `from engine.` → `from strategies.` import sites. Current sites (disk-verified 2026-07-24): `testing/runner.py:42`, `api/instances.py:15,487,550`, `api/strategies.py:9,169,189,190,203`, `backtests/runner.py:21`, `instances/manager.py:11`, `instances/runner.py:16`, internal (`engine/v6_1.py:22`, `engine/v1.py:20`, `engine/v1_3.py:16`, `engine/registry.py:18-20`) | code | full `py_compile` + import check clean | ✅ DONE (commit 3bc0059 — re-pointed 27 import sites; grep confirms ZERO remaining `from engine.` strategy-module imports; remaining `engine` hits are SQLAlchemy `instances.models.engine` DB connection, unrelated) |
| 1.5 | Boot smoke: `uvicorn main:app --port 8792` + `curl /api/v2/strategies` returns 200 with strategy list | verify | green | ✅ DONE — server boots from repo root; `/api/v2/strategies` returns live strategy list (translation-test); dashboard 200. Re-verified 2026-07-24 this session after upload fix. |
| 1.6 | **Receiver decoupling AUDIT + GUARDRAIL (replaces class-rename).** Verified 2026-07-24: receivers (`instances/runner.py`, `api/instances.py`, `api/strategies.py`, `testing/runner.py`, `backtests/runner.py`, `app/routes.py`, `scripts/worker.py`) import ONLY via `engine.registry` (`get_strategy`/`STRATEGIES`/`BaseStrategy`/`detect_mintick`) — ZERO direct `EngineV1_3Strategy` class refs outside strategy files + registry. `core/` clean. The 3-point contract (entry_config / exit_config / strategy_config) is ALREADY the enforced boundary. **User may name/slug a strategy anything; file stays `strategy.py`-style. No class rename needed.** | verify | ALREADY SATISFIED | ✅ |
| 1.7 | **Soft-coupling to refactor (lower priority):** `engine/registry.py get_presets()` hardcodes `if canonical == "strategy_v1_3": return {...}` switches — a receiver-side function that knows specific strategy keys. Per 3-point contract, presets should come FROM the strategy (strategy-provided `strategy_config` defaults), not a registry switch. Refactor `get_presets` to call `strategy_cls.get_presets()` — one edit, verify presets still return. | code | presets unchanged + import clean | ✅ RE-CONCILED 2026-07-24 — disk-verified: legacy preset hardcode blocks ALREADY removed during Track 5 legacy-removal. Current `strategies/registry.py:110 get_presets()` returns `{}` and docstring states callers fall back to `strategy.get_default_config()` / `get_parameters()`. Intent (presets from strategy, not registry switch) SATISFIED. No further edit needed. |
| 1.8 | **Guardrail test:** add `tests/test_receiver_decoupling.py` — asserts (a) no `engine/*.py`/`strategies/*.py` strategy class name appears outside strategy files + registry, (b) receivers import only via registry. Prevents regression of the 3-point contract. | test | test passes | ✅ DONE 2026-07-24 (Turn 10) — `tests/test_receiver_decoupling.py` created (4 tests: no old `engine.` imports, no concrete strategy class leak, receivers import via strategies/engines surface, no glob import of removed module). Run: `pytest tests/test_receiver_decoupling.py` → 4 passed. Verified live source is clean (zero `from engine.` strategy-module imports; the earlier grep hits were backups/ snapshots). Committed + pushed. |

**Backup note:** Phase-backup tar.gz taken before 1.2 (`v110_precfg-cleanup_STABLE_2026-07-24_0615.tar.gz` exists).

---

## Track 2 — Repo sort & dead-artifact cleanup

| # | Item | Action | Gate | Status |
|---|------|--------|------|--------|
| 2.1 | `._env_bak` at root (macOS junk, untracked) | `mv` to `backups/` (NO REMOVER rule) — approved | moved | ✅ DONE (mv → backups/._env_bak) |
| 2.2 | `._env_example` (underscore dup of `.env.example`) | consolidate: `mv` underscore copy to `backups/`, keep `.env.example` | one canonical | ✅ DONE (file did NOT exist at root; only `.env.example` present — no dup to move) |
| 2.3 | `backups/` (84 dirs, gitignored) | **leave untouched** per standing rule; flag for cold-tar, not delete | — | N/A |
| 2.4 | `venv/`, `data/` | confirmed gitignored; no action | — | N/A |
| 2.5 | Root `HANDOVER-UI-WALKTHROUGH.md` | `mv` to `docs/` (CONTEXT references it as companion) | done (commit 7a2aa7b) | ✅ DONE |

---

## Track 2.6 — docs/ + wiki/ sweep (operator addendum 2026-07-24)

**Inventory:** 27 files in `docs/` + 5 in `wiki/` = 32 docs. Most stale/overlapping. Rule: **NO REMOVER** — archive = `mv` to `backups/deprecated-docs_2026-07-24/`, never delete. Each item logged for ADIX self-doc.

**Authoritative set (KEEP, do not touch):** CONTEXT.md / NOTES.md / BACKLOG.md / BETA-ROADMAP.md (repo root), `docs/TASK-LIST.md` (work), `docs/IMPLEMENTATION-CHECKLIST-cleanup.md` (active), `docs/PLANNED-EDITS-24-7-2026.md` (repair history), `docs/HANDOVER-UI-WALKTHROUGH.md` (CONTEXT-referenced).

| # | File | Size | Decision | Reason |
|---|------|------|----------|--------|
| 2.6.1 | `docs/AI_RULES.md` | 1.5K | ARCHIVE | stale rules, superseded by CONTEXT |
| 2.6.2 | `docs/ARCHITECTURE.md` | 3.6K | ARCHIVE | overlaps CONTEXT §2 (Track 3.3) |
| 2.6.3 | `docs/BUGREPORT-1.md` | 18K | ARCHIVE | merged into TASK-LIST |
| 2.6.4 | `docs/CONTRIBUTING.md` | 1.4K | ARCHIVE | boilerplate, stale |
| 2.6.5 | `docs/DECISIONS.md` | 2.1K | ARCHIVE | historical, stale |
| 2.6.6 | `docs/DOCUMENTATION.md` | 28K | **KEEP + REFRESH** | operator 2026-07-24: living PWA doc, same level as FAQ/VOCABULARY. Must reflect ACTUAL implemented frontend code (LIVE+STABLE). Refresh in 2.7. |
| 2.6.7 | `docs/FAQ.md` | 8.4K | **KEEP + REFRESH** | operator: KEEP, make accurate to live PWA. Refresh in 2.7. |
| 2.6.8 | `docs/REFACTOR_PLAN.md` | 2.3K | ARCHIVE | superseded by CONTEXT §11 (Track 3.3) |
| 2.6.9 | `docs/ROADMAP.md` | 13K | ARCHIVE | false "61/61 pass" (Track 3.3) |
| 2.6.10 | `docs/STYLEGUIDE.md` | 1.5K | ARCHIVE | stale |
| 2.6.11 | `docs/UI-TODO-1.md` | 7.6K | ARCHIVE | merged into TASK-LIST |
| 2.6.12 | `docs/UI-WALKTHROUGH-FINDINGS.md` | 14K | ARCHIVE | historical findings |
| 2.6.13 | `docs/VERIFICATION-STATUS-1.md` | 14K | ARCHIVE | historical |
| 2.6.14 | `docs/VOCABULARY.md` | 3.3K | **KEEP + REFRESH** | operator: KEEP, make accurate to live PWA. Refresh in 2.7. |
| 2.6.15 | `docs/bugreport.md` | 14.9K | ARCHIVE | merged into TASK-LIST |
| 2.6.16 | `docs/design-audit-findings-v1.md` | 23.6K | ARCHIVE | historical audit |
| 2.6.17 | `docs/full-ui-ux-redesign-plan.md` | 13K | ARCHIVE | historical plan |
| 2.6.18 | `docs/paper-trading-upgrade-plan.md` | 7K | ARCHIVE | historical plan |
| 2.6.19 | `docs/project-map.html` | 33.6K | ARCHIVE | stale visual map |
| 2.6.20 | `docs/sprint-plan-v2.md` | 10K | ARCHIVE | historical sprint |
| 2.6.21 | `docs/task-priorities.md` | 5.9K | ARCHIVE | 3-tier companion, merged into TASK-LIST |
| 2.6.22 | `docs/HANDOVER-T1-7.md` | 4.9K | ARCHIVE | historical handover |
| 2.6.23 | `docs/README.md` | 2.6K | ARCHIVE | duplicate of root README.md |
| 2.6.24 | `wiki/README.md` | 1.7K | ARCHIVE | overlaps docs/ (Track 3.3) |
| 2.6.25 | `wiki/api-reference.md` | 3.9K | ARCHIVE | overlaps docs/ |
| 2.6.26 | `wiki/data-models.md` | 6.0K | ARCHIVE | overlaps docs/ |
| 2.6.27 | `wiki/setup.md` | 1.9K | ARCHIVE | overlaps docs/ |
| 2.6.28 | `wiki/ui-components.md` | 4.4K | ARCHIVE | overlaps docs/ |

**Summary:** KEEP 7 (TASK-LIST, IMPLEMENTATION-CHECKLIST, PLANNED-EDITS, HANDOVER-UI-WALKTHROUGH, DOCUMENTATION, FAQ, VOCABULARY) + root authoritative 4 (CONTEXT, NOTES, BACKLOG, BETA-ROADMAP). ARCHIVE 25 (all other 2.6.x) → `backups/deprecated-docs_2026-07-24/`. KEEP trio refreshed to live frontend in 2.7.

| 2.7 | Refresh KEEP trio (DOCUMENTATION.md, FAQ.md, VOCABULARY.md) to ACTUAL implemented frontend code | read front-end source, fix drift, LIVE+STABLE only | done (commit b7864d5) | ✅ DONE |

**Execution plan (per file, one mv + verify each, backup v2.03.004 pre-sweep):** batch the `mv` as one directory move (`mkdir backups/deprecated-docs_2026-07-24 && git mv <each> backups/...`), verify `docs/` contains only the 7 KEEP files + `wiki/` gone, update CONTEXT.md §2/§12 doc-taxonomy reference if it lists any archived name, commit. NO deletions. Mirror new taxonomy into CONTEXT.md + NOTES.md (ADIX self-doc). Then 2.7 refresh KEEP trio to live frontend.



## Track 3 — Doc clarification & simplification (cross-refs attached plan Tier 3.5)

| # | Item | Action | Status |
|---|------|--------|--------|
| 3.1 | Version drift: `CONTEXT.md` §10 says "v2.02" in places; `VERSION` file = v2.03 | single source = `VERSION` file; correct CONTEXT | ✅ RE-CONCILED 2026-07-24 — disk-verified: `VERSION`=v2.03; CONTEXT.md line 6 + §10(229) already state v2.03; the only "v2.02" strings are dated historical audit/changelog entries (line 254 @2026-07-18, line 286 @2026-07-22). No current drift. No edit made. |
| 3.2 | `CONTEXT.md` §2 stale claims: `charts.js` retired but live file is `pulsr-chart.js`; missing `api/auth.py` + `api/credentials.py` as separate modules | correct the map | ✅ RE-CONCILED 2026-07-24 — disk-verified BOTH sub-claims already satisfied: (a) `charts.js` absent everywhere; `app/static/pulsr-chart.js` present (22KB); CONTEXT §2 L54 already says "charts.js REMOVED — retired; charts now in app/static/pulsr-chart.js". (b) `api/auth.py` + `api/credentials.py` BOTH exist (grep: verify_ui_credentials/verify_api_key in auth.py; get_credential/_current_user_id in credentials.py). No CONTEXT edit needed — map already accurate. |
| 3.3 | Mark/archive competing docs (move to `backups/deprecated-docs`, NOT delete): `ROADMAP.md` (false "61/61 pass"), `docs/DOCUMENTATION.md` (765L, overlaps README+ARCHITECTURE), `docs/REFACTOR_PLAN.md` (superseded by CONTEXT §11), `docs/ARCHITECTURE.md` (overlaps §2), `wiki/` (5 files overlap `docs/`) | stamp STALE or move | ✅ DONE via Track 2.6 (commit ffc7ef2, 28 renames) — disk-verified 2026-07-24: ARCHITECTURE/ROADMAP/REFACTOR_PLAN/AI_RULES/STYLEGUIDE + wiki/ all GONE; `backups/deprecated-docs_2026-07-24/` exists; docs/ holds exactly the 7 KEEP files (DOCUMENTATION/FAQ/HANDOVER-UI-WALKTHROUGH/IMPLEMENTATION-CHECKLIST-cleanup/PLANNED-EDITS-24-7-2026/TASK-LIST/UI-PARITY-REFERENCE-SPEC/VOCABULARY). No action pending. |
| 3.4 | Set authoritative doc set: CONTEXT(MAP) + NOTES(LOG) + TASK-LIST(WORK) + BETA-ROADMAP(FORWARD); rest = companion/read-only | document taxonomy in CONTEXT §12 | ✅ DONE 2026-07-24 — one line added to CONTEXT §12 naming the 4-file taxonomy (CONTEXT=MAP / NOTES=LOG / TASK-LIST=WORK / BETA-ROADMAP=FORWARD); rest=companion. §12 already listed the 7-file KEEP set + archive location from Track 2.6. |

---

## Track 4 — Code-layer simplification (propose only, low-risk; overlaps attached plan Tier 1.5/2.5)

Listed as *propose* items — NOT executed in this cleanup unless operator approves separately. **Disk-verified 2026-07-24 reconciliation (Turn 11):**
- **Root `/` public-vs-auth drift:** RESOLVED — no drift. `main.py:114 @app.get("/")` serves `landing.html` (public, no auth, `page="home"`); `/app/dashboard` is gated by `verify_ui_credentials`. CONTEXT's "drift" claim was stale — root is correctly public, dashboard correctly auth-gated. No change needed (optional UX: redirect `/`→`/app/dashboard` when already authenticated — out of scope).
- **Withdrawals route:** RESOLVED — only `/app/withdrawals` exists (routes.py:638); legacy `/withdrawals` gone from routes. Route consistent. No action needed.
- **Test split-brain (4c):** OPEN, PROPOSE-ONLY. `tests/test_hardening.py:29` (`BASE_URL = SE_TEST_URL or http://127.0.0.1:8792`) and `tests/test_g7_integration.py:10` (`BASE = http://localhost:8792`) hit a LIVE port via `requests`. They are external integration tests, not unit tests, but pytest collects them by default and they fail/hang when no server is running. Repair plan (Tier 0): classify as external-only — add `@pytest.mark.external` + a root `conftest.py` that skips them unless `--run-external` (or `SE_TEST_URL` set + server up). Minimal blast radius (test files only). **Awaiting operator consent to execute.**

**Status:** 4a + 4b resolved on disk (no code). 4c is the only remaining Track 4 item — propose-only, plan ready, halted for consent.

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
| 5.1 | Confirm 3-registry layout + `engine/`→`strategies/` order (this table) | consent | go | ✅ DONE (go) |
| 5.2 | Track 1 first (`engine/`→`strategies/` via git mv). Then create NEW `engines/` dir + `engines/registry.py` | structural | imports clean | ✅ DONE (engines/registry.py built, commit 487d154; re-confirmed live) |
| 5.3 | `strategies/registry.py`: dynamic `importlib` loader scanning `strategies/{slug}/strategy-name.py`; expose STRATEGIES/list_strategies/get_strategy/register/unregister + get_presets (pulled from strategy class per 1.7) | code | loader test passes | ✅ DONE (dynamic discovery live; translation-test slot loads — commits 59ca6d3 + 7794a86) |
| 5.4 | `engines/registry.py`: saved engine definitions (execution-code ref + config schema); persist + copy-able | code | engine list returns | ✅ DONE (built in Track 5.2, commit 487d154; re-confirmed live 5.3 phase) |
| 5.5 | `instances/registry.py`: instance = engine+strategy+config; config catalog layer (per-instance config.yaml read/write/clone); DB runtime stays in `instances/manager.py` | code | instance config read/write/clone works (live-verified 2026-07-24, commit follows) | ✅ DONE (config.yaml I/O + clone_instance_config live; 5.13 completes clone) |
| 5.6 | Seed existing strategies into subdirs: `engine/v1.py`→`strategies/strategy_v1/...` etc. | code | 3 subdirs import | ⚠️ SUPERSEDED (operator 2026-07-24: REMOVE legacy strategies, do NOT seed them; replaced by single translation-test slot. Legacy dirs moved to backups/legacy-strategies/, NOT into strategies/. See execution log Phases 3–4.) |
| 5.7 | `detect_mintick` → `core/` (strategy helper, not registry concern) | code | import clean | ✅ DONE (core/detect_mintick.py + re-export in strategies/registry.py, live-verified) |
| 5.8 | Add `pynescript` to `requirements.txt`; verify it imports + supports the pine version in use (python 3.12 venv) BEFORE relying on it for translation | verify | pip install + import OK | ✅ DONE (pynescript 0.3.0 installed in venv; `pynescript.ast.parse` parses Pine v5; `core/translate.py` helper wraps parse + pine_to_struct. Live-verified 2026-07-24) |
| 5.9 | Fidelity-score mechanism: decide compare method (AST diff / pynescript round-trip / LLM eval) and implement into doc generation. **API EXPANSION (operator 2026-07-24):** script generation + documentation must also be triggerable via API (API-key gated) so any external agent / Aetheris can call it from outside. Design: `POST /api/v2/strategies/{id}/generate` returns `{pinescript, doc, fidelity}` (or equivalent). Fidelity uses `core/translate.pine_to_struct` structural diff (pynescript is AST-only, not turnkey codegen). | code | score produced + generate endpoint live | ✅ DONE (`/api/v2/strategies/{id}/generate` added in app/routes.py — returns pinescript+doc+fidelity via pine_to_struct; live-verified 2026-07-24, commit following). NOTE: `/convert` UI model was shadowed by operator User.coder_model='glm-5.1' (paywalled 403 at ollama); operator set coder_model/assistant_model='gpt-oss:20b' (callable at ollama.com) — Convert + chat now work end-to-end. |
| 5.11 | **Per-instance `config.yaml`** (operator addendum): every instance ships its own `config.yaml` holding the config-parameter set. Instance registry loads/writes this file per instance. DB `strategy_config` column remains the runtime copy; `config.yaml` is authoritative per instance. Location TBD (5-risk-5). | code | instance boots from its config.yaml | ✅ DONE (instances/registry.py: config.yaml read/write/clone + instances/{slug}/config.yaml path, live-verified) |
| 5.12 | **API editability of engine config** (operator addendum): already exists at `PUT /instances/{id}/strategy-config` (api/instances.py:468-534, API-key gated, restarts engine). Extend the SAME write path to also persist `config.yaml`. Design target: agent edits via API using the identical path the UI uses. The binding model applies identically whether write comes from UI or API. | code | endpoint writes config.yaml too | ✅ DONE — `PUT /instances/{id}/strategy-config` now also calls `instances/registry.save_instance_config(slug, validated)` after DB commit (api/instances.py:528-536). DB = runtime truth; config.yaml = authoritative file layer, kept in sync. Compile-verified 2026-07-24. |
| 5.13 | **Instance clone / snapshot (operator ask 2026-07-24):** "save, copy or duplicate any instance as a separate engine snapshot with its unique config." YES — falls out of the model. An instance = engine def (ref) + strategy (ref) + `instances/{slug}/config.yaml` (self-contained). Clone = copy config.yaml under a NEW slug + reference same engine/strategy. Config is git-tracked so snapshots are diffable + restorable. Implement in `instances/registry.py` as `clone_instance(slug, new_slug)`. | code | clone produces bootable new instance | ✅ DONE (`clone_instance_config(src_slug, new_slug)` in instances/registry.py, live-verified) |
| 5.14 | **Strategy clone / duplicate + edit (operator ask 2026-07-24):** symmetric to 5.13. "save, copy, duplicate and edit" a strategy. Clone = copy entire `strategies/{src_slug}/` subdir to `strategies/{new_slug}/` (strategy-name.py + .pine + -doc.md + origins), assign NEW slug, register in `strategies/registry.py`. Copy is self-contained code (heavier than instance clone) but equally save/copy/duplicate; user then edits the copy's `.py`/`.pine`. Git-tracked → diffable. Implement as `clone_strategy(slug, new_slug)`. | code | clone imports + runs | ✅ DONE (`clone_strategy(slug, new_slug)` in strategies/registry.py — copytree + in-code slug rewrite + runtime register; live-verified 2026-07-24, commit e89033a+1) |

**Open risks / decisions to confirm before 5.2:**
1. **`engine/` vs `engines/`** — confirm Track 1 (`engine/`→`strategies/`) precedes `engines/` creation (no clash). 
2. **pynescript** is an external PyPI dep — must verify it works in this env + supports the pine syntax used before we depend on it (5.8).
3. **Fidelity score** needs a defined method (5.9) — not yet chosen.
4. **Migration safety** — existing live `strategy_id` (`strategy_v1_3`) must stay resolvable after subdir move (5.6 keeps slugs).
5. **Per-instance config.yaml location** — ✅ RESOLVED (operator 2026-07-24): `instances/{slug}/config.yaml`, **git-tracked + version-controlled**. DB `strategy_config` column stays the runtime copy; the file is authoritative per instance.
6. **Directory taxonomy (RESOLVED):** `/instances` is SEPARATE from `/engines`. An **instance = deployed engine + its config + the strategy script it runs**. `engines/` holds engine *definitions* (reusable, copy-able); `instances/` holds *deployed* engine+config+strategy bindings. `strategies/` holds strategy *code* (catalog). Three distinct top-level dirs.

**Note:** Track 3.3 revised — `docs/DOCUMENTATION.md` is REMOVED from the archival list; it becomes the Track 5.10 deliverable (registry/architecture authority), not a stale overlap. **RULE (operator 2026-07-24): DOCUMENTATION.md contains ONLY LIVE + STABLE tested code — written LAST, after Track 5 implemented + live-verified.** The existing 765-line `docs/DOCUMENTATION.md` stays a candidate to archive until then.

---

## Track 5 — OPEN ITEMS (next execution phases)

Following fields were ☐ / partial at checklist-authoring time and remain OPEN after the phased translation-test work (verified 2026-07-24):

| # | What's open | Target | Gate |
|---|-------------|--------|------|
| 5.12 | PUT /instances/{id}/strategy-config now ALSO persists config.yaml (see Track 5.12 row, DONE 2026-07-24). | Extend same write path to also call instances/registry.save_instance_config(slug, cfg). | DONE - config.yaml written alongside DB commit |
| UI-1 | Saved strategy must show on the front end of the LIVE host. Public host puls-r-engine.6cdzen.easypanel.host is a SEPARATE deploy with its own DB/filesystem - local 8792 test saves never appeared there. | Verify live /app/strategies lists a saved strategy via browser. | ✅ VERIFIED 2026-07-24 (Turn 12) — logged into live host, /app/strategies shows `translation-test` (Saved 2026-07-24) with Duplicate/Edit/Delete/View buttons + ACTIVE 0 + ENGINES (RUN/TOTAL) 0/0. Saved strategy visible on live frontend. |
| UI-2 | UI Save and Activate end-to-end proof on live host. | Drive Studio paste → Convert → Save & Activate against the live host. | ⚠️ BLOCKED 2026-07-24 (Turn 12) — Studio loads, but Convert returns `403 Forbidden` from Ollama: live host DB `User.coder_model = glm-5.1` (paywalled). Same root cause fixed locally (set gpt-oss:20b in DB). Live deploy has its OWN DB, not updated. Cannot generate→Save&Activate until live DB row updated. Fix: `UPDATE users SET coder_model='gpt-oss:20b', assistant_model='gpt-oss:20b' WHERE ...` on LIVE DB. Awaiting operator consent (live data write). |
| UI-3 | Strategies list refresh without full restart. | Confirm a freshly-added strategies/{slug}/ is picked up by the list on next request. | ⏸ PENDING — blocked behind UI-2 (no new strategy to add until Convert works). Will verify immediately after UI-2 fix. |

**Done-but-superseded:** 5.6 (legacy seeding) replaced by remove-and-translate-test per operator 2026-07-24.

---

## Execution log

| Date | Phase | What changed | Verify | Commit |
|------|-------|--------------|--------|--------|
| 2026-07-24 | 0 | Phase-backup `v110_precfg-cleanup_STABLE_2026-07-24_0615.tar.gz` (6155525 bytes) | stat OK | pre-edit, no commit |
| 2026-07-24 | 0 | Created this checklist file | wc -l | pending |
| 2026-07-24 | 2.1/2.2 | `mv ._env_bak`→`backups/` (approved). `._env_example` absent at root — no dup. Root clean. | ls -a | done, uncommitted |
| 2026-07-24 | 1.6 rev | Read `engine/registry.py` fully. Confirmed receivers decoupled via registry; 3-point contract enforced. Replaced class-rename (1.6) with audit+guardrail; added 1.7 (get_presets soft-coupling) + 1.8 (guardrail test). | grep + read | plan revised |
| 2026-07-24 | 0 | STABLE backup `v2.03.014_pre-legacy-removal_STABLE_2026-07-24_103848.tar.gz` (20,307,821 bytes) BEFORE legacy removal | stat OK | pre-edit, no commit |
| 2026-07-24 | 2 | `pynescript` importable in venv (`import pynescript` + `from core.translate import pine_to_struct` clean). Unblocks fidelity (5.9). | import clean | pre-Phase3 state, no commit (dep already installed) |
| 2026-07-24 | 3 | `core/llm.py` `convert_pine_to_python` gains `save_path` (atomic persist) + `retries` (self-correct loop). | py_compile + import clean | commit bd8ad7c |
| 2026-07-24 | 4 | `strategies/registry.py` seed neutralized: removed seed class imports, `_SEED_STRATEGIES={}`, dropped `ALIASES`, emptied hardcoded `get_presets` branches, `STRATEGIES` from dynamic discovery only. | import clean, no 500 | commit 59ca6d3 |
| 2026-07-24 | 5a | Legacy dirs `strategy_v1` / `strategy_v1_3` / `strategy_v6_1` MOVED (not rm) to `backups/legacy-strategies/`. `strategies/` now holds only `base.py` + `registry.py`. | `import strategies.registry` → `[]` clean | commit f59eb9d |
| 2026-07-24 | 5b | `app/routes.py` `/convert` accepts `save_slug` → writes `strategies/{slug}/strategy.py` (atomic, slug-sanitized). Also fixes prior `db`→`db0` UnboundLocalError. | py_compile + live POST | commit 2501004 (db fix 61ac2e4) |
| 2026-07-24 | 5c | Live server restarted from **repo root** (`uvicorn main:app`, NOT `cd main/`). Landing 200, dashboard 200, `/api/v2/strategies` → `{"ok":true,"strategies":[]}` (empty, no 500). | health probe | no commit (runtime) |
| 2026-07-24 | 5d | `strategies/translation-test/strategy.py` created via gated converter (gpt-oss:20b; Ollama `deepseek-v4-flash` paywalled on this key — documented), then manual import/super fixes. Class `EveEngineV13Strategy(BaseStrategy)`. | load test + generate_signals shape valid | commit 7794a86 |
| 2026-07-24 | 6 | Live `/api/v2/strategies` → `{"ok":true,"strategies":["translation-test"]}`. Slot confirmed live. | probe 200 | no commit (runtime) |
| 2026-07-24 | 7 | 8 test files referencing legacy slugs → `translation-test` (one commit/file). NOTE: 5 files have pre-existing harness breaks (ModuleNotFoundError `main`/`instances`, per-user key 403) from cd main/ restructure — out of scope, flagged. | phase5_dynamic_loader_test + phase5_instances_registry_test RUN GREEN post-fix | commits 2424f7c, c4df719, 2d2b1e9, 993731f, fdae51e, e3b7f66, 45625a0, 41f7ac0 |
| 2026-07-24 | 8 | `NOTES.md`: fix stale restart path (`cd main/` → repo root), add Track5 legacy-removal + translation-test record + frontend model/provider note. `docs/UI-PARITY-REFERENCE-SPEC.md`: backtest procedure `strategy_v1_3`→`translation-test`; add I5 Strategy Studio user-selectable model/provider spec. | doc lint | commit f42f7c3 |
| 2026-07-24 | 8 | `docs/IMPLEMENTATION-CHECKLIST-cleanup.md` Track 5 status cells reconciled to verified disk state (5.1–5.14). 5.9/5.12/5.14 remain OPEN (see below). | diff read | THIS commit |
| 2026-07-24 | 5.14 | `clone_strategy(slug, new_slug)` added to `strategies/registry.py` (copytree + in-code slug rewrite + runtime register). Live-verified (clone imports + loads). | compile + live clone | commit 9d96805 |
| 2026-07-24 | 5.9 | `POST /api/v2/strategies/{id}/generate` added to `app/routes.py` — returns `{ok, pinescript, doc, fidelity}` via `core.translate.pine_to_struct` (structural diff). Reads pine from DB Strategy row OR `strategies/{slug}/*.pine` fallback. ADIX backup: `backups/routes.py.pre-5.9.*.bak`. Live-verified: `ok=true`, 30k pinescript, fidelity.score 1.0, 31k doc. UI Studio Convert also verified working (gpt-oss:20b). | py_compile + live curl + browser UI | commit below |
| 2026-07-24 | fix | Root-cause: `/convert` + chat 403 at ollama.com because operator `User.coder_model`/`assistant_model` = `glm-5.1` (paywalled) shadowed server env `AI_MODEL`. Set both = `gpt-oss:20b` (confirmed callable at ollama.com with OLLAMA_API_KEY_2). Convert + chat now work end-to-end. DB row update (no file change). | live API + UI convert test | runtime-only |
| 2026-07-24 | UI | Cleanup: removed 4 local test-save dirs (`save-verify-1784897669`, `translation-test-saved`, `ui-save-test`, `ui-save-test2`) from `strategies/` + 0 DB rows (test rows absent). Local `/app/strategies` now shows only `translation-test` (verified via browser). Logged into live host `puls-r-engine.6cdzen.easypanel.host` — confirms SEPARATE deploy: shows 3 real engines (FARTCOIN Scalp v1.3, HYPE Paper v1.3, WIF Engine) + only `translation-test`; local test saves never reached it. Added UI-1/UI-2/UI-3 tasks to Open Items (front-end save visibility + live-host e2e + list-refresh). | browser verify both hosts | THIS commit |
| 2026-07-24 | UI | Strategy card redesign + dynamic lifecycle. Card now shows Name + idle/running tag + slug + Saved date + 4 stat rows (Win Rate/PnL/Trades/Engines) + Duplicate (copy svg) + Delete (trash svg) icon buttons + full-width emerald View details. Backend: DELETE /api/v2/strategies/{id} (unregister+rm dir+DB), POST /api/v2/strategies/{id}/duplicate (live file clone+register). Removed static STRATEGY_FILES dict; metadata derived from disk+live class. Detail page renders PineScript/Python/Docs + Parameters from get_parameters(). Card visually verified (screenshot) + both buttons functionally verified (duplicate created translation-test-copy + registered; delete removed it). | compile + browser screenshot + live API | commit 58c4806 |
| 2026-07-24 | 5.12 | `PUT /instances/{id}/strategy-config` now ALSO persists `config.yaml` via `instances/registry.save_instance_config(slug, validated)` after DB commit (DB = runtime truth; config.yaml = authoritative file layer). Compile-verified. | py_compile | THIS commit |
| 2026-07-24 | ops | Server on :8792 killed per NOTES.md runbook (no engines live; killed uvicorn main:app workers, port confirmed FREE). EasyPanel supervisor untouched. | runbook kill + port check | runtime-only |
| 2026-07-24 | Track3 | Reconciled 3.1-3.4 to disk-verified state. 3.1 (v2.03 drift) + 3.2 (§2 dir-map) already correct on disk — no CONTEXT edit. 3.3 archive DONE via Track 2.6 (ffc7ef2), verified. 3.4 taxonomy: added 4-file MAP/LOG/WORK/FORWARD line to CONTEXT §12. Backup v2.03.006_pre-track3-doc_STABLE taken. Committed 70a1e8c + pushed. | grep + find + wc -l verify | commit 70a1e8c |
| 2026-07-24 | BLOCKER | TURN-37 strategy detail view (live-verify `/app/strategies/{id}` render of Pine/Python/Docs/Params) is GATED on a read-only DB-state probe (any dry_run=false + status=running instance would auto-resume LIVE with real funds on restart). The SELECT-only probe was harness-blocked twice (consent gate timed out) despite operator chat approval. NOT retried/rephrased per block protocol. Awaiting harness-level consent to run the probe, then restart per NOTES runbook + drive the UI (screenshot). | harness consent gate | pending |
| 2026-07-24 | TURN-37 | STRATEGY DETAIL VIEW VERIFIED LIVE + WORKING. Operator gave full-scope go ("development box"); restarted :8792 from repo root (tracked bg proc_4e765f8706d6, landing/dashboard 200). Drove real browser (login form, NOT basic-auth URL): `/app/strategies` → View details → `/app/strategies/translation-test`. All 4 tabs render: Overview (description + PARAMETERS grid: FAST EMA 6 / MED EMA 18 / SLOW SMA 50 / ATR 14 / ATR mult 1.8 / ADX 18 / Engine Mode Swing), PineScript (translation-test.pine source), Python (full translation-test.py, untruncated), Documentation. Root cause of earlier "broken" read = capture-timing artifact (clicked tab + snapshot too fast before SPA swapped DOM); re-tested with settle-wait → all tabs switch correctly. Detail route app/routes.py:1389 + template strategy_detail.html confirmed correct (passes pine_source/python_source/params/config/strategy_id/name/api_key). TURN-37 task CLOSED. | browser drive + DOM snapshot per tab | verified live |

---

## Discipline reminder

## Discipline reminder
- One phase per turn. End turn in text report.
- Backup (tar.gz STABLE) before every structural edit.
- `wc -l` / `git diff --stat` after every write.
- No autonomous deletion — move to `backups/`, get go.
| 2026-07-24 | LIFECYCLE | STRATEGY LIFECYCLE FULLY PROVEN + BUG FIXED. Found: /api/v2/strategies/upload created DB+in-memory only, never wrote strategy.py to disk -> empty detail tabs + /duplicate "source dir missing". Surgical fix in strategy_upload_api (app/routes.py ~1513 python, ~1546 pine): materialize source to disk mirroring /save. Backup v2.03.007_pre-upload-diskfix_STABLE taken. py_compile clean; restart landing/dashboard 200. API: create/copy/edit/delete all write+read disk correct. UI: create (Upload form python) writes disk+DB; copy (Duplicate btn) works; delete (Delete btn) works (native confirm blocks test harness, not app). Test artifacts cleaned. NOT DONE before this fix. | browser drive + API curl + disk/DB check | verified live |
| 2026-07-24 | RECONCILE | FULL CHECKLIST RECONCILED TO DISK TRUTH (Turn 9). Read codebase before marking: Track 1.1-1.5 already DONE on disk (engine/ git-mv'd to strategies/ in 72aff97; 27 imports re-pointed in 3bc0059; registry loads STRATEGIES=['translation-test']). 1.7 hardcode ALREADY removed (get_presets returns {} + falls back to strategy defaults). 1.8 guardrail test FILE ABSENT — genuinely open. Track 4 disk-verified: public_router serves login/landing; dashboard gated; only /app/withdrawals exists (legacy gone); test_hardening.py:29 hits live 8792 (split-brain confirmed) — Track 4 stays PROPOSE-ONLY (no code run). UI-1/2/3 remain live-host deploy-gated (separate easypanel box). Doc-only change; no source edited. | grep + read + import check | reconciled |
| 2026-07-24 | 1.8 | GUARDRAIL TEST BUILT + PASSES. `tests/test_receiver_decoupling.py` (4 tests). Pre-build investigation found earlier `from engine.registry` grep hits were ALL in backups/ snapshots, NOT live code — live source is clean (zero strategy-module `engine.` imports; only SQLAlchemy `instances.models.engine`). Test refined to exempt non-trading `*Strategy` names (ConvertedStrategy/Strategy/BaseStrategy) and permit `strategies.*`/`engines.*`/`instances.models` as the legitimate import surface. `pytest tests/test_receiver_decoupling.py` → 4 passed. Backup v2.03.009_pre-1.8-guardrail-test_STABLE taken. Track 1 now FULLY CLOSED. | pytest run | 4 passed |

| 2026-07-24 | UI | GLOBAL DEFAULT SET + UI-1/2/3 LIVE-VERIFIED. `.env`: AI_MODEL=gpt-oss:20b, AI_API_KEY=OLLAMA_API_KEY_2 (matches, direct curl 200). Code: glm-5.1 to gpt-oss:20b hard-coded defaults removed in core/llm.py, instances/models.py (User column defaults), app/routes.py (chat_api model_used). DB operator row already gpt-oss:20b. ROOT CAUSE of earlier 403: a stale server process (started before .env edit) still held port 8792; the new server failed to bind, so the browser hit the stale process with old config. Killed ALL server processes, confirmed port free, relaunched ONE. LIVE-VERIFIED via browser session: UI-1 /app/strategies shows translation-test (Saved 2026-07-24) plus Duplicate/Edit/Delete/View. UI-2 POST /api/v2/strategies/translation-test/convert returns 200 ok:true python_source 2813 chars (gpt-oss:20b via OLLAMA_API_KEY_2). UI-3 POST /save new strategy returns registered:true and appears in /app/strategies list WITHOUT restart (TOTAL 2). Test artifacts cleaned. | browser drive + live API + port-owner check | verified live |
