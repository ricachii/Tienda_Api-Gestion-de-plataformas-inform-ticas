import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Union, List

import yaml

# Archivo base (puede sobreescribirse vía IMG_CATALOG_PATH)
DEFAULT_CATALOG_PATH = Path(__file__).with_name("image_catalog.yaml")
ENV_CATALOG_PATH = "IMG_CATALOG_PATH"
ENV_BASE_URL = "IMG_BASE_URL"


def _catalog_file() -> Path:
    """Determina la ruta del catálogo de imágenes."""
    env_path = os.getenv(ENV_CATALOG_PATH)
    if env_path:
        return Path(env_path)
    return DEFAULT_CATALOG_PATH


def _normalize_srcset(item_meta: Dict[str, Any], base_url: Optional[str]) -> Optional[str]:
    """
    Convierte distintos formatos de `srcset` (texto, lista de textos o lista de dicts)
    en la cadena final que consume el frontend.
    """
    srcset = item_meta.get("srcset")
    if not srcset:
        return None
    entries: List[str] = []

    def build_entry(entry: Union[str, Dict[str, Any]]) -> Optional[str]:
        if isinstance(entry, str):
            return entry.strip()
        if isinstance(entry, dict):
            url = entry.get("url")
            if not url:
                rel = entry.get("path")
                if rel and base_url:
                    url = _join_url(base_url, rel)
            if not url:
                return None
            descriptor = entry.get("descriptor", "").strip()
            return f"{url} {descriptor}".strip()
        return None

    if isinstance(srcset, list):
        for entry in srcset:
            built = build_entry(entry)
            if built:
                entries.append(built)
    else:
        built = build_entry(srcset)
        if built:
            entries.append(built)
    return ", ".join(entries) if entries else None


def _join_url(base: str, path: str) -> str:
    """Concatena base + path evitando dobles barras innecesarias."""
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


@lru_cache(maxsize=1)
def _load_catalog() -> Dict[str, Dict[str, Any]]:
    """
    Lee el catálogo YAML una sola vez y lo guarda en caché.
    Soporta dos secciones:
      default: { base_url: "https://cdn..." }
      items:
        slug:
          url: opcional (si viene completo se usa tal cual)
          path: opcional (se concatena con base_url)
          srcset: string | lista[string|dict]
          width/height: enteros
          base_url: override individual
    """
    path = _catalog_file()
    if not path.exists():
        return {}
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}

    default_base = os.getenv(ENV_BASE_URL) or (raw.get("default") or {}).get("base_url")
    items = raw.get("items") or {}
    normalized: Dict[str, Dict[str, Any]] = {}
    for key, meta in items.items():
        if not isinstance(meta, dict):
            continue
        item_base = meta.get("base_url") or default_base
        normalized[key] = {
            "url": meta.get("url"),
            "path": meta.get("path"),
            "base_url": item_base,
            "srcset": meta.get("srcset"),
            "width": meta.get("width"),
            "height": meta.get("height"),
        }
    return normalized


def resolve_product_image(image_key: Optional[str]) -> Dict[str, Any]:
    """
    Devuelve un diccionario con los campos `imagen_*` listos para responder al frontend.
    Si no existe mapeo para la clave, retorna {}.
    """
    if not image_key:
        return {}
    catalog = _load_catalog()
    meta = catalog.get(image_key)
    if not meta:
        return {}

    url = meta.get("url")
    base_url = meta.get("base_url")
    if not url:
        rel = meta.get("path")
        if rel and base_url:
            url = _join_url(base_url, rel)

    payload: Dict[str, Any] = {}
    if url:
        payload["imagen_url"] = url

    srcset = _normalize_srcset(meta, base_url)
    if srcset:
        payload["imagen_srcset"] = srcset

    width = meta.get("width")
    height = meta.get("height")
    if isinstance(width, int):
        payload["imagen_width"] = width
    if isinstance(height, int):
        payload["imagen_height"] = height
    return payload


def refresh_image_catalog() -> None:
    """Permite limpiar la caché para recargar el YAML sin reiniciar FastAPI."""
    _load_catalog.cache_clear()
