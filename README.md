# 🧩 Tienda API – Proyecto de Gestión de Plataformas Informáticas

### 📦 Requisitos
- Python 3.12 o superior
- MySQL/MariaDB (con base de datos `tienda`)
- Red Host-Only entre VM1 y VM2

### ⚙️ Instalación
```bash
git clone https://github.com/ricachii/Tienda_Api-Gestion-de-plataformas-inform-ticas.git
cd Tienda_Api-Gestion-de-plataformas-inform-ticas
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

🔐 Configurar conexión

Copia el archivo de ejemplo:

cp app/.env.example app/.env

Luego abre app/.env y agrega tu contraseña real.

🚀 Ejecutar la API
uvicorn app.main:app --host 0.0.0.0 --port 8000


Accede a:

Swagger: http://127.0.0.1:8000/docs

ReDoc: http://127.0.0.1:8000/redoc


Cómo restaurar la base de datos tienda.sql

Este documento explica cómo importar la base de datos del proyecto Tienda API en tu propio entorno local, para que la API funcione correctamente con la misma información que el equipo original.

🧩 1️⃣ ¿Qué es tienda.sql?

El archivo tienda.sql es un respaldo completo (dump) de la base de datos tienda que está en la Máquina Virtual 2 (VM2) del proyecto original.
Contiene toda la estructura y los datos de las tablas necesarias para ejecutar la API.

⚙️ 2️⃣ Requisitos

Antes de comenzar, asegúrate de tener instalado:

MySQL o MariaDB

Acceso a la terminal o consola de comandos

El archivo tienda.sql (ya viene incluido en el repositorio)

Puedes comprobar si tienes MySQL instalado con:

mysql --version

🧱 3️⃣ Crear la base de datos local

Abre tu terminal, ingresa al cliente MySQL y crea la base de datos vacía:

mysql -u root -p -e "CREATE DATABASE tienda;"


Cuando lo pida, escribe tu contraseña de MySQL (la que usas en tu computador).

📥 4️⃣ Importar el respaldo tienda.sql

Desde la carpeta del proyecto (donde está el archivo tienda.sql):

mysql -u root -p tienda < tienda.sql


✅ Esto creará automáticamente todas las tablas y cargará los datos originales (productos, compras, etc.).

🔍 5️⃣ Verificar que la base de datos se importó correctamente

Conéctate a MySQL y ejecuta una consulta de prueba:

mysql -u root -p -e "SELECT COUNT(*) FROM tienda.productos;"


Si ves un número (por ejemplo, 5), significa que todo se restauró correctamente.

🔐 6️⃣ Configurar las credenciales en el archivo .env

Abre el archivo app/.env dentro del proyecto y edítalo con tus credenciales locales:

DB_HOST=127.0.0.1
DB_USER=root
DB_PASS=tu_contraseña_mysql
DB_NAME=tienda


Guarda los cambios.

🚀 7️⃣ Iniciar la API

Activa tu entorno virtual e inicia el servidor FastAPI:

cd tienda-api
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000


Abre tu navegador y entra en:

Swagger: http://127.0.0.1:8000/docs

ReDoc: http://127.0.0.1:8000/redoc

✅ 8️⃣ Confirmar funcionamiento

Prueba los endpoints:

curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/productos


Si ves los productos y el estado “ok”, todo está conectado correctamente 🎉

📘 Resumen final
Paso	Acción	Resultado esperado
1	Crear base de datos	Base de datos vacía “tienda” creada
2	Importar tienda.sql	Tablas y datos restaurados
3	Configurar .env	Conexión a MySQL local
4	Ejecutar API	Endpoints disponibles en /docs

## Instalación rápida (desarrolladores)

Para trabajar localmente con el frontend y backend de forma reproducible sigue estos pasos:

1. Crear y activar el entorno Python:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Instalar dependencias Node.js reproducibles y construir el frontend:

```bash
cd tienda-api
# usa el lockfile para instalaciones reproducibles
npm ci
npm run build
```

3. Ejecutar la API (desde la raíz del repo):

```bash
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Notas y buenas prácticas:
- No comitees `node_modules/`, `dist/`, `.venv/`, `.uvicorn.log` ni tu carpeta `.vscode/` (están en `.gitignore`).
- Si necesitas reproducir pruebas E2E, instala navegadores de Playwright:
	`npx playwright install --with-deps`

Si quieres que haga una limpieza automática del índice Git para dejar de trackear artefactos generados, dímelo y lo aplico (no borra archivos locales).
