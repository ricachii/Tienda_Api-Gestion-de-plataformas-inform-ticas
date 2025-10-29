import math
from collections import defaultdict
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from .db import (
    get_conn,
    schema_has,
    DBError,
    DBOperationalError,
    DBIntegrityError,
    DBProgrammingError,
)
from .models import (
    CompraRequest,
    CompraResponse,
    Producto,
    ProductosResponse,
    CheckoutRequest,
    CheckoutResponse,
    CheckoutResultItem,
)

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


# -----------------------------
#  Categorías (lista simple)
# -----------------------------
@router.get("/categorias", response_model=List[str])
def categorias():
    conn = get_conn()
    try:
        with conn.cursor() as c:
            if not schema_has(conn, "productos", "categoria"):
                return []
            c.execute(
                """
                SELECT DISTINCT categoria
                FROM productos
                WHERE categoria IS NOT NULL AND categoria <> ''
                ORDER BY categoria
                """
            )
            rows = c.fetchall()
            return [r["categoria"] for r in rows]
    except (DBOperationalError, DBProgrammingError, DBIntegrityError, DBError):
        raise HTTPException(status_code=500, detail="Error de base de datos al listar categorías")
    finally:
        conn.close()


# -----------------------------
#  Listar productos con filtros
#  - Paginación real (total_items / total_pages)
# -----------------------------
@router.get("/productos", response_model=ProductosResponse)
def listar_productos(
    page: int = Query(1, ge=1),
    size: int = Query(12, ge=1, le=500),
    q: Optional[str] = Query(None, description="Búsqueda en nombre/descr."),
    cat: Optional[str] = Query(None, description="Categoría exacta"),
):
    off = (page - 1) * size
    conn = get_conn()
    try:
        has_categoria = schema_has(conn, "productos", "categoria")
        has_img = schema_has(conn, "productos", "imagen_url")
        has_desc = schema_has(conn, "productos", "descripcion")

        select_cols = [
            "id",
            "nombre",
            "precio",
            "stock",
            "categoria" if has_categoria else "NULL AS categoria",
            "imagen_url" if has_img else "NULL AS imagen_url",
            "descripcion" if has_desc else "NULL AS descripcion",
        ]

        where_parts = []
        args: list = []

        if q:
            if has_desc:
                where_parts.append("(nombre LIKE %s OR descripcion LIKE %s)")
                args.extend([f"%{q}%", f"%{q}%"])
            else:
                where_parts.append("(nombre LIKE %s)")
                args.append(f"%{q}%")

        if cat and has_categoria:
            where_parts.append("categoria = %s")
            args.append(cat)

        where_sql = " WHERE " + " AND ".join(where_parts) if where_parts else ""

        # Total para paginación
        with conn.cursor() as c:
            c.execute(f"SELECT COUNT(*) AS n FROM productos{where_sql}", args)
            total_items = c.fetchone()["n"]

        total_pages = math.ceil(total_items / size) if size > 0 else 0

        # Página fuera de rango => lista vacía pero conserva metadatos
        if page > 1 and off >= total_items:
            return ProductosResponse(
                page=page, size=size, total_items=total_items, total_pages=total_pages, items=[]
            )

        sql = f"SELECT {', '.join(select_cols)} FROM productos{where_sql} ORDER BY id LIMIT %s OFFSET %s"
        args_page = args + [size, off]

        with conn.cursor() as c:
            c.execute(sql, args_page)
            items = c.fetchall()

        prod_list = [
            Producto(
                id=it["id"],
                nombre=it["nombre"],
                precio=float(it["precio"]),
                stock=it["stock"],
                categoria=it.get("categoria"),
                imagen_url=it.get("imagen_url"),
                descripcion=it.get("descripcion"),
            )
            for it in items
        ]
        return ProductosResponse(
            page=page, size=size, total_items=total_items, total_pages=total_pages, items=prod_list
        )
    except (DBOperationalError, DBProgrammingError, DBIntegrityError, DBError):
        raise HTTPException(status_code=500, detail="Error de base de datos al listar productos")
    finally:
        conn.close()


# -----------------------------
#  Crear compra (descuenta stock)
#  - Validación atómica con SELECT ... FOR UPDATE
# -----------------------------
@router.post("/compras", response_model=CompraResponse, status_code=status.HTTP_201_CREATED)
def crear_compra(body: CompraRequest):
    conn = get_conn()
    try:
        with conn.cursor() as c:
            # Bloquea la fila del producto
            c.execute(
                "SELECT id, stock FROM productos WHERE id=%s FOR UPDATE",
                (body.producto_id,),
            )
            prod = c.fetchone()
            if not prod:
                conn.rollback()
                raise HTTPException(status_code=404, detail="Producto no existe")

            if prod["stock"] < body.cantidad:
                conn.rollback()
                raise HTTPException(status_code=400, detail="Stock insuficiente")

            # Inserta compra
            c.execute(
                "INSERT INTO compras(producto_id, cantidad) VALUES(%s, %s)",
                (body.producto_id, body.cantidad),
            )
            compra_id = c.lastrowid

            # Descuenta stock
            c.execute(
                "UPDATE productos SET stock = stock - %s WHERE id = %s",
                (body.cantidad, body.producto_id),
            )

        conn.commit()
        return CompraResponse(
            status="OK",
            compra_id=compra_id,
            producto_id=body.producto_id,
            cantidad=body.cantidad,
            detalle="Compra registrada y stock actualizado",
        )
    except HTTPException:
        raise
    except (DBIntegrityError, DBProgrammingError) as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail="Solicitud inválida (SQL)") from e
    except (DBOperationalError, DBError) as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Error interno de base de datos") from e
    finally:
        conn.close()


# -----------------------------
#  Checkout batch (múltiples productos)
#  - All-or-nothing: si uno falla, se cancela todo
#  - Valida duplicados agregando cantidades
#  - SELECT ... FOR UPDATE por cada producto
# -----------------------------
@router.post("/checkout", response_model=CheckoutResponse, status_code=status.HTTP_201_CREATED)
def checkout(body: CheckoutRequest):
    if not body.items:
        raise HTTPException(status_code=400, detail="Lista de items vacía")

    # Consolidar duplicados: sumamos cantidades por producto
    agregados = defaultdict(int)
    for it in body.items:
        agregados[it.producto_id] += it.cantidad

    conn = get_conn()
    try:
        compras_realizadas: List[CheckoutResultItem] = []

        with conn.cursor() as c:
            # 1) Bloquear y validar stock de todos los productos
            for pid, cant in agregados.items():
                c.execute("SELECT id, stock FROM productos WHERE id=%s FOR UPDATE", (pid,))
                row = c.fetchone()
                if not row:
                    conn.rollback()
                    raise HTTPException(status_code=404, detail=f"Producto {pid} no existe")
                if row["stock"] < cant:
                    conn.rollback()
                    raise HTTPException(
                        status_code=400,
                        detail=f"Stock insuficiente para producto {pid} (solicitado {cant}, disponible {row['stock']})",
                    )

            # 2) Insertar compras e impactar stock
            for pid, cant in agregados.items():
                c.execute(
                    "INSERT INTO compras(producto_id, cantidad) VALUES(%s, %s)",
                    (pid, cant),
                )
                compra_id = c.lastrowid
                compras_realizadas.append(
                    CheckoutResultItem(compra_id=compra_id, producto_id=pid, cantidad=cant)
                )

                c.execute(
                    "UPDATE productos SET stock = stock - %s WHERE id = %s",
                    (cant, pid),
                )

        conn.commit()
        total_unidades = sum(x.cantidad for x in compras_realizadas)
        return CheckoutResponse(
            status="OK",
            total_items=len(compras_realizadas),
            total_unidades=total_unidades,
            compras=compras_realizadas,
            detalle="Checkout completado; compras registradas y stock actualizado",
        )
    except HTTPException:
        raise
    except (DBIntegrityError, DBProgrammingError) as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail="Solicitud inválida (SQL)") from e
    except (DBOperationalError, DBError) as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Error interno de base de datos") from e
    finally:
        conn.close()
