from decimal import Decimal
import math
from typing import Any, Dict, List, Optional

from ..db import get_conn, schema_has
from ..image_store import resolve_product_image


def fetch_categories() -> List[str]:
    conn = get_conn()
    try:
        if not schema_has("productos", "categoria"):
            return []
        with conn.cursor() as c:
            c.execute(
                "SELECT DISTINCT categoria FROM productos "
                "WHERE categoria IS NOT NULL AND categoria<>'' ORDER BY categoria ASC"
            )
            rows = [r["categoria"] for r in c.fetchall()]
        conn.commit()
        return rows
    finally:
        conn.close()


def fetch_products(page: int, size: int, q: Optional[str], cat: Optional[str]) -> Dict[str, Any]:
    offset = (page - 1) * size
    conn = get_conn()
    try:
        where = []
        args: List[Any] = []

        has_descripcion = schema_has("productos", "descripcion")
        has_categoria = schema_has("productos", "categoria")
        has_imagen_ref = schema_has("productos", "imagen_ref")
        has_imagen_url = schema_has("productos", "imagen_url")
        has_created = schema_has("productos", "created_at")
        has_updated = schema_has("productos", "updated_at")

        if q:
            if has_descripcion:
                where.append("(LOWER(nombre) LIKE %s OR LOWER(descripcion) LIKE %s)")
                args.extend([f"%{q.lower()}%", f"%{q.lower()}%"])
            else:
                where.append("LOWER(nombre) LIKE %s")
                args.append(f"%{q.lower()}%")
        if cat and has_categoria:
            where.append("categoria=%s")
            args.append(cat)

        where_sql = (" WHERE " + " AND ".join(where)) if where else ""

        select_cols = ["id", "nombre", "precio", "stock"]
        if has_categoria:
            select_cols.append("categoria")
        if has_imagen_ref:
            select_cols.append("imagen_ref")
        if has_imagen_url:
            select_cols.append("imagen_url")
        if schema_has("productos", "imagen_srcset"):
            select_cols.append("imagen_srcset")
        if schema_has("productos", "imagen_width"):
            select_cols.append("imagen_width")
        if schema_has("productos", "imagen_height"):
            select_cols.append("imagen_height")
        if has_descripcion:
            select_cols.append("descripcion")
        if has_created:
            select_cols.append("created_at")
        if has_updated:
            select_cols.append("updated_at")

        cols_sql = ",".join(select_cols)

        with conn.cursor() as c:
            c.execute(f"SELECT COUNT(*) AS total FROM productos{where_sql}", args)
            total = c.fetchone()["total"]
            c.execute(
                f"SELECT {cols_sql} FROM productos{where_sql} ORDER BY id ASC LIMIT %s OFFSET %s",
                args + [size, offset],
            )
            items = c.fetchall()

        if has_imagen_ref:
            for item in items:
                meta = resolve_product_image(item.get("imagen_ref"))
                # Prevalece el valor de la DB si ya está presente
                for k, v in meta.items():
                    if item.get(k) is None:
                        item[k] = v

        # Coerce decimals to Decimal for consistency
        for item in items:
            if "precio" in item and not isinstance(item["precio"], Decimal):
                item["precio"] = Decimal(str(item["precio"]))

        total_pages = math.ceil(total / size) if size else 1
        return {"total_items": total, "total_pages": total_pages, "page": page, "size": size, "items": items}
    finally:
        conn.close()
