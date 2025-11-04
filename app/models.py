from typing import Optional, List, Literal
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, date

# =========
# Productos
# =========
class Producto(BaseModel):
    id: int
    nombre: str
    precio: float
    stock: int
    categoria: Optional[str] = None
    imagen_url: Optional[str] = None
    # Optional image metadata supplied by the API to improve frontend UX
    imagen_srcset: Optional[str] = None
    imagen_width: Optional[int] = None
    imagen_height: Optional[int] = None
    descripcion: Optional[str] = None

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

class CheckoutResultItem(BaseModel):
    compra_id: int
    producto_id: int
    cantidad: int

class CheckoutResponse(BaseModel):
    status: str
    total_items: int
    total_unidades: int
    compras: List[CheckoutResultItem]
    detalle: Optional[str] = None

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
