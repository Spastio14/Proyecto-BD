# Resultados de pruebas de la Fase 4.3

## Alcance

La validación usa PostgreSQL 17 real y una base desechable. No se conectó a
Supabase remoto, no se crearon usuarios reales y no se aplicaron migraciones.
El esquema continúa con 41 tablas y cinco migraciones.

Se cubren estas áreas:

1. saldo y anticipo exactos;
2. pago pendiente frente a pago verificado;
3. rechazo de pagos duplicados por hito;
4. rechazo de sobrepagos;
5. reporte y confirmación idempotentes;
6. concurrencia de pagos;
7. reserva atómica al confirmar anticipo;
8. falta de inventario con rollback completo;
9. CRUD y estados de categorías;
10. CRUD y publicación de productos;
11. códigos únicos y estados de variantes;
12. escalas mayoristas sin solapamiento;
13. artículos nuevos con existencia cero;
14. compra confirmada e ingreso único de stock;
15. ajustes auditados sin consumir reservas;
16. composición incompleta;
17. cálculo de requerimientos, disponibilidad y costo;
18. conservación de la receta histórica reservada;
19. anticipo y diseño requeridos para producción;
20. consumo antes de completar producción;
21. saldo completo antes de entrega;
22. transiciones, historial y auditoría;
23. autorización y propiedad de recursos;
24. KPIs, periodo del tablero y rutas administrativas.

El comando canónico es:

```bash
./backend/tests/run.sh
```

La ejecución final del 7 de noviembre de 2026 obtuvo 215 pruebas Pytest
aprobadas y 2 omitidas por requerir opt-in remoto. Además aprobó 15 pruebas del
parser de preflight y 7 casos Node del flujo de sesión: 237 comprobaciones
aprobadas, 0 fallidas y 2 omitidas en total. El runner SQL se ejecutó aparte y
validó dos reconstrucciones, integridad, RLS, seeds, permisos y consultas.

La revisión visual del navegador no se ejecutó en este entorno. La sintaxis del
frontend y sus flujos de sesión sí se validaron automáticamente; esto no se
presenta como una prueba visual.

## Consultas de verificación

Después de un ciclo local, estas consultas permiten comprobar la trazabilidad:

```sql
select estado, count(*) from public.pedido group by estado order by estado;

select id_pedido, numero_hito, tipo_hito, monto_exigido, estado
from public.hito_pago order by id_pedido, numero_hito;

select id_pedido, tipo_transaccion, monto_con_signo, estado_verificacion
from public.transaccion order by id_transaccion;

select id_pedido, id_articulo, cantidad_reservada, cantidad_pendiente, estado
from public.reserva_inventario order by id_reserva;

select id_articulo, tipo_movimiento, cantidad, id_pedido, id_compra
from public.movimiento_inventario order by id_movimiento;

select accion, tipo_objeto_afectado, referencia_objeto, fecha_hora
from public.registro_auditoria order by id_auditoria desc limit 25;
```

No se calcula utilidad neta. Los documentos aprobados aún no definen una regla
contable completa que asigne compras, gastos, pérdidas, retenciones y
reembolsos al periodo sin doble conteo.
