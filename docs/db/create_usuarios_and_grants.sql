-- create_usuarios_and_grants.sql
-- Ejecutar como administrador MySQL/MariaDB (root@localhost).
-- Crea la tabla `usuarios` (si no existe) y otorga permisos mínimos al usuario de la app `tienda_user`.

CREATE TABLE IF NOT EXISTS usuarios (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(255) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  rol VARCHAR(32) NOT NULL DEFAULT 'cliente',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_usuarios_email (email),
  CONSTRAINT chk_usuarios_rol CHECK (rol IN ('admin','cliente','staff'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Crear/asegurar usuario de aplicación (ajusta contraseña y host según sea necesario)
-- Sustituir 'REPLACE_ME_PASSWORD' por la contraseña segura fuera de este script, o crear el usuario sin contraseña y aplicar ALTER USER posteriormente.
CREATE USER IF NOT EXISTS 'tienda_user'@'192.168.56.10' IDENTIFIED BY 'REPLACE_ME_PASSWORD';

GRANT SELECT, INSERT, UPDATE, DELETE
  ON tienda.*
  TO 'tienda_user'@'192.168.56.10';

FLUSH PRIVILEGES;

-- Variante REQUIRE SSL (descomentarlo solo si el servidor y la app están preparados):
-- ALTER USER 'tienda_user'@'192.168.56.10' REQUIRE SSL;

-- Chequeos post-aplicación (que el DBA puede ejecutar):
-- DESCRIBE usuarios;
-- SHOW GRANTS FOR 'tienda_user'@'192.168.56.10';
-- SELECT COUNT(*) FROM usuarios;
