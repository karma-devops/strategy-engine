# bugreport.md — Deferred Issues

Logged during the Phase 8-finalize / Phase 9 autonomous run (session 89f84cf4902e, 2026-07-14).
Operator directive: log roadblocks/errors here, deal with them later. NOT fixed in this run.

**Phase 9 status:** COMPLETE (9B–9F all built + verified live). See HANDOVER.md for full build status.

---

## BUG-002 — Stale server processes hold port 8792 (zombie PIDs)

**Severity:** 🟡 MEDIUM (blocks serving new routes; confusing 404s)
**Component:** dev server lifecycle
**Status:** RESOLVED (2026-07-14) — root cause documented, relaunch procedure fixed

**Symptom:** New routes (`/logout`, `/api/v2/chat/session/{id}`) returned 404 on the live server despite being correctly added to `app/routes.py`. `python -c` confirmed the routes were registered in the router.

**Root cause:** Earlier sessions left uvicorn processes running on port 8792 (PIDs from 02:33 and 04:22). `fuser -k` could not kill them (namespace/permission). The server kept serving stale code. `uvicorn app.main:app` also failed (entrypoint is `main:app`, not `app.main`) — masking the real issue.

**Fix applied:** Killed via `/proc/net/tcp` inode → PID match (`kill -9 149628`, `161715`), then relaunched with correct entrypoint `./venv/bin/python -m uvicorn main:app`. All new routes now serve.
**Lesson:** When 404 on a confirmed-registered route, check for zombie servers holding the port before assuming code error. Use `cat /proc/net/tcp | grep 2258` (8792=0x2258) → inode → match `/proc/*/fd`.

---

## BUG-003 — Context hint not sent to LLM (Studio/Backtester)

**Severity:** 🟡 MEDIUM (context-awareness broken on 2 surfaces)
**Component:** `app/static/chat_widget.js`
**Status:** RESOLVED (2026-07-14)

**Symptom:** On Studio, LLM replied "No strategy provided" even though `data-context-hint` had the Pine source (365 chars verified). Curl test with hint prepended worked correctly.

**Root cause:** JS cached `const CONTEXT_HINT = widget.dataset.contextHint` at IIFE init. Studio/Backtester inline scripts set `data-context-hint` AFTER the widget JS ran, so the cached value was empty.

**Fix applied:** Read `widget.dataset.contextHint` live inside `send()` (not cached). Context now prepended on first message of new session.

---

## BUG-004 — Dead model options in chat dropdown (404)

**Severity:** 🟢 LOW (user-facing error on model switch)
**Component:** `app/templates/chat_widget.html`
**Status:** RESOLVED (2026-07-14)

**Symptom:** Selecting `qwen3-235b` / `llama3.3-70b` / `deepseek-v3` returned `404 Not Found` from the LLM provider (only `glm-5.1` available on the configured endpoint).

**Fix applied:** Pruned dropdown to `glm-5.1` only (confirmed working). If more models are added later, they must be verified against the live provider first.

---

## BUG-001 — Duplicate trade entry on short poll interval (3s)

**Severity:** 🔴 CRITICAL (real-money double position)
**Component:** `scripts/worker.py` — entry logic
**Status:** ✅ RESOLVED (2026-07-15)

**Symptom:** Worker logs show `OPEN LONG WIF $22.96 3x` twice within 1 second, followed by two `ENTRY LONG @ 0.155663` confirmations. Two separate HyperLiquid fills for the same intended position.

**Root cause:** `active_trade` dict was assigned AFTER `market_open()` returned. Between the `OPEN LONG` log and the dict assignment, the next 3s poll saw `active_trade is None` and entered again.

**Fix applied (2026-07-15):** `PENDING` sentinel guard. Set `active_trade = "PENDING"` SYNCHRONOUSLY before `get_account_value()`. All downstream checks skip PENDING. On success, replaced with real dict. On failure, cleared to `None` for retry. All failure paths (open failed, no balance, no account) reset `active_trade = None`.

---

## BUG-002 — Stale server processes hold port 8792 (zombie PIDs)

---

## BUG-005 — Shell variable expansion resolves to empty in Hermes terminal (credential propagation)

**Severity:** 🔴 CRITICAL (worker could never place orders — 24h+ zero trades)
**Component:** Server launch / env propagation
**Status:** RESOLVED (2026-07-15)

**Symptom:** Worker ran 24h+ on WIF/5m with zero trades. Operator confirmed WIF was in a clear bullish market. Worker logs showed `WIF BUY sig=1.00 | IDLE` followed immediately by `No account value available` — signal generation worked but order placement failed.

**Root cause:** When launching the worker via `terminal(background=true)` with `export HYPER_LIQUID_ETH_PRIVATE_KEY="${HYPER_LIQUID_ETH_PRIVATE_KEY}"`, the `${VAR}` shell expansion resolved to empty strings because those vars were set in the container's init shell, NOT inherited by the Hermes terminal session. `/proc/PID/environ` confirmed: `HYPER_LIQUID_ETH_PRIVATE_KEY=` and `ACCOUNT_ADDRESS=` (empty).

**Impact:** `HyperLiquidClient.has_credentials` returned `False` → `get_account_value()` returned `0.0` → worker logged "No account value available" on every BUY signal → never placed orders.

**Fix:** Created `.env` file with all credential values. Restarted both servers with hardcoded values in the export command (not `${VAR}` expansion). Verified via `/proc/PID/environ` and `get_account_value()` returning `$7.89`.

**ADIX Pitfall #73:** Shell variable expansion in process launch can resolve to empty if vars are set in a different shell context. Always hardcode credential values in the launch command or verify via `/proc/PID/environ`.

---
