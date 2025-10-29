//Punto de entrada que inicializa todo


// main.js
import { initApp } from './events.js';
document.addEventListener('DOMContentLoaded', initApp);

// events.js
import { getProductos, postCheckout } from './api.js';
import { renderGrid, renderCart, alerta } from './ui.js';
import { carrito, addItem, removeItem, changeQty, totals } from './cart.js';
