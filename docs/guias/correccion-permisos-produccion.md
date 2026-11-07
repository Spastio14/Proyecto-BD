# Permiso y consumo de reservas de producción — post Fase 4.4

Esta corrección añade `INVENTARIO_CONSUMIR_RESERVAS` para que PRODUCCION pueda
consumir materiales ya reservados sin recibir `INVENTARIO_GESTIONAR`. El permiso
administrativo continúa protegiendo altas de artículos, ajustes, costos y
cambios generales de inventario.

## Matriz resultante

| Rol | Consultar | Consumir reservas | Administrar inventario |
|---|---:|---:|---:|
| ADMINISTRADOR | Sí | Sí | Sí |
| PRODUCCION | Sí | Sí | No |
| CONTADOR | Sí | No | No |
| VENDEDOR | Según su matriz vigente | No | No |

El script incremental es
`supabase/migrations/202611070002_inventory_consume_reservations_permission.sql`.
Es idempotente: inserta o actualiza un permiso y añade dos asignaciones con
`ON CONFLICT DO NOTHING`. También precisa la descripción del permiso general
sin cambiar sus asignaciones. No elimina ni reconstruye la matriz existente.

## Invariantes del backend

`POST /api/v1/inventario/pedidos/{id}/consumir` exige el permiso nuevo y bloquea
el pedido, sus reservas y los artículos afectados. Sólo admite `EN_PRODUCCION`.
Cada reserva activa se consume por su cantidad pendiente, genera una
`SALIDA_PRODUCCION`, descuenta la existencia física, pasa a `AGOTADA` y queda en
cero. Una repetición durante `EN_PRODUCCION` devuelve el movimiento existente y
no vuelve a descontar. Un pedido `LISTO`, cancelado, expirado, entregado o en
otra etapa queda rechazado.

`POST /api/v1/produccion/pedidos/{id}/completar` mantiene el permiso
`PRODUCCION_INICIAR`, exige todas las reservas agotadas y rechaza la ausencia de
reservas cuando el pedido contiene variantes que requieren producción.

El resumen `GET /api/v1/pedidos/{id}/operacion` combina estado, reservas y
permisos efectivos. El panel sólo muestra iniciar, consumir o completar cuando
la acción aparece en `produccion.acciones_permitidas` y el JWT resuelto por
`/auth/me` contiene el permiso correspondiente.

## Aplicación manual posterior en Supabase

Esta corrección no fue aplicada al proyecto remoto. Desde Git Bash, con
Supabase CLI autenticado y el repositorio situado en esta rama:

```bash
supabase link --project-ref iwvmbdfkxrssduoqobgy
supabase migration list
supabase db push --dry-run
```

El dry-run debe mostrar `202611070002_inventory_consume_reservations_permission`
y cualquier otra migración local todavía pendiente. No se debe ejecutar el push
si aparecen cambios que no hayan sido aprobados por separado. Tras revisar el
plan y recibir autorización expresa:

```bash
supabase db push
supabase migration list
```

La comprobación de sólo lectura posterior, desde SQL Editor o `psql`, es:

```sql
select r.nombre, p.codigo_permiso
from public.rol r
join public.rol_permiso rp using (id_rol)
join public.permiso p using (id_permiso)
where p.codigo_permiso = 'INVENTARIO_CONSUMIR_RESERVAS'
order by r.nombre;
```

El resultado esperado contiene exactamente `ADMINISTRADOR` y `PRODUCCION`.
También debe comprobarse que PRODUCCION no recibió `INVENTARIO_GESTIONAR`.

## Prueba manual con una cuenta PRODUCCION

1. Iniciar sesión y comprobar en `/api/v1/auth/me` que aparecen
   `PRODUCCION_INICIAR`, `INVENTARIO_CONSULTAR` e
   `INVENTARIO_CONSUMIR_RESERVAS`, pero no `INVENTARIO_GESTIONAR`.
2. Abrir **Diseños → Operación de producción**.
3. En `EN_DISENO`, aprobar el diseño e iniciar producción.
4. En `EN_PRODUCCION`, usar **Consumir reservas**. La acción desaparece después
   del consumo y aparece **Completar producción**.
5. Completar y comprobar el estado `LISTO`.
6. Abrir Inventario: la consulta debe funcionar, pero los formularios de alta,
   ajuste y cambio de costo no deben mostrarse. Las llamadas directas a esos
   endpoints deben responder `403`.

Los mensajes del panel explican si faltan diseños, reservas, materiales o el
permiso necesario. Todas las validaciones se repiten en el backend.
