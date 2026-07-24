# Setup Guide

> Environment, keys, first run, DB seed.

## Environment Variables

| Var | Required | Default | Purpose |
|-----|----------|---------|---------|
| `FLASK_SECRET_KEY` | ✅ | — | Session encryption |
| `DASHBOARD_USERNAME` | ✅ | — | Login username |
| `DASHBOARD_PASSWORD` | ✅ | — | Login password |
| `DASHBOARD_EMAIL` | ✅ | — | Account email |
| `PORT` | ❌ | 5000 | (unused — see STRATEGY_ENGINE_PORT) |
| `STRATEGY_ENGINE_PORT` | ❌ | 8792 | Actual server port |
| `DRY_RUN` | ❌ | true | Global default (instance-level overrides) |
| `AGENT_API_KEY` | ✅ | — | API key for /api/v2 endpoints |
| `AI_PROVIDER` | ❌ | ollama | ollama, openrouter, openai, anthropic |
| `AI_MODEL` | ❌ | glm-5.1 | Model slug |
| `AI_BASE_URL` | ❌ | — | OpenAI-compatible endpoint |
| `AI_API_KEY` | ❌ | — | AI provider key |
| `HYPER_LIQUID_ETH_PRIVATE_KEY` | ❌ | — | HL wallet key (global, per-instance overrides) |
| `HYPER_LIQUID_KEY` | ❌ | — | HL API wallet key |
| `ACCOUNT_ADDRESS` | ❌ | — | HL account address |
| `ACTIVE_STRATEGY` | ❌ | engine_v1_3 | Default strategy for new instances |

## First Run
```bash
cd /workspace/projects/strategy-engine
source venv/bin/activate
export FLASK_SECRET_KEY=your-secret
export DASHBOARD_USERNAME=operator DASHBOARD_PASSWORD=operator DASHBOARD_EMAIL=you@email.com
export AGENT_API_KEY=your-api-key
python3 main.py
```

## Live Trading
Add HL keys to env (never write to files):
```bash
export DRY_RUN=false
export HYPER_LIQUID_ETH_PRIVATE_KEY=0x...
export HYPER_LIQUID_KEY=0x...
export ACCOUNT_ADDRESS=0x...
```

## Server Management
- Port: 8792
- Health check: `GET /health` → `{dry_run: true/false}`
- Swagger: `GET /docs`
- Kill stale: `for p in /proc/[0-9]*; do if grep -qa "main.py" "$p/cmdline" 2>/dev/null; then ... fi; done`
- Background launch: `terminal(background=true)` with env vars exported inline