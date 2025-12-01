from __future__ import annotations

from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
MEDIA_URL = "/media"
MEDIA_DIR = BACKEND_DIR / "media"
PRODUCTS_DIR = MEDIA_DIR / "products"
ICONS_DIR = MEDIA_DIR / "icons"
PRODUCTS_URL = f"{MEDIA_URL}/products"
ICONS_URL = f"{MEDIA_URL}/icons"


def ensure_media_dirs() -> None:
    """Garantiza que existan las carpetas de medios locales."""
    for path in (MEDIA_DIR, PRODUCTS_DIR, ICONS_DIR):
        path.mkdir(parents=True, exist_ok=True)
