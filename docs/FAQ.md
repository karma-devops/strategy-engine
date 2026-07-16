# PULS·R Strategy Engine — FAQ

## General

### What is PULS·R?
PULS·R is a systematic trading engine for HyperLiquid perpetuals. It runs Python strategies that generate signals, manages positions via stop-loss/trailing-stop/take-profit, and provides a full PWA dashboard for monitoring and configuration.

### What's the stack?
- **Backend:** Python FastAPI + SQLAlchemy (SQLite)
- **Frontend:** Server-rendered Jinja2 templates + vanilla JS
- **Exchange:** HyperLiquid perps (via official Python SDK)
- **Auth:** HTTP Basic Auth (UI) + X-API-Key (API)
- **PWA:** manifest.json + service worker

### How do I start the dev server?
```bash
cd /workspace/projects/strategy-engine
source venv/bin/activate
export $(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' .env | head -20)
export DATABASE_URL="sqlite:////workspace/projects/strategy-engine/data/dev_test.db"
export DRY_RUN=true
python3 -m uvicorn main:app --host 0.0.0.0 --port 8792
```

### How do I start the worker?
```bash
cd /workspace/projects/strategy-engine
source venv/bin/activate
export $(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' .env | head -20)
export DATABASE_URL="sqlite:////workspace/projects/strategy-engine/data/worker.db"
export DRY_RUN=true
python3 scripts/worker.py --port 9999
```

### What's the difference between the dev server and the worker?
- **Dev server (port 8792):** Full PWA + API + instance runner. Manages engines, trades, backtests, chat, settings. Uses the DB for persistence.
- **Worker (port 9999):** Standalone strategy loop. No DB. Runs one strategy on one token. Has its own minimal web UI for config and monitoring. Used for dedicated live/paper trading.

### What's the entrypoint?
`main:app` — NOT `app.main:app`.

---

## Strategies

### What strategies are available?
| ID | Name | Mode | Default TF | Trail |
|----|------|------|-----------|-------|
| `engine_v1_3` | Eve Engine v1.3 | Swing / Scalp | 15m | 10/4 (Scalp Default) |
| `engine_v1` | Eve Engine v1 (Swing) | Swing only | 1h | 36/12 (Sniper) |
| `engine_v6_1` | Engine v6.1 PRO | Scalp only | 15m | 18/6 |

### What are the three ports?
Each strategy script is standalone and declares three ports:

1. **strategy_config** (Port 1): Static per-instance parameters. Stored in DB, editable via UI settings panel. Pine `input.*` equivalent. Applied via `__init__(**config)`.
2. **entry_config** (Port 2): Per-signal output — direction (BUY/SELL/NEUTRAL), signal strength (0-1), metadata (ADX, EMA values, fan direction, pierce, pin bar). Consumer reads to decide entry.
3. **exit_config** (Port 3): Per-signal exit declaration — stop_loss, take_profit, trail_activation/offset, time_exit, EMA values for cross detection. Consumer is neutral — reads only what strategy declares.

### How do I change strategy parameters?
1. Open the engine detail page
2. Click "⚙ Edit Settings"
3. Scroll to "Strategy Parameters" section
4. Change any field (engine_mode, risk_profile, momentum_thresh, etc.)
5. Click Save

The parameters are stored per-instance in the `strategy_config` JSON column and applied when the runner starts.

### What parameters does v1.3 expose?
15 parameters across 6 groups:
- **Configuration:** engine_mode (Swing/Scalp)
- **Risk Management:** risk_profile (6 profiles), risk_per_trade_pct, atr_mult_input, atr_mult_guard
- **Hyper-Growth Protocol:** growth_target_x, use_momentum, momentum_thresh
- **Scalp Features:** use_fixed_tp, tp_multiplier, use_time_exit, max_bars_in_trade
- **Filters:** use_volume_confirm, volume_lookback, trade_direction

### How do I add a new strategy?
1. Create a new file in `engine/` (e.g. `engine/my_strategy.py`)
2. Subclass `BaseStrategy` from `engine/base.py`
3. Implement `get_parameters()` (returns list of parameter dicts)
4. Implement `generate_signals()` (returns dict with direction, signal, metadata, exit_config)
5. Register in `engine/registry.py` (add to `STRATEGIES` dict)
6. The PWA automatically picks it up — no UI changes needed

### How do I port a PineScript strategy?
See `STRATEGY_CONVERTER.md` for the full contract. Summary:
1. Read the PineScript, identify all `input.*` declarations → these become `get_parameters()`
2. Identify all indicator calculations (EMA, ATR, DMI, etc.) → translate to pandas/numpy
3. Identify entry conditions → return direction + signal + metadata
4. Identify exit conditions → populate exit_config (stop_loss, take_profit, trail, time_exit)
5. The runner/worker are neutral consumers — they evaluate only what you declare

---

## Engines

### How do I create an engine?
Via the UI: Engines → Add Engine. Fill in name, token, strategy, timeframe, leverage.
Via API: `POST /api/v2/instances` with JSON body.

### How do I start/stop an engine?
UI: Click Start/Stop on the fleet card or engine detail page.
API: `POST /api/v2/instances/{slug}/start` or `/stop`.

### What's the difference between Paper and Live?
- **Paper (dry_run=true):** Trades are simulated. Orders are sent to HL but with `DRY_RUN=true` — no real money moves.
- **Live (dry_run=false):** Real orders on HyperLiquid. Real money.

### How do I set per-engine HL credentials?
Engine detail → Settings → HyperLiquid Account dropdown. Choose Global (default account) or a specific credential from Account → Secrets.

---

## Multi-Tenant

### How does user isolation work?
Each user has their own:
- Username + password (User table)
- API keys (Credential table, per-user, Fernet encrypted)
- HL credentials (per-user, encrypted)
- Strategy config (per-instance `strategy_config` JSON)
- Strategies (uploaded/cloned, per-user `user_id`)
- Engines (instances, per-user `user_id`)
- Snapshots (per-instance `snapshot_data` + `snapshot_image_url`)

### How do I create a new tenant DB?
```bash
cp data/template_empty_STABLE.db data/tenant_{user_id}.db
```
The template has 20 tables, 1 operator user, 0 instances.

---

## Testing

### How do I reset to a clean slate?
```bash
# Kill all processes
kill $(pgrep -f 'uvicorn.*8792') 2>/dev/null
kill $(pgrep -f 'worker.*9999') 2>/dev/null

# Reset DB
cp data/template_empty_STABLE.db data/dev_test.db

# Start fresh
# (see startup commands above)
```

### Where is the empty DB template?
`data/template_empty_STABLE.db` (290KB, 20 tables, 1 operator user, 0 instances).

### How do I run the full test suite?
```bash
cd /workspace/projects/strategy-engine
source venv/bin/activate
# Start server first, then run:
python3 -c "
import requests
# ... test code (see NOTES.md for the full 61-test matrix)
"
```

---

## Troubleshooting

### Server won't start — "database disk image is malformed"
The DB file is corrupted. Reset from template:
```bash
rm -f data/dev_test.db data/dev_test.db-wal data/dev_test.db-shm
cp data/template_empty_STABLE.db data/dev_test.db
```

### Worker shows "No account value available"
HL credentials aren't reaching the worker process. Check:
1. `.env` file has `HYPER_LIQUID_ETH_PRIVATE_KEY` and `ACCOUNT_ADDRESS`
2. The export command uses `grep -E '^[A-Za-z_]' .env | head -20` (NOT `cat .env | xargs`)
3. Verify with: `curl -u operator:operator http://localhost:9999/api/state`

### Engine detail page shows empty / white screen
The server may have crashed. Check terminal output. Common causes:
- DB malformed (see above)
- Port already in use (kill old process first)
- Missing env vars

### Settings modal doesn't show strategy parameters
The engine detail page needs `strategy_parameters` in the template context. Verify:
1. The route passes it (check `app/routes.py` engine_detail_page)
2. The template has the `{% if strategy_parameters %}` block
3. The strategy has `get_parameters()` implemented

### "detect_mintick" UnboundLocalError
This was a bug in runner.py where a local import shadowed the module-level import. Fixed in Phase 4 of the Pine fidelity refactor. If you see it, you're running old code.

---

## Backups

### How do I create a backup?
```bash
cd /workspace/projects/strategy-engine
tar czf backups/v{N}_{context}_STABLE_YYYY-MM-DD_HHMM.tar.gz \
  --exclude=backups --exclude=venv --exclude=__pycache__ \
  --exclude='*.pyc' --exclude='data/*.db' --exclude='data/*.db-wal' \
  --exclude='data/*.db-shm' --exclude='data/logs' .
```

### How do I restore from a backup?
```bash
cd /workspace/projects/strategy-engine
tar xzf backups/v{N}_{context}_STABLE_YYYY-MM-DD_HHMM.tar.gz
```

### What's the latest STABLE backup?
v91 — Pine fidelity refactor Phases 1-8 complete. 61/61 tests PASS. Clean slate.
