# Fase 4.3: operación comercial integral

Esta fase completa la operación local de catálogo, inventario, pedidos,
producción, entrega y tablero administrativo. Conserva las 41 tablas y las
cinco migraciones canónicas. No requiere migraciones adicionales ni cambios en
Supabase remoto.

## Preparación local

1. Configure `backend/.env` a partir de `backend/.env.example` con una base
   PostgreSQL 17 local. No copie claves al repositorio.
2. Aplique las cinco migraciones y los seeds de demostración únicamente a esa
   base local.
3. Ejecute `./backend/tests/run.sh`. El runner crea una base desechable,
   comprueba el esquema y elimina el contenedor al terminar.
4. Inicie FastAPI y abra `/app/`. El backend consulta la identidad, roles y
   permisos antes de mostrar el dashboard correspondiente.

Las cuentas de demostración deben crearse con los procedimientos de
`docs/guias/fase-4-2-empleados-roles.md`. El registro público crea sólo clientes.
El primer administrador se vincula con `bootstrap_admin` después de verificar
la identidad en Supabase Auth. Nunca guarde contraseñas de demostración en Git.

## Catálogo e inventario

Un administrador con `CATALOGO_GESTIONAR` puede mantener categorías,
productos, variantes, escalas y composiciones desde **Catálogo y recetas**. Los
códigos de variante son únicos y los rangos mayoristas activos no pueden
solaparse. Una variante que requiere producción y no tiene componentes se
presenta como composición incompleta.

Los artículos nuevos siempre nacen con existencia cero. El inventario físico
sólo cambia mediante una compra confirmada, un ajuste autorizado, producción o
pérdida. Los ajustes requieren motivo, generan `MOVIMIENTO_INVENTARIO` y se
auditan. Una salida manual no puede consumir unidades reservadas.

Cuando un pedido todavía no tiene una reserva, su composición queda protegida
contra cambios. Al confirmar el anticipo se crea una reserva con las cantidades
de esa receta. Los cambios posteriores se aplican a pedidos futuros y no
reescriben la reserva histórica.

## Ciclo de un pedido

1. El cliente crea un pedido. Los precios y descuentos quedan guardados en el
   detalle.
2. En **Pagos**, el resumen muestra el anticipo, el monto pendiente de
   verificación, el total verificado y el saldo. Sólo ofrece hitos que admiten
   un nuevo reporte.
3. Un empleado autorizado confirma el anticipo. La confirmación reserva los
   materiales en la misma transacción; si no hay inventario, todo se revierte.
4. Se inicia diseño, se carga una versión privada y se aprueba la versión
   vigente.
5. Producción inicia sólo con anticipo, diseño y reserva válidos. Después se
   consumen las reservas y se completa producción. El endpoint genérico de
   estados no puede marcar el pedido como `LISTO`.
6. El cliente reporta el saldo y un empleado lo confirma.
7. Se programa el envío cuando corresponda y se completa la entrega. Un pedido
   con saldo pendiente no puede pasar a `ENTREGADO`.

`GET /api/v1/pedidos/{id}/operacion` reúne hitos, diseños, reservas, producción,
entrega y la siguiente acción segura. Cada transición deja historial y las
acciones críticas dejan auditoría.

## Tablero y permisos

El tablero administrativo muestra pedidos por estado, pagos pendientes,
compras confirmadas, inventario bajo mínimo y actividad reciente. El parámetro
`days` de `/api/v1/reportes/resumen` acepta de 1 a 3650 días y limita los datos
del periodo que sí tienen fecha contable definida.

Los clientes sólo ven sus pedidos, pagos, cotizaciones y diseños. Los empleados
reciben las opciones permitidas por PostgreSQL. Ocultar una opción en el
navegador no sustituye la autorización: cada endpoint vuelve a validar el
permiso.

## Comprobación manual en navegador

Use datos ficticios y una base local. Compruebe el flujo completo con un
cliente y un administrador, actualice la página después de cada operación y
revise que `/auth/me` restaure la sesión. En las herramientas de desarrollo
confirme que no se almacenen tokens en URLs o HTML y que los errores 401, 403,
409, 429 y 503 conserven su mensaje específico.

La validación automática no sustituye una revisión visual. Verifique en tamaños
móvil, tableta y escritorio el menú lateral, formularios, tablas con scroll y
mensajes de error antes de una demostración.
