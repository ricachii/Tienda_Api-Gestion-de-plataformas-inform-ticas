//Listeners y eventos de botones


// app/frontend/js/events.js
import { getCategorias, getProductos, postCheckout, postCompra, API_BASE } from './api.js';
import { renderGrid, renderCart, byId, alerta, fmt } from './ui.js';
import { carrito, addItem, removeItem, changeQty, clearCart, totals } from './cart.js';

export function initApp(){
  // Búsqueda y filtros
  byId('buscar').onclick = ()=> loadProducts(true);
  byId('catSel').onchange = ()=> loadProducts(true);
  byId('q').addEventListener('keydown', e=>{ if(e.key==='Enter') loadProducts(true); });

  // Carrito
  byId('vaciar').onclick = ()=>{ clearCart(); renderCart(); };

  // Event delegation para + / − / borrar
  byId('cart').addEventListener('click', (ev)=>{
    const btn = ev.target.closest('button[data-act]');
    if(!btn) return;
    const id = Number(btn.dataset.id);
    const act = btn.dataset.act;
    if(act==='menos') changeQty(id, -1);
    if(act==='mas')   changeQty(id, +1);
    if(act==='del')   removeItem(id);
    renderCart();
  });

  // Resumen y pago
  byId('resumen').onclick = openSummary;
  byId('pagar').onclick   = openSummary;   // obligamos pasar por resumen
  byId('btnConfirmarResumen').onclick = pay;
  document.querySelectorAll('[data-close]').forEach(b=>{
    b.addEventListener('click', ()=> closeOverlay(b.getAttribute('data-close')) );
  });
  byId('btnSeguir').onclick = ()=> closeOverlay('ovDone');

  // Info API
  byId('apiBase').textContent = API_BASE;

  // ESC cierra modales
  window.addEventListener('keydown', e=>{
    if(e.key==='Escape'){ closeOverlay('ovSummary'); closeOverlay('ovDone'); }
  });

  renderCart();
  boot();
}

async function boot(){
  try{
    const cats = await getCategorias();
    byId('catSel').innerHTML = '<option value="">Todas</option>' + (cats||[]).map(c=>`<option>${c}</option>`).join('');
  }catch{}
  await loadProducts(true);
}

async function loadProducts(reset=false){
  try{
    const q = byId('q').value.trim();
    const cat = byId('catSel').value;
    const {items=[]} = await getProductos(1,12,q,cat);
    renderGrid(items);

    // Botón "Agregar" en cada card
    document.querySelectorAll('.card .addbtn').forEach(btn=>{
      btn.onclick = ()=>{
        const card = btn.closest('.card');
        const id = +card.dataset.id;
        const stock = +card.dataset.stock || 0;
        if(stock<=0) return alerta('Sin stock','err');
        const name = card.querySelector('.name').textContent;
        const price = Number(card.querySelector('.price').textContent.replace(/[^\d]/g,''));
        addItem({id, nombre:name, precio:price, stock}, 1);
        renderCart();
        alerta(`Agregado: ${name}`);
      };
    });

  }catch(e){ alerta(e.message||'Error al cargar','err'); }
}

/* ====== Modales ====== */
function openOverlay(id){ const ov = document.getElementById(id); if(ov) ov.style.display='flex'; }
function closeOverlay(id){ const ov = document.getElementById(id); if(ov) ov.style.display='none'; }

function openSummary(){
  const empty  = byId('sumEmpty');
  const content= byId('sumContent');
  const box    = byId('receiptItems');
  const err    = byId('sumErr');

  err.textContent=''; err.style.display='none';

  if(!carrito.length){
    empty.style.display=''; content.style.display='none';
  }else{
    empty.style.display='none'; content.style.display='';
    const {subtotal, ship, disc, total} = totals();
    box.innerHTML = `
      <h4>Detalle</h4>
      ${carrito.map(i=>`<div class="rline"><span>${i.nombre} × ${i.cant}</span><strong>${fmt(i.precio*i.cant)}</strong></div>`).join('')}
      <hr style="border:none;border-top:1px dashed #e5e7eb;margin:8px 0"/>
      <div class="rline"><span>Subtotal</span><strong>${fmt(subtotal)}</strong></div>
      <div class="rline"><span>Despacho (estimado)</span><strong>${fmt(ship)}</strong></div>
      <div class="rline"><span>Descuentos</span><strong>${disc?('− '+fmt(disc)):fmt(0)}</strong></div>
      <div class="rline"><span>Total</span><strong>${fmt(total)}</strong></div>
    `;
    const mem = JSON.parse(localStorage.getItem('cliente')||'{}');
    byId('inpNombre').value = mem?.nombre || '';
    byId('inpEmail').value  = mem?.email  || '';
  }
  openOverlay('ovSummary');
}

/* ====== Pago ====== */
async function pay(){
  if(!carrito.length){ alerta('Carrito vacío','err'); return; }
  const err = byId('sumErr'); err.textContent=''; err.style.display='none';

  const nombre = byId('inpNombre').value.trim();
  const email  = byId('inpEmail').value.trim();

  // Validaciones (tu backend las requiere)
  if(nombre.length < 2){
    err.textContent = 'Ingresa tu nombre (mínimo 2 caracteres).';
    err.style.display=''; byId('inpNombre').focus(); return;
  }
  if(!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)){
    err.textContent = 'Ingresa un email válido.';
    err.style.display=''; byId('inpEmail').focus(); return;
  }

  // Guarda temporalmente por si falla el pago
  localStorage.setItem('cliente', JSON.stringify({ nombre, email }));

  const items = carrito.map(i=>({ producto_id:i.id, cantidad:i.cant }));
  const btnConfirm = byId('btnConfirmarResumen'); const btnPay = byId('pagar');
  btnConfirm.disabled = true; btnConfirm.textContent='Procesando…';
  btnPay.disabled = true; btnPay.textContent='Procesando…';

  try{
    // Preferimos /checkout (envía también "cliente" por compatibilidad)
    await postCheckout({
      items,
      customer_name: nombre,
      customer_email: email,
      cliente: { nombre, email }
    });
  }catch(e){
    // Fallback a /compras si /checkout no existe
    if(/404|405|no permitida|no encontrado/i.test(e.message)){
      for(const it of items){ await postCompra(it.producto_id, it.cantidad); }
    }else{
      err.textContent = e.message || 'Error al pagar';
      err.style.display = '';
      return;
    }
  }finally{
    btnConfirm.disabled = false; btnConfirm.textContent='Confirmar y pagar';
    btnPay.disabled = false; btnPay.textContent='Pagar';
  }

  // ===== ÉXITO =====
  const total = totals().total;
  const copy = carrito.map(i=>({...i}));

  // 1) limpiar carrito y totales
  clearCart(); renderCart();

  // 2) refrescar catálogo desde la API para ver el stock actualizado
  await loadProducts(true);

  // 3) limpiar datos de cliente (para que no queden prellenados)
  localStorage.removeItem('cliente');
  byId('inpNombre').value = '';
  byId('inpEmail').value  = '';

  // 4) boleta
  byId('doneOrder').textContent = '—';
  byId('doneTotal').textContent = fmt(total);
  byId('doneItems').innerHTML = copy.map(it =>
    `<div class="rline"><span>${it.nombre} × ${it.cant}</span><strong>${fmt(it.precio*it.cant)}</strong></div>`
  ).join('');

  // cerrar/abrir modales
  closeOverlay('ovSummary');
  openOverlay('ovDone');
}

