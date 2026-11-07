-- Permiso mínimo para consumir reservas vinculadas a pedidos en producción.
-- DML incremental e idempotente; no reemplaza la matriz de permisos existente.

begin;

update public.permiso
set descripcion = 'Registrar artículos y ajustes generales de inventario'
where codigo_permiso = 'INVENTARIO_GESTIONAR'
  and descripcion is distinct from 'Registrar artículos y ajustes generales de inventario';

insert into public.permiso (codigo_permiso, descripcion, modulo)
values (
  'INVENTARIO_CONSUMIR_RESERVAS',
  'Consumir materiales previamente reservados para pedidos en producción',
  'INVENTARIO'
)
on conflict (codigo_permiso) do update
set descripcion = excluded.descripcion,
    modulo = excluded.modulo;

insert into public.rol_permiso (id_rol, id_permiso)
select r.id_rol, p.id_permiso
from public.rol r
join public.permiso p
  on p.codigo_permiso = 'INVENTARIO_CONSUMIR_RESERVAS'
where r.nombre in ('ADMINISTRADOR', 'PRODUCCION')
on conflict do nothing;

commit;
