# Sublimación Doble R

Sistema web para gestionar las operaciones comerciales y administrativas de
Sublimación Doble R, un negocio de personalización de productos en Managua,
Nicaragua.

El proyecto se encuentra en **Fase 0: auditoría y preparación**. En esta fase se
documentaron las fuentes disponibles y las reglas del negocio, pero todavía no
se ha creado el esquema PostgreSQL definitivo. La conversión comenzará cuando el
propietario confirme las discrepancias registradas en
[`docs/modelos/auditoria-fuentes.md`](docs/modelos/auditoria-fuentes.md).

## Tecnologías acordadas

- PostgreSQL alojado en Supabase, con migraciones SQL versionadas.
- Python 3.12, FastAPI, SQLAlchemy 2.x, Psycopg 3, Pydantic y Pytest.
- Next.js, React, TypeScript y Tailwind CSS.
- Supabase Auth y Storage, con RLS y privilegios mínimos.

Las versiones exactas se fijarán al iniciar la fase que introduce cada
componente. No se agregaron dependencias durante la Fase 0 porque aún no existe
código ejecutable.

## Fuentes actuales

- `docs/S2R_BD.drawio.xml`: diagrama editable con el MERE y el modelo
  relacional de 41 tablas.
- `docs/copia - Sublimacion2R.sql`: referencia SQL Server con 41 tablas,
  restricciones, datos de demostración y consultas preliminares.

El archivo SQL no está identificado dentro del repositorio como “V3.0” ni como
versión aprobada. Se conserva sin modificar como referencia histórica.

## Estructura preparada

```text
backend/                 API y reglas de negocio (fases posteriores)
database/
  queries/               consultas académicas PostgreSQL
  reference/             inventario de fuentes históricas
  seeds/                 datos ficticios reproducibles
docs/
  arquitectura/          decisiones y límites técnicos
  modelos/               auditoría del modelo de datos
  pruebas/               estrategia y evidencias
  reglas-negocio/        reglas y matriz de trazabilidad
frontend/                aplicación Next.js (fase posterior)
supabase/
  migrations/            fuente canónica futura del esquema PostgreSQL
```

## Documentación de la Fase 0

- [Informe de auditoría](docs/modelos/auditoria-fuentes.md)
- [Arquitectura acordada](docs/arquitectura/arquitectura.md)
- [Matriz de trazabilidad](docs/reglas-negocio/matriz-trazabilidad.md)
- [Estrategia de pruebas](docs/pruebas/estrategia.md)
- [Plan técnico](docs/plan-implementacion.md)

## Configuración futura

Los nombres previstos de las variables están en `.env.example`. Ese archivo no
contiene secretos. Las credenciales reales se introducirán por medios seguros y
nunca se guardarán en Git.

Cuando exista la primera migración aprobada, este README incorporará comandos
verificados para iniciar PostgreSQL local, aplicar migraciones, ejecutar FastAPI,
correr Pytest e iniciar el frontend. No se publican comandos no probados como si
ya fueran funcionales.

## Estado de validación

La Fase 0 verificó el inventario y la coherencia estática de las fuentes. No se
ejecutó el SQL Server contra PostgreSQL porque no es compatible directamente y
convertirlo antes de resolver las discrepancias alteraría la fuente de verdad.
Tampoco hay aún una aplicación que iniciar ni pruebas automatizadas que ejecutar.
