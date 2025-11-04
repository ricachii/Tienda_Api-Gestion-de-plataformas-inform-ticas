
# README — Base de datos `tienda` (VM2)

Este documento describe en detalle la base de datos `tienda` del proyecto académico "Tienda API – Gestión de Plataformas Informáticas" (instancia en VM2). Contiene la arquitectura interna, esquema, comandos de administración, respaldo/restauración, seguridad y tareas de mantenimiento.

NOTA: todo el contenido técnico, rutas y ejemplos han sido recopilados y verificados en la máquina que hospeda la base de datos (VM2). Los fragmentos de SQL y rutas han sido adaptados a la configuración actual.

---

## 1️ Arquitectura interna de la base de datos

Descripción general
- Motor: MariaDB 10.11.x (compatible con MySQL)
- Almacenamiento: InnoDB (transaccional, soporta llaves foráneas y ACID)
- Servicio: se ejecuta como servicio del sistema (consultar con `systemctl status mariadb`)

Diagrama de texto simple:

```
+----------------------+
|      Base: tienda    |
+----------------------+
| Tablas principales:  |
| - productos          |
| - compras            |
+----------------------+

Relación:
compras.producto_id → productos.id

Procesos internos:
- Inserción y control de stock
- Registro de compras (transaccional)
- Mantenimiento automático de timestamps (created_at / updated_at)
- Logs de rendimiento (slow queries) y binlog para auditoría/PITR
```

Detalles
- Integridad referencial mantenida mediante llaves foráneas (InnoDB).
- MariaDB corre como servicio del sistema (`mariadb`) y arranca en el boot.

## 2️ Especificaciones técnicas

- Motor: MariaDB 10.11.x
- Directorio de datos: `/var/lib/mysql/`
- Configuraciones principales: `/etc/mysql/mariadb.conf.d/` y personalizaciones en `/etc/mysql/conf.d/99-custom.cnf`
- Archivos personalizados añadidos por administración: `/etc/mysql/conf.d/99-custom.cnf`
- Ubicación de respaldos locales: `/var/backups/tienda/` (dumps gz, .gpg y .sha256)
- Binlog activo (ruta configurada): `log_bin = /var/log/mysql/mysql-bin`
- Slow query log: activado y volcado a archivo `/var/log/mysql/mysql-slow.log` y a la tabla `mysql.slow_log` (según configuración temporaria)
- Certificados SSL del servidor: `/etc/mysql/ssl/` (ca, server-cert.pem, server-key.pem)
- Exporters activos:
  - `mysqld_exporter` (servicio systemd)
  - `node_exporter` (servicio systemd)

Automatización y scripts relevantes
- Script de backup local y encriptado: `/usr/local/bin/backup_tienda.sh` (mysqldump → gzip → .sha256)
- Script de subida offsite cifrada: `/usr/local/bin/backup_offsite.sh` (gpg + rclone)
- Script de comprobación: `/usr/local/bin/check_backup.sh`
- Script de prueba de restauración: `/usr/local/bin/test_restore.sh`
- Systemd unit & timer para offsite upload: `backup-offsite.service`, `backup-offsite.timer`

Rclone remote configurado: `backup:` (remote en Google Drive u otro proveedor). La copia remota de snapshot se almacenó en `backup:tienda-images/`.

## 3️ Estructura del esquema

Las tablas mostradas a continuación son la representación actual del esquema `tienda` y han sido verificadas con los dumps y migraciones presentes en el sistema. Ajusta los nombres si tu migración tiene variaciones.

Tabla `productos`

```sql
CREATE TABLE productos (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(100) NOT NULL,
  precio DECIMAL(10,2) NOT NULL,
  stock INT NOT NULL DEFAULT 0,
  categoria VARCHAR(50),
  imagen_url VARCHAR(255),
  descripcion TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

Tabla `compras`

```sql
CREATE TABLE compras (
  id INT AUTO_INCREMENT PRIMARY KEY,
  producto_id INT NOT NULL,
  cantidad INT NOT NULL,
  precio_unitario DECIMAL(10,2),
  fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (producto_id) REFERENCES productos(id)
    ON UPDATE CASCADE
    ON DELETE RESTRICT
);
```

Reglas de integridad y supuestos
- `productos.id` es clave primaria.
- `compras.producto_id` referencia `productos.id` (no permite borrados en cascada que invaliden compras históricas).
- No se permite stock negativo: las aplicaciones deben validar antes de actualizar stock (y en transacción).
- Motor InnoDB garantiza atomicidad y rollback en operaciones multi-statement.

## 4️ Funcionalidades principales de la base de datos

a) Gestión de productos
- Listado, filtrado y búsqueda por nombre/categoría.
- Control de stock: campo `stock` actualizado en cada compra.
- Timestamps automáticos (`created_at`, `updated_at`).

b) Registro de compras
- Inserción de registros en `compras` por cada venta/checkout.
- Actualización transaccional del stock para evitar condiciones de carrera.

c) Transacciones atómicas (ejemplo de comprobación y checkout)

```sql
START TRANSACTION;
SELECT stock FROM productos WHERE id = 1 FOR UPDATE;
-- validar stock >= cantidad
UPDATE productos SET stock = stock - 2 WHERE id = 1;
INSERT INTO compras (producto_id, cantidad, precio_unitario)
  VALUES (1, 2, 14990);
COMMIT;

-- Si ocurre un error, ejecutar: ROLLBACK;
```

d) Auditoría y rendimiento
- `slow_query_log` activado para identificar consultas lentas.
- Análisis con `pt-query-digest` (Percona Toolkit) o `mysqldumpslow` para agrupar fingerprints.
- Binary log (binlog) activo para auditoría y point-in-time recovery (PITR).

## 5️ Consultas comunes de administración

-- Ver bases disponibles
```sql
SHOW DATABASES;
```

-- Seleccionar base principal
```sql
USE tienda;
```

-- Ver tablas
```sql
SHOW TABLES;
```

-- Ver columnas de productos
```sql
DESCRIBE productos;
```

-- Listar productos (muestra)
```sql
SELECT * FROM productos LIMIT 5;
```

-- Consultar categorías
```sql
SELECT DISTINCT categoria FROM productos WHERE categoria IS NOT NULL;
```

-- Ver compras recientes
```sql
SELECT * FROM compras ORDER BY fecha DESC LIMIT 5;
```

-- Ver DDL de tabla compras
```sql
SHOW CREATE TABLE compras;
```

## 6️ Respaldo y restauración

Ubicación de respaldos locales: `/var/backups/tienda/` (dumps comprimidos, checksums y archivos cifrados)

Backup manual (ejemplo)

```bash
mysqldump -u root tienda | gzip > /var/backups/tienda/tienda_$(date +%F).sql.gz
sha256sum /var/backups/tienda/tienda_$(date +%F).sql.gz > /var/backups/tienda/tienda_$(date +%F).sql.gz.sha256
```

Verificación de checksum

```bash
sha256sum -c /var/backups/tienda/tienda_$(date +%F).sql.gz.sha256
```

Cifrado (GPG) y subida offsite (rclone)

```bash
# cifrar con la clave pública del custodio
gpg -e -r 'GPG_KEY_ID' /var/backups/tienda/tienda_$(date +%F).sql.gz
# subir vía rclone al remote 'backup:'
rclone copy /var/backups/tienda/ backup:tienda/ -P
```

Restauración (entorno de prueba)

```bash
gunzip -c /var/backups/tienda/tienda_2025-11-03.sql.gz | mysql -u root tienda_test
```

Automatización
- `backup_offsite.sh` y `test_restore.sh` están gestionados por systemd timers (`backup-offsite.timer`) para correr las subidas y las pruebas según lo configurado.
- Logs relacionados con backups: `/var/log/backup_offsite.log` (script) y syslog (`logger` tag: `tienda-backup`).

## 7️ Seguridad y control de acceso

- Acceso de red: restringido a la red de la organización; las cuentas de aplicación limitadas por host (ej.: `192.168.56.%`).
- Usuario de aplicación con mínimos privilegios

Ejemplo (usuario app — ajustado a la práctica):
```sql
GRANT SELECT, INSERT, UPDATE, DELETE ON tienda.* TO 'tienda_user'@'192.168.56.%' IDENTIFIED BY '***';
FLUSH PRIVILEGES;
```

- Cuentas administrativas (`root@localhost`, `mysql.*`) conservan privilegios elevados y no deben aceptar conexiones remotas.
- SSL/TLS: certificados servidor en `/etc/mysql/ssl/`; MariaDB configurado para usarlos. `REQUIRE SSL` no se forzó todavía para evitar romper clientes que no estén configurados.
- Binlog habilitado para auditoría; revisar retención y espacio (`expire_logs_days`).
- Auditoría de grants: exportada en `/root/mysql_user_grants_full_2025-11-03.sql`.

## 8️ Monitoreo y mantenimiento

Comandos y checks útiles

```bash
# Estado del servicio
sudo systemctl status mariadb

# Revisar logs de error
sudo tail -n 200 /var/log/mysql/error.log

# Consultar slow queries (tabla)
mysql -e "SELECT start_time,user_host,query_time,sql_text FROM mysql.slow_log ORDER BY query_time DESC LIMIT 50;"

# Revisar archivo slow log
sudo tail -n 200 /var/log/mysql/mysql-slow.log

# Estado de exporters
systemctl is-active mysqld_exporter node_exporter

# Métricas mysqld_exporter (por defecto)
curl http://127.0.0.1:9104/metrics

# Ver binlogs
mysql -e "SHOW BINARY LOGS;"

# Espacio en disco para /var/log/mysql y /var/lib/mysql
df -h /var/log/mysql /var/lib/mysql
```

Mantenimiento recomendado
- Mantener `slow_query_log` en TABLE por 24–48h para análisis y exportarlo con `pt-query-digest` cuando se detecte degradación.
- Revisar crecimiento del binlog y ajustar `expire_logs_days` (o rotación manual) para evitar llenar disco.
- Ejecutar `test_restore.sh` periódicamente (recomendado mensual) para validar que los backups son restaurables.

## 9️ Acciones de mejora planificadas (recomendaciones)

- Forzar `REQUIRE SSL` para usuarios remotos una vez que los clientes/APPs estén configurados con `ssl_ca`.
- Integrar exporters con Prometheus + Grafana y crear alertas para: backup fallido, disco lleno, alta latencia en queries.
- Implementar rotación de claves GPG y rotación/reciclado de tokens rclone según política de seguridad.
- Evaluar replicación (master/replica) o solución de HA si requiere RTO < X minutos.
- Pinear versiones en `requirements.txt` para reproducibilidad y CI.

## Anexos y archivos críticos (ubicaciones)

- Configuración personalizada MariaDB: `/etc/mysql/conf.d/99-custom.cnf`
- Certificados SSL: `/etc/mysql/ssl/` (ca-cert.pem, server-cert.pem, server-key.pem)
- Backups locales: `/var/backups/tienda/` (ej.: `tienda_2025-11-03_2030.sql.gz`, `tienda_2025-11-03_2030.sql.gz.gpg`, `*.sha256`)
- Scripts de backup y automación: `/usr/local/bin/backup_offsite.sh`, `/usr/local/bin/backup_tienda.sh`, `/usr/local/bin/test_restore.sh`, `/usr/local/bin/check_backup.sh`
- Systemd units: `/etc/systemd/system/backup-offsite.service`, `/etc/systemd/system/backup-offsite.timer`
- Exporters: systemd services `mysqld_exporter`, `node_exporter`
- Grants export: `/root/mysql_user_grants_full_2025-11-03.sql`
- Snapshot local: `/root/db-state-snapshot/2025-11-03/` (contiene copia de `/etc/mysql`, rclone config y copia offsite descargada)
- Copia remota (Drive): `backup:tienda-images/db-state-snapshot_2025-11-03.tar.gz` (enlace compartible generado durante la operación)