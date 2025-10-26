from fastapi import APIRouter, HTTPException
from .db import get_conn
from .models import CompraIn

router = APIRouter()

@router.get("/health")
def health():
    return {"status": "ok"}

@router.get("/productos")
def listar_productos(page: int = 1, size: int = 10, q: str | None = None):
    off = (page - 1) * size
    sql = "SELECT id,nombre,precio,stock FROM productos"
    args = []
    if q:
        sql += " WHERE nombre LIKE %s"
        args.append(f"%{q}%")
    sql += " ORDER BY id LIMIT %s OFFSET %s"
    args.extend([size, off])
    con = get_conn()
    with con.cursor() as c:
        c.execute(sql, args)
        data = c.fetchall()
    return {"page": page, "size": size, "items": data}

@router.get("/productos/{pid}")
def detalle_producto(pid: int):
    con = get_conn()
    with con.cursor() as c:
        c.execute("SELECT id,nombre,precio,stock FROM productos WHERE id=%s", (pid,))
        row = c.fetchone()
        if not row:
            raise HTTPException(404, "Producto no encontrado")
    return row

@router.post("/compras", status_code=201)
def crear_compra(body: CompraIn):
    con = get_conn()
    with con.cursor() as c:
        c.execute("SELECT stock FROM productos WHERE id=%s", (body.producto_id,))
        prod = c.fetchone()
        if not prod:
            raise HTTPException(404, "Producto no existe")
        if prod["stock"] < body.cantidad:
            raise HTTPException(400, "Stock insuficiente")
        c.execute("INSERT INTO compras(producto_id,cantidad) VALUES(%s,%s)",
                  (body.producto_id, body.cantidad))
        c.execute("UPDATE productos SET stock = stock - %s WHERE id=%s",
                  (body.cantidad, body.producto_id))
    return {"status": "OK"}
