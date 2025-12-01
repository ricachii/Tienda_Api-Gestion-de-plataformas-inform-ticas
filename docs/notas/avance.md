# Avance del proyecto — Tienda API (estudiante)

Este documento explica de forma clara y paso a paso el proyecto "Tienda API": su propósito, cómo está organizado, cómo se implementó y cómo usarlo localmente. Está redactado en español con un enfoque para estudiante.

## Resumen del proyecto

La aplicación es una API para una tienda en línea con un frontend estático (empotrado) y un backend en Python (FastAPI). Provee endpoints para listar productos y categorías, crear compras y procesar un simple flujo de checkout. Además incluye pruebas E2E con Playwright y un workflow de CI para ejecutar comprobaciones automáticas.

Componentes principales:
- Backend: FastAPI (archivo `app/main.py`, `app/routes.py`, `app/models.py`, `app/db.py`).
- Frontend: archivos estáticos en `app/frontend/` que se construyen con un script de bundling (`build.js`) y quedan en `/dist`.
- Base de datos: script SQL `tienda.sql` con el esquema y datos de ejemplo (uso MySQL/MariaDB local o en CI).
- Tests E2E: Playwright bajo `tests/playwright/`.
- CI: workflows en `.github/workflows/` para build y pruebas (se añadió `frontend-ci.yml` y un workflow de debug temporal).

## Objetivo funcional

Permitir a un usuario (o a tests E2E) navegar el catálogo, ver productos por categoría, crear compras y probar el flujo de pago simulado. La API es RESTful y el frontend consume la API localmente al ejecutarse el servidor.

## Estructura del repositorio (resumen)

- `app/`
  - `main.py` — arranque de la app FastAPI.
  - `routes.py` — endpoints expuestos (productos, categorías, compras, checkout).
  - `models.py` — modelos de datos (Pydantic / mapeo simple).
  - `db.py` — conexión a la base de datos (PyMySQL) y helpers.
  - `frontend/` — paquete del frontend: `index.html`, `css/`, `js/`, `package.json`, `build.js`.
- `tests/playwright/` — pruebas E2E (p. ej. `basic.spec.js`, `e2e.spec.js`).
- `tienda.sql` — DDL y datos de ejemplo para popular la base de datos.
- `requirements.txt` — dependencias Python.
- `.github/workflows/` — workflows de CI.
- `scripts/smoke_test.py` — script ligero para comprobar la API sin navegador.

## Cómo se llevó a cabo (pasos de implementación)

1. Diseño y modelado: definir entidades básicas (producto, categoría, compra). Guardé esquema y datos de ejemplo en `tienda.sql`.
2. Backend: se creó una API con FastAPI. Implementé rutas CRUD/lectura necesarias en `routes.py` y utilicé `db.py` para las consultas.
3. Frontend: se dejó una UI mínima en `app/frontend/` que consume la API. Para mantener reproducibilidad, el tooling Node quedó dentro de `app/frontend` con su `package.json` y `package-lock.json`.
4. Bundling: agregué `build.js` usando `esbuild` para generar `dist/` en la raíz cuando se hace build.
5. Tests E2E: escribí specs Playwright que recorren el sitio y verifican flujos básicos. Están bajo `tests/playwright/`.
6. CI: añadí un workflow para ejecutar build y pruebas en GitHub Actions. También añadí un workflow de debug temporal para diagnosticar problemas de descubrimiento de tests.

## Cómo funcionan sus partes (explicación técnica)

- Backend (FastAPI): arranca con `uvicorn app.backend.main:app`. Lee configuración de conexión a la base de datos desde variables/`db.py`. Expone endpoints JSON.
- DB (MySQL/MariaDB): la app consulta con PyMySQL; para empezar localmente se importa `tienda.sql` en una instancia MariaDB/MySQL.
- Frontend: HTML/JS consume la API en `http://127.0.0.1:8000`. El build copia estáticos y genera `dist/`.
- Playwright: las pruebas usan `@playwright/test` y se descargan los navegadores en CI con `npx playwright install --with-deps`.
- CI: el workflow hace checkout, instala deps Python y Node, arranca el backend, construye el frontend, instala navegadores Playwright y ejecuta las pruebas.

## Uso — instrucciones para desarrolladores (local)

Requisitos previos: Python 3.12, Node 18, MariaDB/MySQL (o Docker con un contenedor MariaDB).

1) Clonar repo y crear entorno Python

```bash
git clone <repo-url>
cd tienda-api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Preparar la base de datos

- Si usas MariaDB local: crea una base y ejecuta `tienda.sql`:

```bash
mysql -u root -p < tienda.sql
```

- Si usas Docker (ejemplo rápido):

```bash
docker run -d --name mariadb -e MYSQL_ROOT_PASSWORD=secret -p 3306:3306 mariadb:10.6
sleep 8
docker exec -i mariadb mysql -uroot -psecret < tienda.sql
```

3) Ejecutar el backend

```bash
uvicorn app.backend.main:app --host 127.0.0.1 --port 8000 --reload
# o: python -m uvicorn app.backend.main:app --reload
```

4) Construir el frontend

```bash
cd app/frontend
npm ci
npm run build
# el script build.js generará /dist en la raíz (según la configuración del proyecto)
```

5) Abrir la app

Abre en el navegador: http://127.0.0.1:8000/ (el frontend sirve los archivos estáticos y la API está en `/` rutas JSON).

6) Ejecutar pruebas E2E localmente (opcional)

```bash
cd app/frontend
npm ci
npx playwright install
npm run test:playwright
```

Si las pruebas no se detectan, asegúrate de que `tests/playwright/` existe en la raíz y que `playwright.config.js` apunta a él.

## Pruebas y CI

- Las pruebas E2E están en `tests/playwright/` y usan Playwright. En CI se ejecutan mediante GitHub Actions.
- Para depurar detección de tests añadí un workflow temporal que lista los tests detectados (`npx --prefix app/frontend playwright test --list`) y muestra el layout del repo en el runner.
- También hay un `scripts/smoke_test.py` para comprobaciones rápidas del backend sin navegador.

## Consideraciones, problemas conocidos y recomendaciones

- Si Playwright devuelve "No tests found": suele ser un problema de `cwd` o `testDir` en `playwright.config.js`. Verifica que el `testDir` sea `./tests/playwright` desde el directorio donde se invoca, o usa `npx --prefix app/frontend playwright test tests/playwright` para pasar la ruta explícita.
- Descargas de navegadores Playwright consumen espacio/tiempo; en máquinas locales con pocos recursos usa CI para ejecutar E2E.
- En CI conviene mover credenciales DB a Secrets y reducir paralelismo de test workers si el runner tiene poco memoria.

## Pasos siguientes sugeridos (mejoras)

1. Mover credenciales y configuraciones sensibles a GitHub Secrets.
2. Añadir contenedores de pruebas (MariaDB) en workflows para mayor aislamiento (si aún no están configurados).
3. Añadir cobertura mínima de tests unitarios del backend.
4. Mejorar documentación de endpoints (OpenAPI está disponible via FastAPI en `/docs`).

---

Si quieres, redacto una versión más corta para entregar al profesor (resumen ejecutivo) o adapto `README.md` con estas instrucciones para que sea el documento principal del proyecto.
