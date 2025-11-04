#!/usr/bin/env python3
"""Script para limpiar tokens expirados o usados en la tabla password_resets.
Se puede ejecutar via cron o systemd timer.
"""
import os
from app.db import get_conn

def cleanup():
    conn = get_conn()
    try:
        with conn.cursor() as c:
            c.execute("DELETE FROM password_resets WHERE used = 1 OR expires_at < UTC_TIMESTAMP()")
            deleted = c.rowcount
        conn.commit()
        print(f"cleanup: deleted {deleted} rows")
    finally:
        conn.close()

if __name__ == '__main__':
    cleanup()
