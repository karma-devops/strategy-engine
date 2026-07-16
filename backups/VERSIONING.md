# Backups — strategy-engine

## Conventions
- Slugs: `(version)_(info-context)_(timestamp)/`
- `STABLE` in caps marks a verified restore point
- One backup per phase, before any live edit
- If a live edit breaks, revert to last STABLE
- Python projects: tar.gz with venv/__pycache__/*.pyc/data/*.db excluded

### `v97_phase18-auth-fix_STABLE_2026-07-16_1645` — **LATEST STABLE**

**State:** Phase 18 auth fix complete. `/api/v2/users/me/api-key` and `/regenerate` now accept either Basic Auth or X-API-Key (global or PULS-R per-user). Fixed latent bug: `require_ui_or_api` had `config.AGENT_API_KEY` (wrong) → `config.AGENT_API_KEY` (correct). All 6 auth modes verified.

**Files changed:** `api/auth.py` (require_ui_or_api + AGENT_API_KEY fix), `app/routes.py` (import + decorator change)

**Verified:** Basic-only ✅, API-key-only ✅, PULS-R-key-only ✅, Both ✅, No-auth 401 ✅, Regenerate ✅, Old-key-revoked 401 ✅

### `v96_pre-phase18-auth_2026-07-16_1627`

**State:** Pre-P6 backup. Server running with dry_run fix (v0.095+), DRY_RUN=false global, instances dry_run=true.

### `v94_dry-run-fix_STABLE_2026-07-16_1600`

**State:** Dry-run architecture fix applied. `get_hyperliquid_client()` now respects `instance.dry_run` even when using global credentials.

## Versions

### `v96_phase18-auth-fix_STABLE_2026-07-16_1645` — **LATEST STABLE**

**State:** Phase 18 auth fix complete. `/api/v2/users/me/api-key` + `/regenerate` accept either Basic Auth or X-API-Key (global or PULS-R). 8/8 auth combinations verified. Endpoints moved from ui_routes to main.py to bypass router-level verify_ui_credentials.
**Files changed:** api/auth.py, app/routes.py, main.py
**Git:** b3cbfa4
**Verified:** 8/8 auth tests pass. Fresh DB from template. Server health 200.

### `v94_dry-run-fix_STABLE_2026-07-16_1600`

**State:** Dry-run architecture fix applied. `get_hyperliquid_client()` now respects `instance.dry_run` even when using global env credentials. `.env` DRY_RUN changed to false (global = always live/connected). Git committed (b568f72, 0bc4da9, 7a2046d). All 14 UI routes + 16 API endpoints verified 200. Backtest engine verified (+28.78% FARTCOIN 7d).
**Contents:** All app templates, CSS, JS, routes, models, strategies, scripts, exchange.py (patched), config.py, .gitignore.
**Verification:** py_compile clean, 1,167,689 bytes, git clean.
**Known issues:** Phase 18 auth fix pending (P6). Server not yet restarted with new code.

### `v82_phase10a_STABLE_2026-07-14_0540`
**State:** Phase 10A complete. Chat widget restyle (brand tokens), user dropdown+logout, session reload, BUG-003/004 fixed, mobile overlap fix.
**Contents:** All app templates, CSS, JS, routes, models, strategies, scripts.
**Verification:** 8/8 live browser tests PASS (Assistant, Studio, Backtester, Dashboard send+reply, memory, session reload, CSS tokens, model dropdown).

### `v83_credfix_2026-07-15`
**State:** Credential fix + server restart. `.env` created, both servers restarted with proper HL creds, fresh DB.
**Contents:** Same as v82 + `.env` file. No code changes — env/operational fix only.
**Verification:** `get_account_value()` returns `$7.89`, worker shows `BUY sig=1.0` with no "No account value" errors. — **LATEST STABLE**
**State:** Phase 10A complete + verified. User dropdown (Account/Secrets/Settings/Logout) + `/logout` route, context hint live-read fix (BUG-003), Assistant full-page (no bubble, UX-001), session reload endpoint + JS (C1), model dropdown pruned to glm-5.1 (BUG-004), mobile-nav/chat overlap fix (UX D).
- `layout.html`: user menu button + dropdown CSS/JS + `/static/chat_widget.css` link moved to shared shell
- `app/routes.py`: `/logout` (401), `/api/v2/chat/session/{id}` (messages)
- `app/templates/assistant.html`: `chat-fullpage` class (no bubble)
- `app/static/chat_widget.js`: live context hint + session reload fetch
- `app/templates/chat_widget.html`: model dropdown pruned to glm-5.1
- `app/static/chat_widget.css`: mobile media query (clears 56px bottom nav)
- Server entrypoint: `main:app` (NOT `app.main`)
- Live-verified: all 4 surfaces fire + reply, context-awareness works, session reload works, on-brand CSS

### `v79_phase9f_context_STABLE_2026-07-14_0430`
**State:** Phase 9 complete (9B→9F all verified). Per-user model selection, per-user memory (10-session cap), shared chat widget on 4 surfaces, context-awareness.
- `User.assistant_model` + `coder_model` (default `glm-5.1`) + migration spec.
- `core/llm.py chat()` resolves model: override > user pref > env > glm-5.1. `convert_pine_to_python` uses `model_role="coder"`.
- `ChatSession` + `ChatMessage` tables; `/api/v2/chat` POST + `/api/v2/chat/sessions` GET.
- `chat_widget.html/css/js` on Studio, Backtester, Dashboard (slim), Assistant (full page).
- Context hints: Studio = Pine source + strategy name; Backtester = latestStats (return, WR, PF, DD, Sharpe, trades, status).
**Verification:** live GLM-5.1 replies, memory recall in same session, 10-session cap, browser-verified all 4 surfaces + context hints.
**Known issues:** BUG-001 (duplicate poll) deferred. Send button CSS fixed (flex inline layout).

### `v74_phase8a_hl_credential_STABLE_2026-07-14_0330`
**State:** Phase 8A complete + verified. Per-engine HL credential selector wired end-to-end:
- `Instance.get_resolved_hl_credentials()` resolves `hl_credential_id` → `Credential` row (decrypt), falls back to instance key, then `None`=Global.
- `core/exchange.py get_hyperliquid_client` calls the resolver.
- `api/instances.py UpdateInstanceRequest` accepts `hl_credential_id`; PUT persists via generic setattr loop.
- `app/routes.py engine_detail_page` passes `hl_credentials` + `hl_credential_id`; `Credential` import added.
- `engine_detail.html` settings modal: HL Account `<select>` (Global + Main/Secondary/Tertiary) + JS `saveSettings` sends `hl_credential_id`.
**Verification:** health ok (dry_run=true); `/app/engines/engine-1` → 200; PUT `hl_credential_id:null` → ok + persisted as None. py_compile clean on all 4 touched files.
**Contents:** full project tar (code only, no venv/db).
**Known issues:** none for this phase. (BUG-001 duplicate-entry on worker 3s poll = deferred, see bugreport.md.)
v89 | engine-settings-mobile | 2026-07-15 1650 | engine_detail.html: settings button top, modal scroll fix, mobile CSS | VERIFIED

### `v93_phases9-12-complete_STABLE_2026-07-16_0800` — **LATEST STABLE**
**State:** Phases 9-12 complete. Clone/activate, Python upload, v1+v6.1 params, worker config. 11/11 tests pass.
**Changes:** Strategy clone+activate API, Python upload tab, v1/v6.1 get_parameters(), worker strategy_config endpoints, strategy params UI in worker.
**Backup:** v93_phases9-12-complete_STABLE_2026-07-16_0800.tar.gz (712KB)

### `v92_pre-phase9-clone_STABLE_2026-07-16_0600`
**State:** Phases 1-8 complete + settings modal full round-trip verified. 15 params save/load correctly.
**Backup:** v91 was Phases 1-8 API endpoints. This adds verified frontend settings flow.
**Files changed from v91:** `engine_detail.html` (save flow verified), `app/routes.py` (strategy_config/parameters in template context)emplate.
**Contents:** Full project tar.gz (code only, no venv/db/logs).
**Files changed since v89:**
- `engine/base.py`: `get_parameters()` + `get_default_config()` + kwargs support
- `engine/v1_3.py`: dual-mode (Swing+Scalp), 6 risk profiles, mode-aware params, `get_parameters()` (15 params), `trail_exit_grace_seconds` removed
- `scripts/worker.py`: equity_history trade-close only, grace removed, one-entry-per-bar guard
- `instances/runner.py`: same 3 fixes + `strategy_config` applied at instantiation
- `instances/models.py`: `strategy_config` JSON + `snapshot_data`/`snapshot_image_url`/`snapshot_at` columns + migration
- `api/strategies.py`: GET `/strategies/{id}/parameters` endpoint
- `api/instances.py`: GET/PUT `/instances/{slug}/strategy-config` endpoints
- `app/routes.py`: `get_strategy` import, `strategy_config` + `strategy_parameters` passed to engine detail
- `app/templates/engine_detail.html`: dynamic settings panel (15 params from `get_parameters()`)
**Verification:** 61/61 tests PASS (health, strategy API, instances, strategy-config CRUD, 12 UI routes, engine detail HTML, metadata, stats, swagger, strategy instantiation x19, DB schema). Browser-verified: 15 `data-param` fields in modal DOM.
**Clean slate:** All processes killed, HL positions closed, `template_empty_STABLE.db` saved, `dev_test.db` fresh from template.
**Known issues:** None. Phases 9-10 pending (Studio clone, Python upload, multi-tenant, live test).

---

## Aetheris Session (2026-07-16, e3f7461df4ce)

### `v200_a2-lightweight-charts-library_2026-07-16_1500` — **LATEST**
**State:** Pre-add of TradingView Lightweight Charts v5.2.0 + PulsRChart wrapper. 
**Files:** app/templates/layout.html, app/templates/testing_paper.html, app/static/tokens.css, app/static/style.css
**Change:** none yet — this is the pre-edit snapshot
**Sprint A:** Foundation. Sprint B: paper-trading pilot (operator chose this as the redesign anchor).

## Active Series — UI/UX Redesign (operator choice: full project, starting with paper trading, using lightweight-charts)

### `v104_pt1.1-fleet-clickable-sparks_2026-07-16_1440` (earlier this session)
**State:** Pre Part 1.1 — clickable fleet cards + sparkline container
**Files:** app/templates/testing_paper.html
**Committed:** f1ee4c0 (combined with later commits)
