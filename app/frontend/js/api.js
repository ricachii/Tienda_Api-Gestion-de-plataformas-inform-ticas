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
  // si nada responde, nos quedamos con origin igualmente
  return API_BASE;
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
    const r = await fetch(url, { ...opts, signal: ctrl.signal });
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

// ===== Endpoints =====
export const getProductos = (page = 1, size = 12, q = '', cat = '') => {
  const p = new URLSearchParams({ page, size });
  if (q) p.set('q', q);
  if (cat) p.set('cat', cat);
  return fetchJSON(`${API_BASE}/productos?${p}`);
};

export const getCategorias = () => fetchJSON(`${API_BASE}/categorias`);

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
