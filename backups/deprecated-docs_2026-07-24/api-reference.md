# API Reference

> All endpoints. Generated from source. Update when adding endpoints.

## Base URL
```
http://localhost:8792
```
Auth: `X-API-Key` header (value from `AGENT_API_KEY` env or API key from Account > API Keys).

## Instances

| Method | Path | Purpose | Key Params |
|--------|------|---------|------------|
| GET | `/api/v2/instances` | List all instances | — |
| POST | `/api/v2/instances` | Create instance | `{slug, token, strategy_id, timeframe, leverage, ...}` |
| GET | `/api/v2/instances/{id}` | Get instance detail | `id` = slug |
| PUT | `/api/v2/instances/{id}` | Update instance | `{dry_run, leverage, max_position_pct, ...}` |
| DELETE | `/api/v2/instances/{id}` | Delete instance (cascade) | `id` = slug |
| POST | `/api/v2/instances/{id}/start` | Start engine | — |
| POST | `/api/v2/instances/{id}/stop` | Stop engine | — |
| POST | `/api/v2/instances/{id}/close` | Close position | — |
| POST | `/api/v2/instances/{id}/restart` | Restart engine | — |
| GET | `/api/v2/instances/{id}/trades` | Instance trades | — |
| POST | `/api/v2/instances/{id}/leverage` | Set leverage | `{leverage: N}` |
| POST | `/api/v2/instances/{id}/balance` | Set balance | `{balance: N, mode: "live"|"manual"}` |
| GET | `/api/v2/instances/{id}/balance` | Get balance | — |
| GET | `/api/v2/instances/active` | Active instances | — |

## Summary & Global

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v2/summary` | Global summary (all instances, KPIs, positions) |
| GET | `/api/v2/metadata` | HL universe metadata (tokens, maxLeverage) |
| GET | `/api/v2/stats` | Aggregate stats |
| GET | `/api/v2/health` | (does not exist — use `/health`) |
| GET | `/health` | Server health, dry_run status |

## Trades

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v2/trades` | All trades (global) |
| GET | `/api/v2/instances/{id}/trades` | Trades for one instance |

## Backtests

| Method | Path | Purpose | Key Params |
|--------|------|---------|------------|
| GET | `/api/v2/backtests` | List backtests | — |
| POST | `/api/v2/backtests/run` | Run backtest | `{token, strategy_id, timeframe, days, leverage}` |

## Strategies

| Method | Path | Purpose | Key Params |
|--------|------|---------|------------|
| GET | `/api/v2/strategies` | List strategies | — |
| GET | `/api/v2/strategies/{id}` | Strategy detail | — |
| GET | `/api/v2/strategies/{id}/presets` | Strategy presets | — |
| POST | `/api/v2/strategies/upload` | Upload PineScript | `{name, pine_source}` (TODO) |
| POST | `/api/v2/strategies/{id}/convert` | AI convert Pine→Python | (TODO) |

## Chat

|| Method | Path | Purpose | Key Params |
||--------|------|---------|------------|
|| POST | `/api/v2/chat` | AI chat (per-user model, 10-session memory) | `{context, message, session_id?, model?}` (Basic Auth) |
|| GET | `/api/v2/chat/sessions` | List user's last 10 sessions | — (Basic Auth) |

## Kill Switch

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v2/kill` | Global kill (stop all + close all) |
| POST | `/api/v2/kill/reset` | Reset kill switch |

## Stream

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/stream` | SSE stream (log, signal, trade, ping events) |

## Positions & Metrics

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v2/positions` | All open positions |
| GET | `/api/v2/metrics` | Performance metrics |
| GET | `/api/v2/signals` | Recent signals |
| GET | `/api/v2/monitoring` | Monitoring scores |

## Withdrawals

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v2/withdrawals/config` | Withdrawal config |
| POST | `/api/v2/withdrawals/config` | Update config |
| GET | `/api/v2/withdrawals/history` | Withdrawal history |

## Swagger
- `/docs` — Interactive Swagger UI
- `/redoc` — ReDoc alternative
- `/openapi.json` — OpenAPI 3.1 schema