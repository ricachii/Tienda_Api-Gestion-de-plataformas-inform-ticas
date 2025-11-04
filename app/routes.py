import csv
import io
import math
import time
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any

import jwt  # PyJWT
from fastapi import APIRouter, HTTPException, Query, Depends, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

from .db import (
    get_conn,
    schema_has,
    DBError,
    DBOperationalError,
    DBIntegrityError,
    DBProgrammingError,
    JWT_SECRET,
    JWT_EXPIRE_MIN,
    create_user,
    get_user_by_email,
    get_user_by_id,
    ensure_schema,
    create_password_reset_token,
    consume_password_reset_token,
)
from .models import (
    CompraRequest,
    CompraResponse,
    Producto,
    ProductosResponse,
    CheckoutRequest,
    CheckoutResponse,
    CheckoutResultItem,
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    MeResponse,
    PasswordResetRequest,
    ResetPasswordRequest,
    FechaFiltro,
    VentasResumen,
    VentasSerie,
    SerieItem,
    StatsResponse,
)
from .metrics import APP_START_TIME, get_latency_percentiles, latency_store

router = APIRouter()
logger = logging.getLogger("tienda-api")


# Util: validación de rangos de fecha (from/to)
def validate_from_to(from_date: Optional[date], to_date: Optional[date]) -> None:
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=400, detail="from_date no puede ser mayor que to_date")
    if (to_date or from_date) and ((to_date or date.today()) - (from_date or date(1970,1,1))).days > 3660:
        raise HTTPException(status_code=400, detail="Rango de fechas demasiado amplio")

# JWT helpers
security = HTTPBearer(auto_error=False)

def create_jwt(uid: int, email: str, rol: str) -> str:
    now = int(time.time())
    exp = now + (JWT_EXPIRE_MIN * 60)
    payload = {"sub": str(uid), "email": email, "rol": rol, "iat": now, "exp": exp}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def decode_jwt(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

class RateLimiter:
    # Simple rate-limit por IP para /login: 5 intentos / 5 minutos
    def __init__(self, max_attempts=5, window_sec=300):
        self.max_attempts = max_attempts
        self.window = window_sec
        self.attempts: Dict[str, List[int]] = {}
    def hit(self, key: str):
        now = int(time.time())
        arr = self.attempts.setdefault(key, [])
        arr.append(now)
        self.attempts[key] = [t for t in arr if now - t <= self.window]
        if len(self.attempts[key]) > self.max_attempts:
            raise HTTPException(status_code=429, detail="Demasiados intentos, espera e inténtalo de nuevo")

login_rl = RateLimiter()

def get_current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Dict[str, Any]:
    if not creds:
        raise HTTPException(status_code=401, detail="Falta token")
    data = decode_jwt(creds.credentials)
    uid = int(data["sub"])
    user = get_user_by_id(uid)
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no existe")
    return {"id": user["id"], "email": user["email"], "nombre": user["nombre"], "rol": user["rol"]}

def require_admin(user=Depends(get_current_user)):
    if user["rol"] != "admin":
        raise HTTPException(status_code=403, detail="Requiere rol admin")
    return user

# AUTH: register/login/me
@router.post("/register", response_model=MeResponse, status_code=201, tags=["auth"])
def register(payload: RegisterRequest):
    # Si la tabla no existe (1146), créala y reintenta 1 vez.
    try:
        existing = get_user_by_email(payload.email)
    except DBProgrammingError as e:
        # e.args[0] suele ser 1146 para "table doesn't exist"
        if getattr(e, "args", [None])[0] == 1146:
            ensure_schema()
            existing = get_user_by_email(payload.email)
        else:
            logger.exception("Error de esquema de base de datos en /register")
            raise HTTPException(status_code=500, detail="Error de esquema de base de datos") from e

    if existing:
        raise HTTPException(status_code=409, detail="Email ya registrado")
    try:
        uid = create_user(payload.email, payload.nombre, payload.password, "user")
        user = get_user_by_id(uid)
        return {"id": user["id"], "email": user["email"], "nombre": user["nombre"], "rol": user["rol"]}
    except (DBIntegrityError, DBProgrammingError) as e:
        raise HTTPException(status_code=400, detail="Solicitud inválida (SQL)") from e
    except (DBOperationalError, DBError) as e:
        logger.exception("Error operativo de la base de datos en /register")
        raise HTTPException(status_code=500, detail="Error interno de base de datos") from e

@router.post("/login", response_model=TokenResponse, tags=["auth"])
def login(payload: LoginRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    login_rl.hit(client_ip)
    user = get_user_by_email(payload.email)
    if not user:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    # Si el usuario está marcado para reset forzado, bloquear login e indicar 403
    if user.get("password_reset_required"):
        raise HTTPException(status_code=403, detail="password_reset_required: debe restablecer su contraseña")
    from .db import verify_password
    if not verify_password(payload.password, user["password_hash"], user["salt"]):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    token = create_jwt(user["id"], user["email"], user["rol"])
    return {"access_token": token, "expires_in": JWT_EXPIRE_MIN * 60, "token_type": "bearer"}


@router.post("/request-password-reset", tags=["auth"])
def request_password_reset(payload: PasswordResetRequest):
    """Genera un token de reseteo y lo envía por email si SMTP está configurado.
    Para evitar enumeración de usuarios siempre respondemos 200.
    """
    try:
        user = get_user_by_email(payload.email)
    except Exception:
        user = None
    if not user:
        return {"ok": True}
    # crear token (se guarda hashed en BD)
    token = create_password_reset_token(user['id'])
    # intentar enviar por SMTP; si falla, devolver ok pero sin token (no exponer)
    sent = False
    try:
        from .db import send_reset_email
        sent = send_reset_email(user['email'], user.get('nombre', ''), token)
    except Exception:
        sent = False
    if sent:
        return {"ok": True}
    # fallback: si SMTP no configurado/dev, NO devolver token en la API
    # Escribir token en CSV en repo `docs/db/` para que un operador lo gestione manualmente.
    try:
        from .db import write_pending_token
        write_pending_token(user['email'], token)
    except Exception:
        # si falla la escritura fallback, no exponemos token
        pass
    return {"ok": True}


@router.post("/reset-password", tags=["auth"])
def reset_password(payload: ResetPasswordRequest):
    ok = consume_password_reset_token(payload.token, payload.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail="Token inválido o expirado")
    return {"ok": True, "msg": "Contraseña actualizada"}

@router.get("/me", response_model=MeResponse, tags=["auth"])
def me(user=Depends(get_current_user)):
    return user

# CATÁLOGO
@router.get("/categorias", response_model=List[str], tags=["catalogo"])
def categorias():
    conn = get_conn()
    try:
        # Si la columna 'categoria' no existe en el esquema, devolver lista vacía
        if not schema_has("productos", "categoria"):
            conn.close()
            return []
        with conn.cursor() as c:
            c.execute("SELECT DISTINCT categoria FROM productos WHERE categoria IS NOT NULL AND categoria<>'' ORDER BY categoria ASC")
            rows = [r["categoria"] for r in c.fetchall()]
        conn.commit()
        return rows
    finally:
        conn.close()


# Endpoint interno para chequeo de DB (no en docs)
@router.get("/internal/db-check", include_in_schema=False, tags=["internal"])
def _internal_db_check(request: Request, creds: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """Chequeo interno: verifica conexión a la DB y devuelve lista de tablas.
    Permite acceso desde loopback sin token; fuera de loopback requiere token de admin.
    """
    client_ip = request.client.host if request.client else "-"
    # If not loopback, require token and admin role
    if client_ip not in ("127.0.0.1", "::1", "localhost"):
        if not creds:
            raise HTTPException(status_code=401, detail="Falta token")
        data = decode_jwt(creds.credentials)
        uid = int(data.get("sub"))
        user = get_user_by_id(uid)
        if not user or user.get("rol") != "admin":
            raise HTTPException(status_code=403, detail="Requiere rol admin")

    conn = get_conn()
    try:
        with conn.cursor() as c:
            c.execute("SHOW TABLES")
            rows = c.fetchall()
        conn.commit()
        tables = [list(r.values())[0] for r in rows]
        return {"ok": True, "tables": tables}
    except Exception as e:
        logger.exception("Error en internal db-check")
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()

@router.get("/productos", response_model=ProductosResponse, tags=["catalogo"])
def productos(page: int = Query(1, ge=1), size: int = Query(12, ge=1, le=100),
              q: Optional[str] = None, cat: Optional[str] = None):
    offset = (page - 1) * size
    conn = get_conn()
    try:
        where = []
        args: List[Any] = []

        # Construir filtros teniendo en cuenta columnas opcionales en la tabla
        has_descripcion = schema_has("productos", "descripcion")
        has_categoria = schema_has("productos", "categoria")

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

        # Seleccionar solo las columnas que existen en la tabla
        select_cols = ["id", "nombre", "precio", "stock"]
        if has_categoria:
            select_cols.append("categoria")
        # Image columns: imagen_url is common; optionally include imagen_srcset, imagen_width, imagen_height
        if schema_has("productos", "imagen_url"):
            select_cols.append("imagen_url")
        if schema_has("productos", "imagen_srcset"):
            select_cols.append("imagen_srcset")
        if schema_has("productos", "imagen_width"):
            select_cols.append("imagen_width")
        if schema_has("productos", "imagen_height"):
            select_cols.append("imagen_height")
        if has_descripcion:
            select_cols.append("descripcion")

        cols_sql = ",".join(select_cols)

        with conn.cursor() as c:
            c.execute(f"SELECT COUNT(*) AS total FROM productos{where_sql}", args)
            total = c.fetchone()["total"]
            c.execute(f"SELECT {cols_sql} FROM productos{where_sql} ORDER BY id ASC LIMIT %s OFFSET %s", args + [size, offset])
            items = c.fetchall()

        total_pages = math.ceil(total / size) if size else 1
        return {"total_items": total, "total_pages": total_pages, "page": page, "size": size, "items": items}
    finally:
        conn.close()

# VENTAS
@router.post("/compras", response_model=CompraResponse, status_code=201, tags=["ventas"])
def comprar(payload: CompraRequest):
    conn = get_conn()
    try:
        with conn.cursor() as c:
            c.execute("SELECT id, stock, precio FROM productos WHERE id=%s FOR UPDATE", (payload.producto_id,))
            prod = c.fetchone()
            if not prod:
                raise HTTPException(status_code=404, detail="Producto no encontrado")
            if prod["stock"] < payload.cantidad:
                raise HTTPException(status_code=409, detail="Stock insuficiente")
            c.execute("UPDATE productos SET stock=stock-%s WHERE id=%s", (payload.cantidad, payload.producto_id))
            c.execute("INSERT INTO compras (producto_id, cantidad) VALUES (%s,%s)", (payload.producto_id, payload.cantidad))
            compra_id = c.lastrowid
        conn.commit()
        with conn.cursor() as c2:
            c2.execute("SELECT id, producto_id, cantidad, fecha FROM compras WHERE id=%s", (compra_id,))
            row = c2.fetchone()
        return row
    except HTTPException:
        conn.rollback()
        raise
    except (DBIntegrityError, DBProgrammingError) as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail="Solicitud inválida (SQL)") from e
    except (DBOperationalError, DBError) as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Error interno de base de datos") from e
    finally:
        conn.close()

@router.post("/checkout", response_model=CheckoutResponse, tags=["ventas"])
def checkout(payload: CheckoutRequest):
    if not payload.items:
        raise HTTPException(status_code=400, detail="Carrito vacío")
    conn = get_conn()
    compras_realizadas: List[CheckoutResultItem] = []
    try:
        total_unidades = 0
        with conn.cursor() as c:
            for it in payload.items:
                c.execute("SELECT id, stock FROM productos WHERE id=%s FOR UPDATE", (it.producto_id,))
                prod = c.fetchone()
                if not prod:
                    raise HTTPException(status_code=404, detail=f"Producto {it.producto_id} no existe")
                if prod["stock"] < it.cantidad:
                    raise HTTPException(status_code=409, detail=f"Stock insuficiente para producto {it.producto_id}")
                c.execute("UPDATE productos SET stock=stock-%s WHERE id=%s", (it.cantidad, it.producto_id))
                c.execute("INSERT INTO compras (producto_id, cantidad) VALUES (%s,%s)", (it.producto_id, it.cantidad))
                compras_realizadas.append(CheckoutResultItem(compra_id=c.lastrowid, producto_id=it.producto_id, cantidad=it.cantidad))
                total_unidades += it.cantidad
        conn.commit()
        return CheckoutResponse(
            status="ok",
            total_items=len(payload.items),
            total_unidades=total_unidades,
            compras=compras_realizadas,
            detalle="Checkout completado; compras registradas y stock actualizado",
        )
    except HTTPException:
        conn.rollback()
        raise
    except (DBIntegrityError, DBProgrammingError) as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail="Solicitud inválida (SQL)") from e
    except (DBOperationalError, DBError) as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Error interno de base de datos") from e
    finally:
        conn.close()

# ADMIN (guard /admin/*)
@router.get("/admin/ventas/resumen", response_model=VentasResumen, tags=["admin"])
def admin_resumen(from_date: Optional[date] = Query(None), to_date: Optional[date] = Query(None), user=Depends(require_admin)):
    validate_from_to(from_date, to_date)
    conn = get_conn()
    try:
        where = []
        args: List[Any] = []
        if from_date:
            where.append("DATE(c.fecha) >= %s"); args.append(from_date)
        if to_date:
            where.append("DATE(c.fecha) <= %s"); args.append(to_date)
        where_sql = (" WHERE " + " AND ".join(where)) if where else ""
        sql = f"""
            SELECT COUNT(*) AS compras,
                   COALESCE(SUM(c.cantidad),0) AS unidades,
                   COALESCE(SUM(c.cantidad * p.precio),0) AS monto_total
            FROM compras c
            JOIN productos p ON p.id=c.producto_id
            {where_sql}
        """
        with conn.cursor() as cur:
            cur.execute(sql, args)
            row = cur.fetchone()
        return {"compras": int(row["compras"]), "unidades": int(row["unidades"]), "monto_total": float(row["monto_total"])}
    finally:
        conn.close()

@router.get("/admin/ventas/serie", response_model=VentasSerie, tags=["admin"])
def admin_serie(from_date: Optional[date] = Query(None), to_date: Optional[date] = Query(None), user=Depends(require_admin)):
    today = date.today()
    if not to_date:
        to_date = today
    if not from_date:
        from_date = to_date - timedelta(days=6)  # default: últimos 7 días
    validate_from_to(from_date, to_date)
    conn = get_conn()
    try:
        sql = """
            SELECT DATE(c.fecha) AS f, COUNT(*) AS compras,
                   COALESCE(SUM(c.cantidad),0) AS unidades,
                   COALESCE(SUM(c.cantidad*p.precio),0) AS monto
            FROM compras c
            JOIN productos p ON p.id=c.producto_id
            WHERE DATE(c.fecha) BETWEEN %s AND %s
            GROUP BY DATE(c.fecha)
            ORDER BY 1
        """
        with conn.cursor() as cur:
            cur.execute(sql, (from_date, to_date))
            rows = cur.fetchall()
        by_day = {r["f"]: r for r in rows}
        items: List[SerieItem] = []
        d = from_date
        while d <= to_date:
            r = by_day.get(d, {"compras":0,"unidades":0,"monto":0.0})
            items.append(SerieItem(fecha=d, compras=int(r["compras"]), unidades=int(r["unidades"]), monto_total=float(r["monto"])))
            d += timedelta(days=1)
        return {"items": items}
    finally:
        conn.close()

@router.get("/admin/ventas.csv", tags=["admin"])
def admin_csv(from_date: Optional[date] = Query(None), to_date: Optional[date] = Query(None), user=Depends(require_admin)):
    validate_from_to(from_date, to_date)
    conn = get_conn()
    try:
        where = []
        args: List[Any] = []
        if from_date:
            where.append("DATE(c.fecha) >= %s"); args.append(from_date)
        if to_date:
            where.append("DATE(c.fecha) <= %s"); args.append(to_date)
        where_sql = (" WHERE " + " AND ".join(where)) if where else ""
        sql = f"""
            SELECT c.id, c.producto_id, p.nombre, c.cantidad, p.precio, (c.cantidad*p.precio) AS monto, c.fecha
            FROM compras c
            JOIN productos p ON p.id=c.producto_id
            {where_sql}
            ORDER BY c.fecha DESC, c.id DESC
        """
        with conn.cursor() as cur:
            cur.execute(sql, args)
            rows = cur.fetchall()
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["id","producto_id","nombre","cantidad","precio","monto","fecha"])
        for r in rows:
            writer.writerow([r["id"], r["producto_id"], r["nombre"], r["cantidad"], r["precio"], float(r["monto"]), r["fecha"].strftime("%Y-%m-%d %H:%M:%S")])
        buf.seek(0)
        headers = {"Content-Disposition": "attachment; filename=ventas.csv"}
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers=headers)
    finally:
        conn.close()

# /stats (público)
@router.get("/stats", response_model=StatsResponse, tags=["util"])
def stats():
    conn = get_conn()
    try:
        with conn.cursor() as c:
            c.execute("SELECT COUNT(*) AS n, COALESCE(SUM(stock),0) AS stock_total FROM productos")
            prod = c.fetchone()
            c.execute("SELECT COUNT(*) AS compras, COALESCE(SUM(cantidad),0) AS unidades FROM compras WHERE DATE(fecha)=CURRENT_DATE()")
            hoy = c.fetchone()
        uptime = int(time.time() - APP_START_TIME)
        lat = {}
        for route in list(latency_store.keys()):
            p50, p95, p99 = get_latency_percentiles(route)
            lat[route] = {
                "count": len(latency_store[route]),
                "p50_ms": round(p50, 1),
                "p95_ms": round(p95, 1),
                "p99_ms": round(p99, 1),
            }
        return {
            "uptime_sec": uptime,
            "productos": int(prod["n"]),
            "stock_total": int(prod["stock_total"] or 0),
            "ventas_hoy_compras": int(hoy["compras"] or 0),
            "ventas_hoy_unidades": int(hoy["unidades"] or 0),
            "latency_routes": lat
        }
    finally:
        conn.close()
