# Resultados de pruebas — Fase 4.1

Fecha de ejecución: 2026-11-06. Entorno: PostgreSQL 17.11 en contenedores
Docker locales y Python 3.12.14. No se conectó ni escribió en Supabase remoto.

## Resultados ejecutados

| Comando | Resultado |
|---|---|
| `./database/tests/run.sh` | Aprobado: dos reconstrucciones limpias, 41 tablas, 64 FK, integridad, RLS, seed 4.1 y scripts de reportes/CRUD |
| `./backend/tests/run.sh` | Aprobado: 137 pruebas, 2 remotas omitidas por falta de opt-in, 1 aviso de deprecación externo |
| `node --check frontend/app.js` | Aprobado: JavaScript válido |
| `ruff check backend` | Aprobado |
| `git diff --check` | Aprobado |

## Cobertura añadida

Los casos 110–120 comprueban decisiones y conversión de cotizaciones,
propiedad de pedidos, detalles e historial, compra atómica, incremento único de
inventario, confirmación concurrente idempotente, permisos, entrega, reportes,
archivos estáticos y rutas de consulta/rechazo de pagos.

Los casos anteriores siguen cubriendo anticipos del 50 %, reservas,
idempotencia de pagos, diseños vigentes, producción, consumo, pérdidas,
auditoría, autenticación Supabase, recuperación segura de vínculos y Storage
privado.

## Límites comprobados

- Las dos pruebas remotas permanecen omitidas porque requieren credenciales y
  autorización explícita; esto evita modificar el proyecto de desarrollo.
- Los reembolsos no tienen endpoint de escritura porque faltan reglas
  financieras definitivas. La tabla existente no se alteró.
- El aviso `StarletteDeprecationWarning` procede de la combinación instalada de
  `fastapi.testclient` y `httpx`; no produjo fallos funcionales.
