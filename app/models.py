from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from typing import List

class Producto(BaseModel):
    id: int
    nombre: str
    precio: float
    stock: int
    categoria: Optional[str] = None
    imagen_url: Optional[str] = None
    descripcion: Optional[str] = None

class CompraRequest(BaseModel):
    producto_id: int = Field(ge=1)
    cantidad: int = Field(ge=1)
class CheckoutItem(BaseModel):
    producto_id: int = Field(ge=1)
    cantidad: int = Field(ge=1, le=99)

class CheckoutRequest(BaseModel):
    customer_name: str = Field(min_length=2, max_length=120)
    customer_email: EmailStr
    items: List[CheckoutItem]