"""
API routes for the supplement store
"""
from fastapi import APIRouter, HTTPException, Query
from .db import get_conn
from .models import CompraRequest, ProductosResponse
from typing import Optional

router = APIRouter()

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}

@router.get("/categorias")
async def get_categorias():
    """Get unique product categories"""
    try:
        with get_conn() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT DISTINCT categoria FROM productos ORDER BY categoria")
                categorias = [row['categoria'] for row in cursor.fetchall()]
                return categorias
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/productos", response_model=ProductosResponse)
async def get_productos(
    cat: Optional[str] = Query(None, description="Filter by category"),
    q: Optional[str] = Query(None, description="Search query"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(12, ge=1, le=100, description="Page size")
):
    """Get products with filtering and pagination"""
    try:
        with get_conn() as conn:
            with conn.cursor() as cursor:
                # Build WHERE clause
                where_conditions = []
                params = []
                
                if cat:
                    where_conditions.append("categoria = %s")
                    params.append(cat)
                
                if q:
                    where_conditions.append("(nombre LIKE %s OR descripcion LIKE %s)")
                    params.extend([f"%{q}%", f"%{q}%"])
                
                where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
                
                # Get total count
                count_query = f"SELECT COUNT(*) as total FROM productos WHERE {where_clause}"
                cursor.execute(count_query, params)
                total = cursor.fetchone()['total']
                
                # Calculate offset
                offset = (page - 1) * size
                
                # Get products
                products_query = f"""
                    SELECT id, nombre, precio, stock, categoria, imagen_url, descripcion 
                    FROM productos 
                    WHERE {where_clause}
                    ORDER BY id
                    LIMIT %s OFFSET %s
                """
                cursor.execute(products_query, params + [size, offset])
                productos = cursor.fetchall()
                
                return ProductosResponse(
                    page=page,
                    size=size,
                    total=total,
                    items=productos
                )
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/compras")
async def crear_compra(compra: CompraRequest):
    """Create a new purchase and update stock"""
    try:
        with get_conn() as conn:
            with conn.cursor() as cursor:
                # Start transaction
                conn.begin()
                
                # Check if product exists and get current stock
                cursor.execute("SELECT id, stock FROM productos WHERE id = %s FOR UPDATE", (compra.producto_id,))
                producto = cursor.fetchone()
                
                if not producto:
                    conn.rollback()
                    raise HTTPException(status_code=404, detail="Product not found")
                
                if producto['stock'] < compra.cantidad:
                    conn.rollback()
                    raise HTTPException(status_code=400, detail="Insufficient stock")
                
                # Insert purchase
                cursor.execute(
                    "INSERT INTO compras (producto_id, cantidad) VALUES (%s, %s)",
                    (compra.producto_id, compra.cantidad)
                )
                
                # Update stock
                cursor.execute(
                    "UPDATE productos SET stock = stock - %s WHERE id = %s",
                    (compra.cantidad, compra.producto_id)
                )
                
                # Commit transaction
                conn.commit()
                
                return {
                    "message": "Purchase completed successfully",
                    "producto_id": compra.producto_id,
                    "cantidad": compra.cantidad
                }
                
    except HTTPException:
        raise
    except Exception as e:
        # Rollback in case of error
        try:
            conn.rollback()
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")