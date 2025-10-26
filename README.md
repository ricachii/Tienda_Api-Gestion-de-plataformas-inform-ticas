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
