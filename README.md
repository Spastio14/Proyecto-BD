# Sublimación Doble R

Sistema comercial con esquema PostgreSQL reproducible, backend transaccional
FastAPI e integración local preparada para Supabase Auth y Storage privado. La
Fase 3 conserva las 41 tablas, verifica JWT por JWKS, vincula cuentas al modelo
existente y protege diseños y comprobantes con URLs firmadas.

## Componentes

- PostgreSQL 17 y migraciones canónicas en `supabase/migrations/`.
- Python 3.12, FastAPI, SQLAlchemy 2, Psycopg 3 y Pydantic 2.
- Cálculos monetarios con `Decimal` y `ROUND_HALF_UP`.
- Supabase Auth cerrado por defecto hasta inyectar configuración válida.
- Credencial firmada para invitados sin crear usuarios Auth convencionales.
- Buckets privados para diseños y comprobantes, mediados por FastAPI.
- Pytest contra PostgreSQL real, incluidas carreras con varias conexiones.

```text
backend/
  app/                   API, dominio, modelos, repositorios y servicios
  tests/                 integración, API y concurrencia PostgreSQL
  pyproject.toml          dependencias declaradas
  uv.lock                 versiones reproducibles
database/
  seeds/                 datos ficticios separados
  tests/                 pruebas estructurales de las 41 tablas
docs/                     arquitectura, reglas y evidencias
supabase/migrations/      única fuente canónica del DDL
```

## Validación

Desde Git Bash, con Docker y Python 3.12 instalados:

```bash
./database/tests/run.sh
./backend/tests/run.sh
```

El primer comando reconstruye dos bases y valida las 41 tablas. El segundo
inicia Uvicorn contra PostgreSQL y ejecuta servicios, endpoints, rollback e
interbloqueos concurrentes en bases aisladas.

La instalación base se explica en
[Backend Fase 2](docs/arquitectura/backend-fase-2.md). La configuración de Auth,
Storage, poolers, RLS, rotación y preflight está en
[Supabase Fase 3](docs/arquitectura/supabase-fase-3.md). Los resultados ejecutados
están en [Pruebas Fase 3](docs/pruebas/fase-3-resultados.md).

## Seguridad y alcance

Las rutas protegidas devuelven 401 mientras no exista configuración completa. El
backend verifica firma y claims del JWT y resuelve los permisos de empleado en
las tablas de roles de PostgreSQL. Las claves privadas y la cadena PostgreSQL se
inyectan como secretos y no se versionan.

No existe frontend, pasarela bancaria ni despliegue. La integración remota sigue
pendiente de preflight y autorización explícita. `.env`, credenciales, datos
personales y seeds reales no se versionan.
