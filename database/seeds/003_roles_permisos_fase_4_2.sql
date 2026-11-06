-- Catálogo funcional de roles y permisos para Fase 4.2.
-- Sólo DML idempotente sobre las tablas existentes. No se ejecuta remotamente
-- de forma automática y no modifica las cinco migraciones aprobadas.

begin;

insert into public.permiso (codigo_permiso, descripcion, modulo)
values
  ('INVENTARIO_CONSULTAR', 'Consultar existencias y disponibilidad', 'INVENTARIO'),
  ('INVENTARIO_GESTIONAR', 'Consumir y ajustar inventario autorizado', 'INVENTARIO'),
  ('COMPRA_CONSULTAR', 'Consultar compras y sus detalles', 'COMPRAS'),
  ('COMPRA_REGISTRAR', 'Crear borradores y detalles de compras', 'COMPRAS'),
  ('COMPRA_AUTORIZAR', 'Confirmar compras y entradas de inventario', 'COMPRAS'),
  ('PROVEEDOR_CONSULTAR', 'Consultar proveedores', 'COMPRAS'),
  ('PROVEEDOR_GESTIONAR', 'Crear y mantener proveedores', 'COMPRAS'),
  ('REPORTE_FINANCIERO_CONSULTAR', 'Consultar ingresos, compras y costos autorizados', 'REPORTES'),
  ('PERDIDA_CONSULTAR', 'Consultar incidencias y pérdidas operativas', 'INVENTARIO'),
  ('PERDIDA_COSTO_CONSULTAR', 'Consultar costos históricos de pérdidas', 'REPORTES'),
  ('PAGO_CONSULTAR', 'Consultar pagos de pedidos', 'PAGOS'),
  ('PAGO_VERIFICAR', 'Confirmar o rechazar pagos reportados', 'PAGOS'),
  ('PAGO_TARDIO_AUTORIZAR', 'Autorizar pagos fuera de la ventana ordinaria', 'PAGOS'),
  ('CLIENTE_CONSULTAR', 'Consultar clientes para atención y ventas', 'CLIENTES'),
  ('PEDIDO_GESTIONAR', 'Gestionar pedidos y cotizaciones', 'PEDIDOS'),
  ('DISENO_APROBAR', 'Gestionar y aprobar versiones de diseño', 'DISENOS'),
  ('PRODUCCION_INICIAR', 'Iniciar y gestionar producción autorizada', 'PRODUCCION'),
  ('PERDIDA_REGISTRAR', 'Reportar y confirmar pérdidas operativas', 'INVENTARIO'),
  ('EMPLEADO_GESTIONAR', 'Invitar empleados y asignar roles permitidos', 'SEGURIDAD')
on conflict (codigo_permiso) do update
set descripcion = excluded.descripcion, modulo = excluded.modulo;

insert into public.rol (nombre, descripcion, estado)
values
  ('ADMINISTRADOR', 'Dueño o administrador con gestión integral autorizada', 'ACTIVO'),
  ('CONTADOR', 'Lectura de información financiera y costos autorizados', 'ACTIVO'),
  ('VENDEDOR', 'Pedidos, cotizaciones, clientes y consulta de pagos', 'ACTIVO'),
  ('PRODUCCION', 'Diseños, producción, inventario consultivo e incidencias', 'ACTIVO')
on conflict (nombre) do update
set descripcion = excluded.descripcion, estado = excluded.estado;

delete from public.rol_permiso rp
using public.rol r
where r.id_rol = rp.id_rol
  and r.nombre in ('ADMINISTRADOR', 'CONTADOR', 'VENDEDOR', 'PRODUCCION');

delete from public.rol_permiso rp
using public.rol r, public.permiso p
where r.id_rol = rp.id_rol
  and p.id_permiso = rp.id_permiso
  and r.nombre = 'ADMINISTRACION'
  and p.codigo_permiso = 'PAGO_TARDIO_AUTORIZAR';

with matriz(rol, permiso) as (
  values
    ('CONTADOR','INVENTARIO_CONSULTAR'),
    ('CONTADOR','COMPRA_CONSULTAR'),
    ('CONTADOR','PROVEEDOR_CONSULTAR'),
    ('CONTADOR','REPORTE_FINANCIERO_CONSULTAR'),
    ('CONTADOR','PERDIDA_CONSULTAR'),
    ('CONTADOR','PERDIDA_COSTO_CONSULTAR'),
    ('CONTADOR','PAGO_CONSULTAR'),
    ('VENDEDOR','PEDIDO_GESTIONAR'),
    ('VENDEDOR','CLIENTE_CONSULTAR'),
    ('VENDEDOR','PAGO_CONSULTAR'),
    ('PRODUCCION','PEDIDO_GESTIONAR'),
    ('PRODUCCION','INVENTARIO_CONSULTAR'),
    ('PRODUCCION','DISENO_APROBAR'),
    ('PRODUCCION','PRODUCCION_INICIAR'),
    ('PRODUCCION','PERDIDA_REGISTRAR'),
    ('PRODUCCION','PERDIDA_CONSULTAR')
)
insert into public.rol_permiso (id_rol, id_permiso)
select r.id_rol, p.id_permiso
from matriz m
join public.rol r on r.nombre = m.rol
join public.permiso p on p.codigo_permiso = m.permiso
on conflict do nothing;

insert into public.rol_permiso (id_rol, id_permiso)
select r.id_rol, p.id_permiso
from public.rol r
cross join public.permiso p
where r.nombre in ('ADMINISTRADOR', 'ADMINISTRACION')
  and (r.nombre = 'ADMINISTRADOR' or p.codigo_permiso <> 'PAGO_TARDIO_AUTORIZAR')
on conflict do nothing;

commit;
