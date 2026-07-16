# Data Models

> Every model, every column. From `instances/models.py`.

## User
|| Column | Type | Default | Notes |
||--------|------|---------|-------|
|| id | String(36) PK | UUID | |
|| username | String(64) | — | unique, indexed |
|| display_name | String(128) | null | |
|| start_balance | Float | 1000.0 | |
|| default_dry_run | Boolean | True | |
|| email | String(256) | null | for 2FA/notifications |
|| password_hash | String(256) | null | login auth |
|| withdrawal_eth_address | String(64) | null | withdrawal wallet |
|| avatar_emoji | String(16) | null | emoji icon selector |
|| plan | String(32) | "free" | billing: free/pro/enterprise |
|| twofa_enabled | Boolean | False | |
|| assistant_model | String(64) | "glm-5.1" | per-user AI model (chat) |
|| coder_model | String(64) | "glm-5.1" | per-user AI model (Pine→Python) |
|| created_at | DateTime | utcnow | |
|| updated_at | DateTime | utcnow | onupdate |

## Instance
| Column | Type | Default | Notes |
|--------|------|---------|-------|
| slug | String(32) PK | — | human-readable ID |
| user_id | String(36) | null | FK → User.id |
| name | String(128) | — | display name |
| token | String(64) | — | HL token (FARTCOIN, HYPE, etc.) |
| strategy_id | String(64) | — | FK → strategy registry |
| mode | String(32) | "Scalp" | Scalp, Swing |
| profile | String(64) | "aggressive_8_3" | |
| timeframe | String(16) | "15m" | 5m, 15m, 30m, 1h |
| leverage | Integer | 10 | |
| max_position_pct | Float | 0.97 | 0-1 |
| poll_interval_seconds | Integer | 30 | system-level, NOT user-editable |
| activation | Integer | 8 | from strategy, NOT user-editable |
| offset | Integer | 3 | from strategy, NOT user-editable |
| dry_run | Boolean | True | Paper/Live toggle |
| enabled | Boolean | True | |
| start_balance | Float | 0.0 | 0 = use User.start_balance |
| balance_mode | String(16) | "live" | "live" or "manual" |
| status | String(32) | "stopped" | stopped, running, error, killed |
| hyperliquid_private_key_encrypted | Text | null | Fernet encrypted |
| account_address | String(64) | null | |
| withdrawal_address | String(64) | null | |
| created_at | DateTime | utcnow | |

## Trade
| Column | Type | Notes |
|--------|------|-------|
| id | String(36) PK | UUID |
| instance_slug | String(32) | FK → Instance.slug |
| side | String(8) | BUY, SELL |
| size | Float | |
| entry_price | Float | |
| exit_price | Float | null if open |
| pnl_usd | Float | |
| pnl_pct | Float | |
| status | String(16) | open, closed |
| timestamp | DateTime | |

## AccountSnapshot
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | autoincrement |
| instance_slug | String(32) | FK |
| account_value | Float | feeds Pulse Graph |
| margin_used | Float | |
| timestamp | DateTime | |

## PositionSnapshot
| Column | Type | Notes |
|--------|------|-------|
| id | String(36) PK | UUID |
| instance_slug | String(32) | FK |
| token | String(64) | |
| side | String(8) | LONG, SHORT, FLAT |
| size | Float | |
| entry_price | Float | |
| mark_price | Float | |
| unrealized_pnl | Float | |
| timestamp | DateTime | |

## Signal
| Column | Type | Notes |
|--------|------|-------|
| id | String(36) PK | UUID |
| instance_id | String(32) | |
| direction | String(8) | BUY, SELL, NEUTRAL |
| signal | Float | strength |
| trade_active | Boolean | |
| executed | Boolean | |
| metadata_json | JSON | |
| reasoning_text | Text | |

## Backtest
| Column | Type | Default | Notes |
|--------|------|---------|-------|
| id | String(36) PK | UUID | |
| instance_slug | String(32) | — | |
| kind | String(16) | "backtest" | "backtest" or "forward_test" |
| is_paper | Boolean | False | True if from Paper Trading |
| token | String(64) | — | |
| strategy_id | String(64) | — | |
| timeframe | String(16) | — | |
| mode | String(32) | — | |
| profile | String(64) | — | |
| activation | Integer | 8 | |
| offset | Integer | 3 | |
| leverage | Integer | 10 | |
| start_date | DateTime | — | |
| end_date | DateTime | — | |
| status | String(32) | "pending" | pending, running, done, error |
| initial_capital | Float | 1000.0 | |
| final_capital | Float | null | |
| total_return_pct | Float | 0.0 | |
| win_rate | Float | 0.0 | |
| profit_factor | Float | 0.0 | |
| max_drawdown_pct | Float | 0.0 | |
| total_trades | Integer | 0 | |
| sharpe_ratio | Float | 0.0 | |
| trades_json | JSON | [] | full trade list |
| equity_curve_json | JSON | [] | equity curve points |
| error_message | Text | null | |

## Strategy (TODO — to be created)
| Column | Type | Notes |
|--------|------|-------|
| id | String(36) PK | UUID |
| user_id | String(36) | FK → User |
| name | String | display name |
| strategy_id | String | unique slug (snake_case) |
| pine_source | Text | raw PineScript |
| python_source | Text | converted Python (null until converted) |
| documentation | Text | markdown docs |
|| status | String | "pending", "active", "error" |
|| parameters | JSON | extracted params |
|| created_at | DateTime | |
|| updated_at | DateTime | |

## ChatSession
|| Column | Type | Default | Notes |
||--------|------|---------|-------|
|| id | String(36) PK | UUID | session ID |
|| user_id | String(36) | — | FK → User.id |
|| title | String(128) | "New Chat" | session title (auto-set from first message) |
|| model | String(64) | null | model used for this session |
|| context | String(32) | "assistant" | assistant/studio/backtester/dashboard |
|| created_at | DateTime | utcnow | |
|| updated_at | DateTime | utcnow | onupdate |

## ChatMessage
|| Column | Type | Default | Notes |
||--------|------|---------|-------|
|| id | String(36) PK | UUID | message ID |
|| session_id | String(36) | — | FK → ChatSession.id |
|| role | String(16) | — | "user" or "assistant" |
|| content | Text | — | message text |
|| model | String(64) | null | model that generated this message |
|| created_at | DateTime | utcnow | |

(Cap: 10 sessions per user, oldest pruned on create; messages retained per session.)