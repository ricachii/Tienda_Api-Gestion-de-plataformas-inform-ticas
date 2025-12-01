#!/usr/bin/env bash
# Ejecutar en VM1. Comprueba conectividad a VM2, lista tablas y (opcional) descarga el tar.
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Uso: $0 <IP_VM2> <USUARIO_DB> [DEST_DIR]"
  echo "Ejemplo: $0 192.168.56.20 tienda_user /tmp"
  exit 2
fi

IP_VM2=$1
DB_USER=$2
DEST_DIR=${3:-/tmp}

echo "1) Verificando puerto 3306 en ${IP_VM2}..."
# Requiere nc (netcat) instalado; si no, usar 'timeout 1 bash -c "</dev/tcp/${IP_VM2}/3306"' (bash TCP) 
if command -v nc >/dev/null 2>&1; then
  nc -zv ${IP_VM2} 3306 || { echo "Puerto 3306 cerrado o inaccesible"; exit 1; }
else
  # intento con bash native (puede fallar en algunas shells)
  timeout 1 bash -c "</dev/tcp/${IP_VM2}/3306" 2>/dev/null || { echo "Puerto 3306 cerrado o inaccesible (nc no instalado)"; exit 1; }
fi

echo "2) Intentando listar tablas (te pedirá contraseña de ${DB_USER})..."
mysql -u ${DB_USER} -p -h ${IP_VM2} -P 3306 -e "USE tienda; SHOW TABLES;"

echo "3) (Opcional) Descargar tar 'db-artifacts-clean.tar.gz' desde VM2 al directorio ${DEST_DIR}"
read -p "¿Deseas descargar el tar desde VM2? (y/N): " yn
if [[ "${yn,,}" == "y" || "${yn,,}" == "yes" ]]; then
  read -p "Usuario SSH en VM2 (ej: usuario): " SSH_USER
  scp ${SSH_USER}@${IP_VM2}:/tmp/db-artifacts-clean.tar.gz ${DEST_DIR}/ || { echo "scp falló"; exit 1; }
  echo "Archivo descargado en ${DEST_DIR}/db-artifacts-clean.tar.gz"
  echo "Verificando SHA256..."
  sha256sum ${DEST_DIR}/db-artifacts-clean.tar.gz
  echo "Compara el SHA con: 2cd545439a85166a93ec83756c3d4581e1fbc0ab0a1ade9cdbbaf814a787988c"
fi

echo "Hecho. Si la lista de tablas devolvió resultados, la importación/permisos están OK."
