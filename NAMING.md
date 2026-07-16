# PULS-R Naming Conventions

> Canonical reference. When in doubt, check here. Update when patterns evolve.

---

## 1. Routes (app/routes.py)

### UI Pages (HTML responses)
```
/app/{section}                    → section overview (e.g. /app/engines)
/app/{section}/{id}               → detail page (e.g. /app/engines/engine-2)
/app/{section}/{subsection}       → sub-page (e.g. /app/testing/historical)
/app/{section}/{id}/{subsection}  → nested detail sub (e.g. /app/strategies/engine_v1_3/python)
```

**Rules:**
- All UI routes prefixed with `/app/`
- `kebab-case` for section names: `/app/engines`, `/app/strategies`, `/app/testing`
- `{id}` is always the entity's natural key: `slug` for engines, `strategy_id` for strategies
- Legacy routes (`/app/live`, `/app/paper`, `/app/settings`, `/app/withdrawals`) redirect to new structure

### API Endpoints (api/*.py)
```
/api/v2/{resource}                        → list/create (GET/POST)
/api/v2/{resource}/{id}                    → get/update/delete (GET/PUT/DELETE)
/api/v2/{resource}/{id}/{action}           → action (POST, e.g. /start, /stop)
/api/v2/{resource}/{id}/{sub-resource}     → nested list (GET)
```

**Rules:**
- All API routes prefixed with `/api/v2/`
- `kebab-case` for resource names but currently `snake_case` in practice (instances, trades, backtests)
- `{id}` uses the entity's primary key: `instance_id` or `slug` for instances
- Action verbs: `start`, `stop`, `close`, `restart`, `kill`, `reset`
- Versioned: `v2` prefix (v1 was Flask, deprecated)

### Chat (Phase 9)
```
/api/v2/chat              → POST create message (Basic Auth, per-user model, 10-session memory)
/api/v2/chat/sessions    → GET list user's last 10 sessions (Basic Auth)
```

### Existing API patterns
| Resource | Path | ID field |
|----------|------|----------|
| instances | `/api/v2/instances` | `instance_id` (slug) |
| summary | `/api/v2/summary` | (global, no ID) |
| trades | `/api/v2/trades` | (global) or `/instances/{id}/trades` |
| backtests | `/api/v2/backtests` | `instance_slug` |
| metadata | `/api/v2/metadata` | (HL universe) |
| kill | `/api/v2/kill` | (global kill switch) |
| stream | `/stream` | (SSE, no /api/v2 prefix) |

---

## 2. Templates (app/templates/)

```
{section}.html              → overview page (e.g. engines.html, strategies.html)
{section}_detail.html       → detail page (e.g. engine_detail.html, strategy_detail.html)
{section}_{subsection}.html → sub-page (e.g. testing_historical.html)
layout.html                 → shared shell (sidebar, topbar, PWA, toast)
landing.html                → public landing page
{form}.html                 → form page (e.g. instance_form.html)
```

**Rules:**
- `snake_case` for filenames: `engine_detail.html`, not `engineDetail.html`
- Each page extends `layout.html` with `{% extends "layout.html" %}`
- Each page sets `{% block title %}`, `{% block heading %}`, `{% block content %}`, `{% block scripts %}`
- Active nav item set via `active` context variable: `active='engines'`

### Template block structure
```html
{% extends "layout.html" %}
{% block title %}PULS-R — {{ page_title }}{% endblock %}
{% block heading %}{{ page_title }}{% endblock %}
{% block content %}
    {# page content #}
{% endblock %}
{% block scripts %}
    <script>
        {# page-specific JS #}
    </script>
{% endblock %}
```

---

## 3. Models (instances/models.py)

```
class {EntityName}(Base):
    __tablename__ = "{snake_case_plural}"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # natural key if applicable (slug, strategy_id)
    # foreign keys
    # columns
    # timestamps (created_at, updated_at)
```

**Rules:**
- Class names: `PascalCase` singular: `Instance`, `Trade`, `Backtest`, `Strategy`
- Table names: `snake_case` plural: `instances`, `trades`, `backtests`, `strategies`
- IDs: UUID strings (36 chars) for most, `slug` (String 32) for instances
- Timestamps: `created_at`, `updated_at` (UTC, `DateTime`)
- Booleans: `is_*` prefix (`is_paper`, `dry_run`) or descriptive (`enabled`, `dismissed`)
- JSON columns: `*_json` suffix (`trades_json`, `equity_curve_json`, `metadata_json`)
- Encrypted fields: `*_encrypted` suffix (`hyperliquid_private_key_encrypted`)

### Existing models
| Model | Table | PK |
|-------|-------|-----|
| User | users | id (UUID) |
| Instance | instances | slug (String 32) |
| KillSwitchState | kill_switch_state | id (UUID) |
| Signal | signals | id (UUID) |
| CapitalBaseline | capital_baselines | id (UUID) |
| WithdrawalConfig | withdrawal_configs | id (UUID) |
| WithdrawalRecord | withdrawal_records | id (UUID) |
| Trade | trades | id (UUID) |
| PositionSnapshot | position_snapshots | id (UUID) |
| AccountSnapshot | account_snapshots | id (UUID) |
| Backtest | backtests | id (UUID) |
| Alert | alerts | id (UUID) |
| MonitoringScore | monitoring_scores | id (UUID) |
| RotationRecommendation | rotation_recommendations | id (UUID) |
| CandleCache | candle_cache | id (UUID) |

---

## 4. CSS Classes

### Naming pattern: BEM-lite
```
.{component}                     → container (e.g. .chart-card, .kpi-grid)
.{component}-{element}            → child element (e.g. .kpi-label, .kpi-value)
.{component}-{modifier}           → variant (e.g. .btn-start, .btn-stop, .tag-running)
.{state}                          → state class (e.g. .active, .negative, .positive)
```

**Rules:**
- `kebab-case` always: `.chart-card`, not `.chartCard`
- Component prefixes: `kpi-`, `fleet-`, `pos-`, `perf-`, `pulse-`, `console-`, `nav-`, `sidebar-`, `topbar-`, `toast-`, `bt-`
- State classes: `active`, `running`, `stopped`, `negative`, `positive`, `open`, `muted`, `empty`
- Tags (badges): `.tag` + `.tag-{value}`: `.tag-running`, `.tag-stopped`, `.tag-long`, `.tag-short`, `.tag-flat`
- Buttons: `.btn-{action}`: `.btn-start`, `.btn-stop`, `.btn-close`, `.btn-restart`, `.btn-sm`

### Design tokens (app/static/tokens.css)
```
--color-{name}          → --color-profit, --color-loss, --color-info
--color-{name}-bg       → background variant: --color-profit-bg
--color-{name}-border   → border variant: --color-profit-border
--space-{n}             → --space-1 (4px) through --space-6 (24px)
--text-{size}           → --text-xs, --text-sm, --text-md, --text-lg
--radius-{size}         → --radius-sm, --radius-md, --radius-lg, --radius-full
--dur-{speed}           → --dur-fast (120ms), --dur-normal (240ms)
--surface-{level}       → --surface-card, --surface-inset, --surface-raised, --surface-hover
--brand                 → primary brand color
--font-{role}           → --font-display, --font-mono
--weight-{level}        → --weight-regular, --weight-semibold, --weight-bold
```

---

## 5. JavaScript Functions

```
{verb}{Noun}()    → action functions: apiPost(), buildPulse(), renderFleet(), renderPositions()
{noun}{Verb}()    → rarely, when natural: consoleCopy() instead we use copyConsole()
```

**Rules:**
- `camelCase` for function names: `buildPulse`, `renderFleet`, `copyConsole`
- Constants: `UPPER_SNAKE_CASE`: `API_BASE`, `API_KEY`, `SLUG`, `DRY`
- DOM IDs: `kebab-case`: `console-log`, `pulse-path`, `kpi-pnl`, `pos-mark`
- Fetch wrapper: `apiPost(path)` for POST, inline `fetch()` for GET
- SSE: `EventSource` instance named `es`
- Poll: `setInterval(refresh, 3000)` — always 3s

### Standard page JS pattern
```javascript
const API_KEY = "{{ api_key }}";
const API_BASE = (location.origin || 'http://localhost:8792').replace(/^https?:\/\/[^@/]+@/, 'http://');

function apiPost(path) { /* POST wrapper */ }
function refresh() { /* GET /api/v2/summary, update DOM */ }
function addConsole(kind, msg) { /* SSE log line */ }
function copyConsole() { /* copy log to clipboard */ }
function clearConsole() { /* clear log */ }

// SSE stream
const es = new EventSource(API_BASE + '/stream');
es.onmessage = ev => { /* handle log/signal/trade/ping */ };

// Initial render + poll
refresh();
setInterval(refresh, 3000);
```

---

## 6. Strategy Naming

### Registry
```
engine_v{major}_{minor}    → e.g. engine_v1_3, engine_v1, engine_v6_1
```

**Rules:**
- `snake_case` strategy IDs in the registry
- Python class: `PascalCase` + `Strategy`: `EngineV1_3Strategy`
- File: `engine/v{version}.py`: `engine/v1_3.py`
- PineScript file: `pinescript-tv/{Name}.pine`: `Eve_Engine_v1_3.pine`
- Display name: human readable: "Scalp v1.3", "Swing v1", "PRO v6.1"

### User-uploaded strategies
- `strategy_id`: user-defined slug, `snake_case`, unique: `my_scalp_v2`, ` breakout_hunter`
- Status: `pending` (Pine only, not converted) → `active` (Python converted) → `error` (conversion failed)
- Stored in DB (Strategy model), not as files on disk

---

## 7. Instance Naming

### Slug
```
engine-{n}              → auto-generated: engine-1, engine-2, engine-3
{custom-slug}           → user-defined: hype-scalp, sol-swing
```

**Rules:**
- `kebab-case`, max 32 chars
- Auto-generated slugs increment from highest existing number
- User-defined slugs must be unique
- Slug is the primary key — never changes after creation

### Display name
```
{TOKEN} {Strategy} v{version}    → FARTCOIN Scalp v1.3, HYPE Paper v1.3
```

---

## 8. File Structure

```
strategy-engine/
├── main.py                    # FastAPI entry, lifespan, router includes
├── config.py                  # Env config (uppercase vars)
├── api/                       # API routers (v2)
│   ├── instances.py           # CRUD + control + delete
│   ├── metadata.py            # HL universe + stats
│   ├── signals.py
│   ├── positions.py
│   ├── metrics.py
│   ├── withdrawals.py
│   ├── strategies.py          # Strategy CRUD + upload + convert
│   ├── killswitch.py
│   ├── backtests.py
│   ├── monitoring.py
│   ├── stream.py              # SSE
│   ├── auth.py                # Basic Auth + API key
│   └── ratelimit.py           # Rate limiting
├── app/                       # UI layer
│   ├── routes.py              # UI routes (HTML responses)
│   ├── static/                # CSS, manifest, sw.js
│   └── templates/             # Jinja2 templates
├── core/                      # HyperLiquid integration
│   ├── exchange.py            # HL exchange client
│   ├── market_data.py         # OHLCV + metadata
│   └── position_sizer.py
├── instances/                 # Instance management
│   ├── models.py              # SQLAlchemy models
│   ├── manager.py             # Fleet seeding, lifecycle
│   ├── runner.py              # One instance loop
│   └── events.py              # Event bus
├── engine/                    # Strategy implementations
│   ├── registry.py           # Strategy registry + fleet seed
│   ├── base.py                # BaseStrategy
│   ├── v1_3.py                # Scalp v1.3
│   ├── v1.py                  # Swing v1
│   └── v6_1.py                # PRO v6.1
├── backtests/                 # Backtest runner
├── scripts/                   # Standalone operational scripts (separate processes)
│   └── worker.py              # Live strategy worker — port 9999, standalone FastAPI, NOT an /app route. Config via /api/config, control via /api/start|/api/stop, state via /api/state, logs via /stream (SSE).
├── pinescript-tv/             # PineScript source files
├── backups/                   # ADIX versioned backups
├── data/                      # SQLite DB
├── wiki/                      # Project wiki (see below)
├── CONTEXT.md                 # Project context (rules, scope)
├── NOTES.md                   # Session memory (fluid state)
├── SPECSHEET.md               # Full specification
├── IA-SPEC.md                 # Information architecture spec
├── NAMING.md                  # This file
├── HANDOVER.md                # Session handoff
├── DEPLOYMENT.md              # Deployment guide
└── PIPE-ARCHITECTURE.md       # Pipeline architecture