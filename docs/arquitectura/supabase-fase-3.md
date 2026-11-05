# Integración con Supabase — Fase 3

## Estado y alcance

La integración está implementada y validada localmente en PostgreSQL 17.11.
No se enlazó el CLI, no se consultó el historial remoto y no se aplicó ninguna
migración al proyecto `SublimacionDobleR-prueba` (`iwvmbdfkxrssduoqobgy`). El
entorno actual no contiene credenciales Supabase y su política de red no permite
los dominios del proyecto ni de la API de administración.

La URL pública esperada es
`https://iwvmbdfkxrssduoqobgy.supabase.co`. Las claves pública y privada, token
del CLI, contraseña PostgreSQL y `DATABASE_URL` sólo se suministran como secretos
del entorno. Nunca se escriben en Git ni en los logs.

## Preparación de PostgreSQL y migraciones

`supabase/migrations/` conserva cinco revisiones ordenadas. Las primeras cuatro
crean y protegen las 41 tablas aprobadas. La revisión
`202611050002_supabase_auth_storage.sql` mantiene ese conteo y realiza dos cambios:

1. añade a `transaccion` una referencia opcional y coherente al comprobante:
   `ruta_comprobante`, `comprobante_mime` y `comprobante_tamano_bytes`;
2. si se ejecuta dentro de Supabase, crea o endurece los buckets `disenos` y
   `comprobantes` como privados, con límites de tamaño y MIME permitidos.

El modelo no tenía una referencia para unir un comprobante con su pago. Tres
columnas en `transaccion` son el cambio mínimo: no agregan una entidad número 42,
mantienen una relación uno a cero/uno y una restricción exige que los tres datos
estén completos o todos sean nulos. Reemplazar un comprobante queda prohibido en
el servicio para preservar evidencia; una política posterior de versionado
requeriría una decisión de modelo separada.

Antes de aplicar cambios remotos debe ejecutarse:

```bash
export SUPABASE_PROJECT_REF=iwvmbdfkxrssduoqobgy
./scripts/supabase/preflight.sh
```

El script requiere Supabase CLI 3.x, comprueba nombre, ref y estado, ejecuta
consultas SQL dentro de una transacción `--read-only`, muestra
`migration list --remote` y ejecuta `db push --remote --dry-run --skip-vault`.
No contiene `db push` real. El enlace debe usar una contraseña nueva almacenada
fuera del repositorio; no se debe recuperar ni reutilizar ninguna contraseña
expuesta anteriormente.

El estado inicial remoto de cero tablas y cero migraciones procede de las
instrucciones del propietario y sigue pendiente de verificación directa. Si el
historial remoto no está vacío o el dry-run propone borrar o reescribir objetos,
se detiene el proceso y se reconcilia antes de pedir autorización para aplicar.

## Conexión PostgreSQL

FastAPI acepta cuatro modos explícitos:

| Modo | Uso | Preparación Psycopg |
|---|---|---|
| `direct` | migraciones y tareas administrativas controladas | TLS obligatorio |
| `session_pooler` | backend persistente; opción recomendada si IPv4 o pooling gestionado es necesario | `pool_pre_ping`, reciclaje y TLS |
| `transaction_pooler` | procesos efímeros con muchas conexiones | desactiva prepared statements con `prepare_threshold=None` |
| `local` | desarrollo y pruebas desechables | permite `sslmode=prefer` |

Para conexiones remotas, la configuración rechaza `disable` y `prefer`; se usa
`require`, `verify-ca` o `verify-full`. El host y la región del pooler se copian
del panel del proyecto y se guardan dentro de `DATABASE_URL`. La aplicación no
imprime la URL. `connect_timeout`, tamaño, excedente y reciclaje del pool quedan
acotados mediante variables tipadas.

El rol PostgreSQL del backend necesita las operaciones transaccionales de la
aplicación. Los roles Data API `anon` y `authenticated` siguen limitados por
grants y RLS. La clave privada de Supabase sirve para Auth administrativo y
Storage desde el servidor; no se usa como sustituto de la identidad del usuario.

## Auth y modelo de identidad

El registro llama a Supabase Auth con correo y contraseña y después crea, en una
sola transacción local, `persona`, `cliente` de tipo `REGISTRADO` y
`cuenta_acceso`. El UUID de Auth se almacena únicamente en
`cuenta_acceso.identificador_autenticacion`. Si el commit local falla, el
coordinador elimina el usuario Auth recién creado con la clave privada. Si la
compensación también falla se devuelve un error operativo explícito para
intervención; no se presenta un registro parcial como exitoso.

Supabase debe mantener habilitada la confirmación por correo. La respuesta del
registro indica `email_verification_required=true`; la URL final de redirección
se configurará cuando exista el frontend autorizado.

Cada petición protegida sigue este orden:

1. extrae exactamente un `Bearer` de `Authorization`;
2. acepta sólo firmas asimétricas ES256 o RS256;
3. obtiene la clave pública desde el JWKS oficial del proyecto;
4. verifica firma, `iss`, `aud`, `exp`, `iat` y `sub`;
5. resuelve `sub` contra una `cuenta_acceso` activa;
6. deriva cliente o empleado desde las tablas locales activas;
7. consulta roles y permisos en PostgreSQL cuando el caso de uso los exige.

No se hace decode-only. No se aceptan roles, precios, propietarios ni permisos de
claims personalizados o metadatos del navegador. Un token de otro proyecto no
supera la comprobación del emisor.

Los invitados no crean un usuario Supabase. `POST /api/v1/auth/invitado` crea la
persona y cliente persistentes y emite una cookie cifrada y autenticada con
`Secure`, `HttpOnly`, `SameSite=Strict` y vencimiento. El identificador no queda
visible en el navegador y cualquier alteración se rechaza. El servidor vuelve a
comprobar que el perfil sea un `INVITADO` activo. Ningún endpoint acepta un ID de
persona como credencial.

## Storage privado

Los únicos tipos aceptados son PNG, JPEG y PDF. El backend comprueba MIME,
extensión, contenido no vacío y tamaño antes de contactar Storage. Los límites
son 10 MiB para diseños y 5 MiB para comprobantes. Los nombres de objeto usan un
UUID aleatorio dentro de rutas controladas por el servidor:

```text
disenos/pedidos/{pedido}/lineas/{linea}/{uuid}.{ext}
comprobantes/transacciones/{transaccion}/{uuid}.{ext}
```

Una versión de diseño guarda esa ruta privada en `version_diseno.ruta_archivo`.
Un comprobante guarda ruta, MIME y tamaño en su `transaccion`. Si la escritura de
base de datos falla después de cargar el objeto, el coordinador borra el objeto
como compensación. La base sigue siendo la fuente de autorización y referencia.

No hay lectura pública ni policies abiertas sobre `storage.objects`. El backend
accede con la clave privada, comprueba propiedad o permiso y emite una URL firmada
por 300 segundos. Este diseño evita duplicar en Storage toda la lógica de roles,
pedidos y versiones. Una futura exposición directa al navegador requerirá nuevas
políticas específicas y sus pruebas antes de conceder grants.

La revisión inicial de Fase 3 contenía `REVOKE ALL` sobre `storage.buckets` y
`storage.objects`. Esos grants son de tabla y afectarían globalmente todos los
buckets administrados por Supabase; PostgreSQL no permite acotarlos por ID de
bucket. La instrucción se retiró antes de cualquier aplicación remota. La
migración sólo inserta o actualiza los IDs `disenos` y `comprobantes`, y conserva
los privilegios administrados. El preflight muestra grants y policies existentes;
si aparece una policy amplia que alcance esos IDs, el proceso se detiene.

## Matriz RLS y privilegios

| Recurso | `anon` | `authenticated` por Data API | FastAPI |
|---|---|---|---|
| categoría, producto y variante publicados | SELECT filtrado | SELECT filtrado | lectura |
| promoción vigente y relación con variante | SELECT filtrado | SELECT filtrado | lectura y cálculo |
| escala mayorista | denegado | denegado | lectura tras resolver tipo real |
| identidad, pedidos, pagos, inventario, diseños, pérdidas y auditoría | denegado | denegado | según propiedad o permiso |
| buckets `disenos` y `comprobantes` | denegado | denegado | carga, borrado compensatorio y URL firmada |

Las 41 tablas tienen RLS habilitado. No hay `USING (true)` para datos privados,
funciones `security definer` ni políticas que confíen en roles enviados por el
cliente. FastAPI es el límite transaccional para los datos privados en esta fase.

## Variables y rotación

`backend/.env.example` contiene sólo nombres, valores locales y la URL/ref
públicos. En ejecución se inyectan por el gestor de secretos:

- `DATABASE_URL`, modo de conexión y `DATABASE_SSLMODE`;
- `SUPABASE_PUBLIC_KEY` para Auth público;
- `SUPABASE_SECRET_KEY` sólo en el backend para compensación y Storage;
- `GUEST_COOKIE_SECRET`, independiente y aleatorio.

La rotación consiste en crear una clave nueva, actualizar el secreto del entorno,
reiniciar instancias, comprobar salud y revocar la anterior. Rotar la clave de
cookie invalida las sesiones invitadas, por lo que debe anunciarse y ejecutarse
en una ventana controlada. Los logs nunca incluyen tokens, contraseñas, cookies,
claves ni URL PostgreSQL.

## Guía de puesta en marcha para desarrollo

Desde Git Bash, usando el checkout actualizado de esta rama:

```bash
cd /c/ruta/a/Proyecto-BD
git switch feat/fase-3-supabase
git pull --ff-only origin feat/fase-3-supabase

npx --yes supabase@3.0.0 login
npx --yes supabase@3.0.0 link --project-ref iwvmbdfkxrssduoqobgy

export SUPABASE_PROJECT_REF=iwvmbdfkxrssduoqobgy
set -o pipefail
./scripts/supabase/preflight.sh 2>&1 | tee fase-3-preflight.txt
```

`login` y `link` reciben las credenciales de forma interactiva. No se pasan con
flags, no se guardan en el repositorio y no deben aparecer en
`fase-3-preflight.txt`. El archivo compartible contiene sólo identidad/estado del
proyecto, versión PostgreSQL, extensiones, grants/policies, historial, dry-run y
metadatos JWKS (`kid`, `kty`, `alg`, `use`). Si el script termina con `FALLO`, se
comparte esa salida y no se ejecuta ningún otro comando.

1. Instalar Supabase CLI 3.x o disponer de Node.js/npx. Desde la raíz,
   `supabase status` debe reconocer `supabase/config.toml`; el stack local sólo
   existe después de iniciarlo de forma deliberada.
2. Iniciar sesión con `supabase login` usando un token introducido en la consola,
   nunca en un archivo, y enlazar exactamente el ref de desarrollo con
   `supabase link --project-ref iwvmbdfkxrssduoqobgy`.
3. Inyectar una contraseña PostgreSQL nueva mediante el mecanismo seguro del
   entorno. No escribirla en el comando, documentación o historial del shell.
4. Ejecutar `./scripts/supabase/preflight.sh`, guardar su salida sin secretos y
   revisar el historial y el dry-run. Detenerse si aparece un objeto inesperado.
5. Solicitar autorización expresa para aplicar. Sólo tras recibirla se ejecuta
   `supabase db push --remote --skip-vault`; no se ejecuta el seed.
6. En el panel Auth, habilitar correo/contraseña y confirmación por correo. La URL
   de sitio y redirecciones deben apuntar al frontend autorizado cuando exista.
7. Copiar la publishable key y secret key al gestor de secretos del backend. La
   secret key jamás se entrega al navegador.
8. Configurar `DATABASE_URL`, modo de conexión, TLS y secreto de cookie a partir
   de `backend/.env.example`; iniciar `uv run uvicorn app.main:app --reload`.
9. Registrar un usuario ficticio con `POST /api/v1/auth/registro`, confirmar el
   correo y usar `POST /api/v1/auth/login`. Enviar el `access_token` como
   `Authorization: Bearer <token>` a `/api/v1/clientes/me`. No copiar el token a
   Git, documentación o capturas.
10. Subir un diseño con multipart a
    `/api/v1/disenos/pedidos/{pedido}/lineas/{linea}/versiones` y solicitar su
    endpoint `/archivo`; la respuesta debe ser temporal. Repetir con el
    comprobante de una transacción autorizada.
11. Ejecutar `./database/tests/run.sh` y `./backend/tests/run.sh`. Las pruebas
    remotas sólo se habilitan en el proyecto de desarrollo aislado con
    `RUN_SUPABASE_REMOTE_TESTS=1` y una URL inyectada como secreto.

No se crea el primer empleado desde un endpoint público. Se registra primero una
cuenta Auth ficticia y un administrador autorizado vincula su UUID a una
`persona`/`empleado` ya aprobada mediante un procedimiento operativo auditado.
El navegador nunca decide que una cuenta es empleada o administradora.

### Errores habituales

| Síntoma | Comprobación |
|---|---|
| 401 con un token reciente | revisar issuer, audience, confirmación de correo y vínculo activo en CUENTA_ACCESO |
| 403 para empleado | revisar estado laboral y asignación vigente de rol/permiso en PostgreSQL |
| fallo TLS o DNS PostgreSQL | confirmar host/modo del pooler, región, `sslmode` y política de red |
| error de prepared statement | usar session pooler o configurar `transaction_pooler` para desactivarlos |
| 409 al subir | revisar MIME real, extensión, tamaño, propiedad y si ya existe comprobante |
| URL firmada devuelve acceso denegado | confirmar bucket privado, ruta persistida y vigencia de 300 segundos |
| dry-run propone cambios inesperados | no aplicar; comparar historial remoto con los cinco archivos locales |
| registro Auth sin perfil local | revisar el error de compensación y resolver el usuario huérfano antes de reintentar |

## Operación pendiente y rollback

El orden remoto autorizado será: verificar proyecto, historial y versión;
ejecutar dry-run; revisar que las cinco migraciones sean sólo aditivas; pedir
autorización expresa; aplicar; ejecutar pruebas remotas no destructivas; y
registrar evidencia. No se ejecutan seeds.

Si falla una migración, la transacción SQL la revierte. Después de aplicar, no se
borra el esquema para retroceder. Los buckets pueden conservarse privados sin
afectar el backend anterior; las nuevas columnas son nulas y compatibles. Una
reversión posterior debe prepararse como migración nueva y sólo retirar columnas
cuando se demuestre que no contienen referencias.
