# Cambios aplicados en VM2 y procedimiento de rollback

Resumen rápido tras la inspección

- El tar con artefactos existe: `db-artifacts-clean.tar.gz`.
- SHA comprobada: `2cd545439a85166a93ec83756c3d4581e1fbc0ab0a1ade9cdbbaf814a787988c`.
- Hay un volcado en `tienda.sql` (3.1 KB).
- MariaDB está activo y escucha en `0.0.0.0:3306`.
- El archivo de configuración `50-server.cnf` ya contiene `bind-address = 0.0.0.0` y hay un backup de ese archivo.

Conclusión: el cambio de `bind-address` ya está aplicado y el servicio escucha remotamente; quedan por verificar el firewall (UFW) y la conectividad desde VM1, transferir los artefactos y documentar los cambios/rollback.

---

Siguientes pasos propuestos (ejecución segura y completa)

1) Verificar desde VM1 que puede conectarse y consultar la base (esto confirma usuario/privilegios e importación).
2) Si la import no está hecha o quieres forzarla, ejecutar la importación del dump `tienda.sql` en VM2 (el archivo ya está en VM2).
3) Transferir el tar `db-artifacts-clean.tar.gz` a VM1 y verificar la SHA allí.
4) Añadir este README de cambios/rollback en VM2 (archivo actual).
5) Verificación final y cierre.

---

Comandos listos para ejecutar — copia y pega según lo necesites

A. Verificar UFW en VM2 (si usas UFW)

```bash
# Ver reglas UFW
sudo ufw status verbose

# Permitir solo desde la red/app host (ej. 192.168.56.10)
sudo ufw allow from 192.168.56.10 to any port 3306 proto tcp

# Listar reglas con numeración
sudo ufw status numbered
```

B. Probar conexión desde VM1 (reemplaza <IP_VM2> por la IP de VM2, p. ej. 192.168.56.20)

```bash
# Probar conexión al puerto y listar tablas
mysql -u tienda_user -p -h <IP_VM2> -P 3306 -e "USE tienda; SHOW TABLES;"

# Si quieres ver algunas filas de ejemplo
mysql -u tienda_user -p -h <IP_VM2> -P 3306 -e "SELECT COUNT(*) FROM usuarios;" tienda
```

Si devuelve tablas y filas, la importación y los permisos están OK.

C. Si necesitas importar el dump en VM2 ahora (ejecuta en VM2)

```bash
# Importar como root (recomendado para la import inicial)
mysql -u root -p tienda < /ruta/a/tienda.sql

# O, si prefieres hacerlo con el usuario de la app (si tiene permisos CREATE/INSERT):
mysql -u tienda_user -p -h 127.0.0.1 tienda < /ruta/a/tienda.sql
```

D. Transferir el tar a VM1 (opción "push" desde VM2)

```bash
# En VM2: enviar a VM1
scp /ruta/a/db-artifacts-clean.tar.gz usuario@<IP_VM1>:/ruta/destino/

# Verificar SHA en VM1
sha256sum /ruta/destino/db-artifacts-clean.tar.gz
# Debe coincidir con:
# 2cd545439a85166a93ec83756c3d4581e1fbc0ab0a1ade9cdbbaf814a787988c
```

Opción alternativa ("pull" desde VM1 — recomendada si push falla)

```bash
# En VM1: bajar desde VM2
scp usuario@<IP_VM2>:/ruta/a/db-artifacts-clean.tar.gz /ruta/local/
sha256sum /ruta/local/db-artifacts-clean.tar.gz
```

E. Crear README de cambios/rollback en VM2 (este archivo)

Ejemplo de contenido (ya incluido en este README):

- Backup antes de cambios: `/var/backups/tienda/tienda_before_bindchange_YYYYMMDD_HHMMSS.sql.gz`
- Config editada: `50-server.cnf` (backup `50-server.cnf.bak.YYYYMMDD_HHMMSS`)
- Cambios aplicados: `bind-address = 0.0.0.0`
- UFW: regla permitiendo `192.168.56.10 -> 3306`
- DB: `tienda` (dump `tienda.sql`), usuario `tienda_user@'192.168.56.10'` (NO incluir contraseñas en el README)

Cómo revertir (rollback)

1) Restaurar la configuración de MariaDB

```bash
# Restaurar el archivo de configuración original
sudo cp /etc/mysql/mariadb.conf.d/50-server.cnf.bak.YYYYMMDD_HHMMSS /etc/mysql/mariadb.conf.d/50-server.cnf
sudo systemctl restart mariadb
```

2) Restaurar datos desde un backup SQL (si es necesario)

```bash
# Restaurar dump comprimido
gunzip -c /var/backups/tienda/tienda_before_bindchange_YYYYMMDD_HHMMSS.sql.gz | mysql -u root -p tienda
```

3) Quitar regla UFW (si fue añadida)

```bash
# Listar reglas y eliminar por número
sudo ufw status numbered
sudo ufw delete <número_de_regla>
```

Notas y advertencias

- No incluir contraseñas en este archivo ni en repositorios. Proporciona contraseñas a los administradores por canales seguros.
- Si la aplicación necesita que el usuario tenga permisos `CREATE` y `ALTER`, concédelos temporalmente solo para la import inicial y luego revócalos si lo deseas.
- Verifica que el usuario MySQL esté limitado por host (`'tienda_user'@'192.168.56.10'`) para reducir la superficie de ataque.

Contacto

Si necesitas, puedo:
- generar este README en el repo (ya creado)
- crear un script de verificación/transferencia automatizado
- ayudar a ejecutar cualquiera de los pasos de forma remota (si me das las instrucciones)

---

Registro de comprobaciones realizadas

- SHA del tar verificada: 2cd545439a85166a93ec83756c3d4581e1fbc0ab0a1ade9cdbbaf814a787988c
- `tienda.sql` presente (3.1 KB)
- `bind-address` aplicado en `50-server.cnf`, backup creado
- MariaDB escucha en `0.0.0.0:3306`

Siguientes pasos: verificar UFW, probar conexión desde VM1, transferir artefactos y marcar cierre.
