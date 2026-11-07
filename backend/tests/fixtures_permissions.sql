-- Permisos ficticios exclusivos del entorno de prueba. No depende de IDs
-- porque las migraciones incrementales pueden registrar permisos antes del seed.
insert into public.permiso (codigo_permiso, descripcion, modulo)
values
    ('PEDIDO_GESTIONAR', 'Gestionar pedidos de prueba', 'PEDIDOS'),
    ('PAGO_VERIFICAR', 'Verificar pagos de prueba', 'PAGOS'),
    ('INVENTARIO_GESTIONAR', 'Gestionar inventario de prueba', 'INVENTARIO'),
    ('INVENTARIO_CONSUMIR_RESERVAS', 'Consumir reservas de producción', 'INVENTARIO'),
    ('DISENO_APROBAR', 'Aprobar diseños de prueba', 'DISENOS'),
    ('PRODUCCION_INICIAR', 'Iniciar producción de prueba', 'PRODUCCION'),
    ('PERDIDA_REGISTRAR', 'Registrar pérdidas de prueba', 'INVENTARIO')
on conflict (codigo_permiso) do update
set descripcion = excluded.descripcion, modulo = excluded.modulo;

insert into public.rol_permiso (id_rol, id_permiso)
select r.id_rol, p.id_permiso
from public.rol r
cross join public.permiso p
where r.nombre = 'ADMINISTRACION'
  and p.codigo_permiso in (
    'PEDIDO_GESTIONAR',
    'PAGO_VERIFICAR',
    'INVENTARIO_GESTIONAR',
    'INVENTARIO_CONSUMIR_RESERVAS',
    'DISENO_APROBAR',
    'PRODUCCION_INICIAR',
    'PERDIDA_REGISTRAR'
  )
on conflict do nothing;
