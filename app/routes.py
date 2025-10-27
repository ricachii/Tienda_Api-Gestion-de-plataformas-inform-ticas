from fastapi import APIRouter, HTTPException, Query
from .db import get_conn
from .models import CompraRequest  # ajusta si tu clase tiene otro nombre

router = APIRouter()

@router.get("/health")
def health():
    return {"status": "ok"}

# -----------------------------
#  Categorías (lista simple)
# -----------------------------
@router.get("/categorias")
def categorias():
    conn = get_conn()
    try:
        with conn.cursor() as c:
            c.execute("""
                SELECT DISTINCT categoria
                FROM productos
                WHERE categoria IS NOT NULL AND categoria <> ''
                ORDER BY categoria
            """)
            rows = c.fetchall()
            # Devolver lista simple de strings
            return [r["categoria"] for r in rows]
    finally:
        conn.close()

# -----------------------------
#  Listar productos con filtros
# -----------------------------
@router.get("/productos")
def listar_productos(
    page: int = Query(1, ge=1),
    size: int = Query(12, ge=1, le=500),
    q: str | None = Query(None, description="Búsqueda en nombre/descr."),
    cat: str | None = Query(None, description="Categoría exacta"),
):
    off = (page - 1) * size

    sql = """
        SELECT id, nombre, precio, stock, categoria, imagen_url, descripcion
        FROM productos
    """
    args = []
    where = []

    if q:
        where.append("(nombre LIKE %s OR descripcion LIKE %s)")
        args.extend([f"%{q}%", f"%{q}%"])

    if cat:
        where.append("categoria = %s")
        args.append(cat)

    if where:
        sql += " WHERE " + " AND ".join(where)

    sql += " ORDER BY id LIMIT %s OFFSET %s"
    args.extend([size, off])

    conn = get_conn()
    try:
        with conn.cursor() as c:
            c.execute(sql, args)
            items = c.fetchall()
        return {"page": page, "size": size, "items": items}
    finally:
        conn.close()

# -----------------------------
#  Crear compra (descuenta stock)
# -----------------------------
@router.post("/compras", status_code=201)
def crear_compra(body: CompraRequest):
    conn = get_conn()
    try:
        with conn.cursor() as c:
            # Verificar producto y stock
            c.execute("SELECT stock FROM productos WHERE id=%s", (body.producto_id,))
            prod = c.fetchone()
            if not prod:
                raise HTTPException(status_code=404, detail="Producto no existe")
            if prod["stock"] < body.cantidad:
                raise HTTPException(status_code=400, detail="Stock insuficiente")

            # Registrar compra y descontar stock
            c.execute(
                "INSERT INTO compras(producto_id, cantidad) VALUES(%s, %s)",
                (body.producto_id, body.cantidad),
            )
            c.execute(
                "UPDATE productos SET stock = stock - %s WHERE id = %s",
                (body.cantidad, body.producto_id),
            )

        return {"status": "OK"}
    finally:
        conn.close()
