/* ============================================================
   EdgeHub — js/api.js
   Central API client (prefix /api/v1) + shared UI utilities
   ============================================================ */

const API_BASE = '/api/v1';

// ── HTTP core ─────────────────────────────────────────────
async function apiFetch(method, path, body) {
  const opts = { method, credentials: 'include', headers: { 'Content-Type': 'application/json' } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  
  let res;
  try { res = await fetch(API_BASE + path, opts); }
  catch { throw new Error('Network error — is the backend reachable?'); }

  if (res.status === 401) {
    // Evita il loop se siamo già sulla pagina di login
    if (!location.pathname.includes('index.html')) {
      const dest = encodeURIComponent(location.pathname + location.search);
      location.href = '/index.html?next=' + dest;
    }
    throw new Error('Unauthorized');
  }
  
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
}

const get     = (p)     => apiFetch('GET',    p);
const post    = (p, b)  => apiFetch('POST',   p, b);
const patch   = (p, b)  => apiFetch('PATCH',  p, b);
const del     = (p)     => apiFetch('DELETE', p);

// Alias per compatibilità con le pagine HTML
const fetchJSON = apiFetch;

// ── API namespaces ────────────────────────────────────────
const Auth = {
  login:  (key) => post('/auth/login',  { admin_key: key }),
  logout: ()    => post('/auth/logout'),
  check:  ()    => apiFetch('GET', '/nodes/').then(() => true).catch(() => false),
};

const Sites = {
  list:         ()            => get('/sites/'),
  get:          (id)          => get('/sites/' + id),
  create:       (body)        => post('/sites/', body),
  patch:        (id, body)    => patch('/sites/' + id, body),
  delete:       (id)          => del('/sites/' + id),
  nodes:        (id)          => get('/sites/' + id + '/nodes'),
  tokens:       (id)          => get('/sites/' + id + '/tokens'),
  createToken:  (id, body)    => post('/sites/' + id + '/tokens', body),
  renewToken:   (id, tid, body)=> post(`/sites/${id}/tokens/${tid}/renew`, body),
  deleteToken:  (id, tid)     => del(`/sites/${id}/tokens/${tid}`),
};

const Nodes = {
  list:       ()            => get('/nodes/'),
  get:        (id)          => get('/nodes/' + id),
  patch:      (id, body)    => patch('/nodes/' + id, body),
  delete:     (id)          => del('/nodes/' + id),
  heartbeats: (id, limit)   => get(`/nodes/${id}/heartbeats?limit=${limit || 100}`),
};

// ── Format helpers ────────────────────────────────────────
function esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function relTime(iso) {
  if (!iso) return '—';
  const s = Math.floor((Date.now() - new Date(iso)) / 1000);
  if (s < 5)  return 'just now';
  if (s < 60) return s + 's ago';
  const m = Math.floor(s/60);
  if (m < 60) return m + 'm ago';
  const h = Math.floor(m/60);
  if (h < 24) return h + 'h ago';
  return Math.floor(h/24) + 'd ago';
}
function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-GB', { day:'2-digit', month:'short', year:'numeric', hour:'2-digit', minute:'2-digit' });
}
function fmtUptime(s) {
  if (s == null) return '—';
  const d = Math.floor(s/86400), h = Math.floor((s%86400)/3600), m = Math.floor((s%3600)/60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m ${s%60}s`;
}
function fmtPct(v) { return v == null ? '—' : parseFloat(v).toFixed(1) + '%'; }
function barCls(v) { const n = parseFloat(v); return n > 85 ? 'danger' : n > 65 ? 'warn' : 'ok'; }

// ── HTML helpers ──────────────────────────────────────────
// ── HTML helpers ──────────────────────────────────────────
function statusBadge(status, offline_cycles, offline_alert_sent) {
  const on = status === 'online';
  
  // Stile in linea per forzare il centraggio perfetto di testo e pallino
  const centerStyle = "display: inline-flex; align-items: center; justify-content: center; text-align: center;";
  
  // If online, return standard online badge
  if (on) {
    return `<span class="badge badge-online" style="${centerStyle}"><span class="bdot"></span>Online</span>`;
  }
  
  // If offline and alert was sent, show critical error badge
  if (offline_alert_sent) {
    return `<span class="badge badge-danger" style="${centerStyle}"><span class="bdot"></span>Alert Sent</span>`;
  }
  
  // If offline but alert not yet sent, show warning badge with cycle count
  if (offline_cycles > 0) {
    return `<span class="badge badge-warn" style="${centerStyle}"><span class="bdot"></span>Failing (${offline_cycles}/3)</span>`;
  }

  // Fallback for standard offline
  return `<span class="badge badge-offline" style="${centerStyle}"><span class="bdot"></span>Offline</span>`;
}

function tokenBadge(t) {
  if (t.used)     return `<span class="badge badge-neutral">Used</span>`;
  if (t.is_valid) return `<span class="badge badge-online">Valid</span>`;
  return `<span class="badge badge-danger">Expired</span>`;
}
function agentTypeBadge(type) {
  return `<span class="badge badge-info">${esc(type||'—')}</span>`;
}
function kvRow(k, v) {
  return `<div class="kv"><span class="kv-k">${esc(k)}</span><span class="kv-v">${esc(v??'—')}</span></div>`;
}
function meterRow(lbl, val) {
  const pct = Math.min(parseFloat(val)||0, 100);
  return `<div class="meter">
    <span class="meter-lbl">${esc(lbl)}</span>
    <div class="meter-track"><div class="meter-fill ${barCls(pct)}" style="width:${pct}%"></div></div>
    <span class="meter-val">${fmtPct(val)}</span>
  </div>`;
}
function emptyState(title, desc) {
  return `<div class="empty">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.3">
      <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
      <rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
    </svg>
    <div class="empty-title">${esc(title)}</div>
    <div class="empty-desc">${esc(desc)}</div>
  </div>`;
}
function loaderRow(msg) {
  return `<div class="loader-row"><div class="spinner"></div>${esc(msg||'Loading…')}</div>`;
}

// ── Toast ─────────────────────────────────────────────────
function toast(msg, type = 'ok') {
  let stack = document.getElementById('toast-stack');
  if (!stack) { stack = Object.assign(document.createElement('div'), {id:'toast-stack'}); document.body.appendChild(stack); }
  const el = Object.assign(document.createElement('div'), { className: `toast t-${type}`, textContent: msg });
  stack.appendChild(el);
  setTimeout(() => { el.style.transition='opacity .3s'; el.style.opacity='0'; setTimeout(()=>el.remove(),300); }, 3200);
}

// ── Modal helpers ─────────────────────────────────────────
function openModal(id)  { document.getElementById(id)?.classList.remove('hidden'); }
function closeModal(id) { document.getElementById(id)?.classList.add('hidden'); }
document.addEventListener('click', e => { if (e.target.classList.contains('modal-backdrop')) e.target.classList.add('hidden'); });

function copyText(text, btn) {
  navigator.clipboard.writeText(text).then(() => {
    if (btn) { const o = btn.textContent; btn.textContent = 'Copied!'; setTimeout(()=>btn.textContent=o, 1500); }
    toast('Copied to clipboard');
  }).catch(() => toast('Copy failed', 'error'));
}

function confirmAction(title, message, onConfirm, btnLabel = 'Delete') {
  document.getElementById('confirm-title').textContent   = title;
  document.getElementById('confirm-message').textContent = message;
  document.getElementById('confirm-btn').textContent     = btnLabel;
  document.getElementById('confirm-btn').onclick = async () => {
    closeModal('modal-confirm');
    await onConfirm();
  };
  openModal('modal-confirm');
}

// ── Auth guard ────────────────────────────────────────────
async function requireAuth() {
  const ok = await Auth.check();
  if (!ok) {
    const dest = encodeURIComponent(location.pathname + location.search);
    location.href = '/index.html?next=' + dest;
    return false;
  }
  const page = location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.nav-link').forEach(el => {
    const href = (el.getAttribute('href') || '').split('/').pop();
    el.classList.toggle('active', href === page);
  });
  return true;
}

async function doLogout() {
  await Auth.logout().catch(() => {});
  location.href = '/index.html';
}

const SIDEBAR_HTML = `
<aside class="sidebar" style="height: 100vh; display: flex; flex-direction: column;">
  <div class="sidebar-brand">
    <div class="brand-mark"><svg viewBox="0 0 20 20"><path d="M10 2L3 6v4c0 4.4 3 8.5 7 9.5 4-1 7-5.1 7-9.5V6l-7-4z"/></svg></div>
    <span class="brand-name">Edge<em>Hub</em></span>
  </div>
  <nav class="sidebar-nav" style="flex-grow: 1; overflow-y: auto;">
    <div class="nav-group">
      <span class="nav-group-label">Monitor</span>
      <a href="dashboard.html" class="nav-link">
        <svg viewBox="0 0 20 20" fill="currentColor"><path d="M3 4a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H4a1 1 0 01-1-1V4zm0 8a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H4a1 1 0 01-1-1v-4zm8-8a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1V4zm0 8a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z"/></svg>
        Dashboard
      </a>
      <a href="nodes.html" class="nav-link">
        <svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M2 5a2 2 0 012-2h12a2 2 0 012 2v2a2 2 0 01-2 2H4a2 2 0 01-2-2V5zm14 1a1 1 0 11-2 0 1 1 0 012 0zM2 13a2 2 0 012-2h12a2 2 0 012 2v2a2 2 0 01-2 2H4a2 2 0 01-2-2v-2zm14 1a1 1 0 11-2 0 1 1 0 012 0z" clip-rule="evenodd"/></svg>
        All Nodes
      </a>
    </div>
    <div class="nav-group">
      <span class="nav-group-label">Manage</span>
      <a href="sites.html" class="nav-link">
        <svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clip-rule="evenodd"/></svg>
        Sites
      </a>
    </div>
    <div class="nav-group">
      <span class="nav-group-label">Resources</span>
      <a href="docs.html" class="nav-link">
        <svg viewBox="0 0 20 20" fill="currentColor"><path d="M9 4.804A7.968 7.968 0 005.5 4c-1.255 0-2.443.29-3.5.804v10A7.969 7.969 0 015.5 14c1.669 0 3.218.51 4.5 1.385A7.962 7.962 0 0114.5 14c1.255 0 2.443.29 3.5.804v-10A7.968 7.968 0 0014.5 4c-1.255 0-2.443.29-3.5.804V12a1 1 0 11-2 0V4.804z"/></svg>
        Documentation
      </a>
    </div>
  </nav>
  <div class="sidebar-footer">
    <button class="btn btn-ghost btn-wide" onclick="doLogout()" style="font-size:13px">
      <svg viewBox="0 0 20 20" fill="currentColor" width="14" height="14"><path fill-rule="evenodd" d="M3 3a1 1 0 00-1 1v12a1 1 0 102 0V4a1 1 0 00-1-1zm10.293 9.293a1 1 0 001.414 1.414l3-3a1 1 0 000-1.414l-3-3a1 1 0 10-1.414 1.414L14.586 9H7a1 1 0 100 2h7.586l-1.293 1.293z" clip-rule="evenodd"/></svg>
      Sign out
    </button>
  </div>
</aside>`;