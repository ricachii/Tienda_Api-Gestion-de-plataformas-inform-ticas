// app/frontend/js/state.js
// Pequeño store sin dependencias para centralizar estado de UI

export const initialState = {
  page: 1,
  size: 48,
  q: '',
  cat: '',
  catLabel: '',
  priceMin: '',
  priceMax: '',
  sort: 'featured',
  total_pages: 1,
  loading: false,
  online: typeof navigator !== 'undefined' ? navigator.onLine : true,
};

let state = { ...initialState };
const listeners = new Set();

export function getState(){
  return { ...state };
}

export function setState(updates = {}){
  const prev = state;
  state = { ...state, ...updates };
  listeners.forEach(fn => {
    try { fn(state, prev); } catch (e) { console.error('State listener error', e); }
  });
  return state;
}

// Se puede usar para reaccionar a cambios (ej: conectividad)
export function subscribe(listener){
  listeners.add(listener);
  return ()=> listeners.delete(listener);
}

export function resetState(){
  state = { ...initialState };
  listeners.forEach(fn => {
    try { fn(state, state); } catch (e) { console.error('State listener error', e); }
  });
}
