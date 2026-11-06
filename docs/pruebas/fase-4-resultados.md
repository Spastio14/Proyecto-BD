# Resultados de pruebas — Fase 4

Fecha: 5 de noviembre de 2026 (`America/Managua`).

## Alcance y entorno

La validación se ejecutó sobre el commit de `master` que integra el PR #7 y en
la rama `test/fase-4-integracion-negocio`. Se usaron Python 3.12.14,
PostgreSQL 17.11 real en Docker, FastAPI, SQLAlchemy 2 y Psycopg 3. Cada prueba
de integración recibió una base clonada desde una plantilla migrada y sembrada
con datos ficticios. No se usó SQLite ni se escribió en Supabase remoto.

## Resultados ejecutados

| Suite | Recopiladas | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|---:|
| Pytest backend | 128 | 126 | 0 | 2 |
| Parser de preflight | 15 | 15 | 0 | 0 |
| Aserciones estructurales SQL | 12 | 12 | 0 | 0 |

En total aprobaron 153 comprobaciones identificables. Las dos pruebas omitidas
son exclusivamente remotas: versión/esquema de Supabase e historial enlazado de
migraciones. Requieren opt-in y credenciales privadas que no estaban disponibles;
no se declaran aprobadas.

La línea base anterior fue 94 aprobadas y 2 omitidas. Fase 4 añadió 32 casos
ejecutados. Uvicorn inició correctamente y `/api/v1/health` respondió contra
PostgreSQL antes de Pytest. El runner de base de datos hizo dos reconstrucciones
limpias y verificó 41 tablas, 64 claves foráneas, restricciones e RLS.

Comandos ejecutados:

```bash
./database/tests/run.sh
./backend/tests/run.sh
cd backend
UV_CACHE_DIR=/tmp/uv-cache uv run --locked ruff format app tests
UV_CACHE_DIR=/tmp/uv-cache uv run --locked ruff check app tests
```

La única advertencia fue la deprecación conocida de `TestClient` de
Starlette/HTTPX. No causó errores funcionales.

## Fallos reproducidos y correcciones

Las primeras pruebas nuevas reprodujeron seis fallos. Se corrigieron antes de
ampliar la regresión.

1. **Mayorista sin autorización comercial.** `PricingService` elegía escalas
   usando sólo `tipo_cliente`. Ahora exige además
   `condicion_comercial = 'MAYORISTA'`, leída de PostgreSQL.
2. **Conversión de cotización eludía límites.** Una cotización aceptada podía
   generar seis unidades para un invitado o un tercer pedido pendiente. La
   creación directa y la conversión comparten ahora la misma validación bajo el
   bloqueo de `CLIENTE`.
3. **Rechazo posterior de diseño ignorado.** Producción buscaba cualquier
   aprobación histórica de la última versión. Ahora comprueba el estado vigente
   `version_diseno.es_aprobado`; una decisión posterior de rechazo bloquea el
   inicio.
4. **Idempotencia concurrente de pagos.** Dos reportes simultáneos con la misma
   clave podían terminar en una violación `UNIQUE`. Un advisory lock
   transaccional por clave serializa el reintento y ambos reciben la misma
   transacción.
5. **Carrera de números de versión.** La selección de `max(numero_version)+1`
   no bloqueaba el pedido. `DesignService` bloquea ahora `PEDIDO` y asigna
   versiones consecutivas bajo concurrencia.
6. **Carrera al adjuntar comprobantes.** Dos cargas podían observar una ruta
   vacía. La persistencia bloquea `TRANSACCION`; sólo un objeto queda vinculado
   y el objeto nuevo perdedor se elimina de forma compensatoria.

No se añadió ni modificó ninguna migración.

## Reglas validadas

- Invitado persistente sin Auth, cookie `Secure`/`HttpOnly`/`SameSite=Strict`,
  expiración y rechazo de alteración.
- Máximo de cinco unidades, suma multilínea y un pedido activo para invitados.
- Dos pedidos `PENDIENTE_PAGO` para registrados, incluso con dos conexiones
  concurrentes; otros estados no cuentan.
- Registro Auth, JWT firmado, recuperación idempotente y vínculo local seguro.
- Permisos de empleado resueltos desde roles de PostgreSQL y rechazo de roles
  declarados por el cliente.
- Precio detalle, autorización mayorista, rangos, promoción vigente, mínimo,
  incompatibilidad con mayorista, paquete de dos tazas por C$170 y conservación
  histórica.
- Totales de cotización/pedido, conversión única y límites al convertir.
- Anticipo del 50 %, separación entre reporte y verificación, rechazo, pago
  tardío, idempotencia y concurrencia.
- Reservas posteriores a verificación, no sobreventa, disponibilidad, consumo
  único, cancelación y rollback.
- Última versión de diseño, aprobación/rechazo vigente e inicio de producción.
- Pérdida confirmada una vez, costo histórico, asociación con pedido, movimiento
  de inventario y confirmación concurrente.
- PNG, JPEG y PDF, MIME/extensión/tamaño, objetos privados, URL firmada,
  propiedad y compensación de Storage simulado.
- Propiedad de pedidos, diseños y comprobantes; tokens alterados, vencidos o de
  otro proyecto; RLS y privilegios cerrados.

Los escenarios integrales A–E están cubiertos por los casos 106–109 y por las
carreras 19, 86, 87, 92, 93, 99, 101 y 105. El escenario A usa un gateway Auth
simulado, verifica el JWT y recorre cotización, pedido, anticipo, reserva, diseño,
aprobación y producción. El escenario B usa HTTP real de FastAPI y cookie segura.

## Cobertura funcional pendiente o parcial

| Área | Estado | Motivo |
|---|---|---|
| Aceptación/rechazo de cotización | Parcial | El servicio convierte una cotización ya aceptada, pero no existe endpoint que registre la decisión. |
| Rechazo de pago | Parcial | `PaymentService.reject` funciona y está probado; falta endpoint HTTP. |
| Transiciones operativas generales | Parcial | El servicio e historial existen; no hay endpoints para pasar a diseño, listo o entregado. |
| Compras y proveedores | Pendiente | Hay tablas, relaciones e índices, pero no servicio ni endpoints de confirmación de compra. |
| Reembolsos/compensaciones | Pendiente | El modelo conserva historial, pero no hay servicio transaccional. |
| Envíos y entrega | Pendiente | Tablas disponibles; no hay servicio que confirme entrega y transición. |
| Reportes de ventas/pérdidas/proveedores | Pendiente | No existen consultas de aplicación ni endpoints. |
| Utilidad o beneficio neto | Pendiente | Faltan política aprobada de asignación de costos y cobertura completa de gastos; no se calcula un beneficio incompleto. |
| Pérdidas por momento | Parcial | Registro y confirmación están validados; falta definir si todo momento de producción debe exigir pedido y etapa. |
| Catálogo comercial ampliado | Pendiente de datos | No se inventaron precios ni composiciones para mouse pads, camisetas, termos o botellas. |
| Promociones entre líneas/productos | No representable | El modelo aprobado conserva una promoción principal por línea. |

Estas carencias no se ocultaron mediante cambios de esquema ni reglas nuevas.

## Rendimiento

La revisión no encontró N+1 en las rutas actuales. Catálogo usa una consulta con
joins; precios consulta una variante y sus reglas; historial, reservas,
movimientos, pérdidas y compras tienen índices alineados con sus filtros. Los
índices relevantes incluyen `ix_pedido_cliente_estado`,
`ix_pedido_vencimiento`, `ix_transaccion_pedido_estado`,
`ix_reserva_articulo_estado`, `ix_movimiento_articulo_fecha`,
`ix_perdida_fecha` e `ix_compra_proveedor_fecha`.

El seed es demasiado pequeño para justificar optimizaciones mediante
`EXPLAIN ANALYZE`. El ordenamiento de todo el historial de pedidos por cliente es
un candidato a benchmark con volumen representativo. Añadir un índice para ese
caso exigiría una migración y autorización; no se realizó una optimización
especulativa.

## Seguridad y alcance remoto

No se ejecutaron `db reset`, `db push`, seeds, migraciones, cargas de archivos ni
operaciones comerciales contra Supabase remoto. No se usaron ni mostraron
credenciales. Las comprobaciones remotas siguen pendientes hasta que el
propietario las ejecute explícitamente con las instrucciones de la guía manual.
