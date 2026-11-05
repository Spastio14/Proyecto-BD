# Resultados de pruebas — Fase 1

Fecha de ejecución: 5 de noviembre de 2026 (UTC).

## Entorno y comando

- Imagen: `postgres:17-alpine` oficial, instancia efímera Docker.
- Versión ejecutada: PostgreSQL 17.11.
- Comando: `./database/tests/run.sh`.
- Datos: seed ficticio `database/seeds/001_demo.sql`.
- Credenciales: contraseña local desechable; sin conexión a Supabase remoto.

## Resultado

El runner terminó con código 0 y emitió:

```text
OK: 41 tablas, 64 FK, nombres conciliados, integridad y RLS verificados.
OK: dos reconstrucciones limpias y pruebas PostgreSQL/RLS completadas.
```

Se reconstruyeron dos bases independientes desde cero. En la primera también se
cargaron las 41 tablas del seed y se comprobaron:

- 41 tablas, 41 PK, 64 FK y RLS habilitado en las 41;
- 19 UNIQUE, 119 CHECK, una exclusión de rangos y 51 índices explícitos;
- presencia de las 57 equivalencias de nombres oficiales;
- `UNIQUE pedido.id_cotizacion` y pertenencia de la cotización al cliente;
- exclusión de rangos mayoristas activos solapados;
- tipos y límites de promoción, FK de promoción en detalle y ambos signos de
  compensación;
- ventana inicial exacta de 24 horas e inicio de revisión limitado a ella;
- descuentos con valor predeterminado cero y motivo de reembolso no vacío;
- coherencia actor/origen de auditoría y catálogo de pérdidas;
- lectura del catálogo como `anon`, rechazo de `persona` y ausencia de escritura.

La primera ejecución descubrió un desbordamiento al representar un rango
mayorista abierto con `int4range` inclusivo. Se sustituyó por `int8range`, se
eliminó el contenedor fallido y la ejecución completa posterior pasó. El runner
elimina su contenedor incluso ante error.

## Alcance pendiente

No se probaron Supabase Auth/Storage ni políticas por propietario porque aún no
existe su integración. Tampoco hay servicios FastAPI para probar concurrencia,
redondeo, transiciones, reservas o idempotencia de extremo a extremo. Esos casos
permanecen definidos en la matriz para la Fase 2 y la fase de Supabase.
