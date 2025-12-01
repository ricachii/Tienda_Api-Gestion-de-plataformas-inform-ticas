#!/usr/bin/env python3
"""
Actualiza productos.imagen_url para apuntar a archivos locales servidos desde /media/products.
Edita PRODUCT_IMAGE_MAP si tus IDs o nombres de archivo difieren.
"""
from __future__ import annotations

from sqlalchemy import text

from app.backend.db import engine
from app.backend.assets import PRODUCTS_URL

# Diccionario {id_producto: nombre_archivo} → /media/products/<nombre_archivo>
PRODUCT_IMAGE_MAP = {
    1: "whey_isolate_1kg.png",
    2: "whey_concentrate_1kg.png",
    3: "proteina_vegana_1kg.png",
    4: "creatina_monohidratada_300g.png",
    5: "pre-entreno_300g.png",
    6: "bcaa_300g.png",
    7: "omega-3_1000mg_120_caps.png",
    8: "multivitaminico_90caps.png",
    9: "barritas_proteicas_12un.png",
    10: "electrolitos_500g.png",
    11: "glutamina_300g.png",
    12: "caseina_1kg_vainilla.png",
}


def main() -> None:
    if not PRODUCT_IMAGE_MAP:
        print("No hay mapeos configurados; nada que actualizar.")
        return

    total_updates = 0
    with engine.begin() as conn:
        for product_id, filename in PRODUCT_IMAGE_MAP.items():
            url = f"{PRODUCTS_URL}/{filename}"
            result = conn.execute(
                text("UPDATE productos SET imagen_url = :url WHERE id = :id"),
                {"url": url, "id": product_id},
            )
            if result.rowcount:
                total_updates += result.rowcount
                print(f"Producto {product_id} → {url}")
            else:
                print(f"Producto {product_id} no existe o no se actualizó.")

    print(f"Actualizaciones totales aplicadas: {total_updates}")


if __name__ == "__main__":
    main()
