# Fase 4.5.1 — UX funcional y presentación de datos

Esta fase conserva la identidad visual aprobada en Fase 4.5: Onest, porcelana,
ciruela y salvia, shells por contexto, navegación adaptable y assets locales.
El trabajo se concentra en la selección, jerarquía y explicación de los datos.

## Portal del cliente

El cliente inicia en un resumen con saludo, pedido destacado, saldos y accesos a
las tareas que requieren atención. Pedidos, cotizaciones y pagos usan componentes
comerciales propios; no reutilizan tablas administrativas ni presentan claves
foráneas. El catálogo consulta el precio al backend para cada cantidad y crea el
pedido o la cotización mediante endpoints autenticados del portal.

Cada pedido muestra el código público, productos, cantidades, precio pactado,
total, pagado, saldo, entrega, estado y próxima acción. El detalle incorpora el
historial permitido y una línea de progreso basada en estados reales. Las etapas
de diseño y producción se omiten cuando las variantes del pedido no requieren
producción. Cancelación, expiración y rechazo interrumpen visualmente el flujo.

## Capa de presentación

`frontend/presentation.js` centraliza:

- etiquetas explícitas para estados, movimientos y próximas acciones;
- fechas con `Intl.DateTimeFormat`, locale `es-NI` y `America/Managua`;
- importes NIO con `Intl.NumberFormat`;
- cantidades legibles;
- mensajes de autorización sin códigos internos;
- etapas del seguimiento según el pedido.

Los códigos desconocidos conservan un fallback legible sin modificar los valores
almacenados en PostgreSQL.

## Tablas y prioridades por rol

`table()` exige ahora una lista explícita de columnas. Se definieron selecciones
conscientes para pedidos, cotizaciones, pagos, inventario, movimientos, compras,
proveedores, pérdidas, clientes, empleados y reportes. El nombre del material,
proveedor o código comercial tiene prioridad sobre el identificador técnico.

- **Administración:** indicadores críticos, pedidos por estado, pagos por revisar,
  stock bajo y actividad reciente; los informes secundarios están desplegables.
- **Producción:** diseño aprobado, reservas, material, condición y próxima acción;
  sólo aparecen operaciones autorizadas por el backend y el permiso específico.
- **Ventas:** clientes, cotizaciones, pedidos y pagos en ese orden.
- **Contabilidad:** importes NIO, pagos, compras, pérdidas y reportes.
- **Cliente:** tienda, pedidos, cotizaciones, pagos, seguimiento y perfil, sin
  información financiera interna ni datos de otras cuentas.

## Contratos del portal y seguridad

Se añadió el prefijo `/api/v1/portal` con DTO exclusivos del cliente:

| Método y ruta | Uso |
|---|---|
| `GET /portal/resumen` | Indicadores y pedido destacado propios |
| `GET /portal/pedidos` | Resúmenes comerciales propios |
| `POST /portal/pedidos` | Pedido autenticado con precio del servidor |
| `GET /portal/pedidos/{codigo}` | Detalle, progreso e hitos permitidos |
| `GET/POST /portal/cotizaciones` | Cotizaciones propias |
| `POST /portal/cotizaciones/{referencia}/decision` | Aceptación o rechazo propio |
| `POST /portal/cotizaciones/{referencia}/convertir` | Conversión autorizada |
| `GET /portal/pagos` | Historial propio sin claves idempotentes |
| `POST /portal/pedidos/{codigo}/pagos` | Reporte para un pedido propio |
| `GET /portal/catalogo` | Catálogo publicado |
| `GET /portal/catalogo/{variante}/precio` | Precio calculado por reglas del backend |

Estos DTO omiten IDs de persona, cliente, pedido, cotización, transacción,
reservas, movimientos y empleados; también omiten costos internos, permisos,
auditoría y claves idempotentes. El identificador de variante permanece oculto
en el formulario porque es necesario para solicitar precio y crear operaciones.

La autorización no depende de la interfaz. Los servicios vuelven a comprobar la
propiedad del pedido, cotización o pago. Un empleado no puede consumir endpoints
del portal y una cuenta distinta recibe 403 o 404 al intentar usar el código o la
referencia de otro cliente.

Los contratos administrativos se conservan. `GET /pagos` añade el código público
del pedido para dar contexto al personal y el resumen operativo añade el nombre
del material reservado.

## Evidencia visual

Las capturas usan respuestas locales simuladas y no contienen datos reales ni
acceden a Supabase:

- [Portal del cliente](../evidencias/fase-4-5-1/portal-cliente.png)
- [Pedido activo](../evidencias/fase-4-5-1/pedido-activo.png)
- [Seguimiento](../evidencias/fase-4-5-1/seguimiento.png)
- [Catálogo en tablet](../evidencias/fase-4-5-1/catalogo-tablet.png)
- [Administración](../evidencias/fase-4-5-1/administracion.png)
- [Producción](../evidencias/fase-4-5-1/produccion.png)
- [Portal móvil](../evidencias/fase-4-5-1/portal-movil.png)
- [Producción móvil](../evidencias/fase-4-5-1/produccion-movil.png)

## Límites conocidos

El modelo actual no guarda imágenes comerciales por variante. El catálogo usa
placeholders visuales coherentes hasta que exista un origen de assets aprobado.
Los datos simulados de las capturas prueban composición y responsive; la lógica,
propiedad y contratos se prueban por separado contra PostgreSQL 17 local.

