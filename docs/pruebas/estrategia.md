# Estrategia de pruebas

## Objetivo

Las pruebas deben demostrar reglas e integridad con el mismo motor usado en
producción. SQLite no sirve como sustituto para concurrencia, tipos PostgreSQL,
restricciones diferibles, índices parciales ni RLS.

## Capas previstas

1. **Unitarias:** cálculos con `Decimal`, selección de precios, transiciones y
   políticas puras sin acceso a red.
2. **Integración PostgreSQL:** migraciones desde cero, PK/FK/CHECK/UNIQUE,
   transacciones, repositorios y servicios.
3. **Concurrencia:** dos conexiones reales coordinadas para límites de pedidos,
   última unidad, idempotencia y doble liberación.
4. **API:** autenticación, autorización, errores y rollback de casos de uso.
5. **Supabase:** RLS, Auth y Storage en un proyecto local o de pruebas aislado.
6. **Frontend:** flujos críticos contra una API de pruebas, sin presentar mocks
   como datos reales.

## Entorno aislado

- Base efímera o esquema dedicado creado para cada ejecución.
- Migraciones canónicas aplicadas desde cero.
- Seeds ficticios, idempotentes y controlados.
- Zona de presentación `America/Managua`; persistencia de instantes en UTC.
- Credenciales de servicio disponibles solo en el proceso de prueba.

## Casos mínimos de reglas

La implementación debe cubrir todos los casos de la matriz de trazabilidad y,
como mínimo: invitado con 5 y 6 unidades; segundo pedido activo de invitado;
tercer pedido pendiente de registrado; reserva solo tras anticipo; competencia
por última unidad; pago y movimiento duplicados; expiración; cancelación y doble
liberación; aprobación por versión; producción sin aprobación; pérdidas; compra;
permisos; propiedad de datos; redondeo; FK inválida y rollback completo.

## RLS

Para cada política se probarán al menos cuatro identidades: anónima, cliente
propietario, cliente ajeno y empleado con/sin permiso. Las pruebas comprobarán
lectura y escritura permitida y denegada. Una policy existente sin estos casos no
se considera validada.

## Evidencia

Cada fase registrará comando, versión del motor, número de pruebas, resultado,
fallos esperados, omitidos y fecha. Un comando no ejecutado no se marcará como
exitoso.

## Estado en Fase 1

La estructura, las migraciones, el seed y la RLS mínima ya se prueban en
PostgreSQL 17 real mediante `database/tests/run.sh`. La evidencia está en
`docs/pruebas/fase-1-resultados.md`.

Las pruebas de servicios, concurrencia, Auth, Storage y propiedad por cliente
siguen pendientes porque requieren el backend y la integración Supabase de fases
posteriores. No se presentan como ejecutadas.
