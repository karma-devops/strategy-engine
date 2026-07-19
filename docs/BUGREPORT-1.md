# BUGREPORT — strategy-engine (karma-devops)
**Compiled:** 2026-07-19 · **Verified against:** `github.com/karma-devops/strategy-engine`, branch `main` @ `e7709b1`
**Method:** Every item below was checked directly against the live repo (grep/view on actual file contents), not against agent-reported summaries. Where I couldn't re-verify against the rewritten frontend, it's marked explicitly — don't treat those as confirmed either way.

---

## How to read this

- ✅ **FIXED** — confirmed present in current code, with file:line.
- ❌ **OPEN** — confirmed still broken/missing, with file:line.
- 🆕 **NEW** — found this session, not previously tracked.
- ⚠️ **UNVERIFIED** — flagged in an earlier pass, frontend has since been substantially rewritten (app.js and dashboard.html's old JS are gone, replaced by a multi-page `app/templates/*.html` structure), and I have not re-checked this specific item against the new code. Needs a fresh look before anyone acts on it.

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
| — | **Dashboard hardcoded credentials, no fail-fast** | `config.py:19-20` — `DASHBOARD_USERNAME`/`PASSWORD` still default to `"operator"`/`"operator"` if env vars unset. **This was in my very first report and has never been added to BACKLOG.md.** Needs a line item + boot-time `raise` if unset. |
| — | **`data/` directory crash on fresh deploy** | Reproduced independently: fresh clone + `python main.py` (or Docker build/run) → `sqlite3.OperationalError: unable to open database file`. Nothing creates `data/` — not `Dockerfile`, not any startup code. **Also never tracked.** |
| — | Circuit breaker (P0) | `grep -rn "error_consecutive\|circuit_break"` → zero hits anywhere. Correctly tracked as open in BACKLOG.md. |
| 32 | "6-Engine Default Fleet" UI copy still says 6, fleet is 1 | `app/templates/instance_form.html:19` — `<optgroup label="6-Engine Default Fleet">` unchanged. `engine/registry.py:17-22` `DEFAULT_FLEET` still has exactly one entry (`engine-1`). BACKLOG.md marks the *decision* as locked ("seed engine-1 only, fix copy") but the copy itself was never actually changed. |
| 54 | `WithdrawalRecord` — no idempotency key | `instances/models.py:314-326` — no unique constraint / idempotency field on the model. Nothing stops two concurrent withdraw actions from double-executing before the first resolves. |
| 64 | `instance_form.html` strategy dropdown missing `engine_v6_1` | `app/templates/instance_form.html:50-51` — only lists `engine_v1_3` and `engine_v1`. `engine_v6_1` exists and has its own `get_parameters()` but isn't selectable from the create-instance UI. |
| 65 | Per-strategy presets endpoint unwired | `app/static/instance_form.js:6` — only calls `/api/v2/presets/fleet`; `GET /strategies/{id}/presets` still has no caller anywhere in the frontend. Dead backend code. |

---

## 🆕 NEW — The 3-Port Architecture (`strategy_config` / `entry_config` / `exit_config`)

This is genuinely new work since my last full pass — a real architecture exists now (`docs/DOCUMENTATION.md` §2.2-2.3, `docs/FAQ.md`), and parts of it work well. Full trace below.

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
`engine/v1.py` (~line 88): the `elif hasattr(self, k): setattr(self, k)` branch has the identical missing-argument typo. Lower probability (only hit when a key doesn't match the uppercase-constant branch checked first) but same defect.

**3. `PUT .../strategy-config` does zero validation.** `api/instances.py:411-423` — accepts any arbitrary `dict`, writes it straight to the DB with no check against `get_parameters()` names/types.

**4. Saving `strategy_config` on a running instance has no effect until restart.** It's read once, at thread start, in `_run_once()`. No API call or (nonexistent) UI flow triggers a restart after save — an operator can save a valid config, get a success response, and the running engine keeps trading on the old one indefinitely.

**5. Backtests never use `strategy_config`.** `backtests/runner.py:389` — `strategy = strategy_cls()`, zero args, always. Backtesting a "customized" instance actually tests the engine's hardcoded defaults every time. Live/backtest parity is broken.

**6. The Pine→Python converter's system prompt contradicts the real contract — this is the dangerous one.**
`core/llm.py:83-94` instructs the LLM to put `stop_loss_long/short`, `take_profit_long/short` **inside `metadata`**. But the runner reads those fields from a **separate top-level `exit_config` key** (see Port 3 above). The prompt never mentions `exit_config`, `get_parameters()`, or `**kwargs` at all.
**Net effect: any strategy generated via Strategy Studio's "Pine → Python Converter" will generate entry signals correctly but silently trade with no stop-loss, no take-profit, and no trailing stop — ever.** Not a crash. Not visible in testing unless someone specifically checks whether exits fire. This is the single highest-priority fix in this report.

**7. No UI surface exists for Port 1 at all.** Checked every template:
   - `engine_detail.html`'s "⚙ Settings" modal only edits `name/token/strategy_id/timeframe/leverage/max_position_pct/dry_run/start_balance` via the generic `PUT /instances/{id}` — zero fields from `get_parameters()`.
   - `strategy_detail.html`'s "Parameters" section (`lines 61-71`) is **read-only** — displays legacy `preset.mode/profile/timeframe/activation/offset`, no form, no inputs.
   - `grep -rl "strategy-config" app/templates/` → **zero matches**, anywhere.
   - `docs/FAQ.md` describes a flow ("Open the engine detail page → ⚙ Edit Settings → 'Strategy Parameters' section") that does not exist in any shipped template. The docs describe the intended feature; it was never built on the frontend.

---

## ⚠️ UNVERIFIED — needs a fresh pass against the rewritten frontend

The frontend was substantially rewritten since these were originally flagged (`app.js`/old `dashboard.html` are gone, replaced by `engines.html`, `engine_detail.html`, `strategy_detail.html`, `strategy_studio.html`, `testing_*.html`, `chat_widget.*`, `assistant.html`, etc.). These items were true against the *old* frontend; do not assume either way against the current one without re-checking:

- XSS-escaping consistency on user-editable fields rendered into `innerHTML`
- Fleet-wide alerts visibility / badge
- Fleet-wide "Evaluate Alerts" trigger vs per-instance only
- Testing Pool UI presence (there's now a `testing_*.html` set of templates — may have closed this gap; not checked)
- Rotation approve/apply UI clarity
- Confirmation step for Dry Run → LIVE toggle
- API-key-not-configured banner
- Loading/error/empty state consistency across tabs
- Mobile responsive layout
- `landing.html` — the specific broken-login-flow bug (synchronous redirect firing before the fetch resolves) — the redirect target itself is now fixed (`/app/dashboard` exists), but I have not re-checked whether the fetch-before-navigate race is still there
- `spec.html` — still likely dead weight, not re-checked

---

## 🆕 SESSION 2 — New findings (credentials, auth, multi-tenancy)

Scope: `api/credentials.py`, `instances/models.py` (`Credential`, `User`), `app/routes.py` (login/signup), `api/auth.py`, `app/paper_routes.py`, `app/backtest_routes.py`, `app/_common.py`.

### Access control

**8. `/api/v2/credentials/*` collapses the shared dashboard key into the operator identity.**
`api/credentials.py:39-49` (`_current_user_id`): if the caller's `X-API-Key` doesn't start with `puls_` (i.e. it's the single global `AGENT_API_KEY` — which is what `window.API_KEY` in every dashboard page uses), the function falls back to `get_or_seed_operator(db).id`. This means **anyone holding the one shared dashboard API key has full list/create/update/delete access to the operator's stored credentials** — including decrypted private keys, HL API keys, and AI provider keys (`POST /{id}/test` even round-trips the decrypted value). The file's own docstring calls this "multi-tenant, encrypted, user-scoped," but the isolation only holds for `puls_`-prefixed per-user keys; the operator's own secrets are reachable by the app-wide key. Given `AGENT_API_KEY` is embedded in page source (`window.API_KEY`) on every dashboard page, this widens the blast radius of a key leak from "can place trades" to "can exfiltrate every stored private key."

**9. `test_credential` reports invalid AI-provider credentials as passing.**
`api/credentials.py:166`:
```python
return {"ok": r.status_code in (200, 401), "status_code": r.status_code}
```
HTTP 401 means the provider explicitly rejected the API key — this is the one status code that should never read as `"ok": True`. A user who pastes a bad key gets a green checkmark.

### Cross-tenant data leak (regression from the "Z1 route split" refactor)

The app now has real multi-user signup/login (`app/routes.py:35-115`) with signed session cookies correctly validated in `api/auth.py:21-48`. But two of the routers that got split out during that refactor never picked up per-session user scoping:

**10. `app/paper_routes.py:testing_paper` (`/app/testing/paper`)** — line 46: `user = get_or_seed_operator(db)`, unconditionally. It never resolves the actual logged-in user from the `username` string that `verify_ui_credentials` already returns. Every signed-up user who opens the Paper Trading page sees the **operator's** instances, equity curve, and trades — not their own. Compare to `app/routes.py` (lines ~180, 573, 694, 1019, 1060), which correctly does `db.query(User).filter(User.username == username).first()` in the same situation — the fix pattern already exists elsewhere in the codebase, it just didn't make it into this file during the split.

**11. `app/backtest_routes.py:testing_historical` (`/app/testing/historical`)** — line 59: `db.query(Backtest).filter(Backtest.kind == "backtest")` with **no user filter at all**, not even the operator fallback. Every logged-in user sees every backtest ever run by every user on the platform.

**Recommend auditing every router touched by the "Z1 route split"** (`app/paper_routes.py`, `app/backtest_routes.py`, and check `app/routes.py` itself for any leftover `get_or_seed_operator(db)` call sitting where a session-derived user should be — 20 total call sites to `get_or_seed_operator` across the app layer, only spot-checked here, not all individually verified) for the same pattern before treating multi-tenancy as functional.

### Auth/crypto hygiene

**12. Login and signup have no rate limiting.** `app/routes.py:35` (`POST /login`) and `:60` (`POST /signup`) — neither has a `@limiter.limit(...)` decorator, unlike the paired GET page routes which do. Unlimited credential-stuffing attempts against `/login`, unlimited automated account creation against `/signup`.

**13. `User.email` has no DB-level unique constraint.** `instances/models.py` — only `username` is `unique=True`; `email` relies solely on the app-level pre-check in `signup_post`, which is a check-then-insert race. Two concurrent signups with the same email can both pass the check and both commit.

**14. No exception handling around `db.commit()` in `signup_post`.** If a race does slip a duplicate `username` past the pre-check, the DB's unique constraint raises `IntegrityError` uncaught — the user gets a raw 500 instead of the friendly "Username already taken" response the pre-check was trying to provide.

**15. Session cookie signature uses hand-rolled `sha256(token + secret)` instead of `hmac.new()`.** `api/auth.py:28`, mirrored in `app/routes.py:51,109`. Functional today (properly checked with `secrets.compare_digest`, and secret-as-suffix isn't susceptible to the classic length-extension forgery the secret-as-prefix version would be), but it's a non-standard MAC construction where the standard library's `hmac` module exists specifically to avoid this class of mistake. Worth swapping for hygiene even without a demonstrated exploit.

**16. `Credential.encrypt_and_store`/`.decrypt` serialize via `str(dict)` + `ast.literal_eval()` instead of `json.dumps`/`json.loads`.** `instances/models.py:113,132-133`. Works for plain string values today, but it's a fragile, non-standard choice for encrypting structured secrets (private keys, API keys) — any future value type that doesn't round-trip cleanly through Python's `repr()` (e.g. anything containing unusual escape sequences) silently corrupts on decrypt. Switch to JSON.

---

## Priority order

1. **Converter system prompt (`core/llm.py`)** — fix the `exit_config` vs `metadata` mismatch. Everything generated through Strategy Studio until this is fixed trades with no exits, silently.
2. **Credentials access control (#8)** — the shared `AGENT_API_KEY` should not resolve to full CRUD over the operator's decrypted private keys. Money-adjacent, silent, and the blast radius of a routine key leak is currently much bigger than it should be.
3. **Cross-tenant data leak in Paper Trading / Historical Backtests (#10, #11)** — real user-facing privacy bug the moment a second person signs up. Also worth the 20-call-site audit of `get_or_seed_operator` before calling multi-tenancy done.
4. **`setattr(self, k)` → `setattr(self, k, v)`** in `v6_1.py` and the fallback branch in `v1.py` — two-character fixes, unblocks Port 1 for 2 of 3 engines.
5. **Dashboard credential fail-fast** + **`data/` directory creation** — both are "never tracked," both are trivial, both will bite on the next fresh deploy.
6. **Circuit breaker (P0)** — correctly tracked, still the biggest genuinely-unstarted safety item.
7. Wire an actual Strategy Parameters form (Port 1) into the UI, validate `PUT .../strategy-config` against `get_parameters()`, and trigger a restart on save.
8. Fix `backtests/runner.py:389` to pass `strategy_config` the same way the live runner does.
9. Login/signup rate limiting (#12) — cheap, closes an open brute-force/spam surface.
10. `#32` copy fix, `#54` withdrawal idempotency, `#64`/`#65` instance-form gaps, `test_credential` 401 handling (#9), `email` unique constraint (#13), signup exception handling (#14) — lower stakes, do after the above.
11. HMAC hygiene (#15), JSON serialization for credentials (#16) — no demonstrated exploit, fix opportunistically.
12. Re-verify the ⚠️ UNVERIFIED list against the current frontend before assuming any of it is still accurate.
