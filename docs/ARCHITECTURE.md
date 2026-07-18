# ARCHITECTURE

## Current Module Map (as of 2026-07-18)

```
main.py
  ├── api/* routers      (instances, killswitch, metrics, backtests, withdrawals, signals, credentials, metadata, monitoring, ratelimit, stream)
  ├── app/routes.py      (LIVE UI: dashboard, engines, strategies, trades, account, settings, instance_form, withdrawals_page)
  ├── app/paper_routes.py (Paper Trading page)
  ├── app/backtest_routes.py (Backtesting page)
  ├── app/_common.py     (pure helpers: _safe_tojson, _inject_theme, _instances_by_mode)
  ├── instances/manager.py → instances/runner.py → core/exchange.py (HyperLiquidClient)
  ├── instances/events.py (EventBus + LOG_BUFFER, thread-safe)
  ├── engine/registry.py → engine/v1_3.py, v1.py, v6_1.py (strategies)
  ├── core/market_data.py (HL candleSnapshot)
  ├── backtests/runner.py + cost_model.py
  ├── testing/runner.py (--mode paper|backtest) + backtest_store.py (isolated DB)
  ├── withdrawal/scheduler.py + manual.py + calculator.py
  └── monitoring/alerts.py, rotator.py, tracker.py, testing_pool.py
```

### Layering (enforced)
`API → Manager → Runner → Exchange → HL API`
UI routes read via `api/*` or render server-side; they never execute trades directly.

### 3-Way Separation (Z1, live)
- **LIVE** — `dry_run=False`, real capital, dashboard + engines + trades
- **PAPER** — `dry_run=True`, top-level menu "Paper Trading"
- **BACKTEST** — isolated `data/backtest.db`, never touches live/paper data

### Auth
- API routes: `X-API-Key` + slowapi rate limits (keyed by `api_key_or_ip`)
- UI routes: Basic Auth (`verify_ui_credentials`)
- Admin logs: Basic Auth only

---

## Target Structure (from REFACTOR_PLAN.md)

The contract specifies a clean port/adapter layout. Migration is a later phase
(no code moves in Phase -1). Target top-level dirs:

```
contracts/      # abstract interfaces (ports): strategy, exchange, execution, market, risk, repository, event_bus
domain/         # pure model: signals, orders, positions, events, types
config/         # loader, schema, templates, validation
strategies/     # versioned packages: puls_r/versions/v6.1/{python.py,pine.pine,metadata.yaml,defaults.yaml,tests.py,README.md}
engines/        # YAML engine definitions only
runtime/        # runner, manager, engine, definition, runtime, context
market/         # provider, cache, replay, aggregator
exchange/       # base, hyperliquid, paper, mock
execution/      # engine, orders, idempotency, reconciler, position_closer
risk/           # manager, checks/, circuit_breaker, killswitch
persistence/    # repositories/, orm/, migrations/, database
infrastructure/ # events, logging, metrics, alerts, health
api/routes/     # split routers
app/            # UI (routes.py, static/, templates/)
backtest/       # offline runner
tests/{unit,integration,e2e,replay,performance,fixtures,builders,factories}
scripts/        # setup, migrate, deploy
```

### Mapping current → target (for future migration)
| Current | Target |
|---------|--------|
| `engine/` | `strategies/` (versioned packages) |
| `instances/` | `runtime/` |
| `core/exchange.py` | `exchange/hyperliquid.py` |
| `core/market_data.py` | `market/provider.py` |
| `backtests/` + `testing/` | `backtest/` + `execution/` |
| `instances/events.py` | `infrastructure/events.py` |
| `monitoring/` | `infrastructure/alerts.py` + `risk/` |
| `withdrawal/` | `execution/` or `infrastructure/` |
| `api/` | `api/routes/` |

### Migration rule
No rename happens until tests pass and imports are verified green. Each module
moves behind a re-export shim first to avoid breaking the running server.
