from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from swagger_ui_bundle import swagger_ui_path  # assets locales
from .routes import router as api

# ============================
#  Configuración principal
# ============================
app = FastAPI(title="Tienda API", version="0.1.0")

# Middleware CORS (permite acceso externo)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================
#  Rutas principales (API real)
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
#  Redoc opcional (versión alternativa)
# ============================
@app.get("/redoc", include_in_schema=False)
def redoc_ui():
    return get_redoc_html(
        openapi_url="/openapi.json",
        title="Tienda API – ReDoc",
        redoc_js_url="https://unpkg.com/redoc/bundles/redoc.standalone.js",
    )

# ============================
#  Página de inicio opcional
# ============================
@app.get("/", include_in_schema=False)
def home():
    return {
        "mensaje": "👋 Bienvenido a Tienda API",
        "documentacion_swagger": "/docs",
        "documentacion_redoc": "/redoc",
    }
