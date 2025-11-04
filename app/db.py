import os
from typing import Optional, Tuple, Any, Dict

import pymysql
from pymysql.cursors import DictCursor
from pymysql.err import MySQLError, OperationalError, IntegrityError, ProgrammingError
from dotenv import load_dotenv
import hashlib
import secrets
import queue
import threading
import time
import smtplib
from email.message import EmailMessage
from datetime import datetime, timezone, timedelta

# Cargar variables de entorno preferentemente desde el archivo `app/.env` (si existe),
# y luego cargar cualquier `.env` en el directorio de trabajo como fallback.
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASS", "")
DB_NAME = os.getenv("DB_NAME", "tienda")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
# Ruta opcional al CA para conexión SSL (si VM2 exige REQUIRE SSL)
DB_SSL_CA = os.getenv("DB_SSL_CA", "")

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "0") or 0)
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "no-reply@tienda.local")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:8000/app")

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change")
JWT_EXPIRE_MIN = int(os.getenv("JWT_EXPIRE_MIN", "60"))

# Connection pool (simple, local, thread-safe)
POOL_MAX = int(os.getenv("DB_POOL_MAX", "8"))
POOL_MIN = int(os.getenv("DB_POOL_MIN", "1"))
_pool_lock = threading.Lock()
_conn_pool: "queue.Queue[pymysql.connections.Connection]" = queue.Queue(maxsize=POOL_MAX)


def _create_raw_conn():
    # Construir argumentos SSL si se proporcionó CA
    ssl_args = None
    if DB_SSL_CA:
        # pymysql espera un dict con clave 'ca' apuntando al archivo PEM
        ssl_args = {"ca": DB_SSL_CA}

    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        port=DB_PORT,
        cursorclass=DictCursor,
        autocommit=False,
        charset="utf8mb4",
        ssl=ssl_args,
    )


def _init_pool():
    with _pool_lock:
        # fill pool up to POOL_MIN
        while _conn_pool.qsize() < POOL_MIN:
            try:
                _conn_pool.put(_create_raw_conn(), block=False)
            except Exception:
                break


# Initialize pool lazily
_init_pool()

# ----------------------------
# Conexión MySQL (VM2)
# ----------------------------
def get_conn(timeout: float = 5.0):
    """
    Obtener una conexión desde el pool (si está disponible) o crear una nueva.
    Devuelve una conexión que debe cerrarse por quien la recibe (conn.close()).
    """
    try:
        conn = _conn_pool.get(block=True, timeout=timeout)
        # test connection
        try:
            with conn.cursor() as c:
                c.execute("SELECT 1")
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            conn = _create_raw_conn()
        return _PooledConnection(conn)
    except queue.Empty:
        # pool agotado, crear conexión temporal
        raw = _create_raw_conn()
        return _PooledConnection(raw)


class _PooledConnection:
    """Wrapper que devuelve la conexión al pool cuando se cierra."""
    def __init__(self, conn: pymysql.connections.Connection):
        self._conn = conn

    def __getattr__(self, item):
        return getattr(self._conn, item)

    def close(self):
        # en lugar de cerrar, intentamos devolver al pool
        try:
            if self._conn.open:
                # rollback cualquier transacción abierta
                try:
                    self._conn.rollback()
                except Exception:
                    pass
                try:
                    _conn_pool.put(self._conn, block=False)
                    return
                except Exception:
                    pass
            self._conn.close()
        except Exception:
            pass

# ----------------------------
# Utilidades de esquema
# ----------------------------
def ensure_schema():
    conn = get_conn()
    try:
        with conn.cursor() as c:
            c.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(120) NOT NULL UNIQUE,
                nombre VARCHAR(100) NOT NULL,
                password_hash VARBINARY(128) NOT NULL,
                salt VARBINARY(32) NOT NULL,
                rol ENUM('user','admin') NOT NULL DEFAULT 'user',
                creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            # asegurar columna password_reset_required si no existe
            c.execute("""
            ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS password_reset_required TINYINT(1) NOT NULL DEFAULT 0;
            """)
        conn.commit()
    finally:
        conn.close()

def schema_has(table: str, column: Optional[str] = None, db: Optional[str] = None) -> bool:
    conn = get_conn()
    try:
        with conn.cursor() as c:
            if column:
                c.execute(
                    "SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s LIMIT 1",
                    (db or DB_NAME, table, column),
                )
            else:
                c.execute(
                    "SELECT 1 FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s LIMIT 1",
                    (db or DB_NAME, table),
                )
            return c.fetchone() is not None
    finally:
        conn.close()

# ----------------------------
# Password hashing (PBKDF2)
# ----------------------------
def hash_password(password: str, salt: Optional[bytes] = None) -> Tuple[bytes, bytes]:
    if salt is None:
        salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000, dklen=32)
    return dk, salt

def verify_password(password: str, password_hash: bytes, salt: bytes) -> bool:
    dk, _ = hash_password(password, salt)
    return secrets.compare_digest(dk, password_hash)

# ----------------------------
# Helpers de usuario
# ----------------------------
def create_user(email: str, nombre: str, password: str, rol: str = "user") -> int:
    conn = get_conn()
    try:
        pwd, salt = hash_password(password)
        # Map application role names to the DB's allowed values.
        # The production DB uses ('admin','cliente','staff') for `rol`.
        role_map = {"user": "cliente", "admin": "admin"}
        db_rol = role_map.get(rol, rol)

        with conn.cursor() as c:
            sql = (
                "INSERT INTO usuarios (email, nombre, password_hash, salt, rol) "
                "VALUES (%s, %s, %s, %s, %s)"
            )
            params = (email, nombre, pwd, salt, db_rol)
            c.execute(sql, params)
            user_id = c.lastrowid
        conn.commit()
        return user_id
    finally:
        conn.close()

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        with conn.cursor() as c:
            c.execute("SELECT * FROM usuarios WHERE email=%s LIMIT 1", (email,))
            row = c.fetchone()
        # Map DB role values to application roles for backwards compatibility
        if row and 'rol' in row:
            row['rol'] = _map_db_role_to_app(row['rol'])
        return row
    finally:
        conn.close()

def get_user_by_id(uid: int) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        with conn.cursor() as c:
            c.execute("SELECT * FROM usuarios WHERE id=%s LIMIT 1", (uid,))
            row = c.fetchone()
        if row and 'rol' in row:
            row['rol'] = _map_db_role_to_app(row['rol'])
        return row
    finally:
        conn.close()


def _map_db_role_to_app(db_role: str) -> str:
    """Mapear valores de rol de la base de datos a los valores esperados por la API.

    DB uses ('admin','cliente','staff'). API expects 'admin' or 'user'.
    """
    mapping = {
        'cliente': 'user',
        'admin': 'admin',
        'staff': 'admin',
    }
    return mapping.get(db_role, db_role)


# ----------------------------
# Password reset helpers
# ----------------------------
def ensure_password_resets_table():
    conn = get_conn()
    try:
        with conn.cursor() as c:
            # token_hash en lugar de token para no guardar el token en texto plano
            c.execute("""
            CREATE TABLE IF NOT EXISTS password_resets (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                token_hash VARCHAR(128) NOT NULL,
                expires_at DATETIME NOT NULL,
                used TINYINT(1) NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES usuarios(id) ON DELETE CASCADE,
                UNIQUE KEY uq_token_hash (token_hash)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
        conn.commit()
    finally:
        conn.close()


def create_password_reset_token(user_id: int, ttl_minutes: int = 60) -> str:
    """Crear y guardar un token de reseteo en DB. Devuelve el token.
    El token es una cadena segura y corta (hex).
    """
    ensure_password_resets_table()
    token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_dt = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
    expires_at = expires_dt.strftime('%Y-%m-%d %H:%M:%S')
    conn = get_conn()
    try:
        with conn.cursor() as c:
            c.execute(
                "INSERT INTO password_resets (user_id, token_hash, expires_at) VALUES (%s, %s, %s)",
                (user_id, token_hash, expires_at),
            )
        conn.commit()
        return token
    finally:
        conn.close()


def verify_password_reset_token(token: str) -> Optional[Dict[str, Any]]:
    """Verifica si el token existe y no ha expirado. Devuelve fila con user_id si OK."""
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    conn = get_conn()
    try:
        with conn.cursor() as c:
            c.execute(
                "SELECT id, user_id, token_hash, expires_at, used FROM password_resets WHERE token_hash=%s LIMIT 1",
                (token_hash,),
            )
            row = c.fetchone()
        if not row:
            return None
        if row.get("used"):
            return None
        # comprobar expiración
        expires = row["expires_at"]
        try:
            expires_dt = datetime.strptime(str(expires), '%Y-%m-%d %H:%M:%S')
            expires_dt = expires_dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None
        if datetime.now(timezone.utc) > expires_dt:
            # token expirado; limpiar
            try:
                with conn.cursor() as c:
                    c.execute("DELETE FROM password_resets WHERE id=%s", (row['id'],))
                conn.commit()
            except Exception:
                pass
            return None
        return row
    finally:
        conn.close()


def consume_password_reset_token(token: str, new_password: str) -> bool:
    """Verifica token y actualiza contraseña del usuario. Retorna True si aplicado."""
    row = verify_password_reset_token(token)
    if not row:
        return False
    user_id = row['user_id']
    # generar hash nuevo
    pwd, salt = hash_password(new_password)

    conn = get_conn()
    try:
        with conn.cursor() as c:
            c.execute(
                "UPDATE usuarios SET password_hash=%s, salt=%s, password_reset_required=0 WHERE id=%s",
                (pwd, salt, user_id),
            )
            c.execute("UPDATE password_resets SET used=1 WHERE id=%s", (row['id'],))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def send_reset_email(to_email: str, to_name: str, token: str) -> bool:
    """Enviar email con enlace de reseteo. Requiere variables SMTP configuradas en env.
    Retorna True si se envió, False en caso de error o si SMTP no está configurado.
    """
    if not SMTP_HOST or not SMTP_PORT:
        return False
    reset_link = f"{FRONTEND_URL}/reset-password?token={token}"
    msg = EmailMessage()
    msg["Subject"] = "Restablece tu contraseña en Tienda"
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    body = f"Hola {to_name or ''},\n\nPara restablecer tu contraseña haz clic en el siguiente enlace: {reset_link}\n\nSi no solicitaste este cambio, ignora este email.\n\nGracias,\nEquipo Tienda"
    msg.set_content(body)
    try:
        s = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
        s.starttls()
        if SMTP_USER:
            s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)
        s.quit()
        return True
    except Exception:
        return False


def write_pending_token(to_email: str, token: str) -> bool:
    """Guardar token en CSV en el repo `docs/db/` para envío manual por un operador.
    Este archivo se crea con nombre `pending_reset_tokens_YYYYMMDD.csv` y se append.
    """
    try:
        from pathlib import Path
        import csv
        date = datetime.now(timezone.utc).strftime('%Y%m%d')
        outdir = Path(__file__).resolve().parent.parent / 'docs' / 'db'
        outdir.mkdir(parents=True, exist_ok=True)
        fname = outdir / f'pending_reset_tokens_{date}.csv'
        # token no se guarda en claro en BD, aquí queda como último recurso para operador
        with open(fname, 'a', newline='') as fh:
            writer = csv.writer(fh)
            writer.writerow([datetime.now(timezone.utc).isoformat(), to_email, token])
        return True
    except Exception:
        return False

# Exponer errores
DBError = MySQLError
DBOperationalError = OperationalError
DBIntegrityError = IntegrityError
DBProgrammingError = ProgrammingError

# Intentar garantizar esquema al importar
try:
    ensure_schema()
except Exception:
    # Si la DB aún no está accesible en arranque, no romper.
    pass
