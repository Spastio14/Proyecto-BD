# Fase 4.5.2 — flujos operativos

Esta fase corrige los flujos de diseños, catálogo y venta presencial sin
modificar datos ni configuración del proyecto Supabase remoto. La rama conserva
las 41 tablas principales. La migración incremental añade metadatos opcionales
a `PRODUCTO` y la descripción de personalización a `DETALLE_PEDIDO`.

## Diseños y producción

`GET /api/v1/disenos/pedidos/{pedido}/lineas` devuelve las líneas y todas sus
versiones en una sola respuesta. Cada versión incluye nombre, fecha,
observaciones, estado y marca de vigencia. Los archivos permanecen en el bucket
privado `disenos` y se consultan mediante una URL firmada de duración limitada.

El procedimiento es el siguiente:

1. Producción o un empleado con `DISENO_APROBAR` carga una versión.
2. El cliente consulta las versiones de su propio pedido desde
   `GET /api/v1/portal/pedidos/{codigo}/disenos`.
3. El cliente aprueba o rechaza la versión vigente desde el portal.
4. Un administrador puede registrar una decisión recibida por WhatsApp o en
   persona. Debe indicar medio, referencia y evidencia; su persona queda como
   responsable en `APROBACION_DISENO` y en auditoría.
5. Una versión posterior empieza pendiente. Las aprobaciones anteriores
   permanecen como historia y no habilitan producción.
6. El resumen operativo explica si falta anticipo, aprobación, composición,
   reserva, consumo o permiso antes de ofrecer la siguiente acción.

Los pedidos entregados aparecen sólo en el historial. El endpoint paginado
`GET /api/v1/pedidos/operativos` acepta `context`, `view`, `page` y `limit` para
evitar una petición del navegador por cada pedido.

## Catálogo y fotografías

El catálogo del cliente agrupa variantes por producto. La tarjeta sólo sirve
para explorar; la vista de detalle permite elegir variante, cantidad,
personalización y entrega. El precio unitario y total se obtienen nuevamente
del backend.

El administrador usa
`POST /api/v1/catalogo/admin/productos/{id}/imagen`. El servidor acepta PNG,
JPEG y WebP de hasta 5 MB, comprueba MIME, firma y extensión, genera una ruta
aleatoria y actualiza la base dentro de una transacción. El archivo anterior se
elimina después de confirmar la nueva referencia. El bucket público dedicado
se llama `catalogo-productos`; los diseños de clientes nunca se copian allí.

## Venta presencial

El módulo `Ventas → Nuevo pedido presencial` usa estos endpoints:

- `GET /api/v1/ventas/clientes/buscar` busca por nombre, teléfono o correo;
- `POST /api/v1/ventas/clientes` crea un invitado individual sin Auth;
- `GET /api/v1/ventas/precios/{variante}` calcula el precio para el cliente;
- `POST /api/v1/ventas/pedidos` crea un pedido de canal `PRESENCIAL`;
- `POST /api/v1/ventas/cotizaciones` crea una cotización trazada por auditoría.

El pedido conserva el cliente y el empleado que lo recibió. El vendedor no
confirma pagos desde este flujo; debe usar el procedimiento de pagos existente
y sólo si su rol tiene el permiso correspondiente. Los invitados mantienen el
máximo de 5 unidades y un pedido activo. No se implementó una excepción de
mostrador porque requiere una decisión comercial expresa.

## Perfil y empleados

Los clientes conservan la edición de sus datos personales autorizados. Un
empleado sólo puede editar su teléfono y dirección desde su propio perfil. El
administrador modifica nombres, apellidos, teléfono o documento desde la ficha
laboral con `EMPLEADO_GESTIONAR`; los cambios quedan auditados. Roles, permisos,
UUID de Auth y correo no se aceptan en ese procedimiento.

`GET /api/v1/empleados/duplicados-posibles` presenta coincidencias para revisión
manual. No fusiona, suspende ni elimina personas.

## Aplicación posterior de la migración

La nueva migración es
`202611070003_product_images_pos_customization.sql`. Antes de aplicarla en un
proyecto autorizado:

```bash
supabase link --project-ref iwvmbdfkxrssduoqobgy
supabase migration list
supabase db push --dry-run
```

El dry-run debe mostrar únicamente esa migración pendiente y los cambios
documentados. No se deben ejecutar seeds. El `db push` real requiere una
autorización separada y no forma parte de esta fase.
