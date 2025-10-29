//Lógica del carrito

export let carrito = JSON.parse(localStorage.getItem('carrito')||'[]');
const save = ()=> localStorage.setItem('carrito', JSON.stringify(carrito));
export const addItem = (prod,cant=1)=>{
  const ex = carrito.find(i=>i.id===prod.id);
  if(ex) ex.cant = Math.min(ex.stock, ex.cant + cant);
  else carrito.push({...prod, cant: Math.min(prod.stock, cant)});
  save();
};
export const removeItem = (id)=>{ carrito = carrito.filter(i=>i.id!==id); save(); };
export const changeQty = (id,delta)=>{
  const it = carrito.find(i=>i.id===id); if(!it) return;
  it.cant = Math.max(1, Math.min(it.stock, it.cant + delta)); save();
};
export const clearCart = ()=>{ carrito=[]; save(); };
export const totals = ()=>{
  const subtotal = carrito.reduce((s,i)=>s+i.precio*i.cant,0);
  const ship = subtotal>0 ? Math.round(Math.min(4990, subtotal*0.02)) : 0;
  const disc = subtotal>=50000 ? Math.round(subtotal*0.05) : 0;
  const total = Math.max(0, subtotal + ship - disc);
  return {subtotal, ship, disc, total};
};
