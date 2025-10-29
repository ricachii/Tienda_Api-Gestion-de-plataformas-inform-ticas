from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field

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
    descripcion: Optional[str] = None

    class Config:
        orm_mode = True

class ProductosResponse(BaseModel):
    page: int = Field(ge=1)
    size: int = Field(ge=1, le=500)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)
    items: List[Producto]

# ========
# Compras
# ========
class CompraRequest(BaseModel):
    producto_id: int = Field(ge=1)
    cantidad: int = Field(ge=1, le=999)

class CompraResponse(BaseModel):
    status: str
    compra_id: Optional[int] = None
    producto_id: Optional[int] = None
    cantidad: Optional[int] = None
    detalle: Optional[str] = None

# =========
# Checkout (batch)
# =========
class CheckoutItem(BaseModel):
    producto_id: int = Field(ge=1)
    cantidad: int = Field(ge=1, le=99)

class CheckoutRequest(BaseModel):
    customer_name: str = Field(min_length=2, max_length=120)
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
