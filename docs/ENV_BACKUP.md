Se han movido los entornos virtuales locales fuera del repositorio para limpiar el árbol y liberar espacio.

Ubicación de backup:

- ~/tienda-env-backups/.venv
- ~/tienda-env-backups/venv

Cómo restaurar temporalmente (por ejemplo, para debug local):

1. Copiar de vuelta al repositorio (desde la raíz del repo):

   mv ~/tienda-env-backups/.venv ./
   mv ~/tienda-env-backups/venv ./

2. Re-activar el entorno:

   source .venv/bin/activate  # o venv/bin/activate según corresponda

Notas:
- Mantener estos backups fuera del repo evita subir dependencias binarias grandes.
- Si no necesitas conservarlos, puedes borrar `~/tienda-env-backups/` tras verificar que todo funciona.
- Para reproducibilidad, prefiere mantener y actualizar `requirements.txt` en lugar de versionar entornos.
