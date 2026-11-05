-- Seguridad Supabase: denegación por defecto y catálogo público mínimo.
-- Supabase provee los roles anon y authenticated. El runner local los crea.

begin;

revoke all on all tables in schema public from public, anon, authenticated;
revoke all on all sequences in schema public from public, anon, authenticated;
alter default privileges in schema public revoke all on tables from public;
alter default privileges in schema public revoke all on sequences from public;

alter table public.persona enable row level security;
alter table public.cuenta_acceso enable row level security;
alter table public.cliente enable row level security;
alter table public.empleado enable row level security;
alter table public.asignacion_rol enable row level security;
alter table public.rol enable row level security;
alter table public.rol_permiso enable row level security;
alter table public.permiso enable row level security;
alter table public.cotizacion enable row level security;
alter table public.pedido enable row level security;
alter table public.historial_pedido enable row level security;
alter table public.detalle_cotizacion enable row level security;
alter table public.detalle_pedido enable row level security;
alter table public.etapa_proceso enable row level security;
alter table public.asignacion_etapa enable row level security;
alter table public.version_diseno enable row level security;
alter table public.solicitud_cambio enable row level security;
alter table public.aprobacion_diseno enable row level security;
alter table public.categoria enable row level security;
alter table public.producto enable row level security;
alter table public.variante_producto enable row level security;
alter table public.articulo_inventariable enable row level security;
alter table public.escala_precio enable row level security;
alter table public.composicion_producto enable row level security;
alter table public.promocion enable row level security;
alter table public.promocion_variante enable row level security;
alter table public.gasto enable row level security;
alter table public.registro_auditoria enable row level security;
alter table public.agencia_envio enable row level security;
alter table public.envio enable row level security;
alter table public.hito_pago enable row level security;
alter table public.transaccion enable row level security;
alter table public.cancelacion enable row level security;
alter table public.reembolso enable row level security;
alter table public.proveedor enable row level security;
alter table public.compra enable row level security;
alter table public.detalle_compra enable row level security;
alter table public.movimiento_inventario enable row level security;
alter table public.reserva_inventario enable row level security;
alter table public.perdida enable row level security;
alter table public.detalle_perdida enable row level security;

grant usage on schema public to anon, authenticated;
grant select on table
    public.categoria,
    public.producto,
    public.variante_producto,
    public.escala_precio,
    public.promocion,
    public.promocion_variante
to anon, authenticated;

create policy catalogo_categoria_lectura
on public.categoria
for select
to anon, authenticated
using (estado = 'ACTIVA');

create policy catalogo_producto_lectura
on public.producto
for select
to anon, authenticated
using (
    estado_publicacion = 'PUBLICADO'
    and exists (
        select 1
        from public.categoria c
        where c.id_categoria = producto.id_categoria
          and c.estado = 'ACTIVA'
    )
);

create policy catalogo_variante_lectura
on public.variante_producto
for select
to anon, authenticated
using (
    estado = 'ACTIVA'
    and exists (
        select 1
        from public.producto p
        join public.categoria c on c.id_categoria = p.id_categoria
        where p.id_producto = variante_producto.id_producto
          and p.estado_publicacion = 'PUBLICADO'
          and c.estado = 'ACTIVA'
    )
);

create policy catalogo_escala_lectura
on public.escala_precio
for select
to anon, authenticated
using (
    estado = 'ACTIVA'
    and exists (
        select 1
        from public.variante_producto v
        join public.producto p on p.id_producto = v.id_producto
        join public.categoria c on c.id_categoria = p.id_categoria
        where v.id_variante = escala_precio.id_variante
          and v.estado = 'ACTIVA'
          and p.estado_publicacion = 'PUBLICADO'
          and c.estado = 'ACTIVA'
    )
);

create policy catalogo_promocion_lectura
on public.promocion
for select
to anon, authenticated
using (
    estado = 'ACTIVA'
    and current_timestamp between fecha_inicio and fecha_fin
);

create policy catalogo_promocion_variante_lectura
on public.promocion_variante
for select
to anon, authenticated
using (
    exists (
        select 1
        from public.promocion pr
        join public.variante_producto v on v.id_variante = promocion_variante.id_variante
        join public.producto p on p.id_producto = v.id_producto
        join public.categoria c on c.id_categoria = p.id_categoria
        where pr.id_promocion = promocion_variante.id_promocion
          and pr.estado = 'ACTIVA'
          and current_timestamp between pr.fecha_inicio and pr.fecha_fin
          and v.estado = 'ACTIVA'
          and p.estado_publicacion = 'PUBLICADO'
          and c.estado = 'ACTIVA'
    )
);

commit;
