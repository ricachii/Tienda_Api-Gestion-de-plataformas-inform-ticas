#!/usr/bin/env bash
# Ejecutar en VM1. Descarga el tar desde VM2, verifica SHA y prueba la conexión MySQL.
set -euo pipefail

if [ "$#" -lt 3 ]; then
  echo "Uso: $0 <IP_VM2> <SSH_USER_VM2> <DB_USER> [DEST_DIR]"
  echo "Ejemplo: $0 192.168.56.20 usuario tienda_user /tmp"
  exit 2
fi

IP_VM2=$1
SSH_USER=$2
DB_USER=$3
DEST_DIR=${4:-/tmp}
EXPECTED_SHA="2cd545439a85166a93ec83756c3d4581e1fbc0ab0a1ade9cdbbaf814a787988c"

TAR_REMOTE_PATH="/tmp/db-artifacts-clean.tar.gz"
TAR_LOCAL_PATH="${DEST_DIR}/db-artifacts-clean.tar.gz"

echo "1) Intentando descargar ${TAR_REMOTE_PATH} desde ${SSH_USER}@${IP_VM2}..."
scp ${SSH_USER}@${IP_VM2}:${TAR_REMOTE_PATH} ${DEST_DIR}/ || { echo "scp falló o archivo no existe"; }

if [ -f "${TAR_LOCAL_PATH}" ]; then
  echo "Archivo descargado: ${TAR_LOCAL_PATH}"
  echo "SHA256 local:" $(sha256sum ${TAR_LOCAL_PATH})
  echo "Comparar con esperado: ${EXPECTED_SHA}"
else
  echo "No se descargó el tar; revisa ruta y permisos en VM2." 
fi

echo

echo "2) Probar conexión MySQL y listar tablas (se pedirá contraseña de ${DB_USER})..."
mysql -u ${DB_USER} -p -h ${IP_VM2} -P 3306 -e "USE tienda; SHOW TABLES;"

echo "3) (Opcional) Extraer y verificar contenido del tar local si existe"
if [ -f "${TAR_LOCAL_PATH}" ]; then
  mkdir -p ${DEST_DIR}/db-artifacts-check
  tar -xzf ${TAR_LOCAL_PATH} -C ${DEST_DIR}/db-artifacts-check || echo "tar falló o contenido inesperado"
  echo "Contenido extraído en ${DEST_DIR}/db-artifacts-check"
fi

echo "Operación completada. Si la lista de tablas devolvió resultados, la import/permisos están OK."