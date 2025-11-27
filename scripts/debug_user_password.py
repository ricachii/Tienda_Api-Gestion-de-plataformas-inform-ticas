#!/usr/bin/env python3
"""
Imprime los datos actuales del usuario (hash/salt) para depurar problemas de login.

Uso:
    python scripts/debug_user_password.py --email nricciardi2021@udec.cl
"""
from __future__ import annotations

import argparse
from binascii import hexlify

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_MODULE = ROOT / "app" / "backend" / "db.py"
spec = importlib.util.spec_from_file_location("app_backend_db", DB_MODULE)
db = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(db)  # type: ignore[arg-type]
get_conn = db.get_conn  # type: ignore[attr-defined]


def fetch_user(email: str):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, password_hash, salt, IFNULL(password_reset_required,0) as reset FROM usuarios WHERE email=%s",
                (email,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def fmt(value):
    if value is None:
        return "None"
    if isinstance(value, (bytes, bytearray, memoryview)):
        data = bytes(value)
        return f"{data.hex()} (len={len(data)})"
    return f"{value} (type={type(value).__name__})"


def main() -> None:
    parser = argparse.ArgumentParser(description="Dump hash/salt info for an email.")
    parser.add_argument("--email", required=True)
    args = parser.parse_args()

    row = fetch_user(args.email)
    if not row:
        print("Usuario no encontrado.")
        return
    print(f"id: {row['id']}")
    print(f"email: {row['email']}")
    print(f"password_hash: {fmt(row['password_hash'])}")
    print(f"salt: {fmt(row['salt'])}")
    print(f"password_reset_required: {row['reset']}")


if __name__ == "__main__":
    main()
