# Resultados de pruebas — Fase 2

Fecha: 5 de noviembre de 2026 (UTC).

## Entorno

- Python 3.12.14.
- PostgreSQL 17.11 en Docker.
- FastAPI, SQLAlchemy 2 y Psycopg 3 según `backend/uv.lock`.
- Una base clonada desde plantilla migrada por cada prueba.
- Sin SQLite, Supabase remoto, credenciales reales ni mocks de PostgreSQL.

## Comandos

```bash
./backend/tests/run.sh
./database/tests/run.sh
```

## Resultado ejecutado

La suite de backend recopiló 50 pruebas y terminó con 50 aprobadas, 0 fallidas y
0 omitidas en 6.89 segundos. Incluyó:

- límites de invitados y registrados con bloqueo de cliente;
- carrera de dos pedidos invitados;
- precios detalle, mayorista y tres tipos de promoción;
- persistencia histórica y oferta de dos tazas por C$170;
- pago reportado, verificado, idempotencia y rollback;
- carrera de dos confirmaciones por la última disponibilidad;
- reserva, consumo único, cancelación y liberación;
- versión de diseño vigente y autorización de producción;
- pérdidas fuera de producción, aplicación única y costo histórico;
- propiedad, permiso real, 401 y rechazo de precios/identidades enviados;
- cotización sin inventario, conversión única y pertenencia;
- expiración inicial/revisión, Uvicorn, OpenAPI y catálogo seguro.
- pago tardío sujeto a permiso administrativo y saldo sin regresión de producción.

La ejecución produjo una advertencia deprecatoria de la integración interna
`TestClient`/HTTPX de la versión instalada. No hubo error funcional. El arranque
real de Uvicorn se añadió al runner y se valida contra `/api/v1/health`.

La suite estructural de Fase 1 también pasó: dos reconstrucciones limpias, 41
tablas, 64 FK, integridad y RLS. Su prueba ahora exige que `anon` no pueda leer
`escala_precio` después de la migración de Fase 2.

## Problemas detectados y corregidos

1. La primera revisión de seguridad del código detectó que un principal podía
   traer permisos en memoria. Se eliminó esa confianza: cada operación consulta
   roles y permisos vigentes en PostgreSQL.
2. Las escalas mayoristas estaban expuestas por RLS. Una migración separada
   revoca el acceso directo y el catálogo HTTP no las devuelve.
3. La verificación de pago y reserva se mantienen juntas. Si inventario falla,
   ambas revierten y el pago reportado queda pendiente para revisión humana.
4. El runner podía observar el PostgreSQL temporal de inicialización antes del
   reinicio definitivo de la imagen. La creación de la plantilla ahora reintenta
   y confirma la conexión, eliminando esa carrera del entorno de prueba.

## Límites conocidos

- Supabase Auth y Storage pertenecen a Fase 3; las rutas protegidas están
  cerradas en ejecución normal.
- No se implementó pasarela bancaria, scheduler externo ni archivos reales.
- Las promociones entre productos distintos no pueden representarse con el
  modelo actual; solo se aplica una promoción principal por línea.
- El backend cubre el núcleo transaccional; reportes académicos y frontend están
  fuera de esta fase.
