//Funciones de interfaz (modales, alertas, render)

// app/frontend/js/ui.js
import { carrito, totals } from './cart.js';

export const CLP = new Intl.NumberFormat('es-CL', { style:'currency', currency:'CLP', maximumFractionDigits:0 });
export const fmt = n => CLP.format(Number(n || 0));
export const byId = id => document.getElementById(id);

export function alerta(msg, type='ok'){
  const el = document.createElement('div');
  el.className = 'alert';
  el.style.borderColor = type==='err' ? '#f87171' : (type==='warn' ? '#fbbf24' : '#4ade80');
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(()=> el.remove(), 2400);
}

// Imagen con fallback accesible
function imageHtml(src, alt){
  const safeSrc = src || '';
  const escAlt = String(alt||'').replace(/"/g,'&quot;');
  return safeSrc
    ? `<img loading="lazy" src="${safeSrc}" alt="${escAlt}"
         onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'ph',textContent:'Imagen'}))">`
    : `<div class="ph" role="img" aria-label="Sin imagen">Imagen</div>`;
}

// === Productos (catálogo) ===
export function renderGrid(items){
  const cont = byId('productos');
  cont.innerHTML = (items||[]).map(p=>`
    <div class="card" data-id="${p.id}" data-stock="${p.stock ?? 0}">
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
}

// === Carrito (aside) ===
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
