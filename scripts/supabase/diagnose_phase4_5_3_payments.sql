-- Diagnóstico estrictamente de solo lectura. Ejecutar con psql pasando
-- order_code_1 y order_code_2 mediante -v para no guardar códigos operativos.
-- No contiene UPDATE, DELETE, INSERT, DDL ni llamadas remotas.

begin transaction read only;

with pedidos_objetivo as (
    select id_pedido, codigo_pedido, total_pedido, estado
    from public.pedido
    where codigo_pedido in (:'order_code_1', :'order_code_2')
)
select *
from pedidos_objetivo
order by codigo_pedido;

select
    p.codigo_pedido,
    h.numero_hito,
    h.tipo_hito,
    h.monto_exigido,
    h.estado as estado_guardado
from public.pedido p
join public.hito_pago h on h.id_pedido = p.id_pedido
where p.codigo_pedido in (:'order_code_1', :'order_code_2')
order by p.codigo_pedido, h.numero_hito;

select
    p.codigo_pedido,
    t.id_transaccion,
    t.numero_hito as hito_heredado,
    t.fecha_hora,
    t.tipo_transaccion,
    t.monto_con_signo,
    t.metodo_pago,
    t.banco_origen,
    t.banco_receptor,
    t.referencia_bancaria,
    t.estado_verificacion,
    t.id_empleado_verificador
from public.pedido p
join public.transaccion t on t.id_pedido = p.id_pedido
where p.codigo_pedido in (:'order_code_1', :'order_code_2')
order by p.codigo_pedido, t.fecha_hora, t.id_transaccion;

select
    p.codigo_pedido,
    a.id_transaccion,
    a.numero_hito,
    a.monto_aplicado,
    t.estado_verificacion
from public.pedido p
join public.aplicacion_transaccion_hito a on a.id_pedido = p.id_pedido
join public.transaccion t on t.id_transaccion = a.id_transaccion
where p.codigo_pedido in (:'order_code_1', :'order_code_2')
order by p.codigo_pedido, a.id_transaccion, a.numero_hito;

select
    p.codigo_pedido,
    p.total_pedido,
    coalesce(sum(t.monto_con_signo) filter (
        where t.tipo_transaccion = 'PAGO'
          and t.estado_verificacion = 'VERIFICADO'
    ), 0) as total_verificado_sin_duplicar,
    coalesce(sum(t.monto_con_signo) filter (
        where t.tipo_transaccion = 'PAGO'
          and t.estado_verificacion = 'PENDIENTE'
    ), 0) as total_pendiente_verificacion
from public.pedido p
left join public.transaccion t on t.id_pedido = p.id_pedido
where p.codigo_pedido in (:'order_code_1', :'order_code_2')
group by p.id_pedido, p.codigo_pedido, p.total_pedido
order by p.codigo_pedido;

rollback;
