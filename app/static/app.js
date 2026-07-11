const API_BASE = window.location.origin;
const API_KEY = window.API_KEY || '';

let logs = [];
let instances = [];
let selectedSlug = null;
let pulseData = [];

function apiHeaders() {
    return { 'X-API-Key': API_KEY };
}

// Pulse Graph -----------------------------------------------------------------
function fetchPulseData() {
    return fetch(`${API_BASE}/api/v2/metrics/account`, { headers: apiHeaders() })
        .then(r => r.ok ? r.json() : null)
        .then(data => {
            if (data && data.snapshots && data.snapshots.length) {
                pulseData = data.snapshots.map(s => ({ t: new Date(s.timestamp), v: s.account_value }));
                document.getElementById('stat-account').textContent = formatUsd(data.account_value || 0);
                document.getElementById('stat-drawdown').textContent = formatPct(-Math.abs(data.drawdown_pct || 0));
                document.getElementById('stat-active').textContent = data.active_engines || 0;
                document.getElementById('stat-pnl').textContent = formatUsd(data.open_pnl || 0);
            } else {
                pulseData = _demoPulse();
                document.getElementById('stat-account').textContent = '-';
                document.getElementById('stat-drawdown').textContent = '-';
            }
            drawPulse();
        })
        .catch(() => {
            pulseData = _demoPulse();
            drawPulse();
        });
}

function _demoPulse() {
    return [];
}

function drawPulse() {
    const container = document.getElementById('pulse-canvas');
    if (!container) return;

    if (!pulseData.length) {
        container.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:40px 0;font-size:13px;">No equity data yet</div>';
        return;
    }

    const values = pulseData.map(p => p.v);
    const max = Math.max(...values);
    const min = Math.min(...values);
    const range = max - min;

    if (range === 0) {
        container.innerHTML = `<div style="text-align:center;color:var(--text-muted);padding:40px 0;font-size:13px;">Equity: $${values[0].toFixed(2)} (flat)</div>`;
        return;
    }

    const width = 600;
    const height = 180;
    const padding = 10;

    const points = values.map((val, i) => {
        const x = (i / (values.length - 1)) * (width - padding * 2) + padding;
        const y = height - padding - ((val - min) / range) * (height - padding * 2);
        return { x, y };
    });

    // Smooth path using quadratic bezier
    let pathD = `M ${points[0].x} ${points[0].y}`;
    for (let i = 1; i < points.length; i++) {
        const prev = points[i - 1];
        const curr = points[i];
        const cpx = (prev.x + curr.x) / 2;
        const cpy = (prev.y + curr.y) / 2;
        pathD += ` Q ${prev.x} ${prev.y} ${cpx} ${cpy}`;
    }
    pathD += ` L ${points[points.length - 1].x} ${points[points.length - 1].y}`;

    const areaD = pathD + ` L ${width - padding} ${height} L ${padding} ${height} Z`;

    const trend = values[values.length - 1] >= values[0];
    const lineColor = trend ? '#34d399' : '#fb7185';
    const gradientId = trend ? 'gradient-green' : 'gradient-red';

    container.innerHTML = `
        <svg width="100%" height="100%" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" style="display:block;">
            <defs>
                <linearGradient id="gradient-green" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" style="stop-color: rgba(52, 211, 153, 0.3); stop-opacity: 1" />
                    <stop offset="100%" style="stop-color: rgba(52, 211, 153, 0); stop-opacity: 0" />
                </linearGradient>
                <linearGradient id="gradient-red" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" style="stop-color: rgba(251, 113, 133, 0.3); stop-opacity: 1" />
                    <stop offset="100%" style="stop-color: rgba(251, 113, 133, 0); stop-opacity: 0" />
                </linearGradient>
            </defs>
            <path d="${areaD}" fill="url(#${gradientId})" opacity="0.5"/>
            <path d="${pathD}" fill="none" stroke="${lineColor}" stroke-width="2"
                  stroke-linecap="round" stroke-linejoin="round"
                  filter="drop-shadow(0 0 3px ${lineColor})" opacity="0.9"/>
            <circle cx="${points[points.length - 1].x}" cy="${points[points.length - 1].y}"
                    r="3" fill="${lineColor}" filter="drop-shadow(0 0 4px ${lineColor})"/>
        </svg>
    `;
}

// Fleet -----------------------------------------------------------------------
async function fetchInstances() {
    try {
        const res = await fetch(`${API_BASE}/api/v2/instances`, { headers: apiHeaders() });
        if (!res.ok) throw new Error('Instances fetch failed');
        const data = await res.json();
        instances = data.instances || [];
        renderInstances(instances);
        const running = instances.filter(i => i.status === 'running').length;
        document.getElementById('global-status').textContent = running > 0 ? `${running} running` : 'Ready';
        document.getElementById('global-status').className = running > 0 ? 'agent-badge running' : 'agent-badge ready';
        document.getElementById('fleet-count').textContent = instances.length;
    } catch (e) {
        console.error('fetchInstances error:', e);
        addLog('Connection lost', 'error');
    }
}

function renderInstances(instances) {
    const grid = document.getElementById('instances-grid');
    if (!instances.length) {
        grid.innerHTML = '<div class="empty-state">No engines yet. Add one to start.</div>';
        return;
    }
    grid.innerHTML = instances.map(inst => {
        const statusClass = inst.status === 'running' ? 'running' : 'stopped';
        const sideClass = inst.position_side === 'LONG' ? 'long' : inst.position_side === 'SHORT' ? 'short' : 'neutral';
        const activeClass = selectedSlug === inst.slug ? 'active' : '';
        const pnlClass = (inst.unrealized_pnl || 0) >= 0 ? 'positive' : 'negative';
        return `
            <div class="fleet-card ${activeClass}" onclick="selectInstance('${inst.slug}')">
                <div class="card-header">
                    <div>
                        <h3>${escapeHtml(inst.name)}</h3>
                        <div class="token">${escapeHtml(inst.token)} · ${inst.strategy_id} · ${inst.timeframe}</div>
                    </div>
                    <span class="badge ${statusClass}">${inst.status}</span>
                </div>
                <div class="card-body">
                    <div class="pnl ${pnlClass}">${formatUsd(inst.unrealized_pnl || 0)} (${formatPct(inst.unrealized_pnl_pct || 0)})</div>
                    <div class="row"><span class="label">Side</span><span class="badge ${sideClass}">${inst.position_side || 'FLAT'}</span></div>
                    <div class="row"><span class="label">Leverage</span><span>${inst.leverage}x</span></div>
                    <div class="row"><span class="label">Max Pos</span><span>${(inst.max_position_pct * 100).toFixed(0)}%</span></div>
                    <div class="row"><span class="label">Dry Run</span><span>${inst.dry_run ? 'Yes' : 'No'}</span></div>
                    <div class="actions" onclick="event.stopPropagation()">
                        <button class="btn-secondary" onclick="controlInstance('${inst.slug}', 'restart')">Restart</button>
                        ${inst.status === 'running'
                            ? `<button class="btn-danger" onclick="controlInstance('${inst.slug}', 'stop')">Stop</button>`
                            : `<button class="btn-primary" onclick="controlInstance('${inst.slug}', 'start')">Start</button>`}
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// Detail panel ---------------------------------------------------------------
function selectInstance(slug) {
    selectedSlug = slug;
    const inst = instances.find(i => i.slug === slug);
    if (!inst) return;
    document.getElementById('detail-title').textContent = `${escapeHtml(inst.name)} (${inst.token})`;
    const actions = document.getElementById('detail-actions');
    actions.innerHTML = `
        <button class="btn-secondary" onclick="controlInstance('${inst.slug}', 'restart')">Restart</button>
        ${inst.status === 'running'
            ? `<button class="btn-danger" onclick="controlInstance('${inst.slug}', 'stop')">Stop</button>`
            : `<button class="btn-primary" onclick="controlInstance('${inst.slug}', 'start')">Start</button>`}
    `;
    renderInstances(instances);
    loadDetailTab('overview', slug);
}

function loadDetailTab(tab, slug) {
    document.querySelectorAll('#detail-tabs .tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`#detail-tabs .tab[data-tab="${tab}"]`)?.classList.add('active');
    document.querySelectorAll('#detail-card .tab-content').forEach(c => c.classList.remove('active'));
    document.getElementById(`tab-${tab}`).classList.add('active');
    if (tab === 'signals') fetchSignals(slug);
    if (tab === 'trades') fetchTrades(slug);
    if (tab === 'overview') renderOverview(slug);
    if (tab === 'backtests') renderBacktests(slug);
    if (tab === 'alerts') renderAlerts(slug);
    if (tab === 'settings') renderSettings(slug);
}

async function renderAlerts(slug) {
    const el = document.getElementById('tab-alerts');
    el.innerHTML = `
        <div class="form-row">
            <button class="btn-primary" onclick="refreshAlerts('${slug}')">Evaluate Alerts</button>
            <button class="btn-secondary" onclick="refreshScores('${slug}')">Refresh Scores</button>
            <button class="btn-secondary" onclick="refreshRotation('${slug}')">Refresh Rotation</button>
            <span id="alerts-msg-${slug}" style="font-size:12px;color:var(--text-muted);"></span>
        </div>
        <div id="alerts-scores-${slug}" style="margin-top:14px;"></div>
        <div id="alerts-rotation-${slug}" style="margin-top:14px;"></div>
        <div class="console-output" id="alerts-list-${slug}" style="margin-top:14px;max-height:200px;"><div class="console-line info">Loading alerts...</div></div>
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
        msgEl.style.color = 'var(--accent-green)';
        await fetchAlerts(slug);
    } catch (e) {
        msgEl.textContent = `Error: ${e.message}`;
        msgEl.style.color = 'var(--accent-red)';
    }
}

async function refreshScores(slug) {
    const msgEl = document.getElementById(`alerts-msg-${slug}`);
    msgEl.textContent = 'Computing scores...';
    try {
        const res = await fetch(`${API_BASE}/api/v2/monitoring/scores/refresh`, {
            method: 'POST',
            headers: { ...apiHeaders(), 'Content-Type': 'application/json' },
            body: JSON.stringify({ days: 30 }),
        });
        const data = await res.json();
        msgEl.textContent = `Scores refreshed for ${data.scores ? data.scores.length : 0} engine(s)`;
        msgEl.style.color = 'var(--accent-green)';
        await fetchScores(slug);
    } catch (e) {
        msgEl.textContent = `Error: ${e.message}`;
        msgEl.style.color = 'var(--accent-red)';
    }
}

async function refreshRotation(slug) {
    const msgEl = document.getElementById(`alerts-msg-${slug}`);
    msgEl.textContent = 'Generating rotation...';
    try {
        const res = await fetch(`${API_BASE}/api/v2/monitoring/rotation/refresh`, { method: 'POST', headers: apiHeaders() });
        const data = await res.json();
        msgEl.textContent = `${data.recommendations ? data.recommendations.length : 0} recommendation(s)`;
        msgEl.style.color = 'var(--accent-green)';
        await fetchRotation(slug);
    } catch (e) {
        msgEl.textContent = `Error: ${e.message}`;
        msgEl.style.color = 'var(--accent-red)';
    }
}

async function fetchScores(slug) {
    const el = document.getElementById(`alerts-scores-${slug}`);
    try {
        const res = await fetch(`${API_BASE}/api/v2/monitoring/scores`, { headers: apiHeaders() });
        const data = await res.json();
        const scores = data.scores || [];
        const mine = scores.find(s => s.instance_slug === slug);
        el.innerHTML = mine ? `
            <div class="metrics-grid">
                <div class="metric"><div class="label">Score</div><div class="value">${mine.score.toFixed(1)}</div></div>
                <div class="metric"><div class="label">Status</div><div class="value">${mine.status}</div></div>
                <div class="metric"><div class="label">Return</div><div class="value ${mine.return_pct >= 0 ? 'positive' : 'negative'}">${formatPct(mine.return_pct)}</div></div>
                <div class="metric"><div class="label">Win Rate</div><div class="value">${mine.win_rate.toFixed(1)}%</div></div>
                <div class="metric"><div class="label">PF</div><div class="value">${mine.profit_factor.toFixed(2)}</div></div>
                <div class="metric"><div class="label">DD</div><div class="value negative">${formatPct(mine.max_drawdown_pct)}</div></div>
            </div>
        ` : '<div class="console-line info">No score computed yet. Click Refresh Scores.</div>';
    } catch (e) {
        el.innerHTML = `<div class="console-line error">Failed to load scores.</div>`;
    }
}

async function fetchRotation(slug) {
    const el = document.getElementById(`alerts-rotation-${slug}`);
    try {
        const res = await fetch(`${API_BASE}/api/v2/monitoring/rotation`, { headers: apiHeaders() });
        const data = await res.json();
        const recs = (data.recommendations || []).filter(r => r.instance_slug === slug && r.status === 'pending');
        el.innerHTML = recs.length ? recs.map(r => `
            <div class="console-line ${r.action === 'REDUCE' ? 'error' : r.action === 'INCREASE' ? 'success' : 'info'}">
                ${r.action}: ${r.reason}<br>
                Current ${r.current_allocation_pct ? r.current_allocation_pct.toFixed(1) : '-'}% → Suggested ${r.suggested_allocation_pct ? r.suggested_allocation_pct.toFixed(1) : '-'}%
                <button class="btn-primary" style="margin-left:8px;padding:2px 8px;font-size:11px;" onclick="approveRotation('${r.id}', true, '${slug}')">Approve</button>
                <button class="btn-danger" style="margin-left:4px;padding:2px 8px;font-size:11px;" onclick="approveRotation('${r.id}', false, '${slug}')">Reject</button>
            </div>
        `).join('') : '<div class="console-line info">No pending rotation recommendations.</div>';
    } catch (e) {
        el.innerHTML = `<div class="console-line error">Failed to load rotation.</div>`;
    }
}

async function approveRotation(recId, approved, slug) {
    const endpoint = approved ? 'approve' : 'reject';
    try {
        await fetch(`${API_BASE}/api/v2/monitoring/rotation/${recId}/${endpoint}`, { method: 'POST', headers: apiHeaders() });
        await fetchRotation(slug);
    } catch (e) {
        console.error('approveRotation error:', e);
    }
}

async function fetchAlerts(slug) {
    const el = document.getElementById(`alerts-list-${slug}`);
    try {
        const res = await fetch(`${API_BASE}/api/v2/alerts?instance_slug=${slug}`, { headers: apiHeaders() });
        const data = await res.json();
        const list = data.alerts || [];
        el.innerHTML = list.length ? list.map(a => {
            const ts = a.created_at ? `[${formatTime(a.created_at)}] ` : '';
            const note = a.internal_note ? `<br><span style="color:var(--text-muted);font-size:11px;">Note: ${escapeHtml(a.internal_note)}</span>` : '';
            return `<div class="console-line ${a.level === 'CRITICAL' ? 'error' : a.level === 'WARNING' ? 'warning' : 'info'}">
                ${ts}<strong>[${a.level}]</strong> ${escapeHtml(a.message)}${note}
                ${a.dismissed ? '' : `<button class="btn-secondary" style="margin-left:8px;padding:2px 8px;font-size:11px;" onclick="dismissAlert('${a.id}', '${slug}')">Dismiss</button>`}
            </div>`;
        }).join('') : '<div class="console-line info">No alerts. Click Evaluate Alerts to scan.</div>';
    } catch (e) {
        el.innerHTML = `<div class="console-line error">Failed to load alerts.</div>`;
    }
}

async function dismissAlert(alertId, slug) {
    try {
        await fetch(`${API_BASE}/api/v2/alerts/${alertId}/dismiss`, { method: 'POST', headers: apiHeaders() });
        await fetchAlerts(slug);
    } catch (e) {
        console.error('dismissAlert error:', e);
    }
}


async function renderBacktests(slug) {
    const el = document.getElementById('tab-backtests');
    el.innerHTML = `
        <div class="form-row">
            <div class="form-group">
                <label>Days</label>
                <input id="bt-days-${slug}" type="number" min="1" max="365" value="30">
            </div>
            <div class="form-group">
                <label>Capital (USDC)</label>
                <input id="bt-capital-${slug}" type="number" min="10" value="1000">
            </div>
            <button class="btn-primary" onclick="runBacktest('${slug}')">Run Backtest</button>
            <span id="bt-msg-${slug}" style="font-size:12px;color:var(--text-muted);"></span>
        </div>
        <div id="bt-results-${slug}" style="margin-top:14px;"></div>
        <div class="console-output" id="bt-list-${slug}" style="margin-top:14px;max-height:200px;"><div class="console-line info">Loading backtests...</div></div>
    `;
    await fetchBacktests(slug);
}

async function runBacktest(slug) {
    const days = parseInt(document.getElementById(`bt-days-${slug}`).value, 10);
    const capital = parseFloat(document.getElementById(`bt-capital-${slug}`).value);
    const msgEl = document.getElementById(`bt-msg-${slug}`);
    msgEl.textContent = 'Running...';
    msgEl.style.color = 'var(--text-muted)';
    try {
        const res = await fetch(`${API_BASE}/api/v2/backtests/run`, {
            method: 'POST',
            headers: { ...apiHeaders(), 'Content-Type': 'application/json' },
            body: JSON.stringify({ instance_slug: slug, days, initial_capital: capital }),
        });
        const data = await res.json();
        if (data.ok && data.backtest) {
            msgEl.textContent = 'Done';
            msgEl.style.color = 'var(--accent-green)';
            renderBacktestResult(data.backtest, slug);
        } else {
            msgEl.textContent = data.message || 'Failed';
            msgEl.style.color = 'var(--accent-red)';
        }
    } catch (e) {
        msgEl.textContent = `Error: ${e.message}`;
        msgEl.style.color = 'var(--accent-red)';
    }
    await fetchBacktests(slug);
}

function renderBacktestResult(bt, slug) {
    const el = document.getElementById(`bt-results-${slug}`);
    const statusClass = bt.status === 'done' ? 'success' : 'error';
    el.innerHTML = `
        <div class="metrics-grid">
            <div class="metric"><div class="label">Status</div><div class="value ${statusClass}">${bt.status}</div></div>
            <div class="metric"><div class="label">Return</div><div class="value ${bt.total_return_pct >= 0 ? 'positive' : 'negative'}">${formatPct(bt.total_return_pct)}</div></div>
            <div class="metric"><div class="label">Trades</div><div class="value">${bt.total_trades}</div></div>
            <div class="metric"><div class="label">Win Rate</div><div class="value">${bt.win_rate.toFixed(1)}%</div></div>
            <div class="metric"><div class="label">Profit Factor</div><div class="value">${bt.profit_factor.toFixed(2)}</div></div>
            <div class="metric"><div class="label">Max DD</div><div class="value negative">${formatPct(bt.max_drawdown_pct)}</div></div>
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
    const w = rect.width;
    const h = rect.height;
    ctx.clearRect(0, 0, w, h);

    const values = equityCurve.map(p => p.equity);
    const min = Math.min(...values) * 0.99;
    const max = Math.max(...values) * 1.01;
    const range = max - min || 1;
    const step = w / (values.length - 1 || 1);
    const getY = v => h - ((v - min) / range) * h;

    ctx.beginPath();
    ctx.moveTo(0, h);
    equityCurve.forEach((p, i) => {
        const x = i * step;
        const y = getY(p.equity);
        if (i === 0) ctx.lineTo(x, y);
        else {
            const prev = equityCurve[i - 1];
            const prevX = (i - 1) * step;
            const prevY = getY(prev.equity);
            const cp1x = prevX + (x - prevX) / 2;
            ctx.bezierCurveTo(cp1x, prevY, cp1x, y, x, y);
        }
    });
    ctx.lineTo(w, h);
    ctx.closePath();
    const grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, 'rgba(0, 255, 136, 0.35)');
    grad.addColorStop(1, 'rgba(0, 255, 136, 0.01)');
    ctx.fillStyle = grad;
    ctx.fill();

    ctx.beginPath();
    equityCurve.forEach((p, i) => {
        const x = i * step;
        const y = getY(p.equity);
        if (i === 0) ctx.moveTo(x, y);
        else {
            const prev = equityCurve[i - 1];
            const prevX = (i - 1) * step;
            const prevY = getY(prev.equity);
            const cp1x = prevX + (x - prevX) / 2;
            ctx.bezierCurveTo(cp1x, prevY, cp1x, y, x, y);
        }
    });
    ctx.strokeStyle = '#00ff88';
    ctx.lineWidth = 2;
    ctx.stroke();
}

async function fetchBacktests(slug) {
    const el = document.getElementById(`bt-list-${slug}`);
    try {
        const res = await fetch(`${API_BASE}/api/v2/backtests?instance_slug=${slug}`, { headers: apiHeaders() });
        const data = await res.json();
        const list = data.backtests || [];
        el.innerHTML = list.length ? list.map(b => {
            const ts = b.created_at ? `[${formatTime(b.created_at)}] ` : '';
            const days = b.end_date && b.start_date ? Math.round((new Date(b.end_date) - new Date(b.start_date)) / (1000 * 60 * 60 * 24)) : 30;
            return `<div class="console-line ${b.status === 'done' ? 'success' : 'error'}">${ts}${days}d ${b.token} ${b.strategy_id} → ${formatPct(b.total_return_pct)} | ${b.total_trades} trades | WR ${b.win_rate.toFixed(1)}% | PF ${b.profit_factor.toFixed(2)} | DD ${formatPct(b.max_drawdown_pct)}</div>`;
        }).join('') : '<div class="console-line info">No backtests yet. Run one above.</div>';
    } catch (e) {
        el.innerHTML = `<div class="console-line error">Failed to load backtests.</div>`;
    }
}

document.addEventListener('click', (e) => {
    if (e.target.classList.contains('tab')) {
        const tab = e.target.dataset.tab;
        if (selectedSlug) loadDetailTab(tab, selectedSlug);
    }
});

function renderOverview(slug) {
    const inst = instances.find(i => i.slug === slug);
    const el = document.getElementById('tab-overview');
    el.innerHTML = `
        <div class="metrics-grid">
            <div class="metric"><div class="label">Status</div><div class="value">${inst.status}</div></div>
            <div class="metric"><div class="label">Side</div><div class="value">${inst.position_side || 'FLAT'}</div></div>
            <div class="metric"><div class="label">Unrealized PnL</div><div class="value">${formatUsd(inst.unrealized_pnl || 0)}</div></div>
            <div class="metric"><div class="label">Strategy</div><div class="value">${inst.strategy_id}</div></div>
        </div>
        <div class="console-output" style="margin-top:14px;max-height:200px;"><div class="console-line info">Live position data and reasoning will appear here.</div></div>
    `;
}

async function fetchSignals(slug) {
    const el = document.getElementById('tab-signals');
    try {
        const res = await fetch(`${API_BASE}/api/v2/instances/${slug}/signals?limit=20`, { headers: apiHeaders() });
        const data = await res.json();
        const signals = data.signals || [];
        el.innerHTML = signals.length ? `<div class="console-output" style="max-height:300px;">${signals.map(s => {
            const ts = s.timestamp ? `[${formatTime(s.timestamp)}] ` : '';
            return `<div class="console-line ${s.direction === 'BUY' ? 'success' : s.direction === 'SELL' ? 'error' : 'info'}">${ts}${s.direction} signal=${s.signal.toFixed(2)} ${s.executed ? 'EXECUTED' : 'skipped'} ${s.reasoning_text ? '| ' + escapeHtml(s.reasoning_text) : ''}</div>`;
        }).join('')}</div>` : '<div class="console-line info">No signals yet.</div>';
    } catch (e) {
        el.innerHTML = `<div class="console-line error">Failed to load signals.</div>`;
    }
}

async function fetchTrades(slug) {
    const el = document.getElementById('tab-trades');
    try {
        const res = await fetch(`${API_BASE}/api/v2/instances/${slug}/trades?limit=20`, { headers: apiHeaders() });
        const data = await res.json();
        const trades = data.trades || [];
        el.innerHTML = trades.length ? `<div class="console-output" style="max-height:300px;">${trades.map(t => {
            const ts = t.timestamp ? `[${formatTime(t.timestamp)}] ` : '';
            return `<div class="console-line ${(t.pnl_usd || 0) >= 0 ? 'success' : 'error'}">${ts}${t.side} ${formatUsd(t.pnl_usd || 0)} (${formatPct(t.pnl_pct || 0)})</div>`;
        }).join('')}</div>` : '<div class="console-line info">No trades yet.</div>';
    } catch (e) {
        el.innerHTML = `<div class="console-line error">Failed to load trades.</div>`;
    }
}

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
                <div class="form-group full">
                    <label>API Private Key (leave blank to keep existing)</label>
                    <input id="pk-${slug}" type="password" placeholder="0x...">
                </div>
                <div class="form-group full">
                    <label>Account / Withdrawal Address</label>
                    <input id="addr-${slug}" type="text" value="${inst.account_address_mask || ''}" placeholder="0x...">
                </div>
            </div>
            <button class="btn-primary" type="submit" style="margin-top:16px;">Save Settings</button>
            <span id="settings-msg-${slug}" style="margin-left:12px;font-size:12px;color:var(--text-muted);"></span>
        </form>
    `;
}

async function saveSettings(slug) {
    const maxPos = parseFloat(document.getElementById(`max-pos-${slug}`).value) / 100;
    const leverage = parseInt(document.getElementById(`leverage-${slug}`).value, 10);
    const poll = parseInt(document.getElementById(`poll-${slug}`).value, 10);
    const pk = document.getElementById(`pk-${slug}`).value.trim();
    const addr = document.getElementById(`addr-${slug}`).value.trim();

    const payload = { max_position_pct: maxPos, leverage, poll_interval_seconds: poll };
    if (pk) payload.hyperliquid_private_key = pk;
    if (addr) { payload.account_address = addr; payload.withdrawal_address = addr; }

    try {
        const res = await fetch(`${API_BASE}/api/v2/instances/${slug}`, {
            method: 'PUT',
            headers: { ...apiHeaders(), 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const data = await res.json();
        const msgEl = document.getElementById(`settings-msg-${slug}`);
        if (data.ok) {
            msgEl.textContent = 'Saved';
            msgEl.style.color = 'var(--accent-green)';
            await fetchInstances();
            if (selectedSlug === slug) selectInstance(slug);
        } else {
            msgEl.textContent = data.message || 'Save failed';
            msgEl.style.color = 'var(--accent-red)';
        }
    } catch (e) {
        document.getElementById(`settings-msg-${slug}`).textContent = `Error: ${e.message}`;
    }
}

// Control ----------------------------------------------------------------------
async function controlInstance(id, action) {
    try {
        const res = await fetch(`${API_BASE}/api/v2/instances/${id}/${action}`, { method: 'POST', headers: apiHeaders() });
        const data = await res.json();
        addLog(data.message || `${action} ${id}`, data.ok ? 'success' : 'error');
        await fetchInstances();
    } catch (e) {
        addLog(`${action} failed: ${e.message}`, 'error');
    }
}

// Logs -------------------------------------------------------------------------
async function fetchLogs() {
    try {
        const res = await fetch(`${API_BASE}/api/v2/logs?limit=50`, { headers: apiHeaders() });
        if (!res.ok) return;
        const data = await res.json();
        logs = data.logs || [];
        renderLogs();
    } catch (e) {
        console.error('fetchLogs error:', e);
    }
}

function renderLogs() {
    const consoleEl = document.getElementById('console');
    if (!logs.length) return;
    consoleEl.innerHTML = logs.map(log => {
        const ts = log.timestamp ? `[${formatTime(log.timestamp)}] ` : '';
        return `<div class="console-line ${log.level || 'info'}">${ts}${escapeHtml(log.message)}</div>`;
    }).join('');
    consoleEl.scrollTop = consoleEl.scrollHeight;
}

function addLog(message, level = 'info') {
    const consoleEl = document.getElementById('console');
    const line = document.createElement('div');
    line.className = `console-line ${level}`;
    line.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
    consoleEl.appendChild(line);
    consoleEl.scrollTop = consoleEl.scrollHeight;
}

async function copyLogs() {
    const text = logs.map(log => `[${log.timestamp || ''}] ${log.message}`).join('\n');
    try {
        await navigator.clipboard.writeText(text);
        addLog('Logs copied to clipboard', 'success');
    } catch (e) {
        addLog('Failed to copy logs', 'error');
    }
}

function clearConsole() {
    const consoleEl = document.getElementById('console');
    consoleEl.innerHTML = '<div class="console-line info">Console cleared.</div>';
    logs = [];
}

function refreshAll() {
    fetchPulseData();
    fetchInstances();
    fetchLogs();
    addLog('Manual refresh triggered', 'info');
}

function updateClock() {
    const el = document.getElementById('clock');
    if (el) el.textContent = new Date().toLocaleTimeString();
}

// SSE -------------------------------------------------------------------------
function connectSSE() {
    const source = new EventSource(`${API_BASE}/stream`);
    source.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.type === 'instance_update') fetchInstances();
            if (data.log) addLog(data.log.message, data.log.level);
        } catch (e) {
            console.error('SSE parse error:', e);
        }
    };
    source.onerror = (e) => {
        console.error('SSE error:', e);
        addLog('SSE connection error', 'error');
    };
}

// Utilities --------------------------------------------------------------------
function formatTime(iso) {
    try { return new Date(iso).toLocaleString(); } catch (e) { return iso; }
}

function formatUsd(n) {
    try {
        return '$' + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    } catch (e) { return '$' + n; }
}

function formatPct(n) {
    try {
        const val = Number(n);
        return (val >= 0 ? '+' : '') + val.toFixed(2) + '%';
    } catch (e) { return n + '%'; }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

window.addEventListener('resize', drawPulse);

(async function init() {
    await fetchPulseData();
    await fetchInstances();
    await fetchLogs();
    connectSSE();
    setInterval(fetchInstances, 5000);
    setInterval(fetchLogs, 5000);
    setInterval(fetchPulseData, 30000);
    setInterval(updateClock, 1000);
})();
