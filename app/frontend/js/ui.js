// app/frontend/js/ui.js
// Funciones de interfaz (modales, alertas, render)
import { carrito, totals } from './cart.js';

export const CLP = new Intl.NumberFormat('es-CL', { style:'currency', currency:'CLP', maximumFractionDigits:0 });
export const fmt = n => CLP.format(Number(n || 0));
export const byId = id => document.getElementById(id);

// Escapa texto para evitar inyecciones en plantillas HTML
export function sanitize(txt){
  return String(txt ?? '')
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;')
    .replace(/'/g,'&#39;');
}

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
export function renderImage(producto = {}){
  const previewSvg = "<svg xmlns='http://www.w3.org/2000/svg' width='400' height='300' viewBox='0 0 400 300'><rect width='100%' height='100%' fill='%23f9fafb'/></svg>";
  const placeholder = 'data:image/svg+xml;utf8,' + encodeURIComponent(previewSvg);
  const src = producto.imagen_url || producto.imagen_ref || '';
  const srcset = producto.imagen_srcset || '';
  const alt = sanitize(producto.nombre || 'Producto');
  let attrs = `loading="lazy" src="${placeholder}" alt="${alt}" class="lazyimg"`;
  if(src) attrs += ` data-src="${sanitize(src)}"`;
  if(srcset) attrs += ` data-srcset="${sanitize(srcset)}"`;
  if(producto.imagen_width) attrs += ` width="${sanitize(producto.imagen_width)}"`;
  if(producto.imagen_height) attrs += ` height="${sanitize(producto.imagen_height)}"`;

  return src
    ? `<img ${attrs}
        onload="if(this.dataset.src){this.src=this.dataset.src; if(this.dataset.srcset){this.srcset=this.dataset.srcset;} delete this.dataset.src; delete this.dataset.srcset;}"
        onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'ph',textContent:'Imagen'}))">`
    : `<div class="ph" role="img" aria-label="Sin imagen">Imagen</div>`;
}

/* === Productos (catálogo) === */
export function renderGrid(items, {append=false} = {}){
  const cont = byId('productos');
  if(cont) cont.setAttribute('role','list');
  const html = (items||[]).map(p=>{
    const hasStock = Number(p.stock ?? 0) > 0;
    const safeName = sanitize(p.nombre || 'Producto');
    const safeCat = sanitize(p.categoria || '');
    const safeDesc = sanitize(p.descripcion || '');
    const imgHtml = renderImage(p);

    return `
      <div class="card product-card glass-card" role="listitem"
           aria-label="${safeName}"
           data-id="${p.id}" data-stock="${p.stock ?? 0}"
           data-price="${p.precio}" data-cat="${safeCat}"
           data-desc="${safeDesc}" data-img="${sanitize(p.imagen_url || '')}">
        <div class="imgwrap">${imgHtml}</div>
        <div class="cnt">
          <div class="cat">${safeCat}</div>
          <div class="name">${safeName}</div>
          <div class="desc">${safeDesc}</div>
          <div class="price">${fmt(p.precio)}</div>
          <div class="row">
            <button class="viewbtn" data-act="ver">
              <span class="icon-chip"><img src="/media/icons/detalle.svg" class="icon" alt=""></span>
              Detalle
            </button>
            <button class="addbtn${hasStock ? '' : ' nostock'}" data-act="add" ${hasStock ? '' : 'disabled aria-disabled="true"'}>
              <span class="icon-chip"><img src="/media/icons/add_car.svg" class="icon" alt=""></span>
              ${hasStock ? 'Agregar' : 'Sin stock'}
            </button>
          </div>
          <div class="stock${hasStock ? '' : ' no-stock'}">${hasStock ? `Stock: ${p.stock}` : 'Sin stock'}</div>
        </div>
      </div>
    `;
  }).join('');
  if(append) cont.insertAdjacentHTML('beforeend', html);
  else cont.innerHTML = html;
}

/* === Carrito (aside) === */
export function renderCart(){
  const c = byId('cart');
  const totalItems = carrito.reduce((s,i)=>s+i.cant,0);
  if(!carrito.length){
    c.classList.add('cart-empty');
    c.innerHTML = `
      <span class="icon-chip"><img src="/media/icons/shopping_car.svg" class="icon" alt=""></span>
      <p>Tu carrito está vacío. Agrega suplementos desde el catálogo para verlos aquí.</p>
    `;
  }else{
    c.classList.remove('cart-empty');
    c.innerHTML = carrito.map(i=>{
      const safeName = sanitize(i.nombre || 'VZ');
      const initial = safeName.trim().charAt(0).toUpperCase() || 'V';
      return `
      <div class="carrito-item">
        <div class="cart-line-primary">
          <div class="cart-pill-media" aria-hidden="true">${initial}</div>
          <div class="cart-line-info">
            <strong>${safeName}</strong>
            <span class="cart-line-meta">× ${i.cant}</span>
          </div>
          <div class="carrito-qty">
            <button class="qtybtn" data-act="menos" data-id="${i.id}" aria-label="Restar uno">−</button>
            <div>${i.cant}</div>
            <button class="qtybtn" data-act="mas" data-id="${i.id}" aria-label="Sumar uno">+</button>
          </div>
        </div>
        <div class="cart-line-footer">
          <div class="cart-line-price">${fmt(i.precio*i.cant)}</div>
          <button class="qtybtn del-btn" data-act="del" data-id="${i.id}" title="Quitar" aria-label="Quitar del carrito">✕</button>
        </div>
      </div>
    `;
    }).join('');
  }
  renderTotals();
  byId('cartCount').textContent = String(totalItems);
  const indicator = document.querySelector('.cart-indicator');
  if(indicator){
    if(totalItems > 0){
      indicator.classList.add('has-items');
      indicator.title = `Tienes ${totalItems} ${totalItems===1?'producto':'productos'} en el carrito`;
    }else{
      indicator.classList.remove('has-items');
      indicator.title = 'Ítems en el carrito';
    }
  }
  // Bloquea acciones cuando no hay productos
  const hasItems = totalItems > 0;
  ['vaciar','resumen','pagar'].forEach(id=>{
    const btn = byId(id);
    if(btn) btn.disabled = !hasItems;
  });
  const notice = byId('cartNotice');
  if(notice) notice.style.display = hasItems ? 'none' : '';
}

export function renderTotals(){
  const {subtotal, ship, disc, total} = totals();
  byId('subtotal').textContent = fmt(subtotal);
  byId('ship').textContent = fmt(ship);
  byId('disc').textContent = disc ? `− ${fmt(disc)}` : fmt(0);
  byId('total').textContent = fmt(total);

}

// Overlay de carga reutilizable para flows largos (login/checkout)
export function showGlobalOverlay(message='Procesando…'){
  const ov = byId('globalLoading');
  if(!ov) return;
  const msg = ov.querySelector('.gl-message');
  if(msg) msg.textContent = message;
  ov.style.display = 'flex';
  ov.setAttribute('aria-hidden','false');
}

export function hideGlobalOverlay(){
  const ov = byId('globalLoading');
  if(!ov) return;
  ov.style.display = 'none';
  ov.setAttribute('aria-hidden','true');
}
