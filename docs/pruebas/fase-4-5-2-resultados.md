# Fase 4.5.2 — resultados de pruebas

La validación se realizó localmente. No se escribió en Supabase, no se aplicó
la nueva migración remotamente y no se ejecutó un despliegue.

| Comprobación | Resultado |
|---|---|
| Parser del preflight | 15 aprobadas |
| JavaScript de sesión y presentación | 16 aprobadas |
| Pytest con PostgreSQL 17.11 | 272 aprobadas, 0 fallidas, 2 remotas omitidas |
| Migraciones desde base vacía | Aprobadas |
| Tablas principales después de migrar | 41 |
| Arranque FastAPI y `/api/v1/health` | Aprobado |
| Ruff | Aprobado |
| Sintaxis JavaScript | Aprobada |
| Chromium escritorio y móvil | 4 vistas aprobadas |
| Controles sin etiqueta / botones sin nombre | 0 / 0 |
| Errores JavaScript / desbordamientos | 0 / 0 |

Las 2 pruebas omitidas requieren credenciales privadas o Supabase CLI enlazado
y están marcadas como remotas. La restricción de esta fase impide ejecutarlas.

## Cobertura nueva

- detalles estructurados de FastAPI sin `[object Object]`;
- dos versiones de diseño descubiertas automáticamente;
- decisión sólo sobre la versión vigente;
- rechazo de acceso por otro cliente;
- aprobación externa con medio, referencia, evidencia y responsable;
- URL firmada sólo después de autorizar al dueño;
- reemplazo de fotografía y limpieza del archivo anterior;
- rechazo de MIME o firma falsa;
- rechazo de carga de fotografías por clientes sin autorización;
- cliente presencial individual, pedido y cotización trazables;
- personalización conservada en `DETALLE_PEDIDO`;
- límite de invitado y condición `DETALLE` conservados;
- identidad laboral bloqueada en el perfil propio;
- pedidos entregados fuera de la lista activa;
- permanencia de las 41 tablas.

La regresión cubrió además pagos, inventario, reservas, pérdidas, producción,
roles, invitaciones, autenticación, reportes, clientes y auditoría.

## Capturas

- [Catálogo del cliente, escritorio](../capturas/fase-4-5-2/cliente-catalogo-escritorio.png)
- [Detalle de producto, móvil](../capturas/fase-4-5-2/cliente-detalle-movil.png)
- [Diseños administrativos, escritorio](../capturas/fase-4-5-2/admin-disenos-escritorio.png)
- [Diseños administrativos, móvil](../capturas/fase-4-5-2/admin-disenos-movil.png)
- [Métricas de revisión](../capturas/fase-4-5-2/revision-visual.json)

Las capturas usan datos API simulados equivalentes al pedido informado y no
demuestran acceso a Supabase. Los flujos y permisos correspondientes sí fueron
ejecutados mediante pruebas de integración con PostgreSQL local.
