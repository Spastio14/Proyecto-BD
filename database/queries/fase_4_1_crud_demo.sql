-- Fase 4.1: ejemplos académicos de CRUD y consultas.
-- EJECUCIÓN SEGURA: todo queda dentro de una transacción que termina en ROLLBACK.
-- No cambiar ROLLBACK por COMMIT en un proyecto compartido.

begin;

-- INSERT: fila aislada de demostración.
insert into public.categoria (nombre, descripcion, estado)
values ('DEMO TEMPORAL', 'Fila creada dentro de una transacción reversible', 'ACTIVA')
returning id_categoria, nombre;

-- SELECT, WHERE, ORDER BY y concatenación.
select id_persona, concat_ws(' ', nombres, apellidos) as nombre_completo
from public.persona
where correo_electronico like '%@example.test'
order by nombre_completo;

-- UPDATE limitado a la fila recién creada.
update public.categoria
set descripcion = 'Ejemplo de actualización segura'
where nombre = 'DEMO TEMPORAL' and descripcion like 'Fila creada%'
returning id_categoria, descripcion;

-- GROUP BY y HAVING.
select estado, count(*) as cantidad
from public.pedido
group by estado
having count(*) >= 1
order by cantidad desc;

-- INNER, LEFT, RIGHT y FULL JOIN.
select p.nombre, c.nombre as categoria from public.producto p
inner join public.categoria c on c.id_categoria = p.id_categoria;
select c.nombre, p.nombre as producto from public.categoria c
left join public.producto p on p.id_categoria = c.id_categoria;
select c.nombre, p.nombre as producto from public.producto p
right join public.categoria c on c.id_categoria = p.id_categoria;
select pr.nombre, c.id_compra from public.proveedor pr
full join public.compra c on c.id_proveedor = pr.id_proveedor;

-- Subconsulta: artículos con existencia superior al promedio.
select codigo, nombre, existencia_actual
from public.articulo_inventariable
where existencia_actual > (select avg(existencia_actual) from public.articulo_inventariable);

-- INSERT ... SELECT: copia reversible de la categoría temporal.
insert into public.categoria (nombre, descripcion, estado)
select nombre || ' COPIA', descripcion, 'INACTIVA'
from public.categoria where nombre = 'DEMO TEMPORAL';

-- Vista académica: existe sólo hasta el ROLLBACK final.
create view public.v_demo_disponibilidad as
select a.id_articulo, a.codigo, a.existencia_actual,
       a.existencia_actual - coalesce(sum(r.cantidad_pendiente)
         filter (where r.estado = 'ACTIVA'), 0) as disponible
from public.articulo_inventariable a
left join public.reserva_inventario r on r.id_articulo = a.id_articulo
group by a.id_articulo, a.codigo, a.existencia_actual;

create or replace view public.v_demo_disponibilidad as
select a.id_articulo, a.codigo, a.existencia_actual,
       a.existencia_actual - coalesce(sum(r.cantidad_pendiente)
         filter (where r.estado = 'ACTIVA'), 0) as disponible,
       a.nombre
from public.articulo_inventariable a
left join public.reserva_inventario r on r.id_articulo = a.id_articulo
group by a.id_articulo, a.codigo, a.nombre, a.existencia_actual;

select * from public.v_demo_disponibilidad order by nombre;

-- DELETE seguro: sólo las filas de prueba creadas por este script.
delete from public.categoria
where nombre in ('DEMO TEMPORAL', 'DEMO TEMPORAL COPIA')
returning id_categoria, nombre;

-- ROLLBACK demuestra reversión y elimina también la vista temporal.
rollback;
