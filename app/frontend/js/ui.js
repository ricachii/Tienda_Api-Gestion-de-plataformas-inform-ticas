// app/frontend/js/ui.js
// Funciones de interfaz (modales, alertas, render)
import { carrito, totals } from './cart.js';

export const CLP = new Intl.NumberFormat('es-CL', { style:'currency', currency:'CLP', maximumFractionDigits:0 });
export const fmt = n => CLP.format(Number(n || 0));
export const byId = id => document.getElementById(id);

/* Alertas flotantes */
export function alerta(msg, type='ok'){
  const el = document.createElement('div');
  el.className = 'alert';
  el.style.borderColor = type==='err' ? '#f87171' : (type==='warn' ? '#fbbf24' : '#4ade80');
  el.textContent = msg;
  // accesibilidad: anunciar cambios y marcar rol
  el.setAttribute('role', type==='err' ? 'alert' : 'status');
  el.setAttribute('aria-live', type==='err' ? 'assertive' : 'polite');
  document.body.appendChild(el);
  setTimeout(()=> el.remove(), 2400);
}

/* Loading skeleton */
export function showLoading(){ const s=byId('loading'); if(s){ s.style.display='grid'; s.setAttribute('aria-hidden','false'); } }
export function hideLoading(){ const s=byId('loading'); if(s){ s.style.display='none'; s.setAttribute('aria-hidden','true'); } }

/* Footer de lista (paginación) */
export function updateListFooter({visible=false, canLoadMore=false}={}){
  const foot = byId('listFooter'); const btn = byId('loadMore'); const end = byId('endMsg');
  if(!foot || !btn || !end) return;
  foot.style.display = visible ? 'flex' : 'none';
  btn.style.display = canLoadMore ? '' : 'none';
  end.style.display = (!canLoadMore && visible) ? '' : 'none';
}

/* Imagen con fallback accesible */
function imageHtml(src, alt){
  const safeSrc = src || '';
  const escAlt = String(alt||'').replace(/"/g,'&quot;');
  // If src provided, include lazy loading, width/height attributes via CSS aspect-ratio,
  // and a small inline SVG placeholder to avoid CLS while loading.
  const placeholder = `data:image/svg+xml;utf8,${encodeURIComponent(`
    <svg xmlns='http://www.w3.org/2000/svg' width='400' height='300' viewBox='0 0 400 300'>
      <rect width='100%' height='100%' fill='%23f9fafb'/>
    </svg>`)};`;
  return safeSrc
    ? `<img loading="lazy" src="${placeholder}" data-src="${safeSrc}" alt="${escAlt}" class="lazyimg"
         onload="if(this.dataset.src){this.src=this.dataset.src;delete this.dataset.src}"
         onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'ph',textContent:'Imagen'}))">`
    : `<div class="ph" role="img" aria-label="Sin imagen">Imagen</div>`;
}

/* === Productos (catálogo) === */
export function renderGrid(items, {append=false} = {}){
  const cont = byId('productos');
  if(cont) cont.setAttribute('role','list');
  const html = (items||[]).map(p=>`
    <div class="card" role="listitem" aria-label="${(p.nombre||'Producto').replace(/"/g,'') }" data-id="${p.id}" data-stock="${p.stock ?? 0}">
      <div class="imgwrap">${imageHtml(p.imagen_url, p.nombre)}</div>
      <div class="cnt">
        <div class="cat">${p.categoria || ''}</div>
        <div class="name">${p.nombre}</div>
        <div class="desc">${p.descripcion || ''}</div>
        <div class="price">${fmt(p.precio)}</div>
        <div class="row">
          <button class="addbtn" aria-label="Agregar al carrito">Agregar 🛒</button>
        </div>
        <div class="stock">${(p.stock ?? 0) > 0 ? `Stock: ${p.stock}` : 'Sin stock'}</div>
      </div>
    </div>
  `).join('');
  if(append) cont.insertAdjacentHTML('beforeend', html);
  else cont.innerHTML = html;
}

/* === Carrito (aside) === */
export function renderCart(){
  const c = byId('cart');
  if(!carrito.length){
    c.classList.add('cart-empty');
    c.textContent = 'Vacío';
    renderTotals();
    byId('cartCount').textContent = '0';
    return;
  }
  c.classList.remove('cart-empty');
  c.innerHTML = carrito.map(i=>`
    <div class="carrito-item">
      <div>${i.nombre}</div>
      <div class="carrito-qty">
        <button class="qtybtn" data-act="menos" data-id="${i.id}" aria-label="Restar uno">−</button>
        <div>${i.cant}</div>
        <button class="qtybtn" data-act="mas" data-id="${i.id}" aria-label="Sumar uno">+</button>
      </div>
      <div>
        ${fmt(i.precio*i.cant)}
        <button class="qtybtn" style="margin-left:8px;background:#eee;color:#000"
                data-act="del" data-id="${i.id}" title="Quitar" aria-label="Quitar del carrito">✕</button>
      </div>
    </div>
  `).join('');

  renderTotals();
  byId('cartCount').textContent = String(carrito.reduce((s,i)=>s+i.cant,0));
}

export function renderTotals(){
  const {subtotal, ship, disc, total} = totals();
  byId('subtotal').textContent = fmt(subtotal);
  byId('ship').textContent = fmt(ship);
  byId('disc').textContent = disc ? `− ${fmt(disc)}` : fmt(0);
  byId('total').textContent = fmt(total);

}

