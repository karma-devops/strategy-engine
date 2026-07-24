# REFACTOR_PLAN

This is the **executable architecture contract** for the strategy-engine project.
The full source is attached to the operator's brief (2026-07-18). Summary below.

## Phase -1 — Architecture Contract (MANDATORY, docs only, no code)
Lock all concepts + interfaces before touching code. Exit: all docs approved,
zero TODOs in contracts.

### Deliverables (`/docs/`)
README, VOCABULARY, CONTEXT (root per operator), ARCHITECTURE, DECISIONS, ROADMAP,
NOTES (root per operator), CONTRIBUTING, STYLEGUIDE, AI_RULES, REFACTOR_PLAN.

### Domain concepts (defined)
Strategy, Strategy Package, Engine, Engine Definition, Engine Runtime, Engine
Context, Runner, Signal, Order, Position, Risk Check, Event, Candle, Portfolio,
Account, Trade.

### Infrastructure concepts
Exchange, Market Provider, Execution Engine, Repository, Event Bus, Logger,
Metrics, Persistence.

### Repository contract (rules for contributors)
- Strategy: pure, deterministic, stateless, testable, portable.
- Engine: owns runtime, not scheduling or DB.
- Runner: scheduling + kill state only.
- Execution: only ExecutionEngine opens/closes orders.
- Risk: every order passes risk; circuit breaker; kill switch.
- Exchange: implements interface, no strategy/risk knowledge.
- Event: facts, immutable, past tense.
- Persistence: repositories behind interfaces, no business logic.
- API: thin, validates, no business logic.
- Docs: update in same PR (ARCHITECTURE, VOCABULARY, DECISIONS, CHANGELOG).

### Definition of Done (every phase)
Tests pass · no circular imports · docs updated · ADR written · behavior preserved ·
paper verified (48h DRY_RUN) · lint + type check · no untracked TODOs · reviewed by
operator · committed · merged.

### Final target architecture
```
contracts/ domain/ config/ strategies/ engines/ runtime/ market/ exchange/
execution/ risk/ persistence/ infrastructure/ api/routes/ app/ backtest/ tests/ scripts/
```
See `docs/ARCHITECTURE.md` for current→target mapping and migration rule (re-export
shim before any rename; verify green before removing shim).

---

**Status:** Phase -1 in progress. Docs established. Code migration to target dirs
is a LATER phase (not started). Current code (api/app/instances/engine/core/...) is
functional and must not break during migration.
