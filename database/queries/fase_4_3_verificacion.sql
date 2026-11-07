-- Verificación de sólo lectura para la operación integral de Fase 4.3.
-- No crea objetos ni altera datos.

select estado, count(*) as cantidad
from public.pedido
group by estado
order by estado;

select p.codigo_pedido,
       p.total_pedido,
       coalesce(sum(t.monto_con_signo) filter (
           where t.tipo_transaccion = 'PAGO'
             and t.estado_verificacion = 'VERIFICADO'
       ), 0) as total_verificado,
       p.total_pedido - coalesce(sum(t.monto_con_signo) filter (
           where t.tipo_transaccion = 'PAGO'
             and t.estado_verificacion = 'VERIFICADO'
       ), 0) as saldo_pendiente
from public.pedido p
left join public.transaccion t on t.id_pedido = p.id_pedido
group by p.id_pedido, p.codigo_pedido, p.total_pedido
order by p.id_pedido;

select a.codigo,
       a.nombre,
       a.existencia_actual,
       coalesce(sum(r.cantidad_pendiente) filter (where r.estado = 'ACTIVA'), 0) as reservado,
       a.existencia_actual
           - coalesce(sum(r.cantidad_pendiente) filter (where r.estado = 'ACTIVA'), 0)
           as disponible,
       a.existencia_minima
from public.articulo_inventariable a
left join public.reserva_inventario r on r.id_articulo = a.id_articulo
group by a.id_articulo, a.codigo, a.nombre, a.existencia_actual, a.existencia_minima
order by a.nombre;

select v.codigo_variante,
       a.codigo as articulo,
       c.cantidad_estandar,
       a.unidad_medida,
       c.cantidad_estandar * a.costo_referencia as costo_estandar
from public.composicion_producto c
join public.variante_producto v on v.id_variante = c.id_variante
join public.articulo_inventariable a on a.id_articulo = c.id_articulo
order by v.codigo_variante, a.codigo;

select fecha_hora, accion, tipo_objeto_afectado, referencia_objeto, id_persona_actor
from public.registro_auditoria
order by id_auditoria desc
limit 25;
