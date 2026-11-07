# Resultados — permisos y consumo de producción

Fecha: 7 de noviembre de 2026 (America/Managua).

Las pruebas se ejecutaron en PostgreSQL 17.11 local. No se conectó ni escribió
en Supabase remoto.

## Resultado

```text
Backend completo: 256 aprobadas, 0 fallidas, 2 omitidas
Frontend: 10 aprobadas, 0 fallidas
Preflight Supabase: 15 aprobadas, 0 fallidas
Base de datos: 41 tablas, 64 FK e integridad/RLS aprobadas
```

Las dos pruebas omitidas requieren acceso remoto opt-in a Supabase. La única
advertencia corresponde a la deprecación futura de `TestClient` de Starlette.

La migración incremental se reaplicó dos veces después del seed local. La
consulta de verificación confirmó un solo permiso, una asignación para
ADMINISTRADOR, otra para PRODUCCION, ninguna para VENDEDOR o CONTADOR y ausencia
de `INVENTARIO_GESTIONAR` en PRODUCCION.

## Evidencia transaccional

El escenario integral creó un pedido autorizado, verificó el anticipo, aprobó
el diseño, inició producción y consumió una reserva de `1.000` unidad:

```text
existencia antes:       18.000
SALIDA_PRODUCCION:       1.000
existencia después:     17.000
cantidad pendiente:      0.000
estado de reserva:     AGOTADA
movimientos creados:         1
estado final:            LISTO
```

Una segunda petición devolvió el mismo identificador de movimiento y mantuvo la
existencia en `17.000`. Dos peticiones concurrentes también produjeron un solo
movimiento y un único descuento. La auditoría registró
`CONSUMIR_RESERVAS_PRODUCCION` con el empleado de PRODUCCION como responsable.

El panel de producción se revisó con Chromium en 1280 × 900 y 390 × 844. Mostró
exactamente iniciar para `EN_DISENO`, consumir para `EN_PRODUCCION` con reservas,
completar para `EN_PRODUCCION` agotado y ninguna acción para `LISTO`. No hubo
desbordamiento horizontal de la página en ninguna vista; las tablas conservan
su desplazamiento interno en móvil.
