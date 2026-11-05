# Guía del backend — Fase 2

## 1. Requisitos

- Git Bash en Windows.
- Docker Desktop con contenedores Linux.
- Python 3.12 disponible como `python`.
- `uv`, instalable con `python -m pip install uv`.

Desde la raíz del repositorio:

```bash
cd backend
uv sync --locked --all-groups
cp .env.example .env
```

`uv.lock` fija las versiones resueltas. `.env` está ignorado por Git.

## 2. PostgreSQL local

Crear una base local desechable:

```bash
docker run --name s2r-postgres -d \
  -p 5432:5432 \
  -e POSTGRES_PASSWORD=local_password \
  -e POSTGRES_DB=sublimacion2r \
  postgres:17-alpine
```

Desde la raíz, crear los roles que Supabase proporciona y aplicar todas las
migraciones en orden:

```bash
docker exec -i s2r-postgres psql -U postgres -d sublimacion2r \
  -v ON_ERROR_STOP=1 < database/tests/bootstrap_supabase.sql

for file in supabase/migrations/[0-9]*.sql; do
  docker exec -i s2r-postgres psql -U postgres -d sublimacion2r \
    -v ON_ERROR_STOP=1 < "$file"
done
```

El seed es opcional y solo debe usarse localmente:

```bash
docker exec -i s2r-postgres psql -U postgres -d sublimacion2r \
  -v ON_ERROR_STOP=1 < database/seeds/001_demo.sql
```

## 3. Variables

Editar `backend/.env`:

```dotenv
DATABASE_URL=postgresql+psycopg://postgres:local_password@localhost:5432/sublimacion2r
APP_ENV=development
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
LOG_LEVEL=INFO
```

No copiar una contraseña real a `.env.example` ni a documentación.

## 4. Iniciar FastAPI

```bash
cd backend
uv run uvicorn app.main:app --reload
```

- Salud: <http://127.0.0.1:8000/api/v1/health>
- Swagger: <http://127.0.0.1:8000/docs>
- OpenAPI: <http://127.0.0.1:8000/openapi.json>

El catálogo y salud son públicos. Las rutas de clientes, cotizaciones, pedidos,
pagos, inventario, diseños, producción y pérdidas responden 401 hasta integrar
Supabase Auth. No hay encabezado de desarrollo que permita suplantar personas.

## 5. Pruebas

Desde la raíz:

```bash
./database/tests/run.sh
./backend/tests/run.sh
```

El runner del backend crea una plantilla PostgreSQL migrada y una base clonada
por prueba. No usa SQLite ni una base remota. Para seleccionar casos:

```bash
./backend/tests/run.sh -k pricing
./backend/tests/run.sh -m concurrency
```

## 6. Expiración invocable

Con `DATABASE_URL` configurada:

```bash
cd backend
uv run python -m app.commands.expire_orders
```

El comando usa bloqueos con `SKIP LOCKED`, puede repetirse y no necesita un
proceso residente. Un programador externo podrá invocarlo en una fase posterior.

## 7. Endpoints implementados

| Grupo | Operaciones |
|---|---|
| `/api/v1/health` | Comprueba API y PostgreSQL |
| `/api/v1/catalogo` | Catálogo activo con precio detalle, sin escalas mayoristas |
| `/api/v1/clientes/me` | Consulta el cliente autenticado |
| `/api/v1/cotizaciones` | Crea, lista y convierte cotizaciones aceptadas |
| `/api/v1/pedidos` | Crea, lista, consulta y cancela pedidos propios |
| `/api/v1/pagos` | Reporta e identifica pagos; confirma con permiso real |
| `/api/v1/inventario` | Disponibilidad y consumo con permiso |
| `/api/v1/disenos` | Versiones privadas y decisión exacta |
| `/api/v1/produccion` | Inicio tras anticipo y diseño vigente aprobado |
| `/api/v1/perdidas` | Reporte y confirmación con movimiento único |

El cliente nunca envía precios, descuentos, totales, estados de verificación ni
identidades propietarias como datos autoritativos.

## 8. Errores comunes

| Respuesta/error | Causa habitual | Acción |
|---|---|---|
| conexión rechazada | Docker no inició o URL/puerto incorrecto | Revisar `docker ps` y `DATABASE_URL` |
| 401 | Supabase Auth aún no está integrado | Esperado fuera de fixtures de prueba |
| 403 | El actor no es propietario o carece de rol/permiso vigente | Revisar asignaciones en PostgreSQL |
| 409 | Estado, duplicado, vencimiento o inventario incompatible | Corregir el flujo, no forzar la escritura |
| 422 | JSON inválido o campos no permitidos | Consultar Swagger; precios e identidad no se aceptan |
| migración detenida | Base parcial o archivo fuera de orden | Recrear la base local y aplicar archivos numerados |

Para detener y eliminar la base local:

```bash
docker rm -f s2r-postgres
```
