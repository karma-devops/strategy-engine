# VOCABULARY

Domain terms for the PULS-R strategy engine. Definitions follow the architecture
contract (see `docs/REFACTOR_PLAN.md`).

## Strategy
A pure trading algorithm that produces signals from market data. Owns trading
logic + parameters. Knows: candles, settings. Does NOT know: exchange, account,
orders, DB, logging, HTTP, other strategies. Immutable at runtime.

## Strategy Package
A versioned bundle: `python.py`, `pine.pine`, `metadata.yaml`, `defaults.yaml`,
`tests.py`, `README.md`. New version = new package (never mutate in place).

## Engine
A deployed strategy = Strategy + Definition + Runtime + Context + Risk + Execution
+ Exchange Adapter. Knows its own state + injected services. Does NOT know other
engines, HTTP/API, or DB directly (uses repositories).

## Engine Definition
Immutable config (name, strategy ref, symbol, exchange, paper/live, risk, interval).
YAML. To change → new definition.

## Engine Runtime
Mutable per-tick state: position, last signal, PnL, drawdown, consecutive errors,
heartbeat, order/trade counts. Disposable (rebuildable from events).

## Engine Context
Injected services: exchange, risk, execution, event_bus, market, logger. Knows
interfaces, not implementations.

## Runner
Scheduler. Orchestrates engine ticks. Owns active-engine list + tick loop + global
kill state. Does NOT know strategy logic, order execution, or DB.

## Signal
A decision from a Strategy: engine_id, strategy_id, version, symbol, direction
(BUY/SELL/HOLD), strength (0–1), timestamp, metadata. Past-tense fact once emitted.

## Order
Instruction to exchange: idempotency key, engine_id, symbol, side, type, size,
price, status, timestamps, fill price. Created by Execution Engine.

## Position
Current exposure: engine_id, symbol, side (LONG/SHORT/FLAT), size, entry, mark,
unrealized/realized PnL, opened/closed timestamps.

## Risk Check
Single validation rule (e.g. PositionLimitCheck). Knows Order + context. Called
every order.

## Event
Immutable past-tense fact. Published → handled by subscribers → persisted.

## Candle
OHLCV for one period. Pure data.

## Portfolio
Aggregate view of all engine positions + PnL. Computed on demand.

## Account
Exchange account state (value, equity, margin, leverage). Fetched from exchange.

## Trade
Completed transaction (open + close). Immutable once closed.

## Exchange (interface)
Abstract: order placement/cancel, position/account queries, candle fetch. Knows
exchange API. Does NOT know strategy/risk/engine.

## Market Provider
Supplies candles + indicators. Live or replay. Does NOT know trading decisions.

## Execution Engine
Owns order lifecycle: signal→order, idempotency, placement, fills, retry,
reconciliation, position closing. Does NOT know strategy/risk.

## Repository
Abstract persistence interface. Knows DB/ORM. Does NOT know business logic.

## Event Bus
Decouples publishers/subscribers. Knows event types + handlers.

## Logger
Structured logging with context injection.

## Metrics
Counters/gauges/histograms from events.

## Persistence
ORM models, migrations, connection pooling.

## Infrastructure Concepts
Exchange, Market Provider, Execution Engine, Repository, Event Bus, Logger,
Metrics, Persistence — the service layer engines depend on via Context.
