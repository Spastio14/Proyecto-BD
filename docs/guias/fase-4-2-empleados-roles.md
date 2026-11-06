# Fase 4.2 — autenticación, empleados, roles y dashboards

Esta guía distingue los pasos locales de las operaciones que requieren una
autorización separada para Supabase remoto. La implementación no añade tablas,
no modifica las cinco migraciones aprobadas y no convierte clientes en
empleados.

## Diagnóstico del registro

El backend interpreta los códigos oficiales que Supabase Auth incluye en
`code` o `error_code`. Distingue contraseña débil, registro deshabilitado,
correo no autorizado, correo sin confirmar, límites de envío, HTTP 429,
credenciales inválidas, fallos de red y respuestas incompatibles.

Los logs internos guardan operación, HTTP y código de error. No guardan correo,
contraseña, token, clave ni cuerpo completo. Para evitar enumerar cuentas, un
correo ya utilizado recibe el mismo mensaje neutral tanto si Supabase responde
`email_exists` como si devuelve un usuario ofuscado sin identidades.

Una respuesta correcta con `confirmation_sent_at` crea el vínculo comercial y
mantiene la confirmación por correo. Si Auth quedó creado sin PERSONA, CLIENTE y
CUENTA_ACCESO, el usuario debe confirmar el correo, iniciar sesión y usar
`POST /api/v1/auth/completar-registro`. El JWT verificado aporta `sub` y correo;
conocer una dirección no permite crear el vínculo.

## Roles instalados

`database/seeds/003_roles_permisos_fase_4_2.sql` contiene únicamente DML
idempotente. Define ADMINISTRADOR, CONTADOR, VENDEDOR y PRODUCCION, además de
permisos separados para consultar, registrar y autorizar compras; consultar y
gestionar proveedores; inventario; pagos; pérdidas; reportes y empleados.

Validación local:

```bash
./database/tests/run.sh
./backend/tests/run.sh
```

Para una base Docker local ya creada:

```bash
docker exec -i s2r-demo psql -U postgres -d sublimacion2r \
  -v ON_ERROR_STOP=1 < database/seeds/003_roles_permisos_fase_4_2.sql
```

Aplicar este archivo al PostgreSQL remoto cambia permisos efectivos y requiere
autorización explícita del propietario. La aplicación no lo ejecuta al iniciar.

## Inicialización única del primer administrador

No existe un endpoint público para elevar privilegios. El comando manual:

1. recibe el UUID de una identidad Auth elegida por el propietario;
2. consulta esa identidad mediante la API administrativa de Supabase;
3. obtiene y compara su correo verificado;
4. rechaza la operación si la identidad o el correo pertenecen a CLIENTE;
5. crea de forma idempotente PERSONA, EMPLEADO, CUENTA_ACCESO y ASIGNACION_ROL;
6. registra auditoría.

Antes de ejecutarlo deben estar configuradas `DATABASE_URL`,
`SUPABASE_URL`, `SUPABASE_PROJECT_REF`, `SUPABASE_PUBLIC_KEY` y
`SUPABASE_SECRET_KEY` sólo en `backend/.env`. El rol y permisos de Fase 4.2 deben
existir en esa misma base.

Desde Git Bash:

```bash
cd backend
read -rsp "UUID Auth verificado del primer administrador: " ADMIN_AUTH_SUB; echo
uv run python -m app.commands.bootstrap_admin \
  --auth-user-id "$ADMIN_AUTH_SUB" \
  --names "Nombre del propietario" \
  --employee-code "EMP-ADMIN-001" \
  --confirm
unset ADMIN_AUTH_SUB
```

El comando se detiene si falta `--confirm`. No solicita contraseña, no imprime
tokens y no transforma la cuenta actual de un cliente. Ejecutarlo con
`DATABASE_URL` remota y claves del proyecto realiza escrituras remotas en Auth
y PostgreSQL; este repositorio sólo lo prepara y no lo ha ejecutado.

## Invitación y activación de empleados

Un ADMINISTRADOR autenticado abre `/app/admin/?view=employees`, introduce los
datos y selecciona un rol cargado desde la API. FastAPI verifica
`EMPLEADO_GESTIONAR`, crea un perfil EMPLEADO inactivo y llama a
`POST /auth/v1/invite` desde el servidor con la clave privada.

El administrador nunca define la contraseña. La persona usa el enlace recibido,
Supabase establece una sesión y `/app/activar-empleado/` envía ese JWT a
`POST /api/v1/auth/activar-empleado`. Sólo entonces el perfil pasa a ACTIVO.

La URL configurada en `EMPLOYEE_INVITE_REDIRECT_URL` debe aparecer también en
la lista de redirect URLs permitidas de Supabase Auth. Para desarrollo local es
`http://127.0.0.1:8000/app/activar-empleado/`; un despliegue debe usar su origen
HTTPS exacto. Cambiar esa lista remota requiere autorización del propietario.

Si falla el correo, el perfil queda INACTIVO y sin privilegios. Si Auth alcanzó
a crear la identidad pero la respuesta se perdió, el empleado puede iniciar
sesión y completar la activación: el backend exige un JWT válido y una
invitación inactiva cuyo correo verificado coincide. Un correo escrito en un
formulario no sirve como prueba.

## SMTP para varias cuentas de demostración

El servicio de correo incorporado de Supabase tiene límites pensados para
pruebas y puede devolver `over_email_send_rate_limit`. No se debe resolver
desactivando permanentemente la confirmación.

Para varias invitaciones durante la presentación, el propietario puede
configurar un proveedor SMTP compatible desde el panel de Supabase Auth. Host,
puerto, usuario y contraseña se guardan en Supabase, nunca en Git ni en el
frontend. Esta configuración es externa, puede tener costo y no se realiza sin
autorización. Después se conserva la confirmación de correo y se prueba con
direcciones ficticias controladas.

## Resolución del dashboard

Después del login y al restaurar `sessionStorage`, el frontend consulta
`GET /api/v1/auth/me`. El endpoint verifica el JWT y devuelve persona, perfil,
roles activos, permisos efectivos, estado y dashboard inicial.

Prioridad cuando existen varios roles: ADMINISTRADOR, CONTADOR, VENDEDOR y
PRODUCCION. La prioridad sólo elige la interfaz; cada endpoint vuelve a consultar
permisos en PostgreSQL. Cambiar una asignación afecta la siguiente petición.

| Perfil | Ruta inicial |
|---|---|
| Cliente | `/app/cliente/` |
| Administrador | `/app/admin/` |
| Contador | `/app/contabilidad/` |
| Vendedor | `/app/ventas/` |
| Producción/diseño | `/app/produccion/` |

La página pública no ofrece un selector de empleado. Un visitante puede descargar
los archivos estáticos de una ruta, pero sin JWT no obtiene datos: todas las APIs
protegidas responden 401 y el JavaScript vuelve al acceso público.

## Operaciones remotas pendientes de autorización

La implementación local está lista, pero no se hicieron estas acciones:

- aplicar `003_roles_permisos_fase_4_2.sql` al PostgreSQL Supabase;
- configurar SMTP propio;
- ejecutar `bootstrap_admin` contra la base y Auth remotos;
- enviar invitaciones reales;
- modificar o eliminar usuarios existentes.

Cada acción debe autorizarse y verificarse por separado. Ninguna requiere una
sexta migración ni un despliegue automático.
