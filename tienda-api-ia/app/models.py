"""
Pydantic models for request/response validation
"""
from pydantic import BaseModel, Field
from typing import Optional, List

class CompraRequest(BaseModel):
    """Model for purchase requests"""
    producto_id: int = Field(ge=1, description="Product ID must be positive")
    cantidad: int = Field(ge=1, le=99, description="Quantity must be between 1 and 99")

class ProductoResponse(BaseModel):
    """Model for product responses"""
    id: int
    nombre: str
    precio: float
    stock: int
    categoria: str
    imagen_url: Optional[str] = None
    descripcion: Optional[str] = None

class ProductosResponse(BaseModel):
    """Model for paginated product responses"""
    page: int
    size: int
    total: int
    items: List[ProductoResponse]