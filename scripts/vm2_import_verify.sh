#!/usr/bin/env bash
# Ejecutar en VM2. Comprueba UFW, muestra bind-address, verifica presencia de tienda.sql, e importa si se indica.
set -euo pipefail

# Opciones:
# -i : importar /tmp/tienda.sql en la BD 'tienda' (requiere credenciales MySQL)
# -s : mostrar sha256 del tar /tmp/db-artifacts-clean.tar.gz

IMPORT=false
SHOW_SHA=false
while getopts "is" opt; do
  case ${opt} in
    i) IMPORT=true ;;
    s) SHOW_SHA=true ;;
    *) echo "Uso: $0 [-i] [-s]"; exit 2 ;;
  esac
done

echo "1) UFW status (si está disponible):"
if command -v ufw >/dev/null 2>&1; then
  sudo ufw status verbose || true
else
  echo "UFW no está instalado o no está disponible. Comprueba iptables/firewalld si procede."
fi

echo

echo "2) Mostrar bind-address en 50-server.cnf (si existe):"
if [ -f /etc/mysql/mariadb.conf.d/50-server.cnf ]; then
  sudo grep -n "bind-address" /etc/mysql/mariadb.conf.d/50-server.cnf || true
else
  echo "No se encontró /etc/mysql/mariadb.conf.d/50-server.cnf"
fi

echo

echo "3) Verificando presencia de /tmp/tienda.sql y tamaño:" 
if [ -f /tmp/tienda.sql ]; then
  ls -lh /tmp/tienda.sql
else
  echo "/tmp/tienda.sql no encontrado. Coloca el dump en /tmp o cambia la ruta."
fi

echo

if [ "${SHOW_SHA}" = true ]; then
  if [ -f /tmp/db-artifacts-clean.tar.gz ]; then
    echo "SHA256 local del tar:"
    sha256sum /tmp/db-artifacts-clean.tar.gz
    echo "Comparar con: 2cd545439a85166a93ec83756c3d4581e1fbc0ab0a1ade9cdbbaf814a787988c"
  else
    echo "No se encontró /tmp/db-artifacts-clean.tar.gz"
  fi
fi

echo

if [ "${IMPORT}" = true ]; then
  if [ -f /tmp/tienda.sql ]; then
    echo "Importando /tmp/tienda.sql en la base 'tienda' (se usará root)
    Introduce la contraseña de MySQL root cuando se solicite." 
    mysql -u root -p tienda < /tmp/tienda.sql
    echo "Importación finalizada. Mostrar tablas:" 
    mysql -u root -p -e "USE tienda; SHOW TABLES;"
  else
    echo "/tmp/tienda.sql no encontrado: no se puede importar."
    exit 1
  fi
fi

echo "4) Mostrar grants del usuario tienda_user (si existe):"
mysql -u root -p -e "SHOW GRANTS FOR 'tienda_user'@'192.168.56.10';" || echo "No se pudo mostrar grants (usuario/host puede no existir)"

echo "Operación completada. Revisa los logs si hay errores: sudo journalctl -u mariadb --no-pager | tail -n 200"
