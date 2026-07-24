# PULS-R Strategy Engine

A multi-engine crypto trading system for HyperLiquid perpetuals. Runs strategies
in Paper (dry_run) or Live mode, with a kill-switch, circuit-breaker-ready runner,
and a server-rendered PWA dashboard.

## Quick links

- **`CONTEXT.md`** (repo root) — why this exists, how we think, operating constraints.
- **`NOTES.md`** (repo root) — engineering log / scratch paper.
- **`docs/TASK-LIST.md`** — current work items and their status.
- **`docs/ROADMAP.md`** — planned milestones (beta gate).
- **`docs/BACKLOG.md`** (repo root) — bugreport tracking ledger.
- **`docs/ARCHITECTURE.md`** — module map (current) + target structure.
- **`docs/VOCABULARY.md`** — domain terms.
- **`docs/DECISIONS.md`** — Architecture Decision Records.
- **`docs/STYLEGUIDE.md`** — code style & structure rules.
- **`docs/AI_RULES.md`** — rules for coding agents.
- **`docs/REFACTOR_PLAN.md`** — the executable architecture contract.

## Layout (current)

```
strategy-engine/
├── main.py                 # FastAPI app entry
├── config.py               # Config loading (Config class)
├── CONTEXT.md              # ROOT (operator working doc)
├── NOTES.md                # ROOT (operator working doc)
├── BACKLOG.md              # ROOT (bug ledger)
├── api/                    # REST API routers (instances, killswitch, metrics, backtests, withdrawals...)
├── app/                    # UI: routes.py, templates/, static/, _common.py, paper_routes.py, backtest_routes.py
├── instances/              # Engine runtime: runner.py, manager.py, models.py, events.py
├── engine/                 # Strategy registry + strategy implementations (v1, v1_3, v6_1)
├── core/                   # exchange.py (HL client), market_data.py
├── backtests/              # Backtest engine (runner.py, cost_model.py)
├── testing/                # Unified runner (--mode paper|backtest), isolated backtest_store.py
├── withdrawal/             # Scheduler + manual withdrawal logic
├── monitoring/             # Alerts, rotator, tracker, testing_pool
├── design-system/          # MASTER.md (palette authority) + components/spec/glow
├── docs/                   # This directory (contract)
├── tests/                  # Test suite
├── pinescript-tv/          # Pine Script equivalents of strategies
├── scripts/                # Standalone worker (port 9999, not merged into main app)
└── data/                   # SQLite DBs (gitignored)
```

See `docs/ARCHITECTURE.md` for the full target structure and migration plan.
