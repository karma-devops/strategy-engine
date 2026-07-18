const API_BASE = window.location.origin;

// BUG #24: all withdrawal API calls require X-API-Key header.
// apiHeaders() mirrors app.js — reads window.API_KEY set by the template.
function apiHeaders() {
    return { "X-API-Key": window.API_KEY || "" };
}
function apiHeadersJson() {
    return { "X-API-Key": window.API_KEY || "", "Content-Type": "application/json" };
}

async function fetchAccount() {
    try {
        const res = await fetch(`${API_BASE}/api/v2/account`, { headers: apiHeaders() });
        if (!res.ok) throw new Error('Account fetch failed');
        return await res.json();
    } catch (e) {
        console.error('fetchAccount error:', e);
        return null;
    }
}

async function fetchConfig() {
    try {
        const res = await fetch(`${API_BASE}/api/v2/withdrawals/config`, { headers: apiHeaders() });
        if (!res.ok) throw new Error('Config fetch failed');
        return await res.json();
    } catch (e) {
        console.error('fetchConfig error:', e);
        return null;
    }
}

async function fetchCalculate() {
    try {
        const res = await fetch(`${API_BASE}/api/v2/withdrawals/calculate`, { headers: apiHeaders() });
        if (!res.ok) throw new Error('Calculate fetch failed');
        return await res.json();
    } catch (e) {
        console.error('fetchCalculate error:', e);
        return null;
    }
}

async function fetchHistory() {
    try {
        const res = await fetch(`${API_BASE}/api/v2/withdrawals/history?limit=20`, { headers: apiHeaders() });
        if (!res.ok) throw new Error('History fetch failed');
        return await res.json();
    } catch (e) {
        console.error('fetchHistory error:', e);
        return null;
    }
}

async function fetchProjection() {
    try {
        const res = await fetch(`${API_BASE}/api/v2/withdrawals/projection?start_capital=10000`, { headers: apiHeaders() });
        if (!res.ok) throw new Error('Projection fetch failed');
        return await res.json();
    } catch (e) {
        console.error('fetchProjection error:', e);
        return null;
    }
}

function formatCurrency(value) {
    if (value === undefined || value === null) return '$0.00';
    return '$' + Number(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

async function updateUI() {
    const account = await fetchAccount();
    const config = await fetchConfig();
    const calc = await fetchCalculate();
    const history = await fetchHistory();
    const proj = await fetchProjection();

    if (account) {
        document.getElementById('account-value').textContent = formatCurrency(account.account_value);
        document.getElementById('withdrawable').textContent = formatCurrency(account.withdrawable);
    }

    if (config) {
        const c = config.config;
        document.getElementById('min-capital').textContent = formatCurrency(c.min_capital);
        document.getElementById('cycle-days').value = c.cycle_days;
        document.getElementById('auto-withdraw').checked = c.auto_withdraw_enabled;
        document.getElementById('withdrawal-rate').value = c.withdrawal_rate;
        document.getElementById('min-capital-input').value = c.min_capital;
        document.getElementById('days-until-next').textContent = c.days_until_next;
    }

    if (calc) {
        document.getElementById('est-50').textContent = formatCurrency(calc.manual_50.amount);
        document.getElementById('est-all').textContent = formatCurrency(calc.manual_all.amount);
        const available = calc.manual_all.amount;
        document.getElementById('available-profit').textContent = formatCurrency(available);
        document.getElementById('btn-50').disabled = calc.manual_50.amount <= 0;
        document.getElementById('btn-all').disabled = calc.manual_all.amount <= 0;
    }

    if (history && history.history.length) {
        document.getElementById('history-table').innerHTML = history.history.map(h => `
            <div class="row" style="border-bottom:1px solid rgba(255,255,255,0.1);padding:8px 0;">
                <span class="small">${new Date(h.timestamp).toLocaleDateString()} — ${h.type}</span>
                <span class="small ${h.status}">${formatCurrency(h.amount)} (${h.status})</span>
            </div>
        `).join('');
    }

    if (proj) {
        const lines = proj.projection.slice(0, 12).map(p =>
            `M${p.month}: capital=${formatCurrency(p.end_capital)} withdrawn=${formatCurrency(p.cumulative_withdrawn)}`
        );
        document.getElementById('projection').textContent = lines.join('\n');
    }
}

document.getElementById('config-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = e.target;
    const data = new FormData(form);
    try {
        const res = await fetch(`${API_BASE}/api/v2/withdrawals/config`, {
            method: 'PUT',
            headers: apiHeaders(),
            body: data,
        });
        const result = await res.json();
        alert(result.message || 'Saved');
        await updateUI();
    } catch (err) {
        alert('Failed to save: ' + err.message);
    }
});

document.getElementById('refresh-btn').addEventListener('click', updateUI);

document.getElementById('btn-50').addEventListener('click', async () => {
    if (!confirm('Withdraw 50% of recent profits?')) return;
    try {
        const res = await fetch(`${API_BASE}/api/v2/withdrawals/manual/50`, { method: 'POST', headers: apiHeaders() });
        const result = await res.json();
        alert(result.message || 'Done');
        await updateUI();
    } catch (err) {
        alert('Failed: ' + err.message);
    }
});

document.getElementById('btn-all').addEventListener('click', async () => {
    if (!confirm('Withdraw ALL available profit above minimum capital?')) return;
    try {
        const res = await fetch(`${API_BASE}/api/v2/withdrawals/manual/all`, { method: 'POST', headers: apiHeaders() });
        const result = await res.json();
        alert(result.message || 'Done');
        await updateUI();
    } catch (err) {
        alert('Failed: ' + err.message);
    }
});

(async function init() {
    await updateUI();
})();
