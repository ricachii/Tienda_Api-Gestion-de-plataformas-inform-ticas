// app/frontend/js/api.js
/* eslint-env browser, es2021 */

// app/frontend/js/api.js
/* eslint-env browser, es2021 */

// ===== Autodetección de API =====
export let API_BASE = window.location.origin;

async function probe(base) {
  try {
    const r = await fetch(`${base}/categorias`, { method: 'GET' });
    return r.ok;
  } catch { return false; }
}

export async function initApiBase() {
  const origin = window.location.origin;
  const m = origin.match(/^(https?:\/\/[^:\/]+)(?::(\d+))?/);
  const host = m ? m[1] : origin;
  const port = m && m[2];

  const candidates = [origin];
  for (const p of ['8000', '8001']) if (p !== port) candidates.push(`${host}:${p}`);

  for (const base of candidates) {
    if (await probe(base)) { API_BASE = base; return base; }
  }
  return API_BASE;
}

// ===== Auth (token en localStorage) =====
let AUTH = { token: null, exp: null, user: null };

export function loadAuth() {
  try {
    const raw = localStorage.getItem('auth');
    AUTH = raw ? JSON.parse(raw) : { token:null, exp:null, user:null };
    // exp opcional: si está vencido, limpiar
    if (AUTH?.exp && Date.now() > Number(AUTH.exp)) clearAuth();
  } catch { AUTH = { token:null, exp:null, user:null }; }
  return AUTH;
}

export function saveAuth(data) {
  AUTH = { ...AUTH, ...data };
  localStorage.setItem('auth', JSON.stringify(AUTH));
  return AUTH;
}

export function clearAuth() {
  AUTH = { token:null, exp:null, user:null };
  localStorage.removeItem('auth');
  return AUTH;
}

function needsAuthHeader(url) {
  return /\/admin\//.test(url) || /\/me$/.test(url);
}

function buildHeaders(url, headers = {}) {
  const base = new Headers(headers || {});
  if (AUTH?.token && needsAuthHeader(url)) {
    base.set('Authorization', `Bearer ${AUTH.token}`);
  }
  return base;
}

// ===== Helper fetch con timeout y reintentos =====
async function getErrMsg(r) {
  try {
    const ct = (r.headers.get('content-type') || '').toLowerCase();
    if (ct.includes('application/json')) {
      const j = await r.clone().json();
      const pick = (x) => x == null ? '' :
        typeof x === 'string' ? x :
        Array.isArray(x) ? x.map(pick).filter(Boolean).join(', ') :
        typeof x === 'object' ? (x.msg || pick(x.detail) || pick(x.message) || pick(x.error) || JSON.stringify(x)) :
        String(x);
      return pick(j) || `HTTP ${r.status}`;
    }
    return (await r.clone().text()).trim() || `HTTP ${r.status}`;
  } catch { return `HTTP ${r.status}`; }
}

export async function fetchJSON(url, opts = {}, retries = 2) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 12000);
  try {
    const r = await fetch(url, {
      ...opts,
      headers: buildHeaders(url, opts.headers),
      signal: ctrl.signal,
    });
    if (!r.ok) throw new Error(await getErrMsg(r));
    return r.json();
  } catch (err) {
    if (retries > 0 && /AbortError|502|503|504/.test(String(err))) {
      await new Promise(res => setTimeout(res, (3 - retries) * 500));
      return fetchJSON(url, opts, retries - 1);
    }
    throw err;
  } finally {
    clearTimeout(t);
  }
}

// ===== Endpoints públicos =====
export const getProductos = (page = 1, size = 12, q = '', cat = '') => {
  const p = new URLSearchParams({ page, size });
  if (q) p.set('q', q);
  if (cat) p.set('cat', cat);
  return fetchJSON(`${API_BASE}/productos?${p}`);
};
export const getCategorias = () => fetchJSON(`${API_BASE}/categorias`);

// Compras
export const postCheckout = (payload) =>
  fetchJSON(`${API_BASE}/checkout`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

export const postCompra = (producto_id, cantidad) =>
  fetchJSON(`${API_BASE}/compras`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ producto_id, cantidad }),
  });

// ===== Auth endpoints =====
export const apiRegister = ({ email, nombre, password }) =>
  fetchJSON(`${API_BASE}/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, nombre, password }),
  });

export const apiLogin = ({ email, password }) =>
  fetchJSON(`${API_BASE}/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });

export const apiMe = () => fetchJSON(`${API_BASE}/me`, { method:'GET' });

// ===== Admin (ejemplos; usarán Authorization automáticamente) =====
export const getVentasResumen = () => fetchJSON(`${API_BASE}/admin/ventas/resumen`);
export const getVentasSerie = () => fetchJSON(`${API_BASE}/admin/ventas/serie`);
export const getVentasCSV = () => fetchJSON(`${API_BASE}/admin/ventas.csv`);

// Explicit named exports to satisfy bundlers that may not detect all hoisted exports
export {
  initApiBase, API_BASE,
  loadAuth, saveAuth, clearAuth,
  apiRegister, apiLogin, apiMe,
  getProductos, getCategorias, postCheckout, postCompra,
  getVentasResumen, getVentasSerie, getVentasCSV
};
