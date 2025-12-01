"""
Helper para lanzar uvicorn asegurando que los assets del frontend estén sincronizados.
Usa app/main.py pero permite servir el contenido desde `dist/` si existe,
lo que evita mezclar archivos con node_modules o pruebas locales.
"""

from __future__ import annotations

import os
import shutil
import sys
import atexit
import signal
import subprocess
from pathlib import Path

import uvicorn

REPO_ROOT = Path(__file__).resolve().parent
FRONTEND_SRC = REPO_ROOT / "app" / "frontend"
FRONTEND_DIST = REPO_ROOT / "dist"
PID_FILE = Path("/tmp/tienda_uvicorn.pid")
PORT = int(os.getenv("UVICORN_PORT", "8000"))


def sync_frontend() -> Path:
    """
    Copia los archivos necesarios desde app/frontend hacia dist/.
    Se excluyen node_modules y resultados de pruebas para evitar copiar miles de archivos.
    """
    if not FRONTEND_SRC.exists():
        return FRONTEND_SRC

    FRONTEND_DIST.mkdir(parents=True, exist_ok=True)

    for name in ("index.html",):
        src = FRONTEND_SRC / name
        if src.exists():
            shutil.copy2(src, FRONTEND_DIST / name)

    for folder in ("css", "js"):
        src_dir = FRONTEND_SRC / folder
        if not src_dir.exists():
            continue
        dest_dir = FRONTEND_DIST / folder
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        shutil.copytree(src_dir, dest_dir)

    return FRONTEND_DIST


def kill_previous_pid():
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            os.kill(old_pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except Exception:
            pass
        finally:
            PID_FILE.unlink(missing_ok=True)


def kill_processes_on_port(port: int):
    commands = [
        ["bash", "-lc", f"fuser -k {port}/tcp"],
        ["bash", "-lc", f"lsof -ti tcp:{port} | xargs -r kill"],
        ["bash", "-lc", "pkill -f 'uvicorn app.backend.main'"],
    ]
    for cmd in commands:
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        except FileNotFoundError:
            continue


def main():
    kill_previous_pid()
    kill_processes_on_port(PORT)
    frontend_dir = sync_frontend()
    os.environ["FRONTEND_DIR"] = str(frontend_dir)

    # Cargar app una vez que el path está configurado
    sys.path.insert(0, str(REPO_ROOT))
    from app.backend.main import app

    PID_FILE.write_text(str(os.getpid()))

    def cleanup():
        PID_FILE.unlink(missing_ok=True)

    atexit.register(cleanup)

    uvicorn.run(app, host="127.0.0.1", port=PORT)


if __name__ == "__main__":
    main()
