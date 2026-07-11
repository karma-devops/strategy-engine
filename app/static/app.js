/* ═══════════════════════════════════════════════
   PULS-R Dashboard — app.js
   Fixed: tab selection, close button, backtest UI
   ═══════════════════════════════════════════════ */

const API_BASE = window.location.origin;
const API_KEY = window.API_KEY || '';

let logs = [];
let instances = [];
let selectedSlug = null;
let pulseData = [];

function apiHeaders() { return { 'X-API-Key': API_KEY }; }
function apiHeadersJson() { return { ...apiHeaders(), 'Content-Type': 'application/json' }; }

/* ── Equity Curve ───────────────────────────── */
function fetchPulseData() {
    return fetch(`${API_BASE}/api/v2/metrics/account`, { headers: apiHeaders() })
        .then(r => r.ok ? r.json() : null)
        .then(data => {
            if (data && data.snapshots && data.snapshots.length) {
                pulseData = data.snapshots.map(s => ({ t: new Date(s.timestamp), v: s.account_value }));
                document.getElementById('stat-account').textContent = formatUsd(data.account_value || 0);
                document.getElementById('stat-drawdown').textContent = formatPct(-Math.abs(data.drawdown_pct || 0));
                document.getElementById('stat-active').textContent = data.active_engines || 0;
                const pnlEl = document.getElementById('stat-pnl');
                pnlEl.textContent = formatUsd(data.open_pnl || 0);
                pnlEl.className = 'stat-value ' + ((data.open_pnl || 0) >= 0 ? 'positive' : 'negative');
            } else {
                pulseData = [];
                document.getElementById('stat-account').textContent = '-';
                document.getElementById('stat-drawdown').textContent = '-';
                document.getElementById('stat-active').textContent = '0';
                document.getElementById('stat-pnl').textContent = '-';
            }
            drawPulse();
        })
        .catch(() => { pulseData = []; drawPulse(); });
}

function drawPulse() {
    const c = document.getElementById('pulse-canvas');
    if (!c) return;
    if (!pulseData.length) {
        c.innerHTML = '<div style="color:var(--text-2);font-size:12px;">No equity data yet</div>';
        return;
    }
    const values = pulseData.map(p => p.v);
    const max = Math.max(...values), min = Math.min(...values), range = max - min;
    if (range === 0) {
        c.innerHTML = `<div style="color:var(--text-2);font-size:12px;">Equity: $${values[0].toFixed(2)} (flat)</div>`;
        return;
    }
    const W = 600, H = 180, P = 12;
    const pts = values.map((v, i) => ({
        x: (i / (values.length - 1)) * (W - P * 2) + P,
        y: H - P - ((v - min) / range) * (H - P * 2)
    }));
    let pathD = `M ${pts[0].x} ${pts[0].y}`;
    for (let i = 1; i < pts.length; i++) {
        const cpx = (pts[i-1].x + pts[i].x) / 2;
        pathD += ` Q ${pts[i-1].x} ${pts[i-1].y} ${cpx} ${(pts[i-1].y + pts[i].y) / 2}`;
    }
    pathD += ` L ${pts[pts.length-1].x} ${pts[pts.length-1].y}`;
    const areaD = pathD + ` L ${W-P} ${H} L ${P} ${H} Z`;
    const trend = values[values.length-1] >= values[0];
    const lc = trend ? '#34d399' : '#fb7185';
    const gid = trend ? 'grad-g' : 'grad-r';
    c.innerHTML = `
        <svg width="100%" height="100%" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" style="display:block;">
            <defs>
                <linearGradient id="grad-g" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" style="stop-color:rgba(52,211,153,0.25)"/>
                    <stop offset="100%" style="stop-color:rgba(52,211,153,0)"/>
                </linearGradient>
                <linearGradient id="grad-r" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" style="stop-color:rgba(251,113,133,0.25)"/>
                    <stop offset="100%" style="stop-color:rgba(251,113,133,0)"/>
                </linearGradient>
            </defs>
            <path d="${areaD}" fill="url(#${gid})"/>
            <path d="${pathD}" fill="none" stroke="${lc}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" opacity="0.9"/>
            <circle cx="${pts[pts.length-1].x}" cy="${pts[pts.length-1].y}" r="3" fill="${lc}"/>
        </svg>`;
}

/* ── Fleet Toggle ─────────────────────────── */
function toggleFleet() {
    const grid = document.getElementById('instances-grid');
    const btn = document.getElementById('fleet-toggle-btn');
    grid.classList.toggle('collapsed');
    btn.textContent = grid.classList.contains('collapsed') ? 'Expand' : 'Collapse';
}

/* ── Trade History (global) ─────────────────── */
async function fetchTradeHistory() {
    const el = document.getElementById('trade-history');
    const countEl = document.getElementById('trade-count');
    if (!el) return;
    try {
        const res = await fetch(`${API_BASE}/api/v2/trades?limit=20`, { headers: apiHeaders() });
        const data = await res.json();
        const trades = data.trades || [];
        countEl.textContent = trades.length;
        if (!trades.length) {
            el.innerHTML = '<div class="empty">No trades yet.</div>';
            return;
        }
        el.innerHTML = trades.map(t => {
            const time = t.timestamp ? new Date(t.timestamp).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' }) : '';
            const pnl = t.pnl_usd || 0;
            const pnlStr = pnl >= 0 ? `+$${pnl.toFixed(2)}` : `-$${Math.abs(pnl).toFixed(2)}`;
            const pnlClass = pnl >= 0 ? 'positive' : 'negative';
            const side = t.side || 'LONG';
            const inst = instances.find(i => i.slug === t.instance_id);
            const symbol = inst ? inst.token : (t.instance_id || '?');
            return `
                <div class="trade-row">
                    <span class="trade-time">${time}</span>
                    <span class="trade-symbol">${escapeHtml(symbol)}</span>
                    <span class="trade-side ${side}">${side}</span>
                    <span class="trade-pnl ${pnlClass}">${pnlStr}</span>
                </div>`;
        }).join('');
    } catch (e) {
        el.innerHTML = '<div class="empty">Failed to load trades.</div>';
    }
}

/* ── Fleet ─────────────────────────────────── */
async function fetchInstances() {
    try {
        const res = await fetch(`${API_BASE}/api/v2/instances`, { headers: apiHeaders() });
        if (!res.ok) throw new Error('fetch failed');
        const data = await res.json();
        instances = data.instances || [];
        renderInstances(instances);
        const running = instances.filter(i => i.status === 'running').length;
        const pill = document.getElementById('global-status');
        pill.querySelector('.status-text').textContent = running > 0 ? `${running} Running` : 'Ready';
        pill.className = 'status-pill' + (running > 0 ? ' running' : '');
        document.getElementById('fleet-count').textContent = instances.length;
    } catch (e) {
        console.error('fetchInstances:', e);
        addLog('Connection lost', 'error');
    }
}

function renderInstances(instances) {
    const grid = document.getElementById('instances-grid');
    if (!instances.length) {
        grid.innerHTML = '<div class="empty">No engines yet. Click + to add one.</div>';
        return;
    }
    grid.innerHTML = instances.map(inst => {
        const statusClass = inst.status === 'running' ? 'tag-running' : 'tag-stopped';
        const sideClass = inst.position_side === 'LONG' ? 'tag-long' : inst.position_side === 'SHORT' ? 'tag-short' : 'tag-neutral';
        const activeClass = selectedSlug === inst.slug ? 'active' : '';
        const pnlClass = (inst.unrealized_pnl || 0) >= 0 ? 'positive' : 'negative';
        return `
            <div class="fleet-card ${activeClass}" onclick="selectInstance('${inst.slug}')">
                <div class="fleet-card-head">
                    <div>
                        <h3>${escapeHtml(inst.name)}</h3>
                        <div class="fleet-card-sub">${escapeHtml(inst.token)} · ${inst.strategy_id} · ${inst.timeframe}</div>
                    </div>
                    <span class="tag ${statusClass}">${inst.status}</span>
                </div>
                <div class="fleet-card-pnl ${pnlClass}">${formatUsd(inst.unrealized_pnl || 0)} (${formatPct(inst.unrealized_pnl_pct || 0)})</div>
                <div class="fleet-row"><span class="label">Side</span><span class="tag ${sideClass}">${inst.position_side || 'FLAT'}</span></div>
                <div class="fleet-row"><span class="label">Leverage</span><span>${inst.leverage}x</span></div>
                <div class="fleet-row"><span class="label">Max Pos</span><span>${(inst.max_position_pct * 100).toFixed(0)}%</span></div>
                <div class="fleet-row"><span class="label">Dry Run</span><span>${inst.dry_run ? 'Yes' : 'No'}</span></div>
                <div class="fleet-actions" onclick="event.stopPropagation()">
                    <button class="btn btn-secondary" onclick="controlInstance('${inst.slug}', 'restart')">Restart</button>
                    ${inst.status === 'running'
                        ? `<button class="btn btn-danger" onclick="controlInstance('${inst.slug}', 'stop')">Stop</button>`
                        : `<button class="btn btn-primary" onclick="controlInstance('${inst.slug}', 'start')">Start</button>`}
                    <button class="btn btn-secondary" onclick="closePosition('${inst.slug}')">Close Pos</button>
                </div>
            </div>`;
    }).join('');
}

/* ── Engine Detail ─────────────────────────── */
function selectInstance(slug) {
    selectedSlug = slug;
    const inst = instances.find(i => i.slug === slug);
    if (!inst) return;
    document.getElementById('detail-title').textContent = `${escapeHtml(inst.name)} (${inst.token})`;
    const actions = document.getElementById('detail-actions');
    actions.innerHTML = `
        <button class="btn btn-secondary" onclick="controlInstance('${inst.slug}', 'restart')">Restart</button>
        ${inst.status === 'running'
            ? `<button class="btn btn-danger" onclick="controlInstance('${inst.slug}', 'stop')">Stop</button>`
            : `<button class="btn btn-primary" onclick="controlInstance('${inst.slug}', 'start')">Start</button>`}
        <button class="btn btn-secondary" onclick="closePosition('${inst.slug}')">Close Pos</button>
    `;
    renderInstances(instances);
    loadDetailTab('overview', slug);
}

function loadDetailTab(tab, slug) {
    document.querySelectorAll('#detail-tabs .tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`#detail-tabs .tab[data-tab="${tab}"]`)?.classList.add('active');
    document.querySelectorAll('.detail-card .tab-pane').forEach(c => c.classList.remove('active'));
    document.getElementById(`tab-${tab}`).classList.add('active');
    if (tab === 'overview') renderOverview(slug);
    if (tab === 'signals') fetchSignals(slug);
    if (tab === 'trades') fetchTrades(slug);
    if (tab === 'backtests') renderBacktests(slug);
    if (tab === 'alerts') renderAlerts(slug);
    if (tab === 'settings') renderSettings(slug);
}

// Fix: tab click handler uses selectedSlug properly
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('tab') && e.target.closest('#detail-tabs')) {
        const tab = e.target.dataset.tab;
        if (selectedSlug) loadDetailTab(tab, selectedSlug);
    }
});

/* ── Overview Tab ─────────────────────────── */
function renderOverview(slug) {
    const inst = instances.find(i => i.slug === slug);
    if (!inst) return;
    const el = document.getElementById('tab-overview');
    const pnlClass = (inst.unrealized_pnl || 0) >= 0 ? 'positive' : 'negative';
    el.innerHTML = `
        <div class="metrics-grid">
            <div class="metric"><div class="label">Status</div><div class="value">${inst.status}</div></div>
            <div class="metric"><div class="label">Side</div><div class="value">${inst.position_side || 'FLAT'}</div></div>
            <div class="metric"><div class="label">Unrealized PnL</div><div class="value ${pnlClass}">${formatUsd(inst.unrealized_pnl || 0)}</div></div>
            <div class="metric"><div class="label">Strategy</div><div class="value">${inst.strategy_id}</div></div>
            <div class="metric"><div class="label">Token</div><div class="value">${inst.token}</div></div>
            <div class="metric"><div class="label">Timeframe</div><div class="value">${inst.timeframe}</div></div>
            <div class="metric"><div class="label">Leverage</div><div class="value">${inst.leverage}x</div></div>
            <div class="metric"><div class="label">Max Position</div><div class="value">${(inst.max_position_pct * 100).toFixed(0)}%</div></div>
        </div>
        <div class="log-area" style="max-height:160px;">
            <div class="log-line info">Token: ${inst.token} | Strategy: ${inst.strategy_id} | Timeframe: ${inst.timeframe}</div>
            <div class="log-line info">Profile: ${inst.profile || '-'} | Mode: ${inst.mode || '-'} | Poll: ${inst.poll_interval_seconds}s</div>
            <div class="log-line info">Dry Run: ${inst.dry_run ? 'Yes (safe mode)' : 'No (LIVE)'} | Activation: ${inst.activation || '-'} | Offset: ${inst.offset || '-'}</div>
        </div>`;
}

/* ── Signals Tab ─────────────────────────── */
async function fetchSignals(slug) {
    const el = document.getElementById('tab-signals');
    el.innerHTML = '<div class="log-area"><div class="log-line info">Loading signals...</div></div>';
    try {
        const res = await fetch(`${API_BASE}/api/v2/instances/${slug}/signals?limit=50`, { headers: apiHeaders() });
        const data = await res.json();
        const signals = data.signals || [];
        el.innerHTML = signals.length ? `<div class="log-area" style="max-height:350px;">${signals.map(s => {
            const ts = s.timestamp ? `[${formatTime(s.timestamp)}] ` : '';
            return `<div class="log-line ${s.direction === 'BUY' ? 'success' : s.direction === 'SELL' ? 'error' : 'info'}">${ts}${s.direction} signal=${s.signal.toFixed(2)} ${s.executed ? 'EXECUTED' : 'skipped'} ${s.reasoning_text ? '| ' + escapeHtml(s.reasoning_text) : ''}</div>`;
        }).join('')}</div>` : '<div class="empty">No signals yet.</div>';
    } catch (e) { el.innerHTML = '<div class="empty">Failed to load signals.</div>'; }
}

/* ── Trades Tab ─────────────────────────── */
async function fetchTrades(slug) {
    const el = document.getElementById('tab-trades');
    el.innerHTML = '<div class="log-area"><div class="log-line info">Loading trades...</div></div>';
    try {
        const res = await fetch(`${API_BASE}/api/v2/instances/${slug}/trades?limit=50`, { headers: apiHeaders() });
        const data = await res.json();
        const trades = data.trades || [];
        el.innerHTML = trades.length ? `<div class="log-area" style="max-height:350px;">${trades.map(t => {
            const ts = t.timestamp ? `[${formatTime(t.timestamp)}] ` : '';
            return `<div class="log-line ${(t.pnl_usd || 0) >= 0 ? 'success' : 'error'}">${ts}${t.side} ${formatUsd(t.pnl_usd || 0)} (${formatPct(t.pnl_pct || 0)})</div>`;
        }).join('')}</div>` : '<div class="empty">No trades yet.</div>';
    } catch (e) { el.innerHTML = '<div class="empty">Failed to load trades.</div>'; }
}

/* ── Backtests Tab ─────────────────────────── */
async function renderBacktests(slug) {
    const inst = instances.find(i => i.slug === slug);
    const el = document.getElementById('tab-backtests');
    el.innerHTML = `
        <div class="form-row">
            <div class="form-group">
                <label>Token</label>
                <input id="bt-token-${slug}" type="text" value="${inst.token}" placeholder="FARTCOIN">
            </div>
            <div class="form-group">
                <label>Strategy</label>
                <select id="bt-strategy-${slug}">
                    <option value="${inst.strategy_id}">${inst.strategy_id}</option>
                </select>
            </div>
            <div class="form-group">
                <label>Timeframe</label>
                <select id="bt-timeframe-${slug}">
                    <option value="${inst.timeframe}">${inst.timeframe}</option>
                    <option value="15m">15m</option>
                    <option value="30m">30m</option>
                    <option value="1h">1h</option>
                    <option value="4h">4h</option>
                </select>
            </div>
            <div class="form-group">
                <label>Leverage</label>
                <input id="bt-leverage-${slug}" type="number" min="1" max="50" value="${inst.leverage || 1}" style="width:70px;">
            </div>
            <div class="form-group">
                <label>Days</label>
                <input id="bt-days-${slug}" type="number" min="1" max="365" value="30" style="width:70px;">
            </div>
            <div class="form-group">
                <label>Capital (USDC)</label>
                <input id="bt-capital-${slug}" type="number" min="10" value="100" style="width:90px;">
            </div>
            <button class="btn btn-primary" onclick="runBacktest('${slug}')">Run Backtest</button>
            <span id="bt-msg-${slug}" style="font-size:12px;color:var(--text-2);"></span>
        </div>
        <div id="bt-results-${slug}" style="margin-bottom:14px;"></div>
        <div class="log-area" id="bt-list-${slug}" style="max-height:200px;"><div class="log-line info">Loading backtests...</div></div>
    `;
    // Populate strategy dropdown with all available strategies
    try {
        const sres = await fetch(`${API_BASE}/api/v2/strategies`, { headers: apiHeaders() });
        const sdata = await sres.json();
        const select = document.getElementById(`bt-strategy-${slug}`);
        if (sdata.strategies) {
            select.innerHTML = sdata.strategies.map(s => {
                const id = typeof s === 'string' ? s : s.id;
                return `<option value="${id}" ${id === inst.strategy_id ? 'selected' : ''}>${id}</option>`;
            }).join('');
        }
    } catch (e) { /* keep default */ }
    await fetchBacktests(slug);
}

async function runBacktest(slug) {
    const days = parseInt(document.getElementById(`bt-days-${slug}`).value, 10);
    const capital = parseFloat(document.getElementById(`bt-capital-${slug}`).value);
    const token = document.getElementById(`bt-token-${slug}`).value.trim().toUpperCase();
    const strategy = document.getElementById(`bt-strategy-${slug}`).value;
    const timeframe = document.getElementById(`bt-timeframe-${slug}`).value;
    const leverage = parseInt(document.getElementById(`bt-leverage-${slug}`).value, 10);
    const msgEl = document.getElementById(`bt-msg-${slug}`);
    msgEl.textContent = 'Running...';
    msgEl.style.color = 'var(--text-2)';
    try {
        const res = await fetch(`${API_BASE}/api/v2/backtests/run`, {
            method: 'POST',
            headers: apiHeadersJson(),
            body: JSON.stringify({ instance_slug: slug, days, initial_capital: capital, token, strategy_id: strategy, timeframe, leverage }),
        });
        const data = await res.json();
        if (data.ok && data.backtest) {
            msgEl.textContent = 'Done';
            msgEl.style.color = 'var(--green)';
            renderBacktestResult(data.backtest, slug);
        } else {
            msgEl.textContent = data.message || 'Failed';
            msgEl.style.color = 'var(--red)';
        }
    } catch (e) {
        msgEl.textContent = `Error: ${e.message}`;
        msgEl.style.color = 'var(--red)';
    }
    await fetchBacktests(slug);
}

function renderBacktestResult(bt, slug) {
    const el = document.getElementById(`bt-results-${slug}`);
    const statusClass = bt.status === 'done' ? 'success' : 'error';
    const retClass = (bt.total_return_pct || 0) >= 0 ? 'positive' : 'negative';
    el.innerHTML = `
        <div class="metrics-grid">
            <div class="metric"><div class="label">Status</div><div class="value ${statusClass}">${bt.status}</div></div>
            <div class="metric"><div class="label">Return</div><div class="value ${retClass}">${formatPct(bt.total_return_pct)}</div></div>
            <div class="metric"><div class="label">Trades</div><div class="value">${bt.total_trades}</div></div>
            <div class="metric"><div class="label">Win Rate</div><div class="value">${(bt.win_rate || 0).toFixed(1)}%</div></div>
            <div class="metric"><div class="label">Profit Factor</div><div class="value">${(bt.profit_factor || 0).toFixed(2)}</div></div>
            <div class="metric"><div class="label">Max DD</div><div class="value negative">${formatPct(bt.max_drawdown_pct)}</div></div>
            <div class="metric"><div class="label">Sharpe</div><div class="value">${(bt.sharpe || 0).toFixed(2)}</div></div>
        </div>
        ${bt.equity_curve && bt.equity_curve.length ? `<canvas id="bt-canvas-${bt.id}" class="bt-chart"></canvas>` : ''}
    `;
    if (bt.equity_curve && bt.equity_curve.length) {
        drawBacktestChart(`bt-canvas-${bt.id}`, bt.equity_curve);
    }
}

function drawBacktestChart(canvasId, equityCurve) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    const w = rect.width, h = rect.height;
    ctx.clearRect(0, 0, w, h);
    const values = equityCurve.map(p => p.equity);
    const min = Math.min(...values) * 0.99;
    const max = Math.max(...values) * 1.01;
    const range = max - min || 1;
    const step = w / (values.length - 1 || 1);
    const getY = v => h - ((v - min) / range) * h;
    // Area fill
    ctx.beginPath();
    ctx.moveTo(0, h);
    equityCurve.forEach((p, i) => {
        const x = i * step, y = getY(p.equity);
        if (i === 0) ctx.lineTo(x, y);
        else {
            const prev = equityCurve[i-1];
            const cp1x = (i - 1) * step + (x - (i-1) * step) / 2;
            ctx.bezierCurveTo(cp1x, getY(prev.equity), cp1x, y, x, y);
        }
    });
    ctx.lineTo(w, h);
    ctx.closePath();
    const grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, 'rgba(52, 211, 153, 0.3)');
    grad.addColorStop(1, 'rgba(52, 211, 153, 0.01)');
    ctx.fillStyle = grad;
    ctx.fill();
    // Line
    ctx.beginPath();
    equityCurve.forEach((p, i) => {
        const x = i * step, y = getY(p.equity);
        if (i === 0) ctx.moveTo(x, y);
        else {
            const prev = equityCurve[i-1];
            const cp1x = (i - 1) * step + (x - (i-1) * step) / 2;
            ctx.bezierCurveTo(cp1x, getY(prev.equity), cp1x, y, x, y);
        }
    });
    ctx.strokeStyle = '#34d399';
    ctx.lineWidth = 2;
    ctx.stroke();
}

async function fetchBacktests(slug) {
    const el = document.getElementById(`bt-list-${slug}`);
    if (!el) return;
    try {
        const res = await fetch(`${API_BASE}/api/v2/backtests?instance_slug=${slug}`, { headers: apiHeaders() });
        const data = await res.json();
        const list = data.backtests || [];
        el.innerHTML = list.length ? list.map(b => {
            const ts = b.created_at ? `[${formatTime(b.created_at)}] ` : '';
            const days = b.end_date && b.start_date ? Math.round((new Date(b.end_date) - new Date(b.start_date)) / (1000*60*60*24)) : 30;
            return `<div class="log-line ${b.status === 'done' ? 'success' : 'error'}">${ts}${days}d ${b.token} ${b.strategy_id} → ${formatPct(b.total_return_pct)} | ${b.total_trades} trades | WR ${(b.win_rate||0).toFixed(1)}% | PF ${(b.profit_factor||0).toFixed(2)} | DD ${formatPct(b.max_drawdown_pct)}</div>`;
        }).join('') : '<div class="log-line info">No backtests yet. Run one above.</div>';
    } catch (e) { el.innerHTML = '<div class="log-line error">Failed to load backtests.</div>'; }
}

/* ── Alerts Tab ─────────────────────────── */
async function renderAlerts(slug) {
    const el = document.getElementById('tab-alerts');
    el.innerHTML = `
        <div class="form-row">
            <button class="btn btn-primary" onclick="refreshAlerts('${slug}')">Evaluate Alerts</button>
            <button class="btn btn-secondary" onclick="refreshScores('${slug}')">Refresh Scores</button>
            <button class="btn btn-secondary" onclick="refreshRotation('${slug}')">Refresh Rotation</button>
            <span id="alerts-msg-${slug}" style="font-size:12px;color:var(--text-2);"></span>
        </div>
        <div id="alerts-scores-${slug}" style="margin-top:14px;"></div>
        <div id="alerts-rotation-${slug}" style="margin-top:14px;"></div>
        <div class="log-area" id="alerts-list-${slug}" style="margin-top:14px;max-height:200px;"><div class="log-line info">Loading alerts...</div></div>
    `;
    await Promise.all([fetchAlerts(slug), fetchScores(slug), fetchRotation(slug)]);
}

async function refreshAlerts(slug) {
    const msgEl = document.getElementById(`alerts-msg-${slug}`);
    msgEl.textContent = 'Evaluating...';
    try {
        const res = await fetch(`${API_BASE}/api/v2/alerts/evaluate`, { method: 'POST', headers: apiHeaders() });
        const data = await res.json();
        msgEl.textContent = `Created ${data.created || 0} alert(s)`;
        msgEl.style.color = 'var(--green)';
        await fetchAlerts(slug);
    } catch (e) { msgEl.textContent = `Error: ${e.message}`; msgEl.style.color = 'var(--red)'; }
}

async function refreshScores(slug) {
    const msgEl = document.getElementById(`alerts-msg-${slug}`);
    msgEl.textContent = 'Computing scores...';
    try {
        const res = await fetch(`${API_BASE}/api/v2/monitoring/scores/refresh`, {
            method: 'POST', headers: apiHeadersJson(), body: JSON.stringify({ days: 30 })
        });
        const data = await res.json();
        msgEl.textContent = `Scores refreshed for ${data.scores ? data.scores.length : 0} engine(s)`;
        msgEl.style.color = 'var(--green)';
        await fetchScores(slug);
    } catch (e) { msgEl.textContent = `Error: ${e.message}`; msgEl.style.color = 'var(--red)'; }
}

async function refreshRotation(slug) {
    const msgEl = document.getElementById(`alerts-msg-${slug}`);
    msgEl.textContent = 'Generating rotation...';
    try {
        const res = await fetch(`${API_BASE}/api/v2/monitoring/rotation/refresh`, { method: 'POST', headers: apiHeaders() });
        const data = await res.json();
        msgEl.textContent = `${data.recommendations ? data.recommendations.length : 0} recommendation(s)`;
        msgEl.style.color = 'var(--green)';
        await fetchRotation(slug);
    } catch (e) { msgEl.textContent = `Error: ${e.message}`; msgEl.style.color = 'var(--red)'; }
}

async function fetchScores(slug) {
    const el = document.getElementById(`alerts-scores-${slug}`);
    try {
        const res = await fetch(`${API_BASE}/api/v2/monitoring/scores`, { headers: apiHeaders() });
        const data = await res.json();
        const mine = (data.scores || []).find(s => s.instance_slug === slug);
        el.innerHTML = mine ? `
            <div class="metrics-grid">
                <div class="metric"><div class="label">Score</div><div class="value">${mine.score.toFixed(1)}</div></div>
                <div class="metric"><div class="label">Status</div><div class="value">${mine.status}</div></div>
                <div class="metric"><div class="label">Return</div><div class="value ${mine.return_pct >= 0 ? 'positive' : 'negative'}">${formatPct(mine.return_pct)}</div></div>
                <div class="metric"><div class="label">Win Rate</div><div class="value">${mine.win_rate.toFixed(1)}%</div></div>
                <div class="metric"><div class="label">PF</div><div class="value">${mine.profit_factor.toFixed(2)}</div></div>
                <div class="metric"><div class="label">DD</div><div class="value negative">${formatPct(mine.max_drawdown_pct)}</div></div>
            </div>` : '<div class="empty">No score computed yet. Click Refresh Scores.</div>';
    } catch (e) { el.innerHTML = '<div class="empty">Failed to load scores.</div>'; }
}

async function fetchRotation(slug) {
    const el = document.getElementById(`alerts-rotation-${slug}`);
    try {
        const res = await fetch(`${API_BASE}/api/v2/monitoring/rotation`, { headers: apiHeaders() });
        const data = await res.json();
        const recs = (data.recommendations || []).filter(r => r.instance_slug === slug && r.status === 'pending');
        el.innerHTML = recs.length ? recs.map(r => `
            <div class="log-line ${r.action === 'REDUCE' ? 'error' : r.action === 'INCREASE' ? 'success' : 'info'}">
                ${r.action}: ${r.reason}<br>
                Current ${r.current_allocation_pct ? r.current_allocation_pct.toFixed(1) : '-'}% → Suggested ${r.suggested_allocation_pct ? r.suggested_allocation_pct.toFixed(1) : '-'}%
                <button class="btn-sm" style="margin-left:8px;" onclick="approveRotation('${r.id}', true, '${slug}')">Approve</button>
                <button class="btn-sm" style="margin-left:4px;" onclick="approveRotation('${r.id}', false, '${slug}')">Reject</button>
            </div>`).join('') : '<div class="log-line info">No pending rotation recommendations.</div>';
    } catch (e) { el.innerHTML = '<div class="empty">Failed to load rotation.</div>'; }
}

async function approveRotation(recId, approved, slug) {
    const endpoint = approved ? 'approve' : 'reject';
    try {
        await fetch(`${API_BASE}/api/v2/monitoring/rotation/${recId}/${endpoint}`, { method: 'POST', headers: apiHeaders() });
        await fetchRotation(slug);
    } catch (e) { console.error('approveRotation:', e); }
}

async function fetchAlerts(slug) {
    const el = document.getElementById(`alerts-list-${slug}`);
    try {
        const res = await fetch(`${API_BASE}/api/v2/alerts?instance_slug=${slug}`, { headers: apiHeaders() });
        const data = await res.json();
        const list = data.alerts || [];
        el.innerHTML = list.length ? list.map(a => {
            const ts = a.created_at ? `[${formatTime(a.created_at)}] ` : '';
            const note = a.internal_note ? `<br><span style="color:var(--text-2);font-size:11px;">Note: ${escapeHtml(a.internal_note)}</span>` : '';
            return `<div class="log-line ${a.level === 'CRITICAL' ? 'error' : a.level === 'WARNING' ? 'warning' : 'info'}">
                ${ts}<strong>[${a.level}]</strong> ${escapeHtml(a.message)}${note}
                ${a.dismissed ? '' : `<button class="btn-sm" style="margin-left:8px;" onclick="dismissAlert('${a.id}', '${slug}')">Dismiss</button>`}
            </div>`;
        }).join('') : '<div class="log-line info">No alerts. Click Evaluate Alerts to scan.</div>';
    } catch (e) { el.innerHTML = '<div class="log-line error">Failed to load alerts.</div>'; }
}

async function dismissAlert(alertId, slug) {
    try {
        await fetch(`${API_BASE}/api/v2/alerts/${alertId}/dismiss`, { method: 'POST', headers: apiHeaders() });
        await fetchAlerts(slug);
    } catch (e) { console.error('dismissAlert:', e); }
}

/* ── Settings Tab ─────────────────────────── */
function renderSettings(slug) {
    const inst = instances.find(i => i.slug === slug);
    document.getElementById('tab-settings').innerHTML = `
        <form id="settings-form-${slug}" onsubmit="event.preventDefault(); saveSettings('${slug}');">
            <div class="settings-form">
                <div class="form-group">
                    <label>Max Position %</label>
                    <input id="max-pos-${slug}" type="number" min="1" max="100" value="${(inst.max_position_pct * 100).toFixed(0)}">
                </div>
                <div class="form-group">
                    <label>Leverage</label>
                    <input id="leverage-${slug}" type="number" min="1" max="50" value="${inst.leverage}">
                </div>
                <div class="form-group">
                    <label>Poll Interval (seconds)</label>
                    <input id="poll-${slug}" type="number" min="5" value="${inst.poll_interval_seconds}">
                </div>
                <div class="form-group">
                    <label>Activation</label>
                    <input id="activation-${slug}" type="number" min="1" value="${inst.activation || 8}">
                </div>
                <div class="form-group">
                    <label>Offset</label>
                    <input id="offset-${slug}" type="number" min="0" value="${inst.offset || 3}">
                </div>
                <div class="form-group">
                    <label>Dry Run</label>
                    <select id="dryrun-${slug}">
                        <option value="true" ${inst.dry_run ? 'selected' : ''}>Yes (safe)</option>
                        <option value="false" ${!inst.dry_run ? 'selected' : ''}>No (LIVE)</option>
                    </select>
                </div>
                <div class="form-group full">
                    <label>API Private Key (leave blank to keep existing)</label>
                    <input id="pk-${slug}" type="password" placeholder="0x...">
                </div>
                <div class="form-group full">
                    <label>Account / Withdrawal Address</label>
                    <input id="addr-${slug}" type="text" value="${inst.account_address_mask || ''}" placeholder="0x...">
                </div>
            </div>
            <button class="btn btn-primary" type="submit" style="margin-top:16px;">Save Settings</button>
            <span id="settings-msg-${slug}" style="margin-left:12px;font-size:12px;color:var(--text-2);"></span>
        </form>`;
}

async function saveSettings(slug) {
    const maxPos = parseFloat(document.getElementById(`max-pos-${slug}`).value) / 100;
    const leverage = parseInt(document.getElementById(`leverage-${slug}`).value, 10);
    const poll = parseInt(document.getElementById(`poll-${slug}`).value, 10);
    const activation = parseInt(document.getElementById(`activation-${slug}`).value, 10);
    const offset = parseInt(document.getElementById(`offset-${slug}`).value, 10);
    const dryRun = document.getElementById(`dryrun-${slug}`).value === 'true';
    const pk = document.getElementById(`pk-${slug}`).value.trim();
    const addr = document.getElementById(`addr-${slug}`).value.trim();
    const payload = { max_position_pct: maxPos, leverage, poll_interval_seconds: poll, activation, offset, dry_run: dryRun };
    if (pk) payload.hyperliquid_private_key = pk;
    if (addr) { payload.account_address = addr; payload.withdrawal_address = addr; }
    try {
        const res = await fetch(`${API_BASE}/api/v2/instances/${slug}`, {
            method: 'PUT', headers: apiHeadersJson(), body: JSON.stringify(payload)
        });
        const data = await res.json();
        const msgEl = document.getElementById(`settings-msg-${slug}`);
        if (data.ok) {
            msgEl.textContent = 'Saved';
            msgEl.style.color = 'var(--green)';
            await fetchInstances();
            if (selectedSlug === slug) selectInstance(slug);
        } else {
            msgEl.textContent = data.message || 'Save failed';
            msgEl.style.color = 'var(--red)';
        }
    } catch (e) { document.getElementById(`settings-msg-${slug}`).textContent = `Error: ${e.message}`; }
}

/* ── Control Actions ─────────────────────── */
async function controlInstance(id, action) {
    try {
        const res = await fetch(`${API_BASE}/api/v2/instances/${id}/${action}`, { method: 'POST', headers: apiHeaders() });
        const data = await res.json();
        addLog(data.message || `${action} ${id}`, data.ok ? 'success' : 'error');
        await fetchInstances();
    } catch (e) { addLog(`${action} failed: ${e.message}`, 'error'); }
}

async function closePosition(id) {
    try {
        const res = await fetch(`${API_BASE}/api/v2/instances/${id}/close`, { method: 'POST', headers: apiHeaders() });
        const data = await res.json();
        addLog(data.message || `Close ${id}`, data.ok ? 'success' : 'error');
        await fetchInstances();
    } catch (e) { addLog(`Close failed: ${e.message}`, 'error'); }
}

/* ── Logs ─────────────────────────────────── */
async function fetchLogs() {
    try {
        const res = await fetch(`${API_BASE}/api/v2/logs?limit=50`, { headers: apiHeaders() });
        if (!res.ok) return;
        const data = await res.json();
        logs = data.logs || [];
        renderLogs();
    } catch (e) { console.error('fetchLogs:', e); }
}

function renderLogs() {
    const el = document.getElementById('console');
    if (!logs.length) return;
    el.innerHTML = logs.map(log => {
        const ts = log.timestamp ? `[${formatTime(log.timestamp)}] ` : '';
        return `<div class="log-line ${log.level || 'info'}">${ts}${escapeHtml(log.message)}</div>`;
    }).join('');
    el.scrollTop = el.scrollHeight;
}

function addLog(message, level = 'info') {
    const el = document.getElementById('console');
    const line = document.createElement('div');
    line.className = `log-line ${level}`;
    line.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
    el.appendChild(line);
    el.scrollTop = el.scrollHeight;
}

async function copyLogs() {
    const text = logs.map(l => `[${l.timestamp || ''}] ${l.message}`).join('\n');
    try { await navigator.clipboard.writeText(text); addLog('Logs copied', 'success'); }
    catch (e) { addLog('Failed to copy logs', 'error'); }
}

function clearConsole() {
    document.getElementById('console').innerHTML = '<div class="log-line info">Console cleared.</div>';
    logs = [];
}

function refreshAll() {
    fetchPulseData();
    fetchInstances();
    fetchTradeHistory();
    fetchLogs();
    addLog('Manual refresh', 'info');
}

function updateClock() {
    const el = document.getElementById('clock');
    if (el) el.textContent = new Date().toLocaleTimeString();
}

/* ── SSE ─────────────────────────────────── */
function connectSSE() {
    const source = new EventSource(`${API_BASE}/stream`);
    source.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.type === 'instance_update') fetchInstances();
            if (data.log) addLog(data.log.message, data.log.level);
        } catch (e) { console.error('SSE parse:', e); }
    };
    source.onerror = () => { console.error('SSE error'); };
}

/* ── Utilities ───────────────────────────── */
function formatTime(iso) { try { return new Date(iso).toLocaleString(); } catch { return iso; } }
function formatUsd(n) { try { return '$' + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }); } catch { return '$' + n; } }
function formatPct(n) { try { const v = Number(n); return (v >= 0 ? '+' : '') + v.toFixed(2) + '%'; } catch { return n + '%'; } }
function escapeHtml(text) { if (!text) return ''; const d = document.createElement('div'); d.textContent = text; return d.innerHTML; }

window.addEventListener('resize', drawPulse);

(async function init() {
    await fetchPulseData();
    await fetchInstances();
    await fetchTradeHistory();
    await fetchLogs();
    connectSSE();
    setInterval(fetchInstances, 5000);
    setInterval(fetchLogs, 5000);
    setInterval(fetchTradeHistory, 10000);
    setInterval(fetchPulseData, 30000);
    setInterval(updateClock, 1000);
})();