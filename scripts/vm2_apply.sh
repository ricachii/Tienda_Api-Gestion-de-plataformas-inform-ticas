#!/usr/bin/env bash
# Ejecutar en VM2 como administrador (sudo cuando se indique).
# Automatiza: backup config, backup DB (si existe), asegurar regla UFW, importar tienda.sql si se solicita,
# mover/validar tar y generar un resumen de cambios/rollback.
set -euo pipefail

# Uso: ./scripts/vm2_apply.sh <IP_VM1> [--import] [--tar-path /ruta/a/db-artifacts-clean.tar.gz]
# Ejemplo: ./scripts/vm2_apply.sh 192.168.56.10 --import --tar-path /tmp/db-artifacts-clean.tar.gz

if [ "$#" -lt 1 ]; then
  echo "Uso: $0 <IP_VM1> [--import] [--tar-path /ruta/a/db-artifacts-clean.tar.gz]"
  exit 2
fi

IP_VM1=$1
IMPORT=false
TAR_PATH="/tmp/db-artifacts-clean.tar.gz"
shift
while [ "$#" -gt 0 ]; do
  case "$1" in
    --import) IMPORT=true; shift ;;
    --tar-path) TAR_PATH="$2"; shift 2 ;;
    *) echo "Parámetro desconocido: $1"; exit 2 ;;
  esac
done

TIMESTAMP=$(date +%F_%H%M%S)
LOG=/tmp/vm2_apply_${TIMESTAMP}.log
SUMMARY=/tmp/vm2_apply_summary_${TIMESTAMP}.md
BACKUP_DIR=/var/backups/tienda
mkdir -p "${BACKUP_DIR}"

echo "Iniciando ejecución de vm2_apply.sh - ${TIMESTAMP}" | tee "${LOG}"

# 1) Backup del archivo de configuración de MariaDB
CFG=/etc/mysql/mariadb.conf.d/50-server.cnf
if [ -f "${CFG}" ]; then
  sudo cp "${CFG}" "${CFG}.bak.${TIMESTAMP}"
  echo "Backup config: ${CFG}.bak.${TIMESTAMP}" | tee -a "${LOG}"
else
  echo "Configuración ${CFG} no encontrada." | tee -a "${LOG}"
fi

# 2) Backup de la base 'tienda' (si existe)
if mysql -u root -e "SHOW DATABASES LIKE 'tienda'" &>/dev/null; then
  echo "Haciendo dump de la base 'tienda'..." | tee -a "${LOG}"
  sudo mysqldump -u root -p tienda | gzip > "${BACKUP_DIR}/tienda_before_${TIMESTAMP}.sql.gz"
  echo "Backup DB creado en ${BACKUP_DIR}/tienda_before_${TIMESTAMP}.sql.gz" | tee -a "${LOG}"
else
  echo "Base 'tienda' no existe todavía, se omitirá backup de datos." | tee -a "${LOG}"
fi

# 3) Asegurar regla UFW
if command -v ufw >/dev/null 2>&1; then
  echo "Comprobando UFW..." | tee -a "${LOG}"
  if sudo ufw status | grep -q "Status: active"; then
    # comprobar si ya existe regla desde IP_VM1 a 3306
    if sudo ufw status | grep -q "${IP_VM1}.*3306"; then
      echo "Ya existe regla UFW para ${IP_VM1} -> 3306" | tee -a "${LOG}"
    else
      echo "Añadiendo regla UFW para ${IP_VM1} -> 3306" | tee -a "${LOG}"
      sudo ufw allow from ${IP_VM1} to any port 3306 proto tcp
    fi
  else
    echo "UFW no está activo. Si usas otro firewall, revisa manualmente." | tee -a "${LOG}"
  fi
else
  echo "UFW no instalado. Omite paso UFW." | tee -a "${LOG}"
fi

# 4) Mostrar bind-address actual
if [ -f "${CFG}" ]; then
  echo "bind-address en ${CFG}:" | tee -a "${LOG}"
  sudo grep -n "bind-address" "${CFG}" | tee -a "${LOG}" || true
fi

# 5) Mostrar y (opcional) importar tienda.sql
SQL_PATHS=("/tmp/tienda.sql" "./tienda.sql" "/home/${USER}/tienda.sql")
SQL_FOUND=""
for p in "${SQL_PATHS[@]}"; do
  if [ -f "$p" ]; then
    SQL_FOUND="$p"
    break
  fi
done

if [ -n "${SQL_FOUND}" ]; then
  echo "Encontrado dump: ${SQL_FOUND}" | tee -a "${LOG}"
else
  echo "No se encontró tienda.sql en rutas comunes." | tee -a "${LOG}"
fi

if [ "${IMPORT}" = true ]; then
  if [ -n "${SQL_FOUND}" ]; then
    echo "Importando ${SQL_FOUND} en la base 'tienda' (se pedirá contraseña root)..." | tee -a "${LOG}"
    mysql -u root -p tienda < "${SQL_FOUND}" || { echo "Error en importación" | tee -a "${LOG}"; exit 1; }
    echo "Importación completada." | tee -a "${LOG}"
  else
    echo "IMPORT solicitado pero no se encontró tienda.sql. Abortando import." | tee -a "${LOG}"
  fi
fi

# 6) Validar tar y mostrar SHA
if [ -f "${TAR_PATH}" ]; then
  echo "Archivo tar localizado en ${TAR_PATH}" | tee -a "${LOG}"
  sha256sum "${TAR_PATH}" | tee -a "${LOG}"
else
  echo "Tar no encontrado en ${TAR_PATH}." | tee -a "${LOG}"
fi

# 7) Generar resumen/rollback local (en /var/backups/tienda)
SUMMARY_FILE="${BACKUP_DIR}/VM2_CHANGES_SUMMARY_${TIMESTAMP}.md"
cat > "${SUMMARY_FILE}" <<EOF
# VM2 Changes applied - ${TIMESTAMP}

- Backup config: ${CFG}.bak.${TIMESTAMP}
- DB backup (si existía): ${BACKUP_DIR}/tienda_before_${TIMESTAMP}.sql.gz (si fue creado)
- bind-address actual: (ver ${CFG})
- UFW: regla permitiendo ${IP_VM1} -> 3306 (si UFW activo)
- Tar verificado: ${TAR_PATH}
- Dump encontrado: ${SQL_FOUND}

Rollback breve:
- Restaurar config: sudo cp ${CFG}.bak.${TIMESTAMP} ${CFG} && sudo systemctl restart mariadb
- Restaurar datos: gunzip -c ${BACKUP_DIR}/tienda_before_${TIMESTAMP}.sql.gz | mysql -u root -p tienda
EOF

echo "Resumen creado en ${SUMMARY_FILE}" | tee -a "${LOG}"

echo "FIN. Revisa ${LOG} y ${SUMMARY_FILE} para detalles." | tee -a "${LOG}"
exit 0
