# Sublimación Doble R

Sistema web para gestionar las operaciones comerciales y administrativas de
Sublimación Doble R en Managua, Nicaragua.

La **Fase 1 (PostgreSQL)** está implementada en una rama de desarrollo. Su
fuente canónica son tres migraciones SQL que crean las 41 tablas conciliadas,
64 claves foráneas, restricciones, índices y una política RLS mínima. No se ha
desplegado ni conectado a un proyecto Supabase de producción.

## Tecnologías acordadas

- PostgreSQL/Supabase con migraciones SQL versionadas.
- Python 3.12, FastAPI, SQLAlchemy 2.x, Psycopg 3, Pydantic y Pytest para fases
  posteriores.
- Next.js, React, TypeScript y Tailwind CSS para fases posteriores.
- Supabase Auth y Storage privado, con RLS y privilegios mínimos.

## Estructura

```text
backend/                 API y reglas de negocio (fases posteriores)
database/
  queries/               consultas académicas PostgreSQL (fase posterior)
  reference/             inventario de fuentes históricas
  seeds/                 datos ficticios separados del DDL
  tests/                 reconstrucción y pruebas PostgreSQL reales
docs/
  modelos/               conciliación, diccionario y diferencias PostgreSQL
  pruebas/               estrategia y resultados ejecutados
  reglas-negocio/        reglas y matriz de trazabilidad
frontend/                aplicación Next.js (fase posterior)
supabase/migrations/      fuente canónica del esquema PostgreSQL
```

Las fuentes históricas `docs/S2R_BD.drawio.xml` y
`docs/copia - Sublimacion2R.sql` se conservan intactas. El SQL Server encontrado
no puede identificarse como “V3.0” con el historial disponible.

## Validación local

Se requiere Docker. Este comando usa una instancia efímera de PostgreSQL 17,
reconstruye dos bases vacías, carga el seed ficticio en una de ellas y ejecuta
las pruebas de integridad y RLS:

```bash
./database/tests/run.sh
```

El contenedor se elimina siempre al terminar. No usa credenciales reales ni
contacta un proyecto Supabase. Los detalles están en
[`docs/pruebas/fase-1-resultados.md`](docs/pruebas/fase-1-resultados.md).

## Documentación

- [Conciliación XML–SQL Server](docs/modelos/conciliacion-xml-sqlserver.md)
- [Diccionario de datos PostgreSQL](docs/modelos/diccionario-datos.md)
- [Diferencias de PostgreSQL](docs/modelos/diferencias-postgresql.md)
- [Matriz de trazabilidad](docs/reglas-negocio/matriz-trazabilidad.md)
- [Resultados de Fase 1](docs/pruebas/fase-1-resultados.md)
- [Plan técnico](docs/plan-implementacion.md)

`.env.example` contiene solo nombres de variables previstas. No se deben guardar
credenciales, datos personales reales ni seeds de demostración en producción.
