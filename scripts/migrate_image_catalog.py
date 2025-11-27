#!/usr/bin/env python3
"""
Automatiza la migración al nuevo modelo de imágenes basado en `imagen_ref`.

- Asegura que la columna exista en productos (ALTER TABLE solo si falta).
- Genera slugs a partir del nombre/url cuando la columna esté vacía.
- Actualiza la base (excepto en modo --dry-run).
- Escribe/actualiza el catálogo YAML consumido por app.backend.image_store.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

import yaml
from pymysql.err import OperationalError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backend.db import get_conn, schema_has  # noqa:E402
from app.backend.image_store import DEFAULT_CATALOG_PATH  # noqa:E402


def slugify(value: str) -> str:
    """Normaliza texto -> slug ascii."""
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-z0-9]+", "-", value.lower())
    return value.strip("-")


def ensure_imagen_ref_column() -> bool:
    """Crea la columna imagen_ref si no existe."""
    if schema_has("productos", "imagen_ref"):
        return False
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute("ALTER TABLE productos ADD COLUMN imagen_ref VARCHAR(120) NULL AFTER categoria")
            except OperationalError as exc:
                conn.rollback()
                if getattr(exc, "args", [None])[0] == 1142:
                    raise RuntimeError(
                        "El usuario de base de datos no tiene privilegios ALTER para crear la columna imagen_ref. "
                        "Ejecuta este script con un usuario con permisos administrativos (ej. root) o aplica el ALTER manualmente."
                    ) from exc
                raise
        conn.commit()
        return True
    finally:
        conn.close()


def fetch_products(optional_cols: List[str]) -> List[Dict[str, Any]]:
    """Obtiene productos con columnas disponibles."""
    cols = ["id", "nombre", "imagen_ref"]
    cols.extend(optional_cols)
    sql = f"SELECT {','.join(cols)} FROM productos ORDER BY id"
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            for row in rows:
                row["_original_ref"] = row.get("imagen_ref")
        return rows
    finally:
        conn.close()


def _slug_candidates(row: Dict[str, Any]) -> List[str]:
    url = row.get("imagen_url") or ""
    candidates: List[str] = []
    if url:
        parsed = urlparse(url)
        path = Path(parsed.path or "")
        if path.stem:
            candidates.append(path.stem)
        path_parts = [p for p in path.parts if p not in ("/", "")]
        if path_parts:
            candidates.append("-".join(path_parts))
    candidates.append(row.get("nombre") or "")
    candidates.append(f"producto-{row['id']}")
    return candidates


def assign_missing_refs(rows: List[Dict[str, Any]]) -> int:
    """Genera claves para filas sin imagen_ref."""
    used = {row["imagen_ref"] for row in rows if row.get("imagen_ref")}
    created = 0
    for row in rows:
        if row.get("imagen_ref"):
            continue
        for cand in _slug_candidates(row):
            slug = slugify(cand)
            if not slug:
                continue
            final = slug
            if final in used:
                final = f"{slug}-{row['id']}"
            row["imagen_ref"] = final
            used.add(final)
            created += 1
            break
        else:
            final = f"producto-{row['id']}"
            if final in used:
                final = f"{final}-{row['id']}"
            row["imagen_ref"] = final
            used.add(final)
            created += 1
    return created


def persist_refs(rows: List[Dict[str, Any]], dry_run: bool) -> int:
    """Actualiza la tabla con las refs recién generadas."""
    updates: List[Tuple[str, int]] = []
    for row in rows:
        orig = row.get("_original_ref")
        new_ref = row.get("imagen_ref")
        if new_ref and not orig:
            updates.append((new_ref, row["id"]))
    if not updates or dry_run:
        return len(updates)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.executemany("UPDATE productos SET imagen_ref=%s WHERE id=%s", updates)
        conn.commit()
        return len(updates)
    finally:
        conn.close()


def build_catalog(rows: List[Dict[str, Any]], default_base: str) -> Dict[str, Any]:
    """Consolida catálogo en memoria."""
    default_base = (default_base or "https://cdn.tienda.udec/img/").rstrip("/") + "/"
    items: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        key = row.get("imagen_ref")
        if not key:
            continue
        entry: Dict[str, Any] = {}
        url = row.get("imagen_url")
        if url:
            normalized_base = default_base.rstrip("/")
            if normalized_base and url.startswith(normalized_base + "/"):
                entry["path"] = url[len(normalized_base) + 1 :]
            else:
                entry["url"] = url
        srcset = row.get("imagen_srcset")
        if srcset:
            entry["srcset"] = srcset
        width = row.get("imagen_width")
        height = row.get("imagen_height")
        if isinstance(width, int):
            entry["width"] = width
        if isinstance(height, int):
            entry["height"] = height
        if "url" not in entry and "path" not in entry:
            entry["path"] = f"{key}.jpg"
        items[key] = entry
    return {"default": {"base_url": default_base}, "items": items}


def write_catalog(catalog: Dict[str, Any], path: Path, dry_run: bool) -> None:
    """Persistir catálogo (o imprimir en dry-run)."""
    if dry_run:
        yaml.safe_dump(catalog, sys.stdout, sort_keys=False)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrar y catalogar imágenes de productos.")
    parser.add_argument("--dry-run", action="store_true", help="No escribe en DB ni en el catálogo; muestra salida.")
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG_PATH), help="Ruta destino del YAML (default: app/backend/image_catalog.yaml).")
    parser.add_argument("--base-url", default=os.getenv("IMG_BASE_URL", "https://cdn.tienda.udec/img/"), help="URL base para paths relativos.")
    args = parser.parse_args()

    try:
        created_col = ensure_imagen_ref_column()
    except RuntimeError as err:
        print(f"ERROR: {err}")
        sys.exit(1)
    optional_cols = []
    for col in ("imagen_url", "imagen_srcset", "imagen_width", "imagen_height"):
        if schema_has("productos", col):
            optional_cols.append(col)
    rows = fetch_products(optional_cols)
    if not rows:
        print("No hay productos para procesar.")
        return

    created_refs = assign_missing_refs(rows)
    updated = persist_refs(rows, args.dry_run)
    catalog = build_catalog(rows, args.base_url)
    write_catalog(catalog, Path(args.catalog), args.dry_run)

    print("--- Resumen ---")
    if created_col:
        print("Columna imagen_ref creada.")
    print(f"Refs generadas: {created_refs}")
    print(f"Filas actualizadas en DB: {updated if not args.dry_run else 0} (dry-run muestra {updated})")
    print(f"Catálogo escrito en: {args.catalog}" + (" (dry-run)" if args.dry_run else ""))


if __name__ == "__main__":
    main()
