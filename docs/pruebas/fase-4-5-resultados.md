# Fase 4.5 — resultados de validación visual

La validación se ejecutó sin despliegue y sin conexión ni escrituras en el
proyecto Supabase remoto.

## Alcance comprobado

- escaparate público y acceso;
- portal del cliente;
- administración;
- shells de ventas, contabilidad y producción;
- activación privada de empleados;
- catálogo dinámico, tablas, formularios, estados vacíos y navegación por rol.

## Ejecuciones

| Comprobación | Resultado |
|---|---|
| Sintaxis de `app.js`, `dashboard.js` y `activation.js` | Aprobada |
| Pruebas Node de sesión, invitaciones y permisos | 10 aprobadas |
| Chromium 1440 × 1000 px | 3 vistas aprobadas |
| Chromium 390 × 844 px | 3 vistas aprobadas |
| Etiquetas, nombres accesibles, foco y ancho de documento | 6 escenarios aprobados |
| PostgreSQL local | PostgreSQL 17.11 aislado |
| Parser del preflight de Supabase | 15 aprobadas |
| Regresión pytest | 256 aprobadas, 0 fallidas, 2 remotas omitidas |
| Arranque FastAPI y `/api/v1/health` | Aprobado contra PostgreSQL |

La prueba de disponibilidad del frontend se actualizó para verificar la nueva
promesa comercial «Hazlo tuyo. Nosotros lo hacemos real.» en lugar del texto
técnico retirado «Sistema de demostración».

La ejecución final de `backend/tests/run.sh -q` terminó con 0 fallos. Las 2
omisiones corresponden a verificaciones remotas que requieren opt-in y
credenciales privadas. Se observó 1 aviso externo de deprecación entre Starlette
y `httpx`; no afecta el resultado funcional.
