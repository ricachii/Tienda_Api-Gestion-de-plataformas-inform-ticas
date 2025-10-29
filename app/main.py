import logging
import time
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from swagger_ui_bundle import swagger_ui_path
from .routes import router as api

# ============================
#  Logging básico (VM1)
# ============================
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("tienda-api")

# ============================
#  App
# ============================
app = FastAPI(title="Tienda API", version="0.3.1")

# ============================
#  Middleware CORS
# ============================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # opcional: restringir a dominios conocidos
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================
#  Handler 422 - Validación Pydantic
# ============================
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Log detallado para diagnóstico
    logger.warning(
        "422 Validation Error on %s %s | errors=%s | body=%s",
        request.method,
        request.url.path,
        exc.errors(),
        exc.body if hasattr(exc, "body") else None,
    )
    # Respuesta estándar pero clara para el cliente
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "message": "Error de validación en la solicitud. Revisa nombres de campos, tipos y valores.",
        },
    )

# ============================
#  Middleware de auditoría
# ============================
@app.middleware("http")
async def access_logger(request: Request, call_next):
    start = time.time()
    client = request.client.host if request.client else "-"
    method = request.method
    path = request.url.path

    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        dur_ms = int((time.time() - start) * 1000)
        logger.info(f"{client} {method} {path} -> {status_code} ({dur_ms} ms)")

# ============================
#  Rutas principales (API)
# ============================
app.include_router(api)

# ============================
#  Swagger local (sin Internet)
# ============================
app.mount("/swagger", StaticFiles(directory=swagger_ui_path), name="swagger")

@app.get("/docs", include_in_schema=False)
def custom_swagger_ui():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Tienda API – Documentación",
        swagger_js_url="/swagger/swagger-ui-bundle.js",
        swagger_css_url="/swagger/swagger-ui.css",
    )

# ============================
#  ReDoc opcional
# ============================
@app.get("/redoc", include_in_schema=False)
def redoc_ui():
    # Si en VM1 no hay Internet, puedes comentar esta ruta
    return get_redoc_html(
        openapi_url="/openapi.json",
        title="Tienda API – ReDoc",
        redoc_js_url="https://unpkg.com/redoc/bundles/redoc.standalone.js",
    )

# ============================
#  Frontend estático
# ============================
FRONTEND_DIR = Path(__file__).parent / "frontend"
app.mount("/app", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

# ============================
#  Página de inicio
# ============================
@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse(url="/app")
