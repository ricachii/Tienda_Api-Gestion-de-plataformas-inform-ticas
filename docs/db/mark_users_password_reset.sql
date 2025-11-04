-- mark_users_password_reset.sql
-- Marca los usuarios identificados para forzar restablecimiento de contraseña
-- Uso: ejecutar como root o usuario con privilegios sobre la base `tienda`

-- (opcional) crear columna si no existe
ALTER TABLE usuarios
ADD COLUMN IF NOT EXISTS password_reset_required TINYINT(1) NOT NULL DEFAULT 0;

-- Marcar usuarios detectados (IDs confirmados por auditoría)
UPDATE usuarios SET password_reset_required = 1 WHERE id IN (1,2,3,7,8);

-- Comprobar
SELECT id, email, rol, password_reset_required FROM usuarios WHERE id IN (1,2,3,7,8);

-- (opcional) crear tabla de tokens de reseteo si se va a usar el flujo
CREATE TABLE IF NOT EXISTS password_resets (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  token VARCHAR(128) NOT NULL UNIQUE,
  expires_at DATETIME NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
