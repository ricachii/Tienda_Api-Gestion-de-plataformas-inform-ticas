# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse
from pathlib import Path

app = FastAPI(title="NutriSupps API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rutas de negocio (MySQL)
from .routes import router as api_router
app.include_router(api_router)

# ==== Frontend estático (ruta relativa a este archivo) ====
PKG_DIR = Path(__file__).resolve().parent          # .../app
FRONTEND_DIR = None
for name in ("frontend", "fronted"):
    cand = PKG_DIR / name                          # .../app/frontend
    if cand.is_dir():
        FRONTEND_DIR = cand
        break

if FRONTEND_DIR:
    app.mount("/app", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

    @app.get("/", include_in_schema=False)
    async def root_redirect():
        return RedirectResponse(url="/app/")
else:
    @app.get("/", include_in_schema=False)
    async def root_message():
        return JSONResponse({
            "message": "API OK, pero no encuentro el frontend.",
            "busque_en": str(PKG_DIR / "frontend"),
            "tip": "Crea app/frontend/index.html y abre /app/",
            "docs": "/docs"
        })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)