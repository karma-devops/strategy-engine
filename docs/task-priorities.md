# TASK-PRIORITIES.md — strategy-engine
**Compiled:** 2026-07-19 · **Companion to:** `BUGREPORT.md`
**Position on the Phase -1 architecture contract:** not blocking. See "Where the rewrite fits" at the bottom.

---

## The ordering principle

Fix what's actively wrong with money and access control first, on the architecture you have. Decide on the full rewrite once nothing urgent is bleeding. Don't let a 3-5 day (realistically longer) documentation-lock gate sit in front of bugs that are live right now.

---

## TIER 0 — Do before anything else touches this repo

Everything here is independently verified against the current `main` branch, not inherited from an agent report.

| # | Task | Why it's Tier 0 | Est. effort |
|---|------|------------------|--------------|
| 1 | Fix `core/llm.py` converter system prompt — align to the real `exit_config` contract, not `metadata` | Any strategy generated via Strategy Studio right now trades live/paper with **no stop-loss, no take-profit, ever**. Silent, not a crash. | 30 min |
| 2 | Fix `api/credentials.py:_current_user_id()` — stop collapsing the shared `AGENT_API_KEY` into the operator identity for credential CRUD | Shared dashboard key currently has full read/write over decrypted private keys | 1-2 hrs |
| 3 | Fix `app/paper_routes.py` and `app/backtest_routes.py` — resolve the actual session user instead of `get_or_seed_operator(db)` | Cross-tenant data leak the moment a second user signs up | 1-2 hrs |
| 4 | `setattr(self, k)` → `setattr(self, k, v)` in `engine/v6_1.py:97` and `engine/v1.py`'s fallback branch | Two-character fix; currently guarantees a crash the moment anyone uses per-instance strategy config on 2 of 3 engines | 15 min |
| 5 | `config.py` — remove the `"operator"/"operator"` default, fail loudly on boot if `DASHBOARD_USERNAME`/`PASSWORD` unset | Never tracked in any prior backlog; live right now | 20 min |
| 6 | Create `data/` directory at startup (or in `Dockerfile`) | Fresh clone + fresh deploy crashes immediately, confirmed by reproduction | 10 min |

**Total: under a day of focused work.** This is the list I'd want closed before writing a single `docs/VOCABULARY.md` entry.

---

## TIER 1 — This week, still on current architecture

| # | Task | Note |
|---|------|------|
| 7 | Circuit breaker (`error_consecutive` counter, trip at 5) | Correctly tracked as P0 in BACKLOG.md, genuinely unstarted |
| 8 | Validate `PUT .../strategy-config` payloads against `get_parameters()`; trigger instance restart on save | Right now a "successful" save can silently do nothing (no restart) or crash on next start (unvalidated keys) |
| 9 | `backtests/runner.py:389` — pass `instance.strategy_config` into the strategy the same way the live runner does | Backtests currently always test engine defaults regardless of what you configured |
| 10 | Login/signup rate limiting (`app/routes.py` `POST /login`, `POST /signup`) | Currently unlimited brute-force / signup-spam surface |
| 11 | `WithdrawalRecord` idempotency key | Money-movement, no dedup protection against a double-click |
| 12 | `test_credential` — stop treating HTTP 401 as `"ok": true` | Small, but actively misleads users about whether their AI-provider key works |

---

## TIER 2 — Cleanup, do opportunistically

- `#32` — fix the "6-Engine Default Fleet" UI copy (decision is locked: 1 engine, just fix the label)
- `instance_form.html` — add `engine_v6_1` to the strategy dropdown
- `instance_form.js` — wire up or remove the unused per-strategy presets endpoint
- `User.email` — add DB-level unique constraint; wrap `signup_post`'s `db.commit()` in a try/except
- Session cookie MAC — swap hand-rolled `sha256(token+secret)` for `hmac.new()`
- `Credential.encrypt_and_store`/`.decrypt` — swap `str()`/`ast.literal_eval()` for `json.dumps`/`json.loads`
- Re-verify the ⚠️ UNVERIFIED list in `BUGREPORT.md` against the current (rewritten) frontend

---

## Where the rewrite fits

Once Tier 0 is closed (and ideally Tier 1), the Phase -1 contract is worth doing — the domain modeling in it is sound. Three changes to how it should run, though:

1. **Docs-in-parallel, not docs-as-gate.** Write `VOCABULARY.md`/`ARCHITECTURE.md`/`DECISIONS.md` alongside a maintenance branch that keeps shipping Tier 1/2 fixes on the current structure, rather than freezing all code for the length of the documentation phase. A system taking live orders doesn't get a multi-day code freeze for a rewrite that isn't finished yet.

2. **Don't lock the domain model before you've used it.** This bug-hunt found real architecture that didn't exist in my mental model three sessions ago (the 3-port `strategy_config`/`entry_config`/`exit_config` contract, the multi-tenant `User`/`Credential` system) — the system is still actively growing new domain concepts. Locking `VOCABULARY.md` to zero-ambiguity *now* risks locking in a model that's already stale in a month. Suggest treating v1 of these docs as a strong draft, not a permanent contract, until the system's shape stabilizes empirically.

3. **The restructure itself needs `git mv`/`git filter-repo`, not a fresh directory + `git init`.** The `main/`-as-new-root move already cost you the commit history for three safety-fix batches this week. A `contracts/`/`domain/`/`runtime/`/`execution/`/`risk/` reorganization touching every file in the repo, done the same way, will do that again at much larger scale. Whoever executes Phase -1's file moves should do it with history-preserving commands, not a copy.

If you want, I can turn the "DOMAIN CONCEPTS" section of the contract into a gap analysis against what actually exists in the current codebase right now (e.g. "Risk Check" as a formal concept doesn't exist yet — `position_sizer.py` does part of it) — that'd tell you how big Phase -1 actually is before you commit 3-5 days to it.