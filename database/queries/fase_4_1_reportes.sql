-- Fase 4.1: reportes académicos de solo lectura.
-- Se pueden ejecutar individualmente en PostgreSQL/Supabase SQL Editor.
-- No crean objetos ni modifican datos. Los ingresos incluyen sólo pagos verificados.

-- 01. Productos publicados con categoría y variantes activas.
select p.id_producto, p.nombre as producto, c.nombre as categoria,
       v.id_variante, v.codigo_variante, v.precio_detalle
from public.producto p
join public.categoria c on c.id_categoria = p.id_categoria
join public.variante_producto v on v.id_producto = p.id_producto
where p.estado_publicacion = 'PUBLICADO' and c.estado = 'ACTIVA' and v.estado = 'ACTIVA'
order by c.nombre, p.nombre, v.codigo_variante;

-- 02. Cantidad de productos por categoría, incluso categorías sin productos.
select c.id_categoria, c.nombre, count(p.id_producto) as cantidad_productos
from public.categoria c
left join public.producto p on p.id_categoria = c.id_categoria
group by c.id_categoria, c.nombre
order by cantidad_productos desc, c.nombre;

-- 03. Tres productos con más unidades pedidas, excluyendo pedidos no efectivos.
select p.id_producto, p.nombre, sum(dp.cantidad) as unidades_pedidas
from public.producto p
join public.variante_producto v on v.id_producto = p.id_producto
join public.detalle_pedido dp on dp.id_variante = v.id_variante
join public.pedido pe on pe.id_pedido = dp.id_pedido
where pe.estado not in ('CANCELADO', 'EXPIRADO')
group by p.id_producto, p.nombre
order by unidades_pedidas desc, p.nombre
limit 3;

-- 04. Pedidos y cotizaciones por cliente registrado o invitado.
select cl.id_persona, concat_ws(' ', per.nombres, per.apellidos) as cliente,
       count(distinct pe.id_pedido) as pedidos,
       count(distinct co.id_cotizacion) as cotizaciones
from public.cliente cl
join public.persona per on per.id_persona = cl.id_persona
left join public.pedido pe on pe.id_cliente = cl.id_persona
left join public.cotizacion co on co.id_cliente = cl.id_persona
group by cl.id_persona, per.nombres, per.apellidos
order by pedidos desc, cotizaciones desc, cliente;

-- 05. Ventas documentadas por fecha de creación del pedido.
select pe.fecha_creacion::date as fecha, count(*) as pedidos,
       sum(pe.total_pedido) as total_documentado
from public.pedido pe
where pe.estado not in ('CANCELADO', 'EXPIRADO')
group by pe.fecha_creacion::date
order by fecha;

-- 06. Ingreso cobrado verificable por día (no equivale a utilidad neta).
select t.fecha_hora::date as fecha, sum(t.monto_con_signo) as ingreso_verificado
from public.transaccion t
where t.tipo_transaccion = 'PAGO' and t.estado_verificacion = 'VERIFICADO'
group by t.fecha_hora::date
order by fecha;

-- 07. Existencia, reserva activa y disponibilidad real por artículo.
select a.id_articulo, a.codigo, a.nombre, a.existencia_actual,
       coalesce(sum(r.cantidad_pendiente) filter (where r.estado = 'ACTIVA'), 0) as reservado,
       a.existencia_actual - coalesce(sum(r.cantidad_pendiente)
           filter (where r.estado = 'ACTIVA'), 0) as disponible
from public.articulo_inventariable a
left join public.reserva_inventario r on r.id_articulo = a.id_articulo
group by a.id_articulo, a.codigo, a.nombre, a.existencia_actual
order by a.nombre;

-- 08. Artículos por debajo del mínimo según disponibilidad, no sólo existencia física.
select x.*
from (
  select a.id_articulo, a.codigo, a.nombre, a.existencia_minima,
         a.existencia_actual - coalesce(sum(r.cantidad_pendiente)
           filter (where r.estado = 'ACTIVA'), 0) as disponible
  from public.articulo_inventariable a
  left join public.reserva_inventario r on r.id_articulo = a.id_articulo
  group by a.id_articulo, a.codigo, a.nombre, a.existencia_minima, a.existencia_actual
) x
where x.disponible <= x.existencia_minima
order by x.disponible, x.nombre;

-- 09. Tres artículos con más cantidad perdida.
select a.id_articulo, a.nombre, sum(dp.cantidad_perdida) as cantidad_perdida
from public.detalle_perdida dp
join public.articulo_inventariable a on a.id_articulo = dp.id_articulo
join public.perdida p on p.id_perdida = dp.id_perdida
where p.estado_registro = 'CONFIRMADA'
group by a.id_articulo, a.nombre
order by cantidad_perdida desc, a.nombre
limit 3;

-- 10. Costo histórico de pérdidas confirmadas.
select p.id_perdida, p.fecha_hora, p.tipo_incidente,
       sum(dp.cantidad_perdida * dp.costo_unitario_historico) as costo_perdida
from public.perdida p
join public.detalle_perdida dp on dp.id_perdida = p.id_perdida
where p.estado_registro = 'CONFIRMADA'
group by p.id_perdida, p.fecha_hora, p.tipo_incidente
order by costo_perdida desc;

-- 11. Proveedor con mayor cantidad comprada en compras confirmadas.
select pr.id_proveedor, pr.nombre, sum(dc.cantidad_comprada) as articulos_comprados
from public.proveedor pr
join public.compra c on c.id_proveedor = pr.id_proveedor and c.estado = 'CONFIRMADA'
join public.detalle_compra dc on dc.id_compra = c.id_compra
group by pr.id_proveedor, pr.nombre
order by articulos_comprados desc, pr.nombre
limit 1;

-- 12. Compras y sus detalles, conservando borradores sin detalle.
select c.id_compra, c.fecha_compra, c.estado, pr.nombre as proveedor,
       dc.numero_linea, a.nombre as articulo, dc.cantidad_comprada,
       dc.costo_unitario_compra, dc.importe, c.total_compra
from public.compra c
join public.proveedor pr on pr.id_proveedor = c.id_proveedor
left join public.detalle_compra dc on dc.id_compra = c.id_compra
left join public.articulo_inventariable a on a.id_articulo = dc.id_articulo
order by c.fecha_compra desc, c.id_compra, dc.numero_linea;

-- 13. Pedidos aún pendientes de ejecución o cobro.
select pe.id_pedido, pe.codigo_pedido, pe.estado, pe.vencimiento_pago,
       concat_ws(' ', per.nombres, per.apellidos) as cliente, pe.total_pedido
from public.pedido pe
join public.persona per on per.id_persona = pe.id_cliente
where pe.estado in ('PENDIENTE_PAGO', 'PAGADO_PARCIAL', 'PAGADO',
                    'EN_DISENO', 'EN_PRODUCCION', 'LISTO')
order by pe.vencimiento_pago, pe.codigo_pedido;

-- 14. Cinco clientes por total documentado en pedidos efectivos.
select cl.id_persona, concat_ws(' ', per.nombres, per.apellidos) as cliente,
       count(pe.id_pedido) as pedidos, coalesce(sum(pe.total_pedido), 0) as total_documentado
from public.cliente cl
join public.persona per on per.id_persona = cl.id_persona
left join public.pedido pe on pe.id_cliente = cl.id_persona
  and pe.estado not in ('CANCELADO', 'EXPIRADO')
group by cl.id_persona, per.nombres, per.apellidos
having count(pe.id_pedido) > 0
order by total_documentado desc, cliente
limit 5;

-- 15. Empleados y roles activos; incluye empleados todavía sin rol.
select e.codigo_empleado, concat_ws(' ', p.nombres, p.apellidos) as empleado,
       r.nombre as rol, ar.fecha_asignacion
from public.empleado e
join public.persona p on p.id_persona = e.id_persona
left join public.asignacion_rol ar on ar.id_empleado = e.id_persona and ar.estado = 'ACTIVA'
left join public.rol r on r.id_rol = ar.id_rol
where e.estado_laboral = 'ACTIVO'
order by e.codigo_empleado, r.nombre;

-- 16. Historia cronológica de estados de pedidos.
select h.id_pedido, pe.codigo_pedido, h.fecha_hora, h.estado_anterior,
       h.estado_nuevo, h.motivo, h.origen_cambio
from public.historial_pedido h
join public.pedido pe on pe.id_pedido = h.id_pedido
order by h.id_pedido, h.fecha_hora;

-- 17. Movimientos de inventario con sus referencias opcionales.
select m.id_movimiento, m.fecha_hora, a.codigo, a.nombre, m.tipo_movimiento,
       m.cantidad, m.costo_unitario_aplicado, m.id_pedido, m.id_compra, m.motivo
from public.movimiento_inventario m
join public.articulo_inventariable a on a.id_articulo = m.id_articulo
order by m.fecha_hora desc, m.id_movimiento desc;

-- 18. Resumen de cobro por pedido: solicitado, verificado y saldo documental.
select pe.id_pedido, pe.codigo_pedido, pe.total_pedido,
       coalesce(sum(t.monto_con_signo) filter (
         where t.tipo_transaccion = 'PAGO' and t.estado_verificacion = 'VERIFICADO'), 0)
         as pagos_verificados,
       pe.total_pedido - coalesce(sum(t.monto_con_signo) filter (
         where t.tipo_transaccion = 'PAGO' and t.estado_verificacion = 'VERIFICADO'), 0)
         as saldo_documental
from public.pedido pe
left join public.transaccion t on t.id_pedido = pe.id_pedido
group by pe.id_pedido, pe.codigo_pedido, pe.total_pedido
order by pe.id_pedido;
