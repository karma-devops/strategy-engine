# HANDOVER PROMPT — strategy-engine (continue in fresh session)

Use this verbatim to resume in a new Hermes session.

---

## Resume context

**Repo:** `/workspace/projects/strategy-engine/main` (git branch `main`, remote `origin` = github.com/karma-devops/strategy-engine.git)
**Server:** uvicorn on `:8792`. Public proxy: `https://hermes-ui.6cdzen.easypanel.host` (proxies localhost — NOT a separate deploy). Basic Auth is supervisor-injected, NOT `operator/***` (the `.env` DASHBOARD_PASSWORD differs; API calls from terminal need the real supervisor creds or drive code in-process).
**Live HL account:** `0xA871D51A9D3Cf670c41FB53CDEe3822c51FD8078` (operator MetaMask). Balance ~7.12 USDC (testing funds only).
**Discipline (operator standing rules):** /adix (backup before write, one file per verify, NO autonomous deletion), /karpathy-guidelines, AEE.md, /project-manager (mode-logger start/mode/write on way in/out). **Every verified step → commit local + push GitHub `main` as one motion.** One task at a time. Never print credentials (use [REDACTED]).
**Restart gotcha:** kill ALL uvicorn PIDs (`for d in /proc/[0-9]*; do grep -qa "uvicorn main:app" $d/cmdline && kill -9 ${d#/proc/}; done`) then let supervisor respawn OR launch a background uvicorn — a stale worker serves old code. Clear `__pycache__` if in doubt.

## What is DONE (committed + pushed, HEAD = fd72e14, 27 commits, local=remote)
- **Tier 0:** T0-1 (converter emits top-level `exit_config`), T0-2 (`test_credential` 403 on non-`puls_` global key), T0-3 (paper/backtest routes user-scoped), T0-4/5/6 (config + data dir). All pushed.
- **Tier 1:** T1-1 (circuit breaker), T1-2 (`PUT strategy-config` validates vs `get_parameters()` + restart), T1-3 (backtest runner reads `instance.strategy_config`), **T1-4** (`/login` + `/signup` rate-limited AUTH_LIMIT 5/min — verified live 429), **T1-5** (`WithdrawalRecord.idempotency_key` — verified idempotent guard). All pushed.
- **Docs:** TASK-LIST.md, NOTES.md, CONTEXT.md consolidated. UI walkthrough 21/21 (recon-only) in UI-WALKTHROUGH-FINDINGS.md.

## CURRENT STATE — T1-7 IN PROGRESS (NOT YET COMMITTED)
Task: disable withdraw/deposit UI + routes (feature deferred per BUG-11/BUG-12).
Edits made, **uncommitted**, need verify + commit + push:
- `api/withdrawals.py`: commented out 4 fund-touching routes — `POST /withdrawals/manual/50`, `POST /withdrawals/manual/all`, `PUT /withdrawals/config`, `GET /withdrawals/calculate`. Kept read-only: `GET /account`, `GET /withdrawals/config`, `GET /withdrawals/history`, `GET /withdrawals/projection`.
- `app/routes.py:559` `withdrawals_page`: now returns an HTML notice "Withdrawals — Not Functional Yet" (no longer renders `withdrawals.html` form). `HTMLResponse` already imported (line 7).
- Lint: both files pass.
- **STRAY FILE:** `._env_bak` in repo root — macOS artifact, do NOT commit (add to .gitignore or `rm`).
**Verify before commit:** kill stale uvicorn, respawn, then: `GET /app/withdrawals` → shows notice (200); `POST /api/v2/withdrawals/manual/50` → 404 (disabled); `GET /api/v2/withdrawals/history` → still 200. Then commit + push.

## DEFERRED FEATURE (do NOT implement without explicit operator go — live funds)
- **BUG-11:** `core/exchange.py:429` calls `self._exchange.withdraw(target, amount)` — SDK has no `.withdraw()`. Fix: `self._exchange.withdraw_from_bridge(amount, destination)` (sig `(amount, destination)`, action `withdraw3`, USDC L1 bridge, mainnet already set at exchange.py:91).
- **BUG-12:** NO deposit code path exists anywhere (no `deposit_to_hl` method/route). Needs building from scratch + idempotency (mirror T1-5).
- Full scope in TASK-LIST.md BUGHUNT (BUG-11+BUG-12) + NOTES.md (2026-07-19 DEFERRED entry) + CONTEXT.md (Known deferred features).

## OPEN NEXT ITEMS (after T1-7 committed)
1. **T1-6:** `test_credential` — stop treating HTTP 401 as `ok:true` (misleads users).
2. **BUG-10:** Signup form end-to-end browser verify (`/signup` creates user but untested in UI).
3. **BUG-7:** Trades table missing on `/app/trades`.
4. **BUG-9-A:** Recurring console exception (dashboard/engines/detail) — needs `window.onerror` root-cause.
5. **BUG-11/12:** deferred withdraw/deposit round-trip (above).
6. **Tier 2:** #32 copy fix, dropdown, email-unique, hmac, json-encrypt.

## Session-quality bar
Something exists that didn't before. Verify with real tool output (live server + browser), commit + push each step. Do not report done without live proof.

## First action in fresh session
1. `cd /workspace/projects/strategy-engine/main && git status` — confirm T1-7 edits present, note `._env_bak` stray.
2. Finish T1-7: verify (restart server, curl the 3 checks above), then `git add api/withdrawals.py app/routes.py && git commit && git push`. Do NOT add `._env_bak`.
3. Report to operator, then ask which open item next (recommend T1-6).
