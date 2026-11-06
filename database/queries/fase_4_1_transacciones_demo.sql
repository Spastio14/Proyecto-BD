-- Demostraciones transaccionales controladas. Ejecutar cada bloque por separado.
-- Los bloques A y B revierten siempre; C debe abrirse en dos sesiones de psql.

-- A. Error de FK y recuperación de la transacción (no deja cambios).
begin;
savepoint antes_fk;
-- Debe fallar porque el proveedor -999 no existe:
insert into public.compra
  (id_proveedor, fecha_compra, numero_documento, estado, total_compra)
values (-999, now(), 'DEMO-FK', 'BORRADOR', 0);
rollback to savepoint antes_fk;
select 'La sesión se recuperó después de la violación FK' as resultado;
rollback;

-- B. Rollback explícito con verificación antes/después.
select existencia_actual as antes from public.articulo_inventariable where id_articulo = 1;
begin;
update public.articulo_inventariable set existencia_actual = existencia_actual + 30
where id_articulo = 1;
select existencia_actual as durante from public.articulo_inventariable where id_articulo = 1;
rollback;
select existencia_actual as despues from public.articulo_inventariable where id_articulo = 1;

-- C. Concurrencia (dos terminales). La segunda sesión espera el COMMIT de la primera.
-- SESIÓN 1:
-- begin;
-- select id_compra, estado from public.compra where id_compra = 1 for update;
-- update public.compra set numero_documento = numero_documento where id_compra = 1;
-- commit;
-- SESIÓN 2, mientras sesión 1 conserva el bloqueo:
-- begin;
-- select id_compra, estado from public.compra where id_compra = 1 for update;
-- rollback;

-- D. Idempotencia de pagos (sólo lectura): la clave es única en la base.
select clave_idem, count(*) as repeticiones
from public.transaccion
group by clave_idem
having count(*) > 1;
-- La consulta debe devolver cero filas. La API retorna la misma transacción al reintentar
-- POST /api/v1/pagos/pedidos/{id}/reportar con la misma idempotency_key.
