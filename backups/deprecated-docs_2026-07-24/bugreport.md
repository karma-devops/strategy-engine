# BUGREPORT — strategy-engine (karma-devops)

**Provenance:** Copied verbatim from operator-supplied attachment `BUGREPORT.md` (Handover session, 2026-07-19).
**Original compiled:** 2026-07-19 · **Verified against:** `github.com/karma-devops/strategy-engine`, branch `main` @ `e7709b1`
**Method:** Every item below was checked directly against the live repo (grep/view on actual file contents), not against agent-reported summaries. Where the frontend was substantially rewritten, items are marked UNVERIFIED.

---

## How to read this

- ✅ **FIXED** — confirmed present in current code, with file:line.
- ❌ **OPEN** — confirmed still broken/missing, with file:line.
- 🆕 **NEW** — found this session, not previously tracked.
- ⚠️ **UNVERIFIED** — flagged in an earlier pass, frontend has since been substantially rewritten (app.js and dashboard.html's old JS are gone, replaced by a multi-page `app/templates/*.html` structure), and not re-checked against the new code. Needs a fresh look.

---

## ✅ CONFIRMED FIXED

| # | Item | Evidence |
|---|------|----------|
| 1 | `/logs` + `/stream` had no auth | `main.py:174` — `stream.router` now behind `Depends(verify_ui_credentials)` |
| 2 | Withdrawal scheduler ignored kill switch | `withdrawal/scheduler.py:20,56` — `is_withdrawal_killed(db)` checked before execution |
| 3 | Dry-run withdrawals marked `"completed"` | `withdrawal/scheduler.py:110-120`, `withdrawal/manual.py:45-54,94` — status branches on `result.get("status") != "dry_run"` |
| 6 | Runner didn't check kill switch mid-tick | `instances/runner.py:201-205` — `is_global_killed(db)` checked at top of `_tick()`, skips order logic |
| 7 | `EventBus._listeners` unguarded across threads | `instances/events.py:14` — `threading.Lock()` added |
| 8 | `LOG_BUFFER` unguarded across threads | `instances/events.py:40` — `LOG_BUFFER_LOCK` added |
| 9 | Alerts re-created duplicates on every evaluation | `monitoring/alerts.py:32-44` — dedup check against existing non-dismissed alert before insert |
| 10 | Account snapshot queries had no `order_by`, "latest" was arbitrary | `api/metrics.py:38,71` — `order_by(...timestamp.desc())` now explicit |
| 12 | Rotation approval didn't apply the suggested allocation | `monitoring/rotator.py:93-94` — `inst.max_position_pct = row.suggested_allocation_pct / 100.0` now happens on approve |
| 14 | Rate limiter ignored `api_key_or_ip`, IP-only bucket | `api/ratelimit.py:36` — `Limiter(key_func=api_key_or_ip)` |
| 15 | `delete_instance` could orphan an open position | `api/instances.py:676-684` — force-closes position before delete |
| 16 | Create-instance form defaulted to LIVE trading | `app/routes.py:350` — `dry_run: bool = Form(True)` |
| 17 | No slug validation on the UI create route | `app/routes.py:362` — `re.match(r"^[a-z0-9-]{1,32}$", slug)` |
| 18 | `market_data.py` fetched a wasteful fixed 60-day window every tick | `core/market_data.py:85-104` — computes `startTime` from `bars`, drops unsupported `limit` key |
| 19 | `WithdrawalConfig.next_scheduled_at` never written | `withdrawal/scheduler.py:78` — now persisted |
| 41 | No kill-switch control in the UI | `app/templates/dashboard.html:530-536` — kill-all button wired to `POST /api/v2/kill` |
| 42/43 | Two competing dashboards (`/shell` vs `/`) | `/shell` route and `app-shell.html` are both gone — resolved by deletion, not by finishing it |
| 44 | Login redirected to nonexistent `/dashboard` | `app/routes.py:175` — `/app/dashboard` is now a real route; `landing.html` redirects there correctly |
| 62 | `sw.js` referenced nonexistent `/static/pages.js`, breaking the entire cache install | `app/static/sw.js:3-8` — `ASSETS` list is now clean (`/`, `tokens.css`, `style.css`, `manifest.json`) |

**Also confirmed correct-as-is (no change needed, verified defensively):**
- `start_instance` API return value propagation
- `_persist_status` fresh-query pattern (not a blind merge)

---

## ❌ CONFIRMED STILL OPEN

| # | Item | Evidence |
|---|------|----------|
| — | **Dashboard hardcoded credentials, no fail-fast** | `config.py:19-20` — `DASHBOARD_USERNAME`/`PASSWORD` still default to `"operator"`/`"operator"` if env vars unset. Never added to BACKLOG.md. Needs a line item + boot-time `raise` if unset. |
| — | **`data/` directory crash on fresh deploy** | Fresh clone + `python main.py` → `sqlite3.OperationalError: unable to open database file`. Nothing creates `data/`. Never tracked. |
| — | Circuit breaker (P0) | `grep -rn "error_consecutive\|circuit_break"` → zero hits. Correctly tracked as open in BACKLOG.md. |
| 32 | "6-Engine Default Fleet" UI copy still says 6, fleet is 1 | `app/templates/instance_form.html:19` — `<optgroup label="6-Engine Default Fleet">` unchanged. `engine/registry.py:17-22` `DEFAULT_FLEET` still has exactly one entry (`engine-1`). |
| 54 | `WithdrawalRecord` — no idempotency key | `instances/models.py:314-326` — no unique constraint / idempotency field. Concurrent withdraws can double-execute. |
| 64 | `instance_form.html` strategy dropdown missing `engine_v6_1` | `app/templates/instance_form.html:50-51` — only lists `engine_v1_3` and `engine_v1`. |
| 65 | Per-strategy presets endpoint unwired | `app/static/instance_form.js:6` — only calls `/api/v2/presets/fleet`; `GET /strategies/{id}/presets` has no caller. Dead backend code. |

---

## 🆕 NEW — The 3-Port Architecture (`strategy_config` / `entry_config` / `exit_config`)

This is genuinely new work since the last full pass. Full trace below.

### What's actually working
- **Port 3 (`exit_config`)** is a real, consistently-honored contract. `instances/runner.py` reads `result["exit_config"]` at four separate call sites (position adopt, side-flip, exit-check, trail-check) — genuinely a "neutral consumer," not decorative.
- **Port 1 (`strategy_config`)** is wired end-to-end on the *live-trading* path: DB column (`instances/models.py:202`) → `GET`/`PUT /instances/{id}/strategy-config` (`api/instances.py:409-445`) → `instances/runner.py:182-183` correctly reads `instance.strategy_config` and calls `strategy_class(**strategy_config)`.
- `engine_v1_3` applies kwargs overrides correctly via `BaseStrategy.__init__`'s properly-written `setattr(self, key, val)`.

### What's broken

**1. `engine_v6_1` crashes on any config override.**
`engine/v6_1.py:97`:
```python
setattr(self, k)   # missing the value argument
```
`get_parameters()` declares 13 params, all pre-existing instance attributes, so `hasattr(self, k)` is true for every one of them — meaning **any non-empty `strategy_config` saved for a v6.1 instance will `TypeError`-crash that instance on next start**, not silently no-op.

**2. `engine_v1` has the same bug in its fallback branch.**
`engine/v1.py` (~line 88): the `elif hasattr(self, k): setattr(self, k)` branch has the identical missing-argument typo.

**3. `PUT .../strategy-config` does zero validation.** `api/instances.py:411-423` — accepts any arbitrary `dict`, writes it straight to the DB with no check against `get_parameters()` names/types.

**4. Saving `strategy_config` on a running instance has no effect until restart.** It's read once, at thread start, in `_run_once()`. No API call or UI flow triggers a restart after save.

**5. Backtests never use `strategy_config`.** `backtests/runner.py:389` — `strategy = strategy_cls()`, zero args, always. Live/backtest parity is broken.

**6. The Pine→Python converter's system prompt contradicts the real contract — this is the dangerous one.** `core/llm.py:83-94` instructs the LLM to put `stop_loss_long/short`, `take_profit_long/short` **inside `metadata`**. But the runner reads those fields from a **separate top-level `exit_config` key**. The prompt never mentions `exit_config`, `get_parameters()`, or `**kwargs` at all.
**Net effect: any strategy generated via Strategy Studio's "Pine → Python Converter" will generate entry signals correctly but silently trade with no stop-loss, no take-profit, and no trailing stop — ever.** This is the single highest-priority fix in this report.

**7. No UI surface exists for Port 1 at all.**
   - `engine_detail.html`'s "⚙ Settings" modal only edits `name/token/strategy_id/timeframe/leverage/max_position_pct/dry_run/start_balance` via the generic `PUT /instances/{id}` — zero fields from `get_parameters()`.
   - `strategy_detail.html`'s "Parameters" section (`lines 61-71`) is **read-only**.
   - `grep -rl "strategy-config" app/templates/` → **zero matches**.
   - `docs/FAQ.md` describes a flow that does not exist in any shipped template.

---

## ⚠️ UNVERIFIED — needs a fresh pass against the rewritten frontend

True against the *old* frontend; do not assume either way against the current one without re-checking:
- XSS-escaping consistency on user-editable fields rendered into `innerHTML`
- Fleet-wide alerts visibility / badge
- Fleet-wide "Evaluate Alerts" trigger vs per-instance only
- Testing Pool UI presence (there's now a `testing_*.html` set — may have closed this gap; not checked)
- Rotation approve/apply UI clarity
- Confirmation step for Dry Run → LIVE toggle
- API-key-not-configured banner
- Loading/error/empty state consistency across tabs
- Mobile responsive layout
- `landing.html` — the specific broken-login-flow bug (synchronous redirect firing before the fetch resolves) — the redirect target itself is now fixed, but the fetch-before-navigate race is not re-checked
- `spec.html` — still likely dead weight, not re-checked

---

## 🆕 SESSION 2 — New findings (credentials, auth, multi-tenancy)

Scope: `api/credentials.py`, `instances/models.py` (`Credential`, `User`), `app/routes.py` (login/signup), `api/auth.py`, `app/paper_routes.py`, `app/backtest_routes.py`, `app/_common.py`.

### Access control

**8. `/api/v2/credentials/*` collapses the shared dashboard key into the operator identity.** `api/credentials.py:39-49` (`_current_user_id`): if the caller's `X-API-Key` doesn't start with `puls_` (i.e. it's the single global `AGENT_API_KEY` — which is what `window.API_KEY` in every dashboard page uses), the function falls back to `get_or_seed_operator(db).id`. This means **anyone holding the one shared dashboard API key has full list/create/update/delete access to the operator's stored credentials** — including decrypted private keys, HL API keys, and AI provider keys (`POST /{id}/test` even round-trips the decrypted value). Given `AGENT_API_KEY` is embedded in page source (`window.API_KEY`) on every dashboard page, this widens the blast radius of a key leak from "can place trades" to "can exfiltrate every stored private key."

**9. `test_credential` reports invalid AI-provider credentials as passing.** `api/credentials.py:166`:
```python
return {"ok": r.status_code in (200, 401), "status_code": r.status_code}
```
HTTP 401 means the provider explicitly rejected the API key — the one status code that should never read as `"ok": True`.

### Cross-tenant data leak (regression from the "Z1 route split" refactor)

**10. `app/paper_routes.py:testing_paper` (`/app/testing/paper`)** — line 46: `user = get_or_seed_operator(db)`, unconditionally. Every signed-up user who opens the Paper Trading page sees the **operator's** instances, equity curve, and trades. Compare to `app/routes.py` (lines ~180, 573, 694, 1019, 1060), which correctly does `db.query(User).filter(User.username == username).first()`.

**11. `app/backtest_routes.py:testing_historical` (`/app/testing/historical`)** — line 59: `db.query(Backtest).filter(Backtest.kind == "backtest")` with **no user filter at all**. Every logged-in user sees every backtest ever run by every user.

**Recommend auditing every router touched by the "Z1 route split"** (`app/paper_routes.py`, `app/backtest_routes.py`, and `app/routes.py` for leftover `get_or_seed_operator(db)` calls — 20 total call sites, only spot-checked) for the same pattern before treating multi-tenancy as functional.

### Auth/crypto hygiene

**12. Login and signup have no rate limiting.** `app/routes.py:35` (`POST /login`) and `:60` (`POST /signup`) — neither has a `@limiter.limit(...)` decorator.

**13. `User.email` has no DB-level unique constraint.** `instances/models.py` — only `username` is `unique=True`; `email` relies solely on the app-level pre-check in `signup_post`, a check-then-insert race.

**14. No exception handling around `db.commit()` in `signup_post`.** If a race slips a duplicate `username` past the pre-check, the DB's unique constraint raises `IntegrityError` uncaught — raw 500 instead of friendly response.

**15. Session cookie signature uses hand-rolled `sha256(token + secret)` instead of `hmac.new()`.** `api/auth.py:28`, mirrored in `app/routes.py:51,109`. Functional today but non-standard MAC construction.

**16. `Credential.encrypt_and_store`/`.decrypt` serialize via `str(dict)` + `ast.literal_eval()` instead of `json.dumps`/`json.loads`.** `instances/models.py:113,132-133`. Fragile, non-standard for encrypting structured secrets.

---

## Priority order

1. **Converter system prompt (`core/llm.py`)** — fix the `exit_config` vs `metadata` mismatch. Everything generated through Strategy Studio until this is fixed trades with no exits, silently.
2. **Credentials access control (#8)** — the shared `AGENT_API_KEY` should not resolve to full CRUD over the operator's decrypted private keys.
3. **Cross-tenant data leak in Paper Trading / Historical Backtests (#10, #11)** — real user-facing privacy bug the moment a second person signs up. Plus the 20-call-site audit of `get_or_seed_operator`.
4. **`setattr(self, k)` → `setattr(self, k, v)`** in `v6_1.py` and the fallback branch in `v1.py` — two-character fixes, unblocks Port 1 for 2 of 3 engines.
5. **Dashboard credential fail-fast** + **`data/` directory creation** — both "never tracked," both trivial, both bite on next fresh deploy.
6. **Circuit breaker (P0)** — correctly tracked, still the biggest genuinely-unstarted safety item.
7. Wire an actual Strategy Parameters form (Port 1) into the UI, validate `PUT .../strategy-config` against `get_parameters()`, and trigger a restart on save.
8. Fix `backtests/runner.py:389` to pass `strategy_config` the same way the live runner does.
9. Login/signup rate limiting (#12) — cheap, closes an open brute-force/spam surface.
10. `#32` copy fix, `#54` withdrawal idempotency, `#64`/`#65` instance-form gaps, `test_credential` 401 handling (#9), `email` unique constraint (#13), signup exception handling (#14) — lower stakes, do after the above.
11. HMAC hygiene (#15), JSON serialization for credentials (#16) — no demonstrated exploit, fix opportunistically.
12. Re-verify the ⚠️ UNVERIFIED list against the current frontend before assuming any of it is still accurate.
