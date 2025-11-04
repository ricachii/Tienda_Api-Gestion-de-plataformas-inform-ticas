# README — Uso desde la API (BD → API) — Tienda (VM2)

Este documento explica cómo la API (FastAPI en VM1, PyMySQL) debe consumir la base de datos `tienda` en VM2 sin romper compatibilidad. Incluye ejemplos paramétricos, plantillas transaccionales, y reglas operativas.

## Conexión
Variables de entorno (archivo `.env` en VM1):
- DB_HOST=192.168.56.10    # IP de VM2 (ejemplo)
- DB_USER=tienda_user
- DB_PASS=REPLACE_ME_PASSWORD
- DB_NAME=tienda
- DB_PORT=3306

Recomendaciones:
- No usar `root` para operaciones de la API.
- Conexiones TLS: si se habilita REQUIRE SSL, la app debe configurarse con `ssl_ca`. (Ver `create_usuarios_and_grants.sql` variante comentada).
- Usar conexión pool (ej. aiomysql / PyMySQL pool) en FastAPI.

## Vistas y contratos para endpoints
Endpoints a soportar:

GET /productos
- Parámetros:
  - q: texto opcional (buscar en nombre y descripción; case-insensitive)
  - cat: categoría exacta opcional
  - page: entero 1-based (default 1)
  - size: entero (default 20)
- Orden: id ASC
- Origen: `v_productos_busqueda` o tabla `productos` (la vista facilita nombre_norm)

GET /categorias
- Origen: vista `v_categorias`
- Query simple:
  - SELECT categoria FROM v_categorias;

POST /compras
- Lógica: compra individual → decrementar stock con LOCK y rollback si no hay stock.
- Uso de plantilla: ver `txn_templates.sql` (START TRANSACTION + SELECT ... FOR UPDATE + UPDATE + INSERT + COMMIT)

POST /checkout
- Lógica: batch atómico de varias compras.
- Bloquear filas necesarias con SELECT ... FOR UPDATE sobre todos los productos involucrados; verificar stock; si ok, aplicar updates+inserts y COMMIT.

## Ejemplo de implementación con PyMySQL (sin ORM) — Compra individual
Pseudocódigo (síncrono):

```python
import pymysql

conn = pymysql.connect(host='DB_HOST', user='DB_USER', password='DB_PASS', db='DB_NAME')
try:
    with conn.cursor() as cur:
        conn.begin()
        cur.execute("SELECT stock, precio FROM productos WHERE id=%s FOR UPDATE", (producto_id,))
        row = cur.fetchone()
        if not row or row[0] < cantidad:
            conn.rollback()
            raise ValueError("No hay stock suficiente")
        cur.execute("UPDATE productos SET stock = stock - %s WHERE id = %s", (cantidad, producto_id))
        cur.execute("INSERT INTO compras (producto_id, cantidad, precio_unitario, fecha) VALUES (%s,%s,%s,NOW())", (producto_id, cantidad, row[1]))
        conn.commit()
except:
    conn.rollback()
    raise
finally:
    conn.close()
```

## Paginación (ejemplo de parámetros)
- page: >=1
- size: 1..100 (limitar por seguridad)
- offset = (page - 1) * size
- Siempre usar COUNT separado para total (cacheable en capa superior si necesario).

## No hacer (reglas estrictas)
- No usar root desde la API.
- No otorgar DDL al usuario de la app.
- No concatenar parámetros en SQL (siempre parametrizar).
- No acelerar transacciones con sleep o waits; mantenerlas cortas.
- Evitar SELECT ... FOR UPDATE en tablas completas sin WHERE; limitar por ids necesarias.

## Tests y seeds
- Ejecutar `seed_tienda.sql` en entorno de staging antes de usar en producción.
- Ejecutar `test_restore.sh` periódicamente (recomendado mensual) para validar que los backups son restaurables.

## Seguridad y operaciones
- Auditoría: export de grants en `/root/mysql_user_grants_full_YYYY-MM-DD.sql`.
- Backups cifrados y offsite: usar GPG + rclone. (ya implementado en VM2)

## Notas de compatibilidad
- Scripts SQL diseñados para MariaDB 10.6+ / MySQL 8+. Si tu versión anterior no soporta bloques anónimos con DELIMITER, adapta la ejecución manualmente.
