Asunto: Solicitud — Aplicar DDL y GRANTS para la API "tienda"

Hola equipo DBA,

Adjunto en la máquina VM1 (usuario `rikashii`) un paquete sanitizado con los artefactos SQL que la API necesita para funcionar correctamente:

Ruta del paquete en VM1:

  /home/rikashii/db-artifacts-clean.tar.gz

SHA256 del paquete:

  2cd545439a85166a93ec83756c3d4581e1fbc0ab0a1ade9cdbbaf814a787988c

Contenido (archivos incluidos):
- create_usuarios_and_grants.sql  (script propuesto para crear `usuarios` y otorgar GRANTs mínimos)
- tienda_schema_only.sql
- tienda.sql
- README-db-for-api.md
- README-db.md
- VM1_COPY_INSTRUCTIONS.md

Pedido
------
1) Ejecutar, como administrador de la base de datos, el script `create_usuarios_and_grants.sql` en la base `tienda` de VM2 (o revisar y adaptar según políticas internas):

   -- Conexión: mysql -u root -p -h 127.0.0.1 tienda
   SOURCE /ruta/a/create_usuarios_and_grants.sql;

2) Confirmar por favor los outputs de los siguientes comandos (pueden pegarlos en la respuesta):

   DESCRIBE usuarios;
   SHOW GRANTS FOR 'tienda_user'@'192.168.56.10';
   SELECT COUNT(*) FROM usuarios;

3) Si por políticas de seguridad no deseáis ejecutar el script tal cual, por favor: indicad la DDL alternativa y qué permisos mínimos se deben otorgar a `tienda_user`.

Notas de seguridad
------------------
- El script contiene una contraseña placeholder `REPLACE_ME_PASSWORD`. No es necesario que cambiéis ese valor en el script: preferimos que creéis el usuario y la contraseña de forma segura o que nos indiquéis la política a seguir (p. ej. creación del usuario sin contraseña en el script y aplicación posterior de `ALTER USER` con REQUIRE SSL si procede).
- El paquete fue sanitizado para excluir claves privadas y ficheros de configuración.

Pasos después de aplicar los cambios (qué haremos desde VM1)
---------------------------------------------------------
Una vez confirméis que la tabla `usuarios` existe y que `tienda_user` tiene los permisos mínimos (SELECT, INSERT, UPDATE, DELETE), haremos lo siguiente en VM1:

1) Ejecutar una batería de pruebas end-to-end (creación de usuario, login, pago/checkout) para validar integridad transaccional.
2) Si todo pasa, instalaremos la unit systemd en VM1 y configuraremos el servicio uvicorn para que arranque en boot.

Contacto y entrega
------------------
- El paquete está en VM1: `/home/rikashii/db-artifacts-clean.tar.gz`.
- Si preferís que os envíe el contenido por otro canal (ticket, SFTP a un host interno, etc.), indicad destino y lo envio.

Gracias y quedo atento a los resultados.

--
Equipo API / Operaciones
ruta: /home/rikashii/tienda-api/docs/db/
Fecha: 2025-11-04
