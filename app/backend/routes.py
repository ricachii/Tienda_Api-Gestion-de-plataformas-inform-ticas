import csv
import json
from pathlib import Path
import hashlib
import io
import time
from decimal import Decimal
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any, Callable, Literal

import jwt  # PyJWT
from fastapi import APIRouter, HTTPException, Query, Depends, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

BACKEND_DIR = Path(__file__).resolve().parent
APP_DIR = BACKEND_DIR.parent

from .db import (
    get_conn,
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
    verify_password,
    upgrade_legacy_password_hash,
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
    OrderItem,
    OrderSummary,
    OrderDetail,
    OrdersResponse,
)
from .metrics import APP_START_TIME, get_latency_percentiles, latency_store
from .repositories.catalog import fetch_categories, fetch_products
from .repositories.orders import load_order_snapshot, list_orders, get_order_detail
from .utils import quantize_money

router = APIRouter()
logger = logging.getLogger("tienda-api")

# Intento simple de exponer la versión del frontend (si está presente)
FRONTEND_DIR = APP_DIR / "frontend"


@router.get("/frontend/version", tags=["util"])  # pequeño endpoint utilitario
def frontend_version():
    p = FRONTEND_DIR / "package.json"
    if not p.exists():
        return {"version": None}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return {"version": data.get("version")}
    except Exception:
        return {"version": None}


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
    """Rate limit simple para proteger /login."""

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

def get_optional_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[Dict[str, Any]]:
    """Devuelve el usuario autenticado si viene un token; de lo contrario None."""
    if not creds:
        return None
    data = decode_jwt(creds.credentials)
    uid = int(data["sub"])
    user = get_user_by_id(uid)
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no existe")
    return {"id": user["id"], "email": user["email"], "nombre": user["nombre"], "rol": user["rol"]}

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
    salt = user.get("salt")
    if not verify_password(payload.password, user.get("password_hash"), salt):
        hash_val = user.get("password_hash")
        salt_val = user.get("salt")
        logger.warning(
            "Login rechazado para %s: hash_type=%s hash_len=%s salt_type=%s salt_len=%s hash_preview=%s",
            user["email"],
            type(hash_val).__name__,
            len(hash_val) if hash_val is not None else None,
            type(salt_val).__name__,
            len(salt_val) if salt_val is not None else None,
            repr(hash_val)[:80],
        )
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    if not salt:
        try:
            upgrade_legacy_password_hash(user["id"], payload.password)
        except Exception as exc:  # no bloquear login si falla upgrade
            logger.warning("No se pudo actualizar hash legado para %s: %s", user["email"], exc)
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
    return fetch_categories()


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
    return fetch_products(page, size, q, cat)

# VENTAS

@router.post("/compras", response_model=CompraResponse, status_code=201, tags=["ventas"])
def comprar(payload: CompraRequest, user=Depends(get_optional_user)):
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
            c.execute(
                "INSERT INTO compras (producto_id, usuario_id, cantidad) VALUES (%s,%s,%s)",
                (payload.producto_id, user["id"] if user else None, payload.cantidad),
            )
            compra_id = c.lastrowid
        conn.commit()
        with conn.cursor() as c2:
            c2.execute("SELECT id, producto_id, usuario_id, cantidad, fecha FROM compras WHERE id=%s", (compra_id,))
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


@router.get("/orders/{order_id}", response_model=OrderDetail, tags=["admin"])
def order_detail(order_id: int, user=Depends(require_admin)):
    order = get_order_detail(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    return order


@router.get("/orders", response_model=OrdersResponse, tags=["admin"])
def orders_list(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    status: Optional[Literal["PAID","CANCELLED","PENDING"]] = Query(None),
    email: Optional[str] = Query(None),
    user=Depends(require_admin),
):
    return list_orders(page, size, status, email)

@router.post("/checkout", response_model=CheckoutResponse, tags=["ventas"])
def checkout(payload: CheckoutRequest, user=Depends(get_optional_user)):
    if not payload.items:
        raise HTTPException(status_code=400, detail="Carrito vacío")
    conn = get_conn()
    compras_realizadas: List[CheckoutResultItem] = []
    try:
        total_unidades = 0
        order_total = Decimal("0.00")
        with conn.cursor() as c:
            idempotency_row_id = None
            idempotency_hash = None
            if payload.idempotency_key:
                idempotency_hash = hashlib.sha256(payload.idempotency_key.encode("utf-8")).hexdigest()
                c.execute(
                    "SELECT id, order_id FROM idempotency_keys WHERE key_hash=%s FOR UPDATE",
                    (idempotency_hash,),
                )
                existing = c.fetchone()
                if existing and existing.get("order_id"):
                    conn.commit()
                    snapshot = load_order_snapshot(conn, existing["order_id"])
                    if snapshot:
                        return snapshot
                if existing:
                    idempotency_row_id = existing["id"]
                else:
                    c.execute("INSERT INTO idempotency_keys (key_hash) VALUES (%s)", (idempotency_hash,))
                    idempotency_row_id = c.lastrowid

            # Validar stock y preparar items
            prepared_items: List[Dict[str, Any]] = []
            for it in payload.items:
                c.execute("SELECT id, stock, precio FROM productos WHERE id=%s FOR UPDATE", (it.producto_id,))
                prod = c.fetchone()
                if not prod:
                    raise HTTPException(status_code=404, detail=f"Producto {it.producto_id} no existe")
                if prod["stock"] < it.cantidad:
                    raise HTTPException(status_code=409, detail=f"Stock insuficiente para producto {it.producto_id}")
                price = prod["precio"]
                if not isinstance(price, Decimal):
                    price = Decimal(str(price))
                prepared_items.append(
                    {
                        "producto_id": prod["id"],
                        "cantidad": it.cantidad,
                        "precio_unit": quantize_money(price),
                    }
                )

            # Crear orden principal
            for it in prepared_items:
                item_total = it["precio_unit"] * Decimal(it["cantidad"])
                order_total += quantize_money(item_total)
                total_unidades += it["cantidad"]
            order_total = quantize_money(order_total)
            c.execute(
                "INSERT INTO orders (customer_name, customer_email, total, status) VALUES (%s,%s,%s,%s)",
                (payload.customer_name, payload.customer_email, order_total, "PAID"),
            )
            order_id = c.lastrowid

            # Insertar items de orden y compras (compatibilidad con reportes existentes)
            for it in prepared_items:
                c.execute(
                    "INSERT INTO order_items (order_id, producto_id, cantidad, precio_unit) VALUES (%s,%s,%s,%s)",
                    (order_id, it["producto_id"], it["cantidad"], it["precio_unit"]),
                )
                order_item_id = c.lastrowid
                c.execute(
                    "UPDATE productos SET stock=stock-%s WHERE id=%s",
                    (it["cantidad"], it["producto_id"]),
                )
                c.execute(
                    "INSERT INTO compras (producto_id, usuario_id, cantidad) VALUES (%s,%s,%s)",
                    (it["producto_id"], user["id"] if user else None, it["cantidad"]),
                )
                compra_id = c.lastrowid
                compras_realizadas.append(
                    CheckoutResultItem(
                        compra_id=compra_id,
                        order_item_id=order_item_id,
                        producto_id=it["producto_id"],
                        cantidad=it["cantidad"],
                    )
                )

            if idempotency_row_id and idempotency_hash:
                c.execute(
                    "UPDATE idempotency_keys SET order_id=%s WHERE id=%s",
                    (order_id, idempotency_row_id),
                )
        conn.commit()
        return CheckoutResponse(
            status="ok",
            order_id=order_id,
            order_status="PAID",
            total=order_total,
            total_items=len(payload.items),
            total_unidades=total_unidades,
            compras=compras_realizadas,
            detalle="Checkout completado; orden y items creados, stock actualizado",
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
