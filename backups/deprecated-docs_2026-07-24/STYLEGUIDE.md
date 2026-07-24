# STYLEGUIDE

## Code style
- Python 3.11+, typed where reasonable.
- `black` formatting (line length 100), `ruff` for lint.
- No silent excepts. Log + re-raise or handle explicitly.
- One responsibility per function. Prefer pure helpers.

## Naming
- Modules: `snake_case`. Classes: `PascalCase`. Functions/vars: `snake_case`.
- Constants: `UPPER_SNAKE`.
- Engine slugs: `^[a-z0-9-]{1,32}$` (validated in `create_instance`).

## Structure rules (from REFACTOR_PLAN.md)
- **Strategy** — pure, no side effects, no exchange/DB/HTTP imports.
- **Engine** — owns runtime state, not scheduling (Runner does) or DB (repositories do).
- **Runner** — scheduling + kill state only; no trading logic.
- **Execution** — only ExecutionEngine opens/closes orders; never bypasses Risk.
- **Risk** — every order passes risk; circuit breaker trips on errors; kill switch stops all.
- **Exchange** — implements interface; no strategy/risk knowledge.
- **API** — thin; validates input; no business logic.
- **Persistence** — repositories behind abstract interfaces; no business logic.

## Docs
- Update ARCHITECTURE.md if structure changes.
- Update VOCABULARY.md if terms change.
- Write an ADR (DECISIONS.md) for any architecture change.
- No PR merges code without docs.

## Discipline (operator-mandated)
- Pulse before thinking.
- One file per turn.
- Backup before overwrite (ADIX).
- Verify after every write (wc -l, grep counts, import check, live curl).
- No autonomous deletion of files.
