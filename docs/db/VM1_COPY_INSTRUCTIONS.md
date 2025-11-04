INSTRUCCIONES PARA VM1 — Cómo obtener el paquete desde VM2

Este archivo acompaña al paquete `db-artifacts-clean.tar.gz` y explica cómo traerlo desde VM2.

1) Desde VM1, crear directorio destino del repo (si no existe):

mkdir -p ~/repo/docs/db

2) Copiar el paquete desde VM2 (ejecutar en VM1). Sustituye vm2_user y IP_VM2:

scp -p vm2_user@IP_VM2:/home/rikashii/db-artifacts-clean.tar.gz ~/repo/docs/db/

3) Verificar suma SHA256 localmente (comparar con la que os pase el equipo de operaciones):

sha256sum ~/repo/docs/db/db-artifacts-clean.tar.gz

4) Descomprimir y revisar contenido:

cd ~/repo/docs/db
tar -xzf db-artifacts-clean.tar.gz
ls -lah

5) Entregar a DBA: mover `create_usuarios_and_grants.sql` a un área segura o pasarlo por ticket/Canal interno.

NOTA: No ejecutar scripts sin revisión. `create_usuarios_and_grants.sql` contiene un placeholder para contraseña (`REPLACE_ME_PASSWORD`). Preferible que el DBA cree el usuario y establezca contraseña con política interna o aplique `ALTER USER`.
