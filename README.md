# PULS-R Strategy Engine

A multi-engine crypto trading system for HyperLiquid perpetuals. Runs strategies in
**Paper** (dry_run) or **Live** mode, with a kill-switch, circuit-breaker-ready
runner, and a server-rendered PWA dashboard.

> This `main/` directory is the deployable application and the git repository root.
> All source, docs, and config live here. Secrets (`cookies.txt`, `.env`) are
> gitignored. Database files live in `data/` (gitignored).

## Quick start

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env_example .env          # fill AGENT_API_KEY, HL creds for live
uvicorn main:app --host 0.0.0.0 --port 8792
```

Open `http://localhost:8792/` → login with `DASHBOARD_USERNAME` / `DASHBOARD_PASSWORD`.

## Layout

```
main/
├── main.py              # FastAPI app entry
├── config.py            # Config (Config class)
├── CONTEXT.md           # Why / how we think (operator working doc)
├── NOTES.md             # Engineering log
├── BACKLOG.md           # Bug-report tracking ledger
├── api/                 # REST routers (instances, killswitch, metrics, ...)
├── app/                 # UI: routes, templates, static
├── instances/           # Engine runtime: runner, manager, models, events
├── engine/              # Strategy registry + implementations
├── core/                # exchange client, market data
├── backtests/           # Backtest engine
├── testing/             # Unified runner (paper|backtest), isolated store
├── withdrawal/          # Scheduler + manual
├── monitoring/          # Alerts, rotator, tracker, testing_pool
├── design-system/       # MASTER.md (palette authority)
├── docs/                # Architecture contract (README, VOCABULARY, ARCHITECTURE, ...)
├── tests/               # Test suite
├── pinescript-tv/       # Pine Script equivalents
├── scripts/             # Standalone worker (port 9999)
└── data/                # SQLite DBs (gitignored)
```

## Documentation

- `docs/README.md` — doc index
- `docs/ARCHITECTURE.md` — module map (current + target)
- `docs/VOCABULARY.md` — domain terms
- `docs/DECISIONS.md` — Architecture Decision Records
- `docs/REFACTOR_PLAN.md` — executable architecture contract
- `docs/STYLEGUIDE.md` — code style
- `docs/AI_RULES.md` — rules for coding agents
- `docs/CONTRIBUTING.md` — how to contribute
- `docs/TASK-LIST.md` — work items / status
- `docs/ROADMAP.md` — milestones

## Key decisions

- **3-way separation:** LIVE (dry_run=False) / PAPER (dry_run=True) / BACKTEST (isolated store)
- **MASTER.md wins** design palette
- **Worker stays standalone** (port 9999, not merged)
- **Seed engine-1 only** on fresh accounts
- **CONTEXT.md / NOTES.md at repo root** (operator navigation)

## Safety

- Kill switch (`POST /kill/global`) closes all positions first.
- `stop_instance` market-closes before stopping.
- Never flip `dry_run=False` without explicit confirmation.

## License

[Specify]

## Version

Current: **v2.02** (see `VERSION` file; `api/metadata.py` reports it via `/api/v2/metadata`). Docs: `CONTEXT.md` (MAP), `NOTES.md` (LOG), `docs/TASK-LIST.md` (WORK), `BETA-ROADMAP.md` (PLAN).
