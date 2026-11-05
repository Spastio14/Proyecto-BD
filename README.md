# Sublimación Doble R

Sistema comercial con esquema PostgreSQL reproducible y backend transaccional
FastAPI. La Fase 2 implementa clientes, cotizaciones, precios, pedidos, pagos,
reservas, inventario, diseños, producción, pérdidas, auditoría y expiración.

## Componentes

- PostgreSQL 17 y migraciones canónicas en `supabase/migrations/`.
- Python 3.12, FastAPI, SQLAlchemy 2, Psycopg 3 y Pydantic 2.
- Cálculos monetarios con `Decimal` y `ROUND_HALF_UP`.
- Autenticación cerrada por defecto y preparada para Supabase Auth en Fase 3.
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

La instalación y ejecución manual se explican en
[Backend Fase 2](docs/arquitectura/backend-fase-2.md). Los resultados reales
están en [Pruebas Fase 2](docs/pruebas/fase-2-resultados.md).

## Seguridad y alcance

Las rutas protegidas devuelven 401 mientras no exista un proveedor de identidad
verificada. Las pruebas inyectan identidades solo dentro del proceso de test. Los
permisos de empleado se comprueban en las tablas de roles de PostgreSQL.

No existe frontend, pasarela bancaria, Supabase Auth, Storage ni despliegue en
esta fase. `.env.example` contiene valores de ejemplo; `.env`, credenciales,
datos personales y seeds reales no se versionan.
