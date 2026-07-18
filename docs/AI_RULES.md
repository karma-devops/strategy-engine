# AI_RULES

Rules for coding agents (Hermes / Aetheris) working in this repo.

## Execution discipline
1. **Pulse first.** Run `self-pulse.sh` before any turn. Not optional.
2. **Read before write.** `CONTEXT.md` (root), `NOTES.md` (root), `docs/TASK-LIST.md`
   before touching code.
3. **One file per turn.** Verify after every write (syntax, import, live route).
4. **Backup before overwrite.** ADIX STABLE tar.gz (exclude venv/pyc/db/.env).
   Never delete files autonomously.
5. **No code without docs.** If structure/terms change, update ARCHITECTURE /
   VOCABULARY / DECISIONS in the same batch.

## Safety (live capital)
- Never flip `dry_run=False` without explicit operator confirmation.
- Kill switch (`/kill/global`) closes positions first (`close_all_positions`).
- `stop_instance` market-closes before stopping (B7).
- Idempotency: PENDING sentinel blocks duplicate entries mid-tick (X1).
- Circuit breaker: trip at 5 consecutive errors (P0, pending).

## Boundaries
- Strategies are pure. No exchange/DB/HTTP in strategy code.
- API routes are thin. Business logic lives in `instances/` / `execution/` / `risk/`.
- No secrets in outputs. Use `[REDACTED]`.

## Verification
- Live-test every route you change: `curl -u operator:operator http://localhost:8792/...`
- Import smoke-test: `python3 -c "import main"`
- Restart server after template/routes changes; confirm dashboard 200.

## Communication
- Operator is right when correcting. Apologize once, move on.
- Bad news first, then fixes.
- No open-ended questions where a programmatic default exists.
