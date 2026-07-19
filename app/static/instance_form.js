const API_BASE = window.location.origin;

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
