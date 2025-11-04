import logging
import os
import time
import uuid
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.exceptions import RequestValidationError

from .routes import router as api
from .metrics import record_latency, latency_snapshot  # métricas sin circularidad
from .db import ensure_schema  # startup: garantizar esquema
from .db import JWT_SECRET

logger = logging.getLogger("tienda-api")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

app = FastAPI(
    title="Tienda API",
    version="1.1.1",
    description="Backend FastAPI (VM1) para Tienda API",
)

# CORS (ajusta origins en producción)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # en prod: lista blanca
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montar frontend estático si existe
FRONTEND_DIR = Path(__file__).parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/app", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

@app.get("/", include_in_schema=False)
def root_redirect():
    return RedirectResponse(url="/app" if FRONTEND_DIR.exists() else "/docs")

# Startup: garantizar que exista la tabla usuarios
@app.on_event("startup")
def _startup_schema_check():
    # Seguridad: evitar arranque en producción con JWT secreto por defecto
    env = os.getenv("ENV", "dev")
    if env != "dev" and (not JWT_SECRET or JWT_SECRET == "dev-secret-change"):
        logger.error("JWT_SECRET no está configurado correctamente en entorno no-dev. Abortando inicio.")
        raise RuntimeError("JWT_SECRET no configurado")
    try:
        ensure_schema()
        logger.info("Schema OK: tabla 'usuarios' verificada/creada.")
    except Exception as e:
        # No detenemos la app: se puede levantar la DB después.
        logger.warning(f"No se pudo verificar/crear schema en startup: {e}")

# Manejo de errores de validación
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "message": "Error de validación en la solicitud. Revisa campos, tipos y valores.",
        },
    )

# Middleware de acceso con latencia
@app.middleware("http")
async def access_logger(request: Request, call_next: Callable):
    start = time.time()
    req_id = str(uuid.uuid4())[:8]
    path = request.url.path
    method = request.method
    client_ip = request.client.host if request.client else "-"
    try:
        response = await call_next(request)
        return response
    finally:
        dur_ms = (time.time() - start) * 1000.0
        record_latency(f"{method} {path}", dur_ms)
        logger.info(f"{client_ip} {method} {path} -> {dur_ms:.1f} ms (id={req_id})")

# Endpoint auxiliar para depuración de latencias (opcional)
@app.get("/_latency", include_in_schema=False)
def _latency_snapshot():
    return latency_snapshot()

# Incluir API principal
app.include_router(api)
