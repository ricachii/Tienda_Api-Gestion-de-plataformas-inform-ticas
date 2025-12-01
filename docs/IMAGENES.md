# Gestión de imágenes e íconos

Todas las imágenes están centralizadas en el backend bajo `app/backend/media/`:

- `products/` → PNG/JPG de productos. Se exponen en `/media/products/<archivo>`.
- `icons/` → íconos reutilizados por el frontend. Se exponen en `/media/icons/<archivo>`.

El módulo `app.backend.assets` define los paths y URLs (`MEDIA_DIR`, `PRODUCTS_DIR`, `ICONS_DIR`, etc.) y `main.py` monta automáticamente `/media`. Si necesitas nuevas carpetas, añádelas allí para mantener el orden.

Para actualizar las URLs de productos sin hacerlo a mano, usa `scripts/update_product_images.py`, que genera rutas `/media/products/<archivo>` basadas en un diccionario `{id: archivo}`.

---

## Gestión mediante catálogo (opcional)

El backend puede seguir utilizando `imagen_ref` y el catálogo YAML para resolver metadatos adicionales (`srcset`, dimensiones, CDN externo, etc.). Si trabajas con CDN, deja `IMG_BASE_URL` apuntando a él; si usas el almacenamiento local, basta con mantener los archivos en `app/backend/media/products`.

## Flujo recomendado

1. **Preparar entorno** (variables `.env` en VM1):
   ```env
   IMG_BASE_URL=https://cdn.tienda.udec/img/
   IMG_CATALOG_PATH=/home/rikashii/tienda-api/app/backend/image_catalog.yaml
   ```
   `IMG_CATALOG_PATH` es opcional; si no se define, usa el archivo dentro de `app/`.

2. **Migrar datos existentes** desde VM1 (usa las credenciales de VM2 que ya están en `.env`):
   ```bash
   source .venv/bin/activate
   python scripts/migrate_image_catalog.py
   ```
   El script:
   - crea la columna `imagen_ref` si falta (ALTER TABLE en VM2),
   - genera slugs para los productos que no tienen clave,
   - actualiza `productos.imagen_ref`,
   - reescribe `app/backend/image_catalog.yaml` con los datos actuales (usando las URLs anteriores para no romper el frontend).

   Usa `--dry-run` para previsualizar sin tocar la DB ni el YAML.

3. **Editar el catálogo** (`app/backend/image_catalog.yaml` o la ruta que definas). Cada entrada admite:
   ```yaml
   items:
     whey-protein-500:
       path: whey/whey-protein-500.jpg   # relativo a IMG_BASE_URL
       srcset:
         - path: whey/whey-protein-500.jpg
         - path: whey/whey-protein-500@2x.jpg
           descriptor: 2x
       width: 640
       height: 640
   ```
   También puedes usar `url:` para rutas absolutas si aún no tienes CDN.

4. **Refrescar la caché** (opcional). Si editas el YAML sin reiniciar FastAPI, ejecuta dentro del intérprete:
   ```python
   from app.backend.image_store import refresh_image_catalog
   refresh_image_catalog()
   ```

## Preguntas frecuentes

- **¿Qué pasa si `imagen_ref` no existe?** La API detecta el esquema antiguo y sigue devolviendo `imagen_url` sin pasar por el catálogo. El script anterior añade la columna y actualiza los registros.
- **¿Necesito duplicar las imágenes en VM1?** No. Las imágenes deben residir en el CDN/servidor estático. VM1 solo entrega metadatos.
- **¿Cómo agrego un producto nuevo?** Inserta la fila en `productos` con `imagen_ref='mi-slug'` y añade la entrada correspondiente en el catálogo YAML. La API resolverá automáticamente `imagen_url`, `srcset` y dimensiones.
