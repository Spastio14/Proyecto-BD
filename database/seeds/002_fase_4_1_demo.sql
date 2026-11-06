-- Datos ficticios opcionales para la demostración integral de Fase 4.1.
-- Sólo para PostgreSQL local desechable. No ejecutar en Supabase remoto.
-- El artículo empieza en 20 unidades; la compra de 30 se crea desde la API.

begin;

insert into public.categoria (id_categoria, nombre, descripcion, estado)
values (4101, 'Demostración Fase 4.1', 'Datos ficticios para la defensa académica', 'ACTIVA')
on conflict do nothing;

insert into public.producto
  (id_producto, id_categoria, nombre, descripcion, informacion_comercial, estado_publicacion)
values (4101, 4101, 'Taza Demo Integral', 'Producto ficticio de demostración',
        'No corresponde a una venta real', 'PUBLICADO')
on conflict do nothing;

insert into public.variante_producto
  (id_variante, id_producto, codigo_variante, caracteristicas, precio_detalle,
   requiere_produccion, estado)
values (4101, 4101, 'DEMO41-TAZA', 'Taza ficticia', 100.00, true, 'ACTIVA')
on conflict do nothing;

insert into public.articulo_inventariable
  (id_articulo, codigo, nombre, tipo_articulo, unidad_medida,
   existencia_actual, existencia_minima, costo_referencia, estado)
values (4101, 'DEMO41-INSUMO', 'Insumo Demo Fase 4.1', 'PRODUCTO', 'UNIDAD',
        20.000, 5.000, 30.0000, 'ACTIVO')
on conflict do nothing;

insert into public.composicion_producto
  (id_variante, id_articulo, cantidad_estandar, observaciones)
values (4101, 4101, 1.000, 'Una unidad por producto ficticio')
on conflict do nothing;

insert into public.proveedor
  (id_proveedor, nombre, telefono, correo, direccion, estado)
values (4101, 'Proveedor Ficticio Fase 4.1', '2222-4101',
        'proveedor41@example.test', 'Dirección ficticia', 'ACTIVO')
on conflict do nothing;

do $$
declare item record;
begin
  for item in
    select table_name, column_name from information_schema.columns
    where table_schema = 'public' and is_identity = 'YES'
  loop
    execute format(
      'select setval(pg_get_serial_sequence(%L, %L), '
      || 'greatest((select coalesce(max(%I), 0) from public.%I), 1), true)',
      'public.' || item.table_name, item.column_name, item.column_name, item.table_name
    );
  end loop;
end $$;

commit;
