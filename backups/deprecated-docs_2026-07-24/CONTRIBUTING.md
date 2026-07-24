# CONTRIBUTING

## Setup
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env_example .env   # fill in AGENT_API_KEY, HL credentials for live
uvicorn main:app --host 0.0.0.0 --port 8792
```

## Workflow
1. Pulse first (`self-pulse.sh`) before any turn.
2. Read `CONTEXT.md` (root) + `NOTES.md` (root) + `docs/TASK-LIST.md` for state.
3. One file per turn. Backup before overwrite (ADIX tar.gz). Verify after write.
4. No code changes without a corresponding doc update (ARCHITECTURE / VOCABULARY /
   DECISIONS if structure/terms changed).
5. Commit with convention: `feat:`, `fix:`, `docs:`, `refactor:`.
6. Live-test every route you touch (`curl -u operator:operator ...`).

## Definition of Done (per REFACTOR_PLAN.md)
- [ ] Tests pass (`pytest tests/`)
- [ ] No new circular imports
- [ ] Docs updated
- [ ] ADR written if architecture changed
- [ ] Behavior preserved unless intentionally changed
- [ ] Paper trading verified (48h DRY_RUN minimum before live)
- [ ] Lint + type check pass
- [ ] No untracked TODOs without ROADMAP/NOTES entry
- [ ] Reviewed by Operator

## Doc taxonomy (locked)
- `CONTEXT.md` (root) — MAP / why
- `NOTES.md` (root) — LOG / scratch
- `docs/TASK-LIST.md` — WORK / status
- `docs/ROADMAP.md` — PLAN / milestones
- `docs/BACKLOG.md` (root) — bug ledger
- `docs/ARCHITECTURE.md` — module map
- `docs/VOCABULARY.md` — terms
- `docs/DECISIONS.md` — ADRs
