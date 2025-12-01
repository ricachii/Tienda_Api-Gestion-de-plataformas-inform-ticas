from decimal import Decimal
from typing import Optional, List, Literal
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, date

# =========
# Productos
# =========
class Producto(BaseModel):
    id: int
    nombre: str
    precio: Decimal
    stock: int
    categoria: Optional[str] = None
    imagen_ref: Optional[str] = None
    imagen_url: Optional[str] = None
    # Optional image metadata supplied by the API to improve frontend UX
    imagen_srcset: Optional[str] = None
    imagen_width: Optional[int] = None
    imagen_height: Optional[int] = None
    descripcion: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class ProductosResponse(BaseModel):
    total_items: int
    total_pages: int
    page: int
    size: int
    items: List[Producto]

# =========
# Compras
# =========
class CompraRequest(BaseModel):
    producto_id: int = Field(gt=0)
    cantidad: int = Field(gt=0)

class CompraResponse(BaseModel):
    id: int
    producto_id: int
    usuario_id: Optional[int] = None
    cantidad: int
    fecha: datetime

# =========
# Checkout
# =========
class CheckoutItem(BaseModel):
    producto_id: int = Field(gt=0)
    cantidad: int = Field(gt=0)

class CheckoutRequest(BaseModel):
    customer_name: str = Field(min_length=1, max_length=100)
    customer_email: EmailStr
    items: List[CheckoutItem]
    shipping_address: Optional[str] = None
    customer_notes: Optional[str] = None
    # Idempotency key to avoid double-charging on retries (hashed server-side)
    idempotency_key: Optional[str] = Field(default=None, min_length=1, max_length=128)

class CheckoutResultItem(BaseModel):
    compra_id: Optional[int] = None
    order_item_id: Optional[int] = None
    producto_id: int
    cantidad: int

class CheckoutResponse(BaseModel):
    status: str
    order_id: Optional[int] = None
    order_status: Optional[Literal["PAID","CANCELLED","PENDING"]] = None
    total: Optional[Decimal] = None
    total_items: int
    total_unidades: int
    compras: List[CheckoutResultItem]
    detalle: Optional[str] = None

# =========
# Orders
# =========
class OrderItem(BaseModel):
    id: int
    order_id: int
    producto_id: int
    cantidad: int
    precio_unit: Decimal

class OrderSummary(BaseModel):
    id: int
    customer_name: str
    customer_email: EmailStr
    total: Decimal
    status: Literal["PAID","CANCELLED","PENDING"]
    created_at: datetime
    items: int
    unidades: int

class OrderDetail(BaseModel):
    id: int
    customer_name: str
    customer_email: EmailStr
    total: Decimal
    status: Literal["PAID","CANCELLED","PENDING"]
    created_at: datetime
    total_items: int
    total_unidades: int
    items: List[OrderItem]

class OrdersResponse(BaseModel):
    total_items: int
    total_pages: int
    page: int
    size: int
    items: List[OrderSummary]

# =========
# Auth / Users
# =========
class RegisterRequest(BaseModel):
    email: EmailStr
    nombre: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class MeResponse(BaseModel):
    id: int
    email: EmailStr
    nombre: str
    rol: Literal["user","admin"]

# =========
# Admin Ventas
# =========
class FechaFiltro(BaseModel):
    from_date: Optional[date] = None
    to_date: Optional[date] = None

class VentasResumen(BaseModel):
    compras: int
    unidades: int
    monto_total: float

class SerieItem(BaseModel):
    fecha: date
    compras: int
    unidades: int
    monto_total: float

class VentasSerie(BaseModel):
    items: List[SerieItem]

# =========
# Stats
# =========
class StatsResponse(BaseModel):
    uptime_sec: int
    productos: int
    stock_total: int
    ventas_hoy_compras: int
    ventas_hoy_unidades: int
    latency_routes: dict
