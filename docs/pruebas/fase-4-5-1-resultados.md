# Fase 4.5.1 — resultados de pruebas

La validación se realizó localmente. No se conectó ni escribió en Supabase y no
se ejecutaron migraciones o despliegues remotos.

## Resultados

| Comprobación | Resultado |
|---|---|
| Parser del preflight | 15 aprobadas |
| Pruebas JavaScript de sesión y presentación | 15 aprobadas |
| Pytest con PostgreSQL 17.11 | 262 aprobadas, 0 fallidas, 2 remotas omitidas |
| Arranque FastAPI y `/api/v1/health` | Aprobado contra PostgreSQL local |
| Ruff en archivos Python modificados | Aprobado |
| Sintaxis JavaScript | Aprobada |
| Chromium en 1440, 1024, 768 y 390 px | 9 escenarios aprobados |
| Accesibilidad visual automatizada | 0 controles sin etiqueta, 0 acciones sin nombre |
| Desbordamiento horizontal | 0 escenarios con desbordamiento del documento |
| Errores JavaScript durante las vistas | 0 |

## Casos nuevos de backend

- contrato reducido de pedido y detalle del portal;
- ausencia recursiva de IDs de persona, cliente, pedido, cotización, transacción,
  material, costos, permisos, claves idempotentes y UUID de autenticación;
- intento de leer el pedido de otro cliente;
- intento de decidir la cotización de otro cliente;
- rechazo de empleados en endpoints exclusivos del portal;
- precio del catálogo calculado por `PricingService`;
- resumen y pagos sin referencias internas;
- presencia de tablas con columnas explícitas.

## Casos nuevos de frontend

- traducción explícita de estados y acciones;
- fallback para códigos desconocidos;
- moneda NIO y cantidades;
- conversión horaria a `America/Managua`;
- ocultamiento de códigos de permisos en mensajes;
- seguimiento de 6 etapas para producción y 4 para pedidos que no la requieren.

La regresión completa cubre además autenticación, roles, invitaciones, pedidos,
cotizaciones, pagos, inventario, reservas, producción, pérdidas, administración
y permisos separados. Las 2 pruebas omitidas requieren opt-in y credenciales de
Supabase remoto, prohibidas para esta ejecución.

