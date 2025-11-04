

// app/frontend/js/events.js
// Listeners y flujo principal del frontend (sin frameworks)
import {
  initApiBase, getCategorias, getProductos, postCheckout, postCompra, API_BASE,
  apiLogin, apiRegister, apiMe, loadAuth, saveAuth, clearAuth
} from './api.js';
import { renderGrid, renderCart, byId, alerta, fmt, showLoading, hideLoading, updateListFooter } from './ui.js';
import { carrito, addItem, removeItem, changeQty, clearCart, totals } from './cart.js';

/* Estado de la lista/paginación */
let state = {
  page: 1,
  size: 12,
  q: '',
  cat: '',
  total_pages: 1,
  loading: false,
};

/* Debounce simple para la búsqueda */
function debounce(fn, ms=450){
  let t; return (...a)=>{ clearTimeout(t); t=setTimeout(()=>fn(...a), ms); };
}

export function initApp(){
  // Búsqueda y filtros
  byId('buscar').onclick = ()=> reloadProducts();
  byId('catSel').onchange = ()=> { state.cat = byId('catSel').value; persistFilters(); reloadProducts(); };
  byId('q').addEventListener('keydown', e=>{ if(e.key==='Enter') reloadProducts(); });
  byId('q').addEventListener('input', debounce(()=>{ state.q = byId('q').value.trim(); persistFilters(); reloadProducts(); }, 500));

  // Cargar más
  byId('loadMore').onclick = ()=> loadMore();

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
  byId('pagar').onclick   = openSummary;
  byId('btnConfirmarResumen').onclick = pay;
  document.querySelectorAll('[data-close]').forEach(b=>{
    b.addEventListener('click', ()=> closeOverlay(b.getAttribute('data-close')) );
  });
  byId('btnSeguir').onclick = ()=> closeOverlay('ovDone');

  // Auth UI
  byId('btnLogin').onclick = ()=> openOverlay('ovAuth');
  byId('btnLogout').onclick = doLogout;
  byId('btnDoLogin').onclick = doLogin;
  byId('btnDoRegister').onclick = doRegister;

  // Conectividad
  syncOfflineBanner();
  window.addEventListener('online', syncOfflineBanner);
  window.addEventListener('offline', syncOfflineBanner);

  // Arranque
  renderCart();
  boot();
}

  
  // Keyboard shortcuts: '/' focus search, 'c' open resumen/carrito, 's' open summary
  function globalShortcuts(e){
    const tag = (document.activeElement && document.activeElement.tagName||'').toLowerCase();
    if(tag === 'input' || tag === 'textarea' || document.activeElement?.isContentEditable) return;
    if(e.key === '/'){
      const q = byId('q'); if(q){ e.preventDefault(); q.focus(); q.select(); }
    }
    if(e.key === 'c'){
      // abrir resumen/carrito
      openSummary();
    }
    if(e.key === 's'){
      openSummary();
    }
  }
  
  // global shortcuts
  document.addEventListener('keydown', globalShortcuts);
  
  // menu toggle (small screens)
  const mt = byId('menuToggle'); if(mt){
    mt.addEventListener('click', ()=>{
      const hdr = document.querySelector('header');
      const open = hdr.classList.toggle('toolbar-open');
      mt.setAttribute('aria-expanded', String(open));
    });
  }
async function boot(){
  await initApiBase();
  byId('apiBase').textContent = API_BASE;

  try{
    const cats = await getCategorias();
    byId('catSel').innerHTML = '<option value="">Todas</option>' + (cats||[]).map(c=>`<option>${c}</option>`).join('');
  }catch{}

  restoreFilters();

  // Cargar auth previa (si existe) y poblar /me (opcional)
  const auth = loadAuth();
  if (auth?.token) {
    try {
      const me = await apiMe();
      saveAuth({ user: me });
      renderSession();
    } catch {
      // token inválido
      doLogout(true);
    }
  } else {
    renderSession();
  }

  await reloadProducts();
}

function renderSession(){
  const who = byId('whoami');
  const btnIn = byId('btnLogin');
  const btnOut = byId('btnLogout');
  const auth = loadAuth();

  if (auth?.user?.nombre || auth?.user?.email) {
    who.textContent = auth.user.nombre ? `${auth.user.nombre}` : auth.user.email;
    btnIn.style.display = 'none';
    btnOut.style.display = '';
  } else {
    who.textContent = 'Invitado';
    btnIn.style.display = '';
    btnOut.style.display = 'none';
  }
}

async function doLogin(){
  const email = byId('authEmail').value.trim();
  const password = byId('authPass').value;
  const err = byId('authErr');

  err.style.display='none'; err.textContent='';

  if(!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)){
    err.textContent = 'Email inválido.'; err.style.display=''; return;
  }
  if(!password || password.length<4){
    err.textContent = 'Contraseña demasiado corta.'; err.style.display=''; return;
  }

  try{
    const res = await apiLogin({ email, password }); // { access_token, token_type, expires_in? }
    const exp = res?.expires_in ? Date.now() + Number(res.expires_in)*1000 : null;
    saveAuth({ token: res.access_token, exp });

    const me = await apiMe(); // carga perfil + rol
    saveAuth({ user: me });

    alerta('Sesión iniciada');
    closeOverlay('ovAuth');
    renderSession();
  }catch(e){
    err.textContent = e.message || 'No fue posible iniciar sesión.';
    err.style.display=''; 
  }
}

async function doRegister(){
  const email = byId('authEmail').value.trim();
  const password = byId('authPass').value;
  const nombre = byId('authName').value.trim();
  const err = byId('authErr');

  err.style.display='none'; err.textContent='';

  if(!nombre || nombre.length<2){ err.textContent='Ingresa tu nombre.'; err.style.display=''; return; }
  if(!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)){ err.textContent='Email inválido.'; err.style.display=''; return; }
  if(!password || password.length<6){ err.textContent='Usa al menos 6 caracteres.'; err.style.display=''; return; }

  try{
    await apiRegister({ email, nombre, password });
    alerta('Registro exitoso. Ahora inicia sesión.');
  }catch(e){
    err.textContent = e.message || 'No fue posible registrar.';
    err.style.display='';
  }
}

function doLogout(silent=false){
  clearAuth();
  renderSession();
  if(!silent) alerta('Sesión cerrada');
}

/* ===== helpers UI ya existentes ===== */
function persistFilters(){ localStorage.setItem('filters', JSON.stringify({ q: state.q, cat: state.cat })); }
function restoreFilters(){
  const f = JSON.parse(localStorage.getItem('filters')||'{}');
  if(f.q) { state.q = f.q; byId('q').value = f.q; }
  if(f.cat){ state.cat = f.cat; byId('catSel').value = f.cat; }
}

async function reloadProducts(){ state.page = 1; await loadProducts({ reset:true }); }
async function loadMore(){ if(state.loading) return; if(state.page >= state.total_pages) return; state.page += 1; await loadProducts({ reset:false }); }

async function loadProducts({reset=false}={}){
  state.loading = true;
  showLoading();
  updateListFooter({visible:false});
  try{
    const data = await getProductos(state.page, state.size, state.q, state.cat);
    state.total_pages = data.total_pages || 1;
    const items = data.items || [];
    renderGrid(items, {append: !reset});

    document.querySelectorAll('.card .addbtn').forEach(btn=>{
      if(btn._wired) return;
      btn._wired = true;
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

    const canLoadMore = state.page < state.total_pages;
    updateListFooter({visible: state.total_pages>1 || items.length>0, canLoadMore});
    if(reset && (!items.length)) alerta('Sin resultados para tu búsqueda','warn');
  }catch(e){ alerta(e.message||'Error al cargar','err'); }
  finally{ hideLoading(); state.loading = false; }
}

/* Modales */
function openOverlay(id){
  const ov = document.getElementById(id);
  if(!ov) return;
  // show
  ov.style.display='flex';
  ov.removeAttribute('aria-hidden');
  // remember previously focused element to restore later
  ov._previousActive = document.activeElement;

  // focus first focusable element inside modal
  const focusable = ov.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
  if(focusable && focusable.length) focusable[0].focus();

  // key handler for ESC and Tab trapping
  const keyHandler = (e)=>{
    if(e.key === 'Escape') { closeOverlay(id); }
    if(e.key === 'Tab'){
      const foc = Array.from(focusable).filter(el=> !el.hasAttribute('disabled') && el.offsetParent!==null);
      if(!foc.length) return;
      const first = foc[0], last = foc[foc.length-1];
      if(e.shiftKey && document.activeElement === first){ e.preventDefault(); last.focus(); }
      else if(!e.shiftKey && document.activeElement === last){ e.preventDefault(); first.focus(); }
    }
  };
  ov._keyHandler = keyHandler;
  document.addEventListener('keydown', keyHandler);

  // close when clicking on backdrop
  const clickHandler = (ev)=>{ if(ev.target === ov) closeOverlay(id); };
  ov._clickHandler = clickHandler;
  ov.addEventListener('click', clickHandler);
}

function closeOverlay(id){
  const ov = document.getElementById(id);
  if(!ov) return;
  ov.style.display='none';
  ov.setAttribute('aria-hidden','true');
  // remove handlers
  if(ov._keyHandler) document.removeEventListener('keydown', ov._keyHandler);
  if(ov._clickHandler) ov.removeEventListener('click', ov._clickHandler);
  // restore focus
  try{ if(ov._previousActive) ov._previousActive.focus(); }catch{}
}

/* Pago */
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

async function pay(){
  if(!carrito.length){ alerta('Carrito vacío','err'); return; }
  const err = byId('sumErr'); err.textContent=''; err.style.display='none';

  const nombre = byId('inpNombre').value.trim();
  const email  = byId('inpEmail').value.trim();

  if(nombre.length < 2){ err.textContent = 'Ingresa tu nombre.'; err.style.display=''; byId('inpNombre').focus(); return; }
  if(!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)){ err.textContent = 'Ingresa un email válido.'; err.style.display=''; byId('inpEmail').focus(); return; }

  localStorage.setItem('cliente', JSON.stringify({ nombre, email }));

  const items = carrito.map(i=>({ producto_id:i.id, cantidad:i.cant }));
  const btnConfirm = byId('btnConfirmarResumen'); const btnPay = byId('pagar');
  btnConfirm.disabled = true; btnConfirm.textContent='Procesando…';
  btnPay.disabled = true; btnPay.textContent='Procesando…';

  try{
    await postCheckout({ items, customer_name:nombre, customer_email:email, cliente:{nombre,email} });
  }catch(e){
    if(/404|405|no permitida|no encontrado/i.test(e.message)){
      for(const it of items){ await postCompra(it.producto_id, it.cantidad); }
    }else{
      err.textContent = e.message || 'Error al pagar'; err.style.display=''; return;
    }
  }finally{
    btnConfirm.disabled = false; btnConfirm.textContent='Confirmar y pagar';
    btnPay.disabled = false; btnPay.textContent='Pagar';
  }

  const total = totals().total;
  const copy = carrito.map(i=>({...i}));
  clearCart(); renderCart();
  await reloadProducts();

  localStorage.removeItem('cliente');
  byId('inpNombre').value = '';
  byId('inpEmail').value  = '';

  byId('doneOrder').textContent = '—';
  byId('doneTotal').textContent = fmt(total);
  byId('doneItems').innerHTML = copy.map(it =>
    `<div class="rline"><span>${it.nombre} × ${it.cant}</span><strong>${fmt(it.precio*it.cant)}</strong></div>`
  ).join('');

  closeOverlay('ovSummary');
  openOverlay('ovDone');
}

/* Conectividad */
function syncOfflineBanner(){
  if(navigator.onLine) document.body.classList.remove('offline');
  else document.body.classList.add('offline');
}
