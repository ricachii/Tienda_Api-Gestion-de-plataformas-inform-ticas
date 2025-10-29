import os
import pymysql
from pymysql.cursors import DictCursor
from pymysql.err import MySQLError, OperationalError, IntegrityError, ProgrammingError
from dotenv import load_dotenv
from typing import Optional

# Carga variables .env (VM1)
# Espera: DB_HOST, DB_USER, DB_PASS, DB_NAME
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASS", "")
DB_NAME = os.getenv("DB_NAME", "tienda")

def get_conn() -> pymysql.connections.Connection:
    """
    Abre una conexión nueva a MySQL (VM2) usando PyMySQL.
    - DictCursor para resultados tipo dict.
    - Charset/Collation en utf8mb4.
    - Timeouts para evitar cuelgues.
    - autocommit=False para transacciones explícitas.
    """
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        cursorclass=DictCursor,
        charset="utf8mb4",
        autocommit=False,
        read_timeout=10,
        write_timeout=10,
        connect_timeout=5,
    )

def schema_has(conn, table: str, column: str, database: Optional[str] = None) -> bool:
    """
    Devuelve True si la columna existe en la tabla (para soportar esquemas mínimos/extendidos).
    """
    db = database or DB_NAME
    sql = """
        SELECT 1
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s
        LIMIT 1
    """
    with conn.cursor() as c:
        c.execute(sql, (db, table, column))
        return c.fetchone() is not None

# Exponer errores específicos por conveniencia en routes
DBError = MySQLError
DBOperationalError = OperationalError
DBIntegrityError = IntegrityError
DBProgrammingError = ProgrammingError
