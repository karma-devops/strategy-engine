const API_BASE = window.location.origin;
let fleet = [];

async function loadFleet() {
    try {
        const res = await fetch(`${API_BASE}/api/v2/presets/fleet`);
        const data = await res.json();
        fleet = data.fleet || [];
        const group = document.getElementById('fleet-optgroup');
        group.innerHTML = fleet.map((p, i) => `<option value="${i}">${p.name}</option>`).join('');
    } catch (e) {
        console.error('loadFleet error:', e);
    }
}

function applyPreset(index) {
    const preset = fleet[index];
    if (!preset) return;
    document.getElementById('slug').value = preset.slug || '';
    document.getElementById('name').value = preset.name;
    document.getElementById('token').value = preset.token;
    document.getElementById('strategy_id').value = preset.strategy_id;
    document.getElementById('mode').value = preset.mode;
    document.getElementById('profile').value = preset.profile;
    document.getElementById('timeframe').value = preset.timeframe;
    document.getElementById('leverage').value = preset.leverage;
    document.getElementById('max_position_pct').value = preset.max_position_pct;
    document.getElementById('poll_interval_seconds').value = preset.poll_interval_seconds;
    // activation/offset defaults based on profile
    if (preset.profile === 'aggressive_8_3') {
        document.getElementById('activation').value = 8;
        document.getElementById('offset').value = 3;
    } else if (preset.profile === 'sniper_36_12') {
        document.getElementById('activation').value = 36;
        document.getElementById('offset').value = 12;
    }
}

document.getElementById('preset-select').addEventListener('change', (e) => {
    const idx = e.target.value;
    if (idx === '') return;
    applyPreset(parseInt(idx, 10));
});

document.getElementById('instance-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = e.target;
    const data = new FormData(form);
    // Convert checkbox to true/false string for backend
    data.set('dry_run', document.getElementById('dry_run').checked ? 'true' : 'false');
    // Only send private key if user typed something; blank means "use global"
    const pk = document.getElementById('hyperliquid_private_key').value.trim();
    if (!pk) {
        data.delete('hyperliquid_private_key');
    }
    try {
        const res = await fetch(`${API_BASE}/instances`, {
            method: 'POST',
            body: data,
        });
        if (res.ok) {
            window.location.href = '/';
        } else {
            const text = await res.text();
            alert('Failed: ' + text);
        }
    } catch (err) {
        alert('Network error: ' + err.message);
    }
});

(async function init() {
    await loadFleet();
})();
