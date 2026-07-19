# VERIFICATION-STATUS.md — strategy-engine
**Verified:** 2026-07-19 · **Against:** `github.com/karma-devops/strategy-engine`, `main` @ `cd3a1a1`
**Method:** every claim checked against actual file contents (not commit messages), several confirmed with a live boot test where the sandbox's network egress allowed it.

**Bottom line: the dev did real, careful, well-evidenced work. 19 of 20 assigned items are genuinely fixed, correctly, with good engineering judgment (see the withdraw/deposit call below). One fix is broken — a straight `NameError`, not a partial fix — and it's the historical backtests page, which will 500 on every load. Two new items were self-discovered and are correctly still tracked as open.**

---

## ✅ DONE — verified correct

| # | Item | Verification |
|---|------|--------------|
| T0-1 | Converter prompt now emits top-level `exit_config` | `core/llm.py:92-98` — matches the runner's actual contract |
| T0-2 | Shared `AGENT_API_KEY` blocked from credential CRUD | `api/credentials.py:39-60` — hard 403, no operator fallback, applied to list/create/update/delete/test uniformly |
| T0-3 (paper) | `app/paper_routes.py` resolves session user, not operator | `paper_routes.py:47` — `User.username == username` first, operator only as last-resort fallback |
| T0-4 | `setattr(self, k, v)` fixed in both engines | `engine/v6_1.py:97`, `engine/v1.py:87,89` — both now pass 3 args |
| T0-5 | Dashboard credentials fail-fast, no defaults | `config.py:19-38` — `_require()` raises `RuntimeError` at import time if unset. **Live-confirmed**: booting without `DASHBOARD_USERNAME` set threw exactly this error in my own test. |
| T0-6 | `data/` directory created at startup | `config.py:70` — `os.makedirs(..., exist_ok=True)` |
| T1-1 | Circuit breaker, trips at 5 consecutive tick errors | `instances/runner.py:80,187-208` — counter resets on success, trips and marks instance errored at threshold |
| T1-2 | `strategy-config` validated against `get_parameters()`, restarts on save | `api/instances.py` — full type coercion per declared param type, rejects unknown keys with 400, calls `manager.restart_instance()` after save, response tells you whether the restart happened |
| T1-3 | Backtests now read `instance.strategy_config` | `backtests/runner.py:389-400` — `strategy_cls(**strategy_config) if strategy_config else strategy_cls()`, live/backtest parity restored |
| T1-4 | Login/signup rate-limited | `app/routes.py:37,63` — `AUTH_LIMIT = "5/minute"` on both POST handlers |
| T1-5 | `WithdrawalRecord` idempotency key | `instances/models.py:330` — `unique=True, index=True` |
| T1-6 | `test_credential` no longer treats 401 as ok | `api/credentials.py:190` — `r.status_code == 200` only |
| T1-7 | Withdraw/deposit fund-moving routes disabled | See "Good judgment call" below — this wasn't on the original list, the dev found it themselves |
| T2-1 | "6-Engine Default Fleet" misleading copy gone | Resolved as a side effect of T2-3 — the whole fleet-preset `<optgroup>` was removed, not just relabeled. No misleading text remains. |
| T2-2 | `engine_v6_1` added to instance-form dropdown | `app/templates/instance_form.html:36` — `<option value="engine_v6_1">PRO v6.1</option>` |
| T2-3 | Dead preset-fetch machinery removed | `app/static/instance_form.js` — confirmed clean, no more calls to the unused `/presets/fleet` wiring |
| T2-4 | `User.email` unique + signup commit wrapped | `instances/models.py:58` (`unique=True`), `app/routes.py:107-113` (`try/except IntegrityError` with rollback + friendly message) |
| T2-5 | Session cookie MAC → real HMAC | `api/auth.py:32`, `app/routes.py:53,119` — all three sites now use `hmac.new(secret, token, sha256)` |
| T2-6 | Credential encryption → JSON | `instances/models.py:114,135` — `json.dumps`/`json.loads`, with a sensible `ast.literal_eval` fallback for decrypting any pre-migration records |

### Good judgment call worth flagging: T1-7 (withdraw/deposit)
Not something I asked for — the dev found it during their own pass. While working the withdrawal idempotency fix (T1-5), they discovered the underlying HyperLiquid SDK **doesn't have a `.withdraw()` method at all** (their `BUG-11`) and that deposits have no implementation whatsoever (`BUG-12`). Rather than ship a half-fixed, fundamentally non-functional fund-movement feature, they commented out the write routes (`PUT /withdrawals/config`, `GET /withdrawals/calculate`, `POST /withdrawals/manual/50`, `POST /withdrawals/manual/all`) and left `/app/withdrawals` returning a "feature deferred" notice instead of a broken form, while keeping the read-only endpoints (history/config/projection/account) live. That's the right call — disable what's broken rather than paper over it — and it's exactly the kind of self-directed catch you want from whoever's touching money-movement code.

---

## ❌ REGRESSION — fix is broken, not partial

### T0-3 (backtest half) — `app/backtest_routes.py:testing_historical` throws `NameError` on every load

```python
backtests = db.query(Backtest).filter(Backtest.kind == "backtest", Backtest.user_id == user.id)...
```

`user` is **never assigned anywhere in this function.** No `user = db.query(User)...`, no `get_or_seed_operator()` call — nothing. This isn't a missed edge case, it's a straight reference to an undefined name. Confirmed statically (full function body has no `user =` assignment before this line) and functionally consistent with how Python resolves names — this will raise on every single call, unconditionally, regardless of session state or data.

**Net effect:** `/app/testing/historical` (Historical Backtests page) is completely down. The original bug (cross-tenant leak — every user saw everyone's backtests) is gone, but only because the page can no longer load for anyone. This needs the same fix pattern already used correctly in `paper_routes.py` right next to it:

```python
user = db.query(User).filter(User.username == username).first()
if not user:
    user = get_or_seed_operator(db)
backtests = db.query(Backtest).filter(Backtest.kind == "backtest", Backtest.user_id == user.id)...
```

Five-minute fix, but it's a live 500 on a page that was in the "fixed" pile.

---

## ⏳ TODO — carried forward, still open

| Item | Status | Notes |
|------|--------|-------|
| Fix `testing_historical`'s undefined `user` | **New, urgent** | Page is down right now. Same pattern as the working `paper_routes.py` fix, just needs to be applied here too. |
| BUG-7 — `/app/trades` has no trades table or Active Positions section | Self-discovered by dev, tracked in `NOTES.md`, not yet fixed | Filter bar renders, then nothing — missing empty-state at minimum, possibly missing the whole data-rendering path |
| BUG-9-A — recurring anonymous JS exception on 5 pages (dashboard, engines, engine-detail, strategies, strategy-detail) | Self-discovered, tracked, not yet fixed | Dev's own notes narrow it to `position-card.js` or the PULSE console widget (pages without those two = zero errors) — needs `window.onerror` capture to pin the exact line |
| Withdraw/deposit round-trip (BUG-11 SDK gap, BUG-12 no deposit path) | Correctly deferred, not fixed | Feature-level gap, not a bug in existing code — needs actual SDK/implementation work whenever it's prioritized |
| Everything in `BUGREPORT.md`'s Tier 2/cleanup list not assigned this round | Not touched this session | `#54` items beyond idempotency, remaining ⚠️ UNVERIFIED frontend items from the earlier rewrite, etc. |

---

---

## 🔌 END-TO-END WIRING VERIFICATION (backend ↔ DB ↔ UI)

Scope of this pass: does data actually flow through the whole stack, not just "is this function correct in isolation." Built the full backend route table (accounting for every router's actual prefix, not just the literal decorator string) and diffed it against every `fetch()`/form-action target across every template and JS file, then spot-checked the highest-stakes paths by hand.

### ✅ Wires up correctly

- **DB migrations are safe for existing databases.** There's a manual `ALTER TABLE ... ADD COLUMN` list (`instances/models.py:537-589`) that runs alongside `Base.metadata.create_all()`. Checked specifically: `strategy_config`, `user_id`, `hl_credential_id` are all in the `instances` table's migration list, so an existing DB from before this session's changes will pick up the new columns instead of crashing on missing-column errors. `T2-4`'s email-uniqueness is applied as an idempotent `CREATE UNIQUE INDEX IF NOT EXISTS`, so it's also safe to re-run against data that predates the fix.
- **Router prefixes are consistent.** Every `api/*.py` router mounts cleanly under `/api/v2` (or `/api/v2/credentials` for the one router that sets its own internal prefix) with no double-prefixing or path collisions. Frontend `fetch()` targets match the actual registered paths for the core instance/signal/position/metric/killswitch/monitoring/metadata surface.
- **Kill switch is fully wired.** `dashboard.html`'s STOP button → `POST /api/v2/kill?reset=false` → `api/killswitch.py` → `instances/runner.py`'s `is_global_killed()` check at tick-start. Confirmed the whole chain, not just the endpoints in isolation.
- **Strategy Studio's convert/save/upload routes are intentionally session-gated, not API-key-gated** — they live in `app/routes.py` under `verify_ui_credentials` rather than `api/strategies.py` under `verify_api_key`. This is a deliberate (and reasonable) design choice, not a bug: those are UI-only mutation flows, and same-origin fetches automatically carry the session cookie.

### ❌ Does not wire up

**17. The entire Port-1 `strategy_config` feature has no UI entry point — still.** This was flagged in the previous session as the biggest gap in the 3-port architecture, and it's still true after this round of fixes. T1-2 made the backend genuinely solid: `PUT /instances/{id}/strategy-config` validates against `get_parameters()`, coerces types, restarts the instance on save. But:
  - `grep -rl "strategy-config\|/parameters" app/templates/*.html app/static/*.js` → **zero matches, anywhere.**
  - `engine_detail.html`'s "⚙ Settings" modal (`openSettings()`/`saveSettings()`, lines 286-337) only reads/writes `name, token, strategy_id, timeframe, leverage, max_position_pct, dry_run, start_balance` via the generic `PUT /api/v2/instances/{slug}` — the same fields as before this session's work, nothing new.
  - No page calls `GET /strategies/{id}/parameters` to fetch the param schema, so there's nothing to build a form from even if one existed.
  - **Net effect: the fix made the backend safe to use, but an operator still cannot, through the app, set a custom ATR multiplier, momentum threshold, or any other per-instance strategy parameter.** The feature is now "correctly inert" instead of "dangerously inert" (it validates and won't crash v6.1 anymore), but it's still inert from a user's perspective.

**18. `app/routes.py` has a genuinely dead, orphaned `withdrawals_page` function.** Not user-facing (confirmed harmless right now), but worth flagging as a wiring/hygiene issue: the file defines `withdrawals_page` **twice**. The first (`line 572`, `@router.get("/app/withdrawals")`) is the live T1-7 notice page — correct, confirmed working. The second (`line ~1746`) has only a bare `@limiter.limit(READ_LIMIT)` with **no `@router.get(...)` above it at all** — it's never registered as a route, and it silently shadows the first function's name in the module namespace. It contains the old "BUG #25" fix (passing `api_key` into `withdrawals.html`'s context) — a fix for a page that, post-T1-7, no longer renders that template at all. This function should just be deleted; it's confusing dead code sitting next to a name it no longer needs to share.

**19. `testing_historical`'s `NameError` (already reported above) is also a wiring failure, not just a logic bug** — worth restating in this context: the page's fetch calls from `testing_historical.html` are all correctly targeted, the route exists at the right path, auth is correctly applied — the entire chain is right except the one line inside the handler. This is the clearest example in the whole audit of "everything wires up except one broken link."

### ⚠️ Not fully verified (couldn't boot-test)

The sandbox's network egress allowlist blocks `api.hyperliquid.xyz`, so `core/exchange.py`'s module-level `HyperLiquidClient()` instantiation prevents a full app boot in this environment — I could not exercise a real HTTP round-trip through the whole FastAPI app. Everything above is verified by tracing actual code paths (route tables, function bodies, template fetch targets) rather than by hitting a running server. Recommend an actual boot + click-through on infrastructure that can reach HyperLiquid before treating any of this as fully load-bearing — static tracing catches routing/logic mismatches like #17-#19 reliably, but won't catch things like a template variable name typo that only surfaces at render time.

---

## Updated priority order (supersedes the previous list)

1. **Fix `testing_historical`'s undefined `user`** — page is down right now, five-minute fix, pattern already exists next door.
2. **Build the Strategy Parameters UI** (closes #17) — this is now purely a frontend task; the backend contract is validated, safe, and ready. Add a form section to `engine_detail.html`'s settings modal (or a dedicated panel) that calls `GET /strategies/{id}/parameters` to build inputs and `PUT /instances/{id}/strategy-config` to save.
3. Delete the orphaned second `withdrawals_page` (#18) — trivial cleanup, prevents future confusion if someone tries to re-enable withdrawals later.
4. BUG-9-A (recurring JS exception, 5 pages) — dev's own notes already narrowed this to two files.
5. BUG-7 (missing trades table).
6. Everything else previously listed in `BUGREPORT.md` that wasn't in this round's scope.
