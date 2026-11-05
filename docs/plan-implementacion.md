# Plan técnico de implementación

## Fase 0 — Auditoría y preparación

Estado: completada, revisada y conciliada por el propietario.

La conciliación posterior está documentada en
`docs/modelos/conciliacion-xml-sqlserver.md`. Sus decisiones semánticas bloquean
la Fase 1 hasta recibir aprobación expresa.

Criterios cubiertos:

- historial y archivos inspeccionados;
- 41 tablas verificadas en XML y T-SQL;
- discrepancias y decisiones pendientes documentadas;
- arquitectura, seguridad, migraciones y pruebas definidas;
- reglas permanentes guardadas en `AGENTS.md`;
- matriz de trazabilidad creada;
- estructura inicial preparada sin crear un esquema alternativo.

## Fase 1 — PostgreSQL

Estado: implementada y validada en la rama de desarrollo; pendiente de revisión
final del propietario. No se desplegó ni se aplicó a Supabase remoto.

### Secuencia

1. Congelar una tabla de correspondencia por entidad: nombre aprobado, columnas,
   nulabilidad, PK, UQ, CHECK, FK, acción de borrado e índices.
2. Resolver la relación 64 y todos los nombres abreviados.
3. Definir la convención PostgreSQL: esquema, nombres, identidades, UUID,
   `numeric`, `timestamptz`, estados y extensiones permitidas.
4. Crear migraciones ordenadas en `supabase/migrations/`, separando tablas,
   relaciones, índices y políticas.
5. Convertir sintaxis T-SQL:
   - `IDENTITY` → `GENERATED ... AS IDENTITY`;
   - `UNIQUEIDENTIFIER`/`NEWID()` → `uuid`/`gen_random_uuid()`;
   - `DATETIME2` → `timestamptz` o tipo aprobado según semántica;
   - `VARCHAR(MAX)` → `text`;
   - corchetes y `dbo` → convención PostgreSQL aprobada;
   - `TOP` → `LIMIT`; concatenación `+` → `concat` o `||`.
6. Implementar restricciones estructurales y revisar las seis FK con cascada
   que forman parte de cuatro composiciones o tablas puente.
7. Añadir índices de FK y de los patrones críticos; justificar cada índice.
8. Preparar seeds separados e idempotentes, sin fechas o identidades que
   comprometan producción.
9. Crear pruebas estructurales y levantar la base desde cero dos veces.
10. Probar compatibilidad en Supabase local y documentar extensiones/RLS.

### Criterios de aceptación

- exactamente 41 tablas aprobadas, sin entidades sustitutas;
- migración completa desde una base PostgreSQL vacía;
- todas las PK, FK, UQ, NOT NULL y CHECK reconciliadas con la matriz aprobada;
- ninguna cascada no justificada sobre historia o finanzas;
- índices verificados con consultas representativas y `EXPLAIN` cuando proceda;
- seeds reproducibles en entorno de prueba y bloqueados para producción;
- pruebas de integridad ejecutadas en PostgreSQL real;
- evidencia de compatibilidad con la versión de PostgreSQL de Supabase;
- documentación de diferencias respecto al T-SQL;
- árbol Git sin secretos ni cambios accidentales en las fuentes originales.

## Fase 2 — Backend y transacciones

Crear el proyecto FastAPI, configuración tipada, SQLAlchemy/Psycopg, servicios y
repositorios. Priorizar identidad, clientes, pedidos, pagos e inventario. Cada
regla concurrente debe probarse con conexiones PostgreSQL reales.

Criterio de salida: API inicia, OpenAPI es coherente, reglas críticas y rollback
están probados, y no existe lógica económica duplicada en frontend o SQL.

## Fase 3 — Supabase

Vincular Auth con `PERSONA`/`CUENTA_ACCESO`, configurar RLS y Storage privado y
probar accesos permitidos y denegados. Las credenciales se introducirán por un
medio seguro.

## Fases 4 a 7

- **Fase 4:** módulos operativos completos y auditables.
- **Fase 5:** consultas académicas, reportes, `EXPLAIN ANALYZE` y optimización.
- **Fase 6:** portal público, panel de empleados y panel administrativo.
- **Fase 7:** despliegue autorizado, variables seguras y validación final.

Cada fase requiere aprobación independiente. Ningún despliegue, migración de
producción, seed de prueba o integración financiera está implícitamente autorizado.

## Riesgos principales

| Riesgo | Efecto | Tratamiento |
|---|---|---|
| Fuente V3.0 no confirmada | Migrar un modelo obsoleto | Resolver antes de Fase 1 |
| Relación 63/64 | Divergencia entre diagrama y DDL | Decisión explícita y prueba de FK |
| Nombres abreviados | API y migraciones incompatibles | Diccionario aprobado por columna |
| Límites bajo concurrencia | Pedidos o reservas superiores al límite | Bloqueos y pruebas de carrera |
| Saldos materializados | Stock o total incoherente | Un solo servicio transaccional por operación |
| Doble conteo de pérdidas | Utilidad incorrecta | Linaje del movimiento y reportes probados |
| Cuenta sombra insegura | Exposición de datos personales | Credencial opaca, propiedad y auditoría |
| RLS incompleta | Fuga entre clientes | Matriz de identidades permitidas/denegadas |
| Seeds mezclados con DDL | Datos ficticios en producción | Separación física y guardas de entorno |
