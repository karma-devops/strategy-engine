# PULS·R Strategy Engine — FAQ

> LIVE + STABLE as of 2026-07-24. Paths reflect the post-Track-1 layout (`strategies/`, not `engine/`).

## General

### What is PULS·R?
A systematic trading engine for HyperLiquid perpetuals. It runs Python strategies that generate signals, manages positions via stop-loss / trailing-stop / take-profit, and provides a full PWA dashboard for monitoring and configuration.

### What's the stack?
- **Backend:** Python FastAPI + SQLAlchemy (SQLite)
- **Frontend:** Server-rendered Jinja2 templates + vanilla JS (in `app/templates`, `app/static`)
- **Exchange:** HyperLiquid perps (official Python SDK via `core/exchange.py`)
- **Auth:** HTTP Basic Auth (UI) + `X-API-Key` (API)
- **PWA:** `app/static/manifest.json` + `app/static/sw.js` (service worker)

### How do I start the server?
```bash
cd /workspace/projects/strategy-engine
./venv/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8792
```
Entrypoint is `main:app` (NOT `app.main:app`). Stop all running instances first via API, then kill every `uvicorn main:app` process (stale duplicates survive a single kill), confirm port free, relaunch one. Full runbook in `NOTES.md`.

### What's the entrypoint?
`main:app`.

---

## Strategies

### What strategies are available?
| ID | Name | Mode | Default TF | Trail |
|----|------|------|-----------|-------|
| `strategy_v1_3` | Eve Engine v1.3 | Swing / Scalp | 15m | 10/4 (Scalp Default) |
| `strategy_v1` | Eve Engine v1 (Swing) | Swing only | 1h | 36/12 (Sniper) |
| `strategy_v6_1` | Engine v6.1 PRO | Scalp only | 15m | 18/6 |

### What are the three ports?
Each strategy exposes three ports (see `VOCABULARY.md`):
1. **strategy_config** (Port 1): static per-instance params. Declared via `get_parameters()`; rendered in the engine settings panel. Applied via `__init__(**config)`.
2. **entry_config** (Port 2): per-signal output — direction, strength (0–1), metadata.
3. **exit_config** (Port 3): per-signal exit — stop_loss, take_profit, trail, time_exit.

### How do I change strategy parameters?
1. Open the engine detail page (`/app/engines/{slug}`)
2. Click "⚙ Edit Settings"
3. Scroll to "Strategy Parameters"
4. Change fields (engine_mode, risk_profile, momentum_thresh, etc.)
5. Click Save → writes `instances/{slug}/config.yaml` (authoritative) + DB copy; engine restarts.

### How do I add a new strategy?
1. Create `strategies/{slug}/strategy-name.py`
2. Subclass `BaseStrategy` from `strategies/base.py`
3. Implement `get_parameters()` (returns list of parameter dicts)
4. Implement `generate_signals()` (returns direction, signal, metadata, exit_config)
5. The registry (`strategies/registry.py`) auto-discovers it via `importlib` — no manual registration needed.
The PWA picks it up automatically.

### How do I port a PineScript strategy?
Translate Pine `input.*` → `get_parameters()`, indicators → pandas/numpy, entry/exit conditions → the 3 ports. The runner/worker are neutral consumers — they evaluate only what you declare. (Pine→Python helper lives in `core/llm.py`; fidelity score recorded in the strategy's `-doc.md`.)

---

## Engines / Instances

### How do I create an instance?
- UI: `Engines` → Add Engine. Fill name, token, strategy, timeframe, leverage.
- API: `POST /api/v2/instances` with JSON body.

### How do I start/stop an instance?
- UI: Start/Stop on the fleet card or engine detail page.
- API: `POST /api/v2/instances/{slug}/start` or `/stop`.

### Paper vs Live?
- **Paper (dry_run=true):** simulated; orders sent to HL with `DRY_RUN=true` — no real money.
- **Live (dry_run=false):** real HyperLiquid orders, real money.

### How do I clone an instance?
Clone = copy `instances/{slug}/config.yaml` under a new slug + reference the same engine/strategy. The config is git-tracked, so snapshots are diffable + restorable (`clone_instance(slug, new_slug)`).

---

## Frontend (actual pages)
All served by `app/routes.py` (mounted as `ui_routes`), Basic-Auth gated:
- `/` landing · `/app/dashboard` · `/app/engines` + `/app/engines/{slug}`
- `/app/strategies` + `/app/strategies/{id}` + `/app/strategies/studio` + `/app/strategies/upload`
- `/app/instances/new` · `/app/trades` · `/app/backtests` · `/app/testing` (+ `/historical`, `/paper`)
- `/app/withdrawals` · `/app/account` + `/settings` + `/secrets` · `/app/assistant` · `/app/live` · `/app/paper` · `/spec`

Key static assets: `pulsr-chart.js` (charts), `position-card.js`, `instance_form.js`, `withdrawals.js`, `chat_widget.js` + `chat_widget.css`, `style.css`, `tokens.css`.

---

## Testing

### How do I reset to a clean slate?
```bash
# Kill server
for p in /proc/[0-9]*/cmdline; do
  [ "$(tr '\0' ' ' < "$p" | cut -d' ' -f1)" = "python3" ] || continue
  tr '\0' ' ' < "$p" | grep -q 'python3 -m uvicorn main:app' && kill -TERM "$(echo $p|cut -d/ -f3)"
done
# Reset DB from template
cp data/template_empty_STABLE.db data/dev_test.db
```
(Replace `dev_test.db` with your active DB. Do NOT touch `backups/`.)

### Where is the empty DB template?
`data/template_empty_STABLE.db` (gitignored, 20 tables, 1 operator user, 0 instances).

---

## Troubleshooting

### "database disk image is malformed"
DB corrupted. Reset from template (see above).

### Engine detail page shows empty / white screen
Server may have crashed. Check the uvicorn log. Common causes: DB malformed, port in use (kill old first), missing env vars.

### Settings modal doesn't show strategy parameters
The engine detail route must pass `strategy_parameters` into the template, the template needs the `{% if strategy_parameters %}` block, and the strategy must implement `get_parameters()`.

---

## Backups

### How do I create a backup?
```bash
cd /workspace/projects/strategy-engine
tar czf backups/v{N}_{context}_STABLE_YYYY-MM-DD_HHMM.tar.gz \
  --exclude=backups --exclude=venv --exclude=__pycache__ \
  --exclude='*.pyc' --exclude='*.db*' --exclude='*.env' --exclude='.env' .
```

### How do I restore?
```bash
cd /workspace/projects/strategy-engine
tar xzf backups/v{N}_{context}_STABLE_YYYY-MM-DD_HHMM.tar.gz
```

### What's the latest STABLE backup?
See `backups/VERSIONING.md` (current track is `v2.03.xxx`). Deprecated docs archived under `backups/deprecated-docs_2026-07-24/`.
