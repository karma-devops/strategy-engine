# PULS-R Information Architecture Spec

> Living document. Updated as we build. Reference during implementation.

---

## 1. Sidebar Navigation

```
SIDEBAR NAV
├── Dashboard                         ← fleet overview, account equity, console
│
├── Engines                           ← collapsible, dynamic (unlimited instances)
│   ├── Overview (all engines)        ← grid with status/pnl/buttons
│   ├── engine-1 (FARTCOIN)          ← per-instance detail + settings modal
│   ├── engine-2 (HYPE)             ← per-instance detail + settings modal
│   ├── ... (unlimited, auto-generated from DB)
│   └── [+ Add Engine]               ← opens instance creation form
│
├── Strategies                        ← collapsible
│   ├── Overview                      ← list all registered strategies
│   ├── engine_v1_3 (Scalp 8/3)      ← strategy detail: Pine + Python + Docs
│   ├── engine_v1 (Swing 36/12)      ← strategy detail
│   ├── engine_v6_1 (PRO 18/6)       ← strategy detail
│   ├── [+ Upload Strategy]          ← upload PineScript (default), saves to DB, not usable until converted
│   └── Strategy Studio              ← Pine→Python AI converter + preview backtest
│
├── Testing                           ← collapsible (replaces Backtests + Paper)
│   ├── Historical                    ← backtest form + results + equity chart
│   └── Paper Trading                 ← forward-test instances (dry_run=True) with live controls
│
├── Trades                            ← all trades across all engines
│
├── Account                           ← collapsible
│   ├── Overview                      ← portfolio value, allocation, per-engine breakdown
│   ├── Settings                      ← start_balance, default_dry_run, display_name
│   ├── Secrets                       ← per-engine credential management (encrypted)
│   ├── Wallet                        ← withdrawal addresses, withdrawal config + history
│   └── API Keys                      ← single API key management + AI provider config
│
└── Assistant                         ← AI chat advisor with trading context
```

### Removed from old nav
- **Live** → engines show Live/Paper as a badge on each card
- **Paper** → merged into Testing > Paper Trading
- **Withdrawals** → merged into Account > Wallet
- **Settings** → merged into Account > Settings
- **Fleet sidebar section** → replaced by Engines section (dynamic children)

---

## 2. Engine Detail Page (`/app/engines/{slug}`)

### Layout (top to bottom)
1. **KPI row** (3 items): Status badge, Unrealized PnL, Mode (LIVE/PAPER)
2. **Performance hero** (4 cells): Win Rate, Total PnL, Closed Trades, Max Drawdown
3. **Two-column row**: Live Position card (left) + Strategy card (right)
4. **Trade History** table
5. **Recent Signals** table (if signals exist)
6. **Runner Console** (SSE, with Copy/Clear + live dot)
7. **Controls bar**: Start/Stop/Close/Restart + Settings gear + Back link

### Settings Modal (popup, gear icon in controls bar)
Only user-adjustable fields:
| Setting | User-editable? | Source / Notes |
|---------|---------------|----------------|
| Name | ✅ | Display name |
| Token | ✅ | HL metadata search dropdown |
| Strategy | ✅ | From strategy registry (only strategies with Python conversion done) |
| Timeframe | ✅ | 5m / 15m / 30m / 1h |
| Leverage | ✅ | Capped by HL maxLeverage for token |
| Max Position % | ✅ | 1-100% |
| Dry Run | ✅ | Toggle Paper/Live |
| Start Balance | ✅ | Per-instance override (0 = use account default) |
| Activation | ❌ | From strategy metadata (not user-set) |
| Offset | ❌ | From strategy metadata (not user-set) |
| Mode / Profile | ❌ | From strategy presets |
| Poll Interval | ❌ | System-level (30s default, not exposed) |

### Info Tooltips
Every metric, config field, and KPI gets a small `(?)` icon with a tooltip explaining:
- Win Rate: "Percentage of closed trades that were profitable"
- Total PnL: "Sum of realized PnL from all closed trades"
- Max Drawdown: "Largest peak-to-trough decline in equity during the period"
- Unrealized PnL: "Current profit/loss on open position, marked to market"
- Leverage: "Position multiplier. Higher = more risk"
- Max Position %: "Maximum % of account equity allocated per trade"
- Dry Run: "Paper mode = no real orders. Live = real HL orders with real capital"

---

## 3. Strategies Section

### Strategy Registration Flow (Pine-first)
1. User uploads PineScript code (textarea paste or file upload)
2. System saves to DB: `Strategy` model with `pine_source`, `status="pending"`, `python_source=NULL`
3. Strategy appears in Overview with status badge: "Pending Conversion" (orange)
4. User opens Strategy Studio, converts Pine → Python via AI
5. Converted Python saved to DB: `python_source` populated, `status="active"`
6. Strategy is now available in engine settings dropdown
7. Optional: user uploads Documentation MD for the strategy detail page

### Strategy Overview (`/app/strategies`)
- Grid of strategy cards showing: name, status (Active/Pending), description, key parameters
- Per-strategy aggregate performance (best backtest return, avg win rate, total trades)
- Click card → strategy detail page
- [+ Upload Strategy] button at top

### Strategy Detail (`/app/strategies/{strategy_id}`)
**Tabs: Overview · PineScript · Python · Documentation**

- **Overview tab:** strategy name, description, parameters (EMA periods, ATR mult, ADX threshold, trail activation/offset), all backtests using this strategy, all engines running it, aggregate performance
- **PineScript tab:** code viewer (read-only, syntax-highlighted) from `Strategy.pine_source`
- **Python tab:** code viewer (read-only, syntax-highlighted) from `Strategy.python_source`. If `python_source` is NULL, show "Not yet converted" + button to open Strategy Studio
- **Documentation tab:** rendered markdown from `Strategy.documentation` or strategy docstring

### Strategy Studio (`/app/strategies/studio`)
- Left panel: Pine input (textarea, pre-filled if converting an existing strategy)
- Right panel: Python output (textarea, AI-generated)
- Provider selector: uses the default AI provider from Account > API Keys
- Convert button → sends Pine to AI, receives Python
- Preview: run a quick backtest with the converted strategy
- Save: updates `Strategy.python_source` + `status="active"`

### Strategy Model (DB-backed)
```
Strategy:
  id (UUID, PK)
  user_id (FK)
  name (String)           — display name
  strategy_id (String)    — unique slug for registry (e.g. "my_scalp_v2")
  pine_source (Text)      — raw PineScript code
  python_source (Text)    — converted Python (NULL until converted)
  documentation (Text)    — markdown docs
  status (String)         — "pending" | "active" | "error"
  parameters (JSON)       — extracted strategy params (EMA periods, ATR mult, etc.)
  created_at (DateTime)
  updated_at (DateTime)
```

---

## 4. Testing Section

### Historical (`/app/testing/historical`)
- Backtest form: Token, Strategy, Timeframe, Days, Leverage (no Mode field)
- Activation auto-fetched from strategy metadata (not user input)
- Results table: Return, DD, Sharpe, WR, PF, Trades, Status
- After running: **equity curve SVG** (same buildPulse pattern from `equity_curve_json`)
- Trade markers on chart (buy/sell arrows at trade entry/exit points)
- Performance KPI strip below chart

### Paper Trading (`/app/testing/paper`)
- Instances with `dry_run=True` only
- Each shows: status, token, strategy, PnL, Start/Stop controls
- Forward-test results logged to Backtest table (`kind="forward_test", is_paper=True`)
- Equity curve from per-instance AccountSnapshot

---

## 5. Account Section

### Overview (`/app/account`)
- Portfolio Value (live HL), Start Balance, Open PnL, Active Engines
- Per-engine allocation breakdown (bar chart or table)

### Settings (`/app/account/settings`)
- `start_balance`, `default_dry_run`, `display_name`
- Already built at `/app/settings`

### Secrets (`/app/account/secrets`)
- Per-engine HL private key management (Fernet encrypted)
- UI shows masked addresses, allows setting per-engine keys
- Falls back to global env keys if not set

### Wallet (`/app/account/wallet`)
- Withdrawal addresses (per-engine)
- Withdrawal config + history + projection
- Already built at `/app/withdrawals`

### API Keys (`/app/account/api-keys`)
- Single API key (sufficient for now, but structured for multi-key future)
- Key creation/revoke UI
- **AI Provider Configuration** (this is where Assistant + Strategy Studio get their model):

| Provider | Key Field | URL Field | Default Model Slug | Model Options |
|----------|-----------|-----------|-------------------|---------------|
| Ollama Cloud | `OLLAMA_API_KEY` | `https://ollama-cloud.nousresearch.com/v1` | `glm-5.1` | glm-5.1, llama3.3-70b, qwen3-235b |
| OpenRouter | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` | `deepseek/deepseek-v4-flash` | deepseek/deepseek-v4-flash, deepseek/deepseek-r1, meta-llama/llama-4-scout |
| OpenAI | `OPENAI_API_KEY` | `https://api.openai.com/v1` | `gpt-4o-mini` | gpt-4o, gpt-4o-mini, o4-mini |
| Claude | `ANTHROPIC_API_KEY` | `https://api.anthropic.com/v1` | `claude-sonnet-4-20250514` | claude-sonnet-4-20250514, claude-haiku-4-20250422 |

- **Default Provider Selector:** user picks which provider the system uses (dropdown)
- **Default Model Slug:** free-text field with suggested options per provider (dropdown with "custom" option)
- Stored encrypted in DB (or env as fallback)

---

## 6. Assistant (`/app/assistant`)

- **Full-page chat** with shared `chat_widget.html` include (also embedded in Studio, Backtester, Dashboard)
- **Per-user model selection**: `User.assistant_model` + `coder_model` (default `glm-5.1` via Ollama Cloud; dropdown offers GLM-5.1, Llama 3.3 70B, Qwen3 235B, DeepSeek V3)
- **Per-user memory**: last 10 sessions persisted in `ChatSession`/`ChatMessage` tables; follow-up messages inject history
- **Context-awareness**:
  - Studio: injects Pine source + strategy name via `data-context-hint` (updates on textarea `input`)
  - Backtester: injects latest backtest results (return, WR, PF, DD, Sharpe, trades, status) via `data-context-hint`
  - Dashboard: general context (no auto-inject)
  - Assistant: general context (full page, no auto-inject)
- **Context hint prepended** to first message in new sessions only (not follow-ups)
- Backend: `POST /api/v2/chat` (Basic Auth), `GET /api/v2/chat/sessions` (last 10)
- **Model resolution**: `model_override` > `User.assistant_model`/`coder_model` > env `AI_MODEL` > `glm-5.1`
- Advisory only — cannot execute trades
- **Suggested questions**: "How is HYPE performing?", "What strategy should I use for SOL?", "Explain the current HYPE signal"

---

## 7. Technical Implications

### New Models Needed
- `Strategy` model (DB-backed strategy registry with Pine/Python/Docs sources)
- `ApiKey` model (id, user_id, key_hash, name, provider, created_at, revoked_at) — structured for future multi-key

### New Routes Needed
- `/app/strategies` — overview
- `/app/strategies/{strategy_id}` — detail with tabs
- `/app/strategies/studio` — Pine→Python converter
- `/app/strategies/upload` — strategy upload form
- `/app/testing/historical` — backtest (replaces `/app/backtests`)
- `/app/testing/paper` — paper trading (replaces `/app/paper`)
- `/app/account` — overview
- `/app/account/secrets` — per-engine credentials
- `/app/account/wallet` — withdrawals (move from `/app/withdrawals`)
- `/app/account/api-keys` — API key + AI provider config
- `/app/assistant` — AI chat (✅ built — full page + shared widget on 4 surfaces)

### New API Endpoints Needed
- `POST /api/v2/strategies/upload` — upload PineScript (textarea or file)
- `POST /api/v2/strategies/{id}/convert` — AI-convert Pine→Python
- `PUT /api/v2/strategies/{id}` — update (add docs, update Python)
- `POST /api/v2/chat` — ✅ built — AI advisor chat (per-user model, 10-session memory, context-aware)
- `GET /api/v2/chat/sessions` — ✅ built — list user's last 10 chat sessions

### Existing Routes to Keep
- `/app/dashboard` — fleet overview (enhanced)
- `/app/engines` — engine overview
- `/app/engines/{slug}` — engine detail (enhanced with settings modal + tooltips)
- `/app/trades` — all trades log
- `/app/settings` → redirect to `/app/account/settings`
- `/app/withdrawals` → redirect to `/app/account/wallet`
- `/app/backtests` → redirect to `/app/testing/historical`
- `/app/paper` → redirect to `/app/testing/paper`
- `/app/live` → remove (merged into engines)

### Engine Count
- **Unlimited.** No hard-coded 6-engine limit. `seed_default_fleet` seeds 2 on first boot. `POST /api/v2/instances` creates new instances with any slug. The "6-engine" comment in CONTEXT.md is outdated.

---

## 8. Build Priority

> **Status as of 2026-07-13:** Phases 1–5 COMPLETE + live worker verified + error page built (held for phase-6 trigger). Phases 6–10 pending.

1. ~~**Nav restructure** (layout.html)~~ ✅ **DONE (v49)** — collapsible sections, removed Live/Paper/Settings/Withdrawals as top-level
2. ~~**Engine detail settings modal**~~ ✅ **DONE (v50)** — popup with correct fields (no poll_interval, no activation/offset)
3. ~~**Info tooltips**~~ ✅ **DONE (v55/v56)** — engine detail + dashboard metrics, JS floating tooltip escapes overflow
4. ~~**Strategies overview + detail**~~ ✅ **DONE (v61)** — new pages with Pine/Python/Docs tabs
5. ~~**Strategy upload**~~ ✅ **DONE (v62–v64)** — Pine-first flow, DB-backed (`Strategy` model), pending→active status
6. **Strategy Studio** ✅ **BUILT (v72)** — Pine→Python AI converter (`core/llm.py` + studio page + convert/save endpoints). LLM call gated on a funded `AI_API_KEY` (env has `OPENROUTER_API_KEY_2` → 402; no reachable gateway in this box). Logic unit-verified; live run needs valid key.
7. **Testing section** ✅ **BUILT (v73)** — `/app/testing` landing + `/app/testing/historical` (backtest form/results/equity) + `/app/testing/paper` (forward-test equity). lightweight-charts for curves. Old `/app/backtests` + `/app/paper` → 301 redirects. OHLC persistence: `OHLCData` model + `save_ohlc_batch` on every fetch (5001 rows accumulated for FARTCOIN/15m). Live backtest verified (19.69% return, 12 trades).
8. **Account section** ✅ **BUILT** — per-engine HL credential selector, multi-wallet UI, credential manager, AI provider wiring
9. **AI Provider + Per-User Models + Chat Widget** ✅ **BUILT (v79)** — `/api/v2/chat` + `/chat/sessions`, `User.assistant_model`/`coder_model` (default glm-5.1), shared widget on Assistant/Studio/Backtester/Dashboard, context-awareness (Studio injects Pine source, Backtester injects latest stats)
10. **Chat Widget Styling** ⏳ PENDING — Port shadcn Bubble/Message design language to pure CSS