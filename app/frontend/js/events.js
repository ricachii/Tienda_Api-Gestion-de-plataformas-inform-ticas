

// app/frontend/js/events.js
// Listeners y flujo principal del frontend (sin frameworks)
import {
  initApiBase, getProductos, getCategorias, postCheckout, postCompra, API_BASE,
  apiLogin, apiRegister, apiMe, loadAuth, saveAuth, clearAuth
} from './api.js';
import { renderGrid, renderCart, byId, alerta, fmt, showLoading, hideLoading, updateListFooter, sanitize, showGlobalOverlay, hideGlobalOverlay, renderImage } from './ui.js';
import { carrito, addItem, removeItem, changeQty, clearCart, totals } from './cart.js';
import { getState, setState, subscribe } from './state.js';

const catalogMap = new Map();
let checkoutStep = 1;
const checkoutForm = { nombre:'', email:'', direccion:'', ciudad:'', notas:'' };
let currentModalProduct = null;
let currentCheckoutKey = null;
const FALLBACK_CATEGORIES = [
  { value:'Proteínas', label:'Proteínas', note:'Premium', icon:'protein' },
  { value:'Pre entreno', label:'Pre entreno', note:'Energía', icon:'burners' },
  { value:'Vitaminas', label:'Vitaminas', note:'Bienestar', icon:'vitamins' },
  { value:'Ganadores', label:'Ganadores', note:'Masa', icon:'gainers' },
  { value:'Aminoácidos', label:'Aminoácidos', note:'Recuperación', icon:'aminoacido' },
  { value:'Hidratación', label:'Hidratación', note:'Electrolitos', icon:'hydration' },
  { value:'Creatina', label:'Creatina', note:'Monohidratada', icon:'tag' },
  { value:'Snacks', label:'Snacks', note:'Para llevar', icon:'snack' },
];

function normalizeKey(str){
  if(!str) return '';
  try{
    return String(str).normalize('NFD').replace(/\p{Diacritic}/gu,'').toLowerCase().trim();
  }catch(e){
    return String(str).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();
  }
}

function nextCheckoutKey(){
  if(currentCheckoutKey) return currentCheckoutKey;
  const gen = (self.crypto?.randomUUID && self.crypto.randomUUID()) ||
    `${Date.now().toString(36)}-${Math.random().toString(36).slice(2,10)}`;
  currentCheckoutKey = gen;
  return currentCheckoutKey;
}

function clearCheckoutKey(){
  currentCheckoutKey = null;
}

/* Debounce simple para la búsqueda */
function debounce(fn, ms=450){
  let t; return (...a)=>{ clearTimeout(t); t=setTimeout(()=>fn(...a), ms); };
}

// Sincroniza el término de búsqueda con el estado antes de recargar
function triggerSearch(){
  const qNow = byId('q').value.trim();
  setState({ q: qNow, page:1 });
  persistFilters();
  reloadProducts();
}

function buildCategoryChip({ value, label, note, icon }){
  const safeLabel = sanitize(label || value);
  const safeNote = note ? `<small>${sanitize(note)}</small>` : '';
  const safeIcon = sanitize(icon || 'categories');
  const safeValue = sanitize(value);
  return `
    <button type="button" class="category-chip" data-cat="${safeValue}" data-label="${safeLabel}">
      <span class="icon-chip"><img src="/media/icons/${safeIcon}.svg" class="icon" alt=""></span>
      <strong>${safeLabel}</strong>
      ${safeNote}
    </button>
  `;
}

function renderCategoryChips(list){
  const wrap = document.getElementById('categoryChips');
  if(!wrap) return;
  const known = new Map(FALLBACK_CATEGORIES.map(c=>[normalizeKey(c.value), c]));
  const source = (list && list.length ? list : FALLBACK_CATEGORIES.map(c=>c.value));
  const rows = source.map(cat=>{
    if(typeof cat === 'string'){
      const raw = cat.trim();
      const key = normalizeKey(raw);
      const meta = known.get(key) || { value: raw, label: raw };
      return buildCategoryChip(meta);
    }
    // objeto: mezclar con known meta si existe para obtener icono por defecto
    const val = (cat && (cat.value || cat.label)) ? String(cat.value || cat.label) : '';
    const key = normalizeKey(val);
    const base = known.get(key) || {};
    const metaObj = { ...base, ...cat };
    return buildCategoryChip(metaObj);
  }).join('');
  wrap.innerHTML = rows;
}

async function setupCategoryChips(){
  let cats = null;
  try{
    cats = await getCategorias();
  }catch(err){
    console.warn('No se pudieron cargar categorías desde la API.', err);
  }
  renderCategoryChips(Array.isArray(cats) ? cats : FALLBACK_CATEGORIES.map(c=>c.value));
  initCategoryChips();
}

export function initApp(){
  // Búsqueda y filtros
  byId('buscar').onclick = ()=> triggerSearch();
  byId('q').addEventListener('keydown', e=>{ if(e.key==='Enter') { e.preventDefault(); triggerSearch(); } });
  byId('q').addEventListener('input', debounce(()=>{
    setState({ q: byId('q').value.trim(), page:1 });
    persistFilters();
    reloadProducts();
  }, 500));
  byId('priceMin').addEventListener('input', debounce(()=>{
    setState({ priceMin: byId('priceMin').value });
    persistFilters();
    refreshFilterVisuals();
    reloadProducts();
  }, 400));
  byId('priceMax').addEventListener('input', debounce(()=>{
    setState({ priceMax: byId('priceMax').value });
    persistFilters();
    refreshFilterVisuals();
    reloadProducts();
  }, 400));
  byId('sortSel').onchange = ()=>{
    setState({ sort: byId('sortSel').value });
    persistFilters();
    refreshFilterVisuals();
    reloadProducts();
  };
  byId('resetFiltros').onclick = resetFilters;
  byId('refreshCatalog').onclick = ()=> reloadProducts();
  byId('btnGoHome')?.addEventListener('click', ()=> document.querySelector('.hero')?.scrollIntoView({behavior:'smooth', block:'start'}));
  byId('btnGoCategories')?.addEventListener('click', ()=> document.querySelector('.category-bar')?.scrollIntoView({behavior:'smooth', block:'start'}));
  byId('btnNotifications')?.addEventListener('click', ()=> alerta('Esta sección es decorativa en la demo.','warn'));
  byId('btnFavs')?.addEventListener('click', ()=> alerta('Favoritos no está disponible en esta demo.','warn'));
  byId('btnIngredients')?.addEventListener('click', ()=> alerta('Busca por ingrediente: ej. creatina, omega, vitaminas.'));

  // Hero shortcuts
  byId('heroExplore').onclick = ()=> document.getElementById('productos').scrollIntoView({behavior:'smooth', block:'start'});
  byId('heroSummary').onclick = ()=> openCheckout();

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
  byId('resumen').onclick = openCheckout;
  byId('pagar').onclick   = openCheckout;
  byId('btnStepNext').onclick = ()=> advanceCheckout(1);
  byId('btnStepBack').onclick = ()=> advanceCheckout(-1);
  byId('btnCheckoutPay').onclick = completeCheckout;
  document.querySelectorAll('[data-close]').forEach(b=>{
    b.addEventListener('click', ()=> closeOverlay(b.getAttribute('data-close')) );
  });
  byId('btnSeguir').onclick = ()=> closeOverlay('ovDone');
  byId('modalAddCart').onclick = ()=> {
    if(currentModalProduct) addProductToCart(currentModalProduct.id);
  };

  // Auth UI
  byId('btnLogin').onclick = ()=> openOverlay('ovAuth');
  byId('btnLogout').onclick = doLogout;
  byId('btnDoLogin').onclick = doLogin;
  byId('btnDoRegister').onclick = doRegister;

  // Conectividad
  // Mantiene clase offline sincronizada con store
  subscribe((next)=>{ document.body.classList.toggle('offline', !next.online); });
  syncOfflineBanner();
  window.addEventListener('online', syncOfflineBanner);
  window.addEventListener('offline', syncOfflineBanner);
  const heroExplore = byId('heroExplore'); if(heroExplore){ heroExplore.setAttribute('tabindex','0'); }

  // Arranque
  byId('productos').addEventListener('click', onGridClick);
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
    if(e.key === 'c' || e.key === 's'){
      openCheckout();
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

  // Obtener versión del frontend desde el backend (si está expuesto)
  (async ()=>{
    try{
      const resp = await fetch('/frontend/version');
      if(resp.ok){
        const j = await resp.json();
        const v = j && j.version ? j.version : '—';
        const el = document.getElementById('frontendVersion');
        if(el) el.textContent = v;
      }
    }catch(e){ /* silencioso */ }
  })();

  restoreFilters();
  await setupCategoryChips();

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
  const btn = byId('btnDoLogin');

  err.style.display='none'; err.textContent='';

  if(!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)){
    err.textContent = 'Email inválido.'; err.style.display=''; return;
  }
  if(!password || password.length<4){
    err.textContent = 'Contraseña demasiado corta.'; err.style.display=''; return;
  }

  const prevTxt = btn?.textContent;
  if(btn){ btn.disabled = true; btn.textContent = 'Ingresando…'; }
  try{
    showGlobalOverlay('Autenticando…');
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
  }finally{
    hideGlobalOverlay();
    if(btn){ btn.disabled = false; btn.textContent = prevTxt || 'Iniciar sesión'; }
  }
}

async function doRegister(){
  const email = byId('authEmail').value.trim();
  const password = byId('authPass').value;
  const nombre = byId('authName').value.trim();
  const err = byId('authErr');
  const btn = byId('btnDoRegister');

  err.style.display='none'; err.textContent='';

  if(!nombre || nombre.length<2){ err.textContent='Ingresa tu nombre.'; err.style.display=''; return; }
  if(!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)){ err.textContent='Email inválido.'; err.style.display=''; return; }
  if(!password || password.length<6){ err.textContent='Usa al menos 6 caracteres.'; err.style.display=''; return; }

  const prevTxt = btn?.textContent;
  if(btn){ btn.disabled = true; btn.textContent = 'Registrando…'; }
  try{
    showGlobalOverlay('Registrando…');
    await apiRegister({ email, nombre, password });
    alerta('Registro exitoso. Ahora inicia sesión.');
  }catch(e){
    err.textContent = e.message || 'No fue posible registrar.';
    err.style.display='';
  }finally{
    hideGlobalOverlay();
    if(btn){ btn.disabled = false; btn.textContent = prevTxt || 'Registrar'; }
  }
}

function doLogout(silent=false){
  clearAuth();
  renderSession();
  if(!silent) alerta('Sesión cerrada');
}

/* ===== helpers UI ya existentes ===== */
function persistFilters(){
  const st = getState();
  localStorage.setItem('filters', JSON.stringify({
    q: st.q,
    cat: st.cat,
    catLabel: st.catLabel,
    priceMin: st.priceMin,
    priceMax: st.priceMax,
    sort: st.sort,
  }));
}
function restoreFilters(){
  const f = JSON.parse(localStorage.getItem('filters')||'{}');
  setState({
    q: f.q || '',
    cat: f.cat || '',
    catLabel: f.catLabel || '',
    priceMin: f.priceMin || '',
    priceMax: f.priceMax || '',
    sort: f.sort || getState().sort,
  });
  const st = getState();
  if(st.q) byId('q').value = st.q;
  if(st.priceMin) byId('priceMin').value = st.priceMin;
  if(st.priceMax) byId('priceMax').value = st.priceMax;
  if(st.sort) byId('sortSel').value = st.sort;
  syncCategoryChips();
  refreshFilterVisuals();
}
function resetFilters(){
  setState({ q:'', cat:'', catLabel:'', priceMin:'', priceMax:'', sort:'featured', page:1 });
  byId('q').value=''; byId('priceMin').value=''; byId('priceMax').value=''; byId('sortSel').value='featured';
  syncCategoryChips();
  persistFilters();
  refreshFilterVisuals();
  reloadProducts();
}

function applyLocalFilters(list){
  let filtered = [...list];
  const st = getState();
  const min = Number(st.priceMin);
  const max = Number(st.priceMax);
  if(!Number.isNaN(min) && st.priceMin !== '') filtered = filtered.filter(p => Number(p.precio) >= min);
  if(!Number.isNaN(max) && st.priceMax !== '') filtered = filtered.filter(p => Number(p.precio) <= max);

  switch(st.sort){
    case 'price-asc': filtered.sort((a,b)=>Number(a.precio)-Number(b.precio)); break;
    case 'price-desc': filtered.sort((a,b)=>Number(b.precio)-Number(a.precio)); break;
    case 'stock': filtered.sort((a,b)=>Number(b.stock||0)-Number(a.stock||0)); break;
    default: break;
  }
  return filtered;
}

function updateResultsCounter(count){
  const label = count === 1 ? 'producto' : 'productos';
  const el = byId('resultsCount');
  if(el) el.textContent = `${count} ${label}`;
}

function refreshFilterVisuals(){
  const minField = byId('priceMin')?.closest('.field');
  const maxField = byId('priceMax')?.closest('.field');
  const sortField = byId('sortSel')?.closest('.field');
  const st = getState();
  if(minField) minField.classList.toggle('active-filter', !!st.priceMin);
  if(maxField) maxField.classList.toggle('active-filter', !!st.priceMax);
  if(sortField) sortField.classList.toggle('active-filter', st.sort && st.sort !== 'featured');

  const status = byId('filterStatus');
  if(!status) return;
  const hasPrice = Boolean(st.priceMin || st.priceMax);
  const hasSort = Boolean(st.sort && st.sort !== 'featured');
  const hasCat = Boolean(st.cat);
  if(!hasPrice && !hasSort && !hasCat){
    status.style.display = 'none';
    status.textContent = '';
    return;
  }
  const parts = [];
  if(hasCat){
    const label = st.catLabel || st.cat;
    parts.push(`Categoría: ${label}`);
  }
  if(hasPrice) parts.push('Precio filtrado');
  if(hasSort){
    const map = {
      'price-asc':'Ordenado menor→mayor',
      'price-desc':'Ordenado mayor→menor',
      'stock':'Ordenado por stock',
    };
    parts.push(map[st.sort] || 'Orden personalizado');
  }
  status.textContent = parts.join(' • ');
  status.style.display = '';
}

function initCategoryChips(){
  const wrap = document.getElementById('categoryChips');
  if(!wrap) return;
  wrap.addEventListener('click', (ev)=>{
    const chip = ev.target.closest('.category-chip[data-cat]');
    if(!chip || !wrap.contains(chip)) return;
    const value = chip.dataset.cat || '';
    const label = chip.dataset.label || chip.textContent.trim();
    const st = getState();
    const isSame = st.cat === value;
    setState({
      cat: isSame ? '' : value,
      catLabel: isSame ? '' : label,
      page:1,
    });
    persistFilters();
    syncCategoryChips();
    reloadProducts();
  }, { passive:true });
  syncCategoryChips();
}

function syncCategoryChips(){
  document.querySelectorAll('.category-chip[data-cat]').forEach(chip=>{
    const value = chip.dataset.cat || '';
    const st = getState();
    const isActive = Boolean(st.cat) && st.cat === value;
    chip.classList.toggle('active', isActive);
    chip.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    if(isActive && !st.catLabel){
      setState({ catLabel: chip.dataset.label || chip.textContent.trim() });
    }
  });
}

function showEmptyResults(){
  const cont = byId('productos');
  if(cont){
    cont.innerHTML = `
      <div class="empty-results">
        <span class="icon-chip empty-icon"><img src="/media/icons/advertencia.svg?v=1" class="icon" alt=""></span>
        <p>No encontramos productos con esos filtros. Prueba limpiarlos o buscar otra marca.</p>
      </div>
    `;
  }
}

async function reloadProducts(){ setState({ page:1 }); await loadProducts({ reset:true }); }
async function loadMore(){
  const st = getState();
  if(st.loading) return;
  if(st.page >= st.total_pages) return;
  setState({ page: st.page + 1 });
  await loadProducts({ reset:false });
}

async function loadProducts({reset=false}={}){
  setState({ loading:true });
  showLoading();
  updateListFooter({visible:false});
  try{
    const st = getState();
    const data = await getProductos(st.page, st.size, st.q, st.cat);
    setState({ total_pages: data.total_pages || 1 });
    const items = data.items || [];

    if(reset) catalogMap.clear();
    items.forEach(p=> catalogMap.set(p.id, p));

    const filtered = applyLocalFilters(items);
    if(reset){
      if(filtered.length){
        renderGrid(filtered, {append:false});
      }else{
        showEmptyResults();
      }
    }else if(filtered.length){
      renderGrid(filtered, {append:true});
    }

    const totalCards = document.querySelectorAll('#productos .card').length;
    updateResultsCounter(totalCards);

    const latest = getState();
    const canLoadMore = latest.page < latest.total_pages;
    updateListFooter({visible: latest.total_pages>1 || items.length>0, canLoadMore});
    if(reset && (!items.length)) alerta('Sin resultados para tu búsqueda','warn');
  }catch(e){ alerta(e.message||'Error al cargar','err'); }
  finally{
    hideLoading();
    setState({ loading:false });
    refreshFilterVisuals();
  }
}

function onGridClick(ev){
  const target = ev.target.closest('[data-act]') || ev.target.closest('.card');
  if(!target) return;
  const card = ev.target.closest('.card');
  if(!card) return;
  const id = Number(card.dataset.id);
  if(ev.target.closest('.addbtn') || target.dataset.act === 'add'){
    addProductToCart(id);
    return;
  }
  if(ev.target.closest('.viewbtn') || target.dataset.act === 'ver'){
    openProductModal(id);
    return;
  }
  if(ev.target.closest('.row')) return;
  openProductModal(id);
}

function addProductToCart(id, qty=1){
  const prod = catalogMap.get(id);
  if(!prod) return alerta('Producto no disponible','err');
  const stock = Number(prod.stock ?? 0);
  if(stock <= 0) return alerta('Sin stock','err');
  addItem({ id: prod.id, nombre: prod.nombre, precio: Number(prod.precio), stock }, qty);
  renderCart();
  alerta(`Agregado: ${prod.nombre}`);
}

function openProductModal(id){
  const prod = catalogMap.get(id);
  if(!prod) return;
  currentModalProduct = prod;
  byId('prodName').textContent = prod.nombre || 'Producto';
  byId('prodCat').textContent = prod.categoria || 'General';
  byId('prodDesc').textContent = prod.descripcion || 'Sin descripción disponible.';
  byId('prodPrice').textContent = fmt(prod.precio);
  byId('prodStock').textContent = prod.stock > 0 ? `${prod.stock} unidades` : 'Sin stock';
  // Usa helper para imagen segura con placeholder
  const media = document.querySelector('.product-media');
  if(media) media.innerHTML = renderImage(prod);
  openOverlay('ovProduct');
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
  if(id === 'ovProduct') currentModalProduct = null;
}

/* Checkout multi-step */
function openCheckout(){
  const empty  = byId('wizardEmpty');
  const content= byId('wizardContent');
  const err    = byId('sumErr');
  err.textContent=''; err.style.display='none';

  if(!carrito.length){
    empty.textContent = 'Tu carrito está vacío. Agrega productos para ver el resumen y pagar.';
    empty.style.display=''; content.style.display='none';
  }else{
    empty.style.display='none'; content.style.display='';
    checkoutStep = 1;
    renderCheckoutItems();
    const mem = JSON.parse(localStorage.getItem('cliente')||'{}');
    byId('ckNombre').value = checkoutForm.nombre = mem?.nombre || '';
    byId('ckEmail').value = checkoutForm.email = mem?.email || '';
    byId('ckDireccion').value = checkoutForm.direccion = mem?.direccion || '';
    byId('ckCiudad').value = checkoutForm.ciudad = mem?.ciudad || '';
    byId('ckNotas').value = checkoutForm.notas = '';
    renderCheckoutStep();
  }
  openOverlay('ovCheckout');
}

function renderCheckoutItems(){
  const box = byId('stepItems');
  const {subtotal, ship, disc, total} = totals();
  box.innerHTML = `
    <h4>Detalle</h4>
    ${carrito.map(i=>`<div class="rline"><span>${sanitize(i.nombre || 'Producto')} × ${i.cant}</span><strong>${fmt(i.precio*i.cant)}</strong></div>`).join('')}
    <hr style="border:none;border-top:1px dashed #e5e7eb;margin:8px 0"/>
    <div class="rline"><span>Subtotal</span><strong>${fmt(subtotal)}</strong></div>
    <div class="rline"><span>Despacho estimado</span><strong>${fmt(ship)}</strong></div>
    <div class="rline"><span>Descuentos</span><strong>${disc?('− '+fmt(disc)):fmt(0)}</strong></div>
    <div class="rline"><span>Total</span><strong>${fmt(total)}</strong></div>
  `;
}

function renderCheckoutStep(){
  document.querySelectorAll('.wizard-step').forEach(step=>{
    step.classList.toggle('active', Number(step.dataset.step) === checkoutStep);
  });
  document.querySelectorAll('#checkoutSteps .step').forEach(step=>{
    step.classList.toggle('active', Number(step.dataset.step) <= checkoutStep);
  });
  byId('btnStepBack').style.visibility = checkoutStep === 1 ? 'hidden' : 'visible';
  byId('btnStepNext').style.display = checkoutStep < 3 ? '' : 'none';
  byId('btnCheckoutPay').style.display = checkoutStep === 3 ? '' : 'none';
}

function advanceCheckout(direction){
  if(!carrito.length){ alerta('Carrito vacío','err'); return; }
  const err = byId('sumErr'); err.textContent=''; err.style.display='none';
  if(direction > 0){
    if(checkoutStep === 1){
      checkoutStep = 2;
    }else if(checkoutStep === 2){
      if(!captureCheckoutForm()) return;
      checkoutStep = 3;
      buildCheckoutSummary();
    }
  }else if(direction < 0 && checkoutStep > 1){
    checkoutStep -= 1;
  }
  renderCheckoutStep();
}

function captureCheckoutForm(){
  const nombre = byId('ckNombre').value.trim();
  const email = byId('ckEmail').value.trim();
  const direccion = byId('ckDireccion').value.trim();
  const ciudad = byId('ckCiudad').value.trim();
  const notas = byId('ckNotas').value.trim();
  const err = byId('sumErr'); err.textContent=''; err.style.display='none';

  if(nombre.length < 2){ err.textContent='Ingresa el nombre del responsable.'; err.style.display=''; byId('ckNombre').focus(); return false; }
  if(!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)){ err.textContent='Ingresa un correo válido.'; err.style.display=''; byId('ckEmail').focus(); return false; }
  if(direccion.length < 3){ err.textContent='Especifica la ubicación o laboratorio de destino.'; err.style.display=''; byId('ckDireccion').focus(); return false; }

  checkoutForm.nombre = nombre;
  checkoutForm.email = email;
  checkoutForm.direccion = direccion;
  checkoutForm.ciudad = ciudad;
  checkoutForm.notas = notas;
  localStorage.setItem('cliente', JSON.stringify({ nombre, email, direccion, ciudad }));
  return true;
}

function buildCheckoutSummary(){
  const box = byId('stepResumen');
  const { total } = totals();
  box.innerHTML = `
    <h4>Confirmación final</h4>
    <p class="muted">Enviaremos confirmación a <strong>${sanitize(checkoutForm.email)}</strong></p>
    <div class="rline"><span>Destinatario</span><strong>${sanitize(checkoutForm.nombre)}</strong></div>
    <div class="rline"><span>Dirección</span><strong>${sanitize(checkoutForm.direccion || '—')}</strong></div>
    <div class="rline"><span>Ciudad</span><strong>${sanitize(checkoutForm.ciudad || '—')}</strong></div>
    <div class="rline"><span>Total</span><strong>${fmt(total)}</strong></div>
    ${checkoutForm.notas ? `<div class="rline"><span>Notas</span><strong>${sanitize(checkoutForm.notas)}</strong></div>` : ''}
  `;
}

async function completeCheckout(){
  if(!carrito.length){ alerta('Carrito vacío','err'); return; }
  if(checkoutStep < 3 && !captureCheckoutForm()){ return; }

  const err = byId('sumErr'); err.textContent=''; err.style.display='none';
  const items = carrito.map(i=>({ producto_id:i.id, cantidad:i.cant }));
  const idempotencyKey = nextCheckoutKey();
  let response = null;
  let usedFallback = false;

  const btnPay = byId('btnCheckoutPay'); const btnNext = byId('btnStepNext');
  const payPrev = btnPay.textContent;
  btnPay.disabled = true; btnPay.textContent='Procesando…';
  btnNext.disabled = true;

  try{
    showGlobalOverlay('Procesando pago…');
    response = await postCheckout({
      items,
      customer_name: checkoutForm.nombre,
      customer_email: checkoutForm.email,
      shipping_address: checkoutForm.direccion || undefined,
      customer_notes: checkoutForm.notas || undefined,
      idempotency_key: idempotencyKey,
    });
  }catch(e){
    if(/404|405|no permitida|no encontrado/i.test(e.message)){
      for(const it of items){ await postCompra(it.producto_id, it.cantidad); }
      clearCheckoutKey();
      usedFallback = true;
      response = { order_id: null, total: totals().total };
    }else{
      err.textContent = e.message || 'Error al pagar';
      err.style.display='';
      btnPay.disabled = false; btnPay.textContent=payPrev || 'Confirmar y pagar';
      btnNext.disabled = false;
      return;
    }
  }finally{
    btnPay.disabled = false; btnPay.textContent=payPrev || 'Confirmar y pagar';
    btnNext.disabled = false;
    hideGlobalOverlay();
  }

  if(response){
    clearCheckoutKey();

    const total = Number(response?.total ?? totals().total);
    const copy = carrito.map(i=>({...i}));
    clearCart(); renderCart();
    await reloadProducts();

    byId('doneOrder').textContent = response?.order_id ? `#${response.order_id}` : (usedFallback ? 'manual' : '—');
    const statusText = response?.order_status || (usedFallback ? 'MANUAL' : '—');
    const doneStatus = byId('doneStatus');
    if(doneStatus) doneStatus.textContent = statusText;
    byId('doneTotal').textContent = fmt(total);
    byId('doneItems').innerHTML = copy.map(it =>
      `<div class="rline"><span>${sanitize(it.nombre)} × ${it.cant}</span><strong>${fmt(it.precio*it.cant)}</strong></div>`
    ).join('');
    if(response?.detalle) alerta(response.detalle, 'ok');

    closeOverlay('ovCheckout');
    openOverlay('ovDone');
  }
}

/* Conectividad */
function syncOfflineBanner(){
  // sincroniza la bandera online/offline en el store
  setState({ online: navigator.onLine });
}
