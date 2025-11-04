-- Fix/normalize `usuarios` table so it matches what the API expects.
-- Run this as a DBA (root@mysql) against the `tienda` database in VM2.
-- This script is written to be safe for existing data: new columns are added NULLABLE
-- so it won't fail for existing rows. After you apply it, the API can insert new users.

ALTER TABLE usuarios
  ADD COLUMN IF NOT EXISTS nombre VARCHAR(100) NULL AFTER email,
  ADD COLUMN IF NOT EXISTS salt VARBINARY(32) NULL AFTER password_hash;

-- Ensure password_hash has sufficient length and binary type expected by the app
ALTER TABLE usuarios
  MODIFY COLUMN password_hash VARBINARY(128) NOT NULL;

-- Ensure role default is 'user' (app expects 'user'/'admin')
ALTER TABLE usuarios
  MODIFY COLUMN rol VARCHAR(32) NOT NULL DEFAULT 'user';

-- Create unique index on email if it doesn't exist
ALTER TABLE usuarios
  ADD UNIQUE KEY IF NOT EXISTS uq_usuarios_email (email);

-- Notes:
-- 1) Existing users (seeded rows) will keep existing password_hash values and NULL salt.
--    Those users won't be able to login until a proper salt/hash is set for them,
--    or until you reset their passwords.
-- 2) After this migration new users created by the API will have proper salt and hash.
-- 3) If you prefer to enforce NOT NULL on nombre/salt for new rows, you can later:
--      ALTER TABLE usuarios MODIFY nombre VARCHAR(100) NOT NULL;
--      ALTER TABLE usuarios MODIFY salt VARBINARY(32) NOT NULL;
--    but first ensure existing rows are populated.

-- End of script
