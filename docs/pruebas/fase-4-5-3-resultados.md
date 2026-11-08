# Resultados de pruebas — Fase 4.5.3

Validación local contra PostgreSQL 17.11:

- 294 pruebas backend aprobadas inicialmente tras integrar la fase.
- 2 pruebas remotas omitidas porque requieren credenciales privadas y opt-in.
- 18 pruebas frontend aprobadas.
- 15 pruebas del parser de preflight aprobadas.
- Uvicorn y `/api/v1/health` respondieron contra PostgreSQL.

La suite específica comprueba límites concurrentes, múltiples abonos, pagos
mixtos, distribución entre hitos, confirmación fuera de orden, rechazo y
reintento, idempotencia, caja, folios, auditoría, referencias bancarias y
consistencia frente a estados de hito obsoletos.

Las capturas responsive están en `docs/capturas/fase-4-5-3/` y utilizan datos
ficticios. Se verificaron tamaños de 1440x1000 y 390x844 con Chromium local.

Los dos pedidos señalados por el propietario no se consultaron en Supabase real
porque este entorno no tiene credenciales remotas habilitadas. El
script `scripts/supabase/diagnose_phase4_5_3_payments.sql` deja preparadas las
consultas de solo lectura. No se alteraron registros para reproducir el problema.
