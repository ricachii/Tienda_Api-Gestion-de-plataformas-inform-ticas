# Auditoría y limpieza después de marcar usuarios para reset

Este documento contiene pasos recomendados para auditar los cambios, limpiar tokens expirados y rotar credenciales si fue necesario.

1) Verificar usuarios marcados

```sql
SELECT id, email, rol, password_reset_required FROM usuarios WHERE password_reset_required = 1;
```

2) Limpiar tokens expirados (ejecutar periódicamente)

```sql
DELETE FROM password_resets WHERE used = 1 OR expires_at < UTC_TIMESTAMP();
```

3) Auditoría: registrar operador

Crear tabla `audit_actions` y añadir una fila cuando se ejecuten marcas masivas:

```sql
CREATE TABLE IF NOT EXISTS audit_actions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  operator VARCHAR(100),
  action VARCHAR(255),
  details TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO audit_actions (operator, action, details) VALUES ('db_admin','mark_password_reset','marked ids: 1,2,3,7,8');
```

4) Limpieza de artefactos temporales

- Revisar `/tmp` y borrar ficheros temporales relacionados con pruebas si no son necesarios.

5) Rotación de credenciales (si se usaron passwords en texto en scripts)

- Si se pusieron passwords en archivos o variables de entorno visibles, rotar las credenciales y actualizar `.env`.

6) Monitorización

- Añadir job cron/CI para ejecutar la eliminación de tokens expirados periódicamente.
