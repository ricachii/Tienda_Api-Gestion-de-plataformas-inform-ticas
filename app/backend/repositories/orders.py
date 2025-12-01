from decimal import Decimal
import math
from typing import Any, Dict, List, Optional

from ..db import get_conn
from ..utils import quantize_money


def _order_totals(items: List[Dict[str, Any]]) -> Dict[str, int]:
    total_items = len(items)
    total_unidades = sum(int(i["cantidad"]) for i in items)
    return {"total_items": total_items, "total_unidades": total_unidades}


def load_order_snapshot(conn, order_id: int) -> Dict[str, Any]:
    """Devuelve una orden con sus items; no cierra la conexión."""
    with conn.cursor() as c:
        c.execute(
            "SELECT id, customer_name, customer_email, total, status, created_at "
            "FROM orders WHERE id=%s",
            (order_id,),
        )
        order = c.fetchone()
        if not order:
            return {}
        c.execute(
            "SELECT id, order_id, producto_id, cantidad, precio_unit FROM order_items WHERE order_id=%s",
            (order_id,),
        )
        items = c.fetchall()
    totals = _order_totals(items)
    total = order["total"]
    if not isinstance(total, Decimal):
        total = Decimal(str(total))
    order_payload = {
        "order_id": order["id"],
        "order_status": order["status"],
        "total": quantize_money(total),
        "total_items": totals["total_items"],
        "total_unidades": totals["total_unidades"],
        "compras": [
            {
                "compra_id": None,
                "order_item_id": it["id"],
                "producto_id": it["producto_id"],
                "cantidad": it["cantidad"],
            }
            for it in items
        ],
        "detalle": "Orden recuperada por idempotency key",
        "status": "ok",
    }
    return order_payload


def get_order(order_id: int) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        payload = load_order_snapshot(conn, order_id)
        return payload or None
    finally:
        conn.close()


def get_order_detail(order_id: int) -> Optional[Dict[str, Any]]:
    """Detalle completo de la orden con items y totales derivados."""
    conn = get_conn()
    try:
        with conn.cursor() as c:
            c.execute(
                "SELECT id, customer_name, customer_email, total, status, created_at FROM orders WHERE id=%s",
                (order_id,),
            )
            order = c.fetchone()
            if not order:
                return None
            c.execute(
                "SELECT id, order_id, producto_id, cantidad, precio_unit FROM order_items WHERE order_id=%s",
                (order_id,),
            )
            items = c.fetchall()
        totals = _order_totals(items)
        total_val = order["total"]
        if not isinstance(total_val, Decimal):
            total_val = Decimal(str(total_val))
        normalized_items: List[Dict[str, Any]] = []
        for it in items:
            price = it["precio_unit"]
            if not isinstance(price, Decimal):
                price = Decimal(str(price))
            normalized_items.append(
                {
                    "id": it["id"],
                    "order_id": it["order_id"],
                    "producto_id": it["producto_id"],
                    "cantidad": it["cantidad"],
                    "precio_unit": quantize_money(price),
                }
            )
        return {
            "id": order["id"],
            "customer_name": order["customer_name"],
            "customer_email": order["customer_email"],
            "total": quantize_money(total_val),
            "status": order["status"],
            "created_at": order["created_at"],
            "items": normalized_items,
            "total_items": totals["total_items"],
            "total_unidades": totals["total_unidades"],
        }
    finally:
        conn.close()


def list_orders(page: int, size: int, status: Optional[str], email: Optional[str]) -> Dict[str, Any]:
    offset = (page - 1) * size
    conn = get_conn()
    try:
        where = []
        args: List[Any] = []
        if status:
            where.append("o.status=%s")
            args.append(status)
        if email:
            where.append("LOWER(o.customer_email)=LOWER(%s)")
            args.append(email)
        where_sql = (" WHERE " + " AND ".join(where)) if where else ""

        with conn.cursor() as c:
            c.execute(f"SELECT COUNT(*) AS total FROM orders o{where_sql}", args)
            total = c.fetchone()["total"]
            c.execute(
                f"""
                SELECT o.id, o.customer_name, o.customer_email, o.total, o.status, o.created_at,
                       COUNT(oi.id) AS items, COALESCE(SUM(oi.cantidad),0) AS unidades
                FROM orders o
                LEFT JOIN order_items oi ON oi.order_id=o.id
                {where_sql}
                GROUP BY o.id
                ORDER BY o.created_at DESC, o.id DESC
                LIMIT %s OFFSET %s
                """,
                args + [size, offset],
            )
            rows = c.fetchall()
        orders: List[Dict[str, Any]] = []
        for r in rows:
            total_val = r["total"]
            if not isinstance(total_val, Decimal):
                total_val = Decimal(str(total_val))
            orders.append(
                {
                    "id": r["id"],
                    "customer_name": r["customer_name"],
                    "customer_email": r["customer_email"],
                    "total": quantize_money(total_val),
                    "status": r["status"],
                    "created_at": r["created_at"],
                    "items": int(r["items"]),
                    "unidades": int(r["unidades"]),
                }
            )
        total_pages = math.ceil(total / size) if size else 1
        return {"total_items": total, "total_pages": total_pages, "page": page, "size": size, "items": orders}
    finally:
        conn.close()
