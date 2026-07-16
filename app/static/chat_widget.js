// PULS-R Assistant chat widget — shared across studio / backtester / dashboard / assistant page.
(function () {
  const widget = document.getElementById('chat-widget');
  if (!widget) return;
  const CTX = widget.dataset.context || 'assistant';
  const CONTEXT_HINT = widget.dataset.contextHint || '';
  // Derive API base from current origin (Basic auth handled by browser).
  const API_BASE = (location.origin || 'http://localhost:8792').replace(/^https?:\/\/[^@\/]+@/, 'http://');
  const MODEL_SEL = document.getElementById('chat-model');
  const SESSIONS_EL = document.getElementById('chat-sessions');
  const MSGS_EL = document.getElementById('chat-messages');
  const INPUT = document.getElementById('chat-input');
  const SEND = document.getElementById('chat-send');
  const API = API_BASE + '/api/v2/chat';
  const SESS_API = API_BASE + '/api/v2/chat/sessions';
  let sessionId = null;
  let busy = false;

  function authHeaders() {
    // UI Basic auth is handled by browser; we just set content-type.
    return { 'Content-Type': 'application/json' };
  }

  function renderMsg(role, text) {
    const d = document.createElement('div');
    d.className = 'chat-msg ' + (role === 'user' ? 'user' : 'assistant');
    d.textContent = text;
    MSGS_EL.appendChild(d);
    MSGS_EL.scrollTop = MSGS_EL.scrollHeight;
    return d;
  }

  function loadSessions() {
    fetch(SESS_API, { headers: authHeaders() })
      .then(r => r.json())
      .then(d => {
        if (!d.ok) return;
        SESSIONS_EL.innerHTML = '';
        (d.sessions || []).forEach(s => {
          const c = document.createElement('span');
          c.className = 'chat-session-chip' + (s.id === sessionId ? ' active' : '');
          c.textContent = s.title || 'chat';
          c.title = s.title || '';
          c.onclick = () => loadSession(s.id);
          SESSIONS_EL.appendChild(c);
        });
      })
      .catch(() => {});
  }

  function loadSession(id) {
    sessionId = id;
    loadSessions();
    MSGS_EL.innerHTML = '<div class="chat-msg assistant thinking">Loading…</div>';
    fetch(SESS_API.replace('/sessions', '/session/' + id), { headers: authHeaders() })
      .then(r => r.json())
      .then(d => {
        if (!d.ok) { MSGS_EL.innerHTML = '<div class="chat-msg assistant">Could not load session.</div>'; return; }
        MSGS_EL.innerHTML = '';
        (d.messages || []).forEach(m => renderMsg(m.role, m.content));
      })
      .catch(() => { MSGS_EL.innerHTML = '<div class="chat-msg assistant">Network error loading session.</div>'; });
  }

  function send() {
    const text = INPUT.value.trim();
    if (!text || busy) return;
    busy = true; SEND.disabled = true;
    renderMsg('user', text);
    const thinking = renderMsg('assistant', '…');
    INPUT.value = '';
    // On first message of a new session, prepend context hint (strategy source, backtest data, etc.)
    // Read live (not cached) so Studio/Backtester inline scripts that set data-context-hint after load are respected.
    const CONTEXT_HINT_LIVE = widget.dataset.contextHint || '';
    let message = text;
    if (!sessionId && CONTEXT_HINT_LIVE) {
      message = CONTEXT_HINT_LIVE + '\n\n' + text;
    }
    const payload = { context: CTX, message: message, model: MODEL_SEL.value || undefined };
    if (sessionId) payload.session_id = sessionId;
    fetch(API, { method: 'POST', headers: authHeaders(), body: JSON.stringify(payload) })
      .then(r => r.json())
      .then(d => {
        if (!d.ok) { thinking.textContent = 'Error: ' + (d.message || 'unknown'); return; }
        sessionId = d.session_id;
        thinking.textContent = d.reply;
        loadSessions();
      })
      .catch(e => { thinking.textContent = 'Network error: ' + e; })
      .finally(() => { busy = false; SEND.disabled = false; });
  }

  // Wire controls
  const toggle = document.getElementById('chat-toggle');
  const close = document.getElementById('chat-close');
  const newBtn = document.getElementById('chat-new');
  if (toggle) toggle.onclick = () => widget.classList.remove('chat-collapsed');
  if (close) close.onclick = () => { widget.classList.add('chat-collapsed'); };
  if (newBtn) newBtn.onclick = () => { sessionId = null; MSGS_EL.innerHTML = ''; loadSessions(); };
  if (SEND) SEND.onclick = send;
  if (INPUT) INPUT.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  });

  // Dashboard slim bar expands on input focus
  if (widget.classList.contains('chat-dashboard')) {
    INPUT.addEventListener('focus', () => widget.classList.add('expanded'));
  }

  // Initial load
  loadSessions();
})();
