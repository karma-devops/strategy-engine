# UI Components

> Reusable patterns. CSS classes, JS functions, template blocks.

## Page Structure
Every page extends `layout.html`:
```html
{% extends "layout.html" %}
{% block title %}PULS-R — {{ title }}{% endblock %}
{% block heading %}{{ title }}{% endblock %}
{% block content %} {# page body #} {% endblock %}
{% block scripts %} <script> {# page JS #} </script> {% endblock %}
```

## Layout Shell (layout.html)
- **Sidebar**: collapsible (220px ↔ 56px), SVG nav icons, localStorage persistence
- **Topbar**: page title, live clock, status pill, refresh button, e-stop button
- **Toast system**: `showToast(msg, type)` — types: success, error, info, warning
- **Mobile nav**: bottom bar at ≤768px
- **PWA**: manifest link + service worker registration

## Reusable Components

### KPI Grid
```html
<div class="kpi-grid">
    <div class="kpi">
        <div class="kpi-label">Label</div>
        <div class="kpi-value" id="kpi-id">value</div>
    </div>
</div>
```
CSS: 5-col grid, 9px labels, tabular-nums values, `.positive` / `.negative` classes

### Chart Card
```html
<div class="chart-card">
    <div class="card-head">
        <h2>Title</h2>
        <div class="card-actions">{# buttons #}</div>
    </div>
    {# content #}
</div>
```

### Pulse Graph (SVG)
```html
<div class="pulse-wrap">
    <svg class="pulse-svg" viewBox="0 0 1000 200">
        <defs><linear-gradient id="pulse-grad">...</linear-gradient></defs>
        <path class="pulse-path" id="pulse-path" />
        <path class="pulse-area" id="pulse-area" />
        <circle class="pulse-dot" id="pulse-dot" r="4" />
    </svg>
</div>
```
JS: `buildPulse()` — sign-aware (emerald positive, red negative), animated stroke-draw, stat strip

### Fleet Card
```html
<div class="fleet-card" onclick="window.location='/app/engines/{slug}'">
    <h3>{name}</h3>
    <div class="fleet-sub">{token} · {status}</div>
    <div class="fleet-actions">
        <button class="fleet-btn btn-start" onclick="apiPost('/api/v2/instances/{slug}/start')">Start</button>
    </div>
</div>
```

### Runner Console
```html
<div class="chart-card">
    <div class="card-head">
        <h2>Runner Console <span class="sse-dot" id="sse-dot"></span></h2>
        <div class="card-actions">
            <button class="btn-sm" onclick="copyConsole()">Copy</button>
            <button class="btn-sm" onclick="clearConsole()">Clear</button>
        </div>
    </div>
    <div id="console-log" class="console-log"></div>
</div>
```

### Data Table
```html
<div class="table-wrap">
    <table class="data-table">
        <thead><tr><th>...</th></tr></thead>
        <tbody>
            <tr class="row-win">{# profit row #}</tr>
            <tr class="row-loss">{# loss row #}</tr>
            <tr class="row-open">{# open trade #}</tr>
        </tbody>
    </table>
</div>
```

### Badge / Tag
```html
<span class="tag tag-running">running</span>
<span class="tag tag-stopped">stopped</span>
<span class="tag tag-long">LONG</span>
<span class="tag tag-short">SHORT</span>
<span class="tag tag-flat">FLAT</span>
```

## Standard JS Pattern
```javascript
const API_KEY = "{{ api_key }}";
const API_BASE = (location.origin || 'http://localhost:8792').replace(/^https?:\/\/[^@/]+@/, 'http://');

function apiPost(path) {
    fetch(API_BASE + path, { method: 'POST', headers: { 'X-API-Key': API_KEY } })
        .then(r => r.json()).then(j => { addConsole('cmd', j.message); refresh(); })
        .catch(e => addConsole('err', 'POST failed: ' + e));
}

function refresh() { /* GET /api/v2/summary, update DOM */ }
function addConsole(kind, msg) { /* SSE log line */ }
function copyConsole() { /* clipboard */ }
function clearConsole() { /* clear */ }

// SSE
const es = new EventSource(API_BASE + '/stream');
es.onmessage = ev => { /* log/signal/trade/ping */ };
es.onerror = () => { sseDot.className = 'sse-dot dead'; };

// Poll
refresh();
setInterval(refresh, 3000);
```

## Design Tokens
See `app/static/tokens.css` for full token reference. Key:
- Colors: `--color-profit` (emerald #10B981), `--color-loss` (coral #EF4444), `--brand` (teal #08798E)
- Surfaces: `--surface-card`, `--surface-inset`, `--surface-raised`, `--surface-hover`
- Spacing: `--space-1` (4px) → `--space-6` (24px)
- Radius: `--radius-sm`, `--radius-md`, `--radius-lg`, `--radius-full`
- Transitions: `--dur-fast` (120ms), `--dur-normal` (240ms)