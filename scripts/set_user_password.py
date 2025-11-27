#!/usr/bin/env python3
"""Forzar cambio de contraseña desde CLI."""
from __future__ import annotations

import argparse
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
DB_MODULE = ROOT / "app" / "backend" / "db.py"
spec = importlib.util.spec_from_file_location("app_backend_db", DB_MODULE)
if spec is None or spec.loader is None:
    raise RuntimeError("No se pudo importar app.backend.db")
db = importlib.util.module_from_spec(spec)
spec.loader.exec_module(db)  # type: ignore[arg-type]

def force_password(email: str, password: str) -> None:
    conn = db.get_conn()  # type: ignore[attr-defined]
    try:
        pwd, salt = db.hash_password(password)  # type: ignore[attr-defined]
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE usuarios SET password_hash=%s, salt=%s, password_reset_required=0 WHERE email=%s",
                (pwd, salt, email),
            )
            if cur.rowcount == 0:
                raise RuntimeError(f"Usuario {email} no encontrado")
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Establecer nueva contraseña para un usuario")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()
    force_password(args.email, args.password)
    print(f"Contraseña actualizada para {args.email}")


if __name__ == "__main__":
    main()
