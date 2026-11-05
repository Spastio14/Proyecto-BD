# Arquitectura acordada

## Principio

La arquitectura sigue la decisión **base de datos estructuralmente sólida +
backend inteligente**.

PostgreSQL conserva estructura, referencias, restricciones, transacciones,
índices, saldos materializados y controles de acceso. FastAPI orquesta los casos
de uso y aplica límites, estados, cálculos, reservas, pagos, promociones,
producción, pérdidas y auditoría dentro de transacciones explícitas.

## Componentes

```text
Next.js / React
      |
      | HTTPS + identidad Supabase
      v
FastAPI (autorización y servicios de negocio)
      |
      | SQLAlchemy 2.x + Psycopg 3
      v
PostgreSQL en Supabase
      +-- Auth
      +-- Storage privado
      +-- RLS para accesos expuestos
```

El navegador nunca recibe credenciales de PostgreSQL ni claves administrativas.
Los diseños y comprobantes se guardan en buckets privados y se sirven mediante
URLs firmadas con duración limitada.

## Límites de responsabilidad

| Área | PostgreSQL | FastAPI |
|---|---|---|
| Integridad | PK, FK, UNIQUE, NOT NULL, CHECK | Validación contextual y mensajes de error |
| Concurrencia | Transacciones, bloqueos, niveles de aislamiento | Orden de operaciones y reintentos seguros |
| Precios | Persistencia de escalas y precios históricos | Selección y cálculo del precio aplicable |
| Inventario | Existencias, reservas, movimientos y restricciones | Reserva, consumo, liberación y prevención de duplicados |
| Pagos | Historial e idempotencia persistente | Confirmación, saldo, compensación y autorización |
| Seguridad | Roles SQL, RLS y privilegios mínimos | Identidad, permisos y propiedad del recurso |
| Auditoría | Registro durable | Construcción del evento y contexto del actor |

## Migraciones

`supabase/migrations/` será la única fuente canónica del DDL PostgreSQL. Si
Alembic se incorpora para apoyar el desarrollo ORM, se configurará para aplicar
o reconocer esas revisiones sin mantener una segunda definición divergente.
Ninguna migración se generará automáticamente contra producción.

## Versiones base de la implementación

La Fase 0 fija versiones mayores conservadoras y mantenidas:

- PostgreSQL 17 como objetivo local; se confirmará la versión ofrecida por el
  proyecto Supabase antes de escribir DDL dependiente de versión.
- Python 3.12.
- SQLAlchemy 2.x y Psycopg 3.x.
- Node.js 22 LTS, React 19 y TypeScript 5.x.

La Fase 3 resolvió y fijó 44 paquetes en `backend/uv.lock`, incluidas versiones
compatibles de FastAPI, Pydantic 2, SQLAlchemy 2, Psycopg 3, Uvicorn, HTTPX y
Pytest, además de PyJWT/cryptography y multipart. Next.js y Tailwind se fijarán
en sus fases respectivas.

## Decisiones para concurrencia

- El alta de pedido bloqueará o serializará el registro del cliente antes de
  contar pedidos activos.
- La reserva bloqueará los artículos involucrados en un orden estable y calculará
  disponible como existencia física menos reservas vigentes.
- La confirmación de pago usará una clave de idempotencia única y no avanzará el
  pedido hasta que el pago quede verificado.
- La expiración será una operación repetible que seleccione pedidos vencidos con
  bloqueo y omita los que ya cambiaron de estado o tienen pago confirmado.
- La liberación y el consumo de reservas comprobarán su estado para impedir una
  segunda aplicación.

La Fase 2 usa `SELECT FOR UPDATE` sobre el cliente antes de contar pedidos y
sobre artículos en orden ascendente antes de calcular disponibilidad. Pagos,
reservas, movimientos y pérdidas bloquean su registro raíz. Expiración usa
`FOR UPDATE SKIP LOCKED`. Dos pruebas con conexiones reales validan el límite de
pedido invitado y la última existencia disponible.

## Unidad de trabajo

Los servicios reciben una `Session` y nunca ejecutan `commit`. La dependencia
HTTP, el comando o la prueba que abre la operación confirma una vez o revierte
todo. Confirmar anticipo y crear todas sus reservas forma una sola unidad; si
falta inventario, la verificación permanece pendiente para tratamiento
administrativo del pago externo.

## Autenticación y permisos

`AuthenticationProvider` verifica JWT de Supabase mediante el JWKS del proyecto
y resuelve su `sub` contra CUENTA_ACCESO. Sin configuración completa no autentica
a nadie y las rutas protegidas devuelven 401. Los invitados usan una cookie
firmada distinta de Auth. En ambos casos, propiedad y permisos se consultan en
CLIENTE, EMPLEADO, ASIGNACION_ROL, ROL, ROL_PERMISO y PERMISO.

El catálogo HTTP omite escalas mayoristas. La migración
`202611050001_restrict_wholesale_price_rls.sql` también revoca su SELECT directo
a `anon` y `authenticated`; FastAPI las usa después de verificar el tipo real del
cliente.

## Estado financiero append-only

Una transacción reportada conserva siempre importe, tipo, pedido, hito, fecha y
clave idempotente. La resolución cambia únicamente `estado_verificacion` de
PENDIENTE a VERIFICADO o RECHAZADO y guarda empleado y evento de auditoría en la
misma transacción. No se elimina ni reemplaza el registro económico. Las
correcciones monetarias futuras deberán usar compensaciones enlazadas, sin
reescribir el importe original.
