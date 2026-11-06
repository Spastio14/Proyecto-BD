# Guía de validación manual — Fase 4

Fecha: 5 de noviembre de 2026 (`America/Managua`). Usa Git Bash, Docker Desktop
y datos ficticios. No guardes claves ni tokens en `.env`, Git o capturas.

## Separación de entornos

| Operación | Docker local | Supabase remoto |
|---|---|---|
| Reconstruir esquema, seed, pedidos, pagos y pérdidas | Sí | No |
| Concurrencia y Storage simulado | Sí | No |
| `db reset`, `db push`, migraciones, RLS | Sólo base desechable | Prohibido |
| Preflight, historial, `migration list`, dry-run | No aplica | Sí, sin aplicar |
| Salud y catálogo público | Sí | Sí |
| Login de cuenta remota de prueba | Opcional | Crea sesión y puede actualizar `last_sign_in_at` |

## Validación automatizada

```bash
git clone https://github.com/Spastio14/Proyecto-BD.git
cd Proyecto-BD
git fetch origin
git checkout test/fase-4-integracion-negocio
./database/tests/run.sh
./backend/tests/run.sh
cd backend
UV_CACHE_DIR=/tmp/uv-cache uv run --locked ruff check app tests
cd ..
```

Resultado esperado: 41 tablas, 64 FK, 126 Pytest aprobadas y 2 remotas
omitidas.

## PostgreSQL local persistente

```bash
export F4_CONTAINER=s2r-fase4-manual
export F4_DATABASE=s2r_fase4
export F4_PASSWORD=s2r_fase4_local
export F4_PORT=55433

docker rm -f "$F4_CONTAINER" 2>/dev/null || true
docker run -d --name "$F4_CONTAINER" \
  -p "127.0.0.1:${F4_PORT}:5432" \
  -e "POSTGRES_PASSWORD=${F4_PASSWORD}" postgres:17-alpine
until docker exec "$F4_CONTAINER" pg_isready -U postgres >/dev/null 2>&1; do sleep 1; done
docker exec "$F4_CONTAINER" createdb -U postgres "$F4_DATABASE"
docker exec -i "$F4_CONTAINER" psql -U postgres -d "$F4_DATABASE" \
  -v ON_ERROR_STOP=1 < database/tests/bootstrap_supabase.sql
for migration in supabase/migrations/[0-9]*.sql; do
  docker exec -i "$F4_CONTAINER" psql -U postgres -d "$F4_DATABASE" \
    -v ON_ERROR_STOP=1 < "$migration"
done
docker exec -i "$F4_CONTAINER" psql -U postgres -d "$F4_DATABASE" \
  -v ON_ERROR_STOP=1 < database/seeds/001_demo.sql
docker exec -i "$F4_CONTAINER" psql -U postgres -d "$F4_DATABASE" \
  -v ON_ERROR_STOP=1 < backend/tests/fixtures_permissions.sql
```

Arranca FastAPI en otra terminal:

```bash
export DATABASE_URL="postgresql+psycopg://postgres:${F4_PASSWORD}@127.0.0.1:${F4_PORT}/${F4_DATABASE}"
export APP_ENV=test DATABASE_SSLMODE=prefer
export GUEST_COOKIE_SECRET='fase-4-cookie-local-cambiar-1234567890'
cd backend
UV_CACHE_DIR=/tmp/uv-cache uv sync --locked
UV_CACHE_DIR=/tmp/uv-cache uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Invitado, catálogo y límites

```bash
export API_URL=http://127.0.0.1:8000/api/v1
export COOKIE_FILE=/tmp/s2r-fase4-cookies.txt
curl --fail-with-body -sS -c "$COOKIE_FILE" \
  -H 'Content-Type: application/json' \
  -d '{"names":"Invitado Ficticio","phone":null}' "$API_URL/auth/invitado"
curl --fail-with-body -sS "$API_URL/catalogo"
```

La cookie es `Secure`; HTTP local no representa TLS. Para esta prueba local,
envíala explícitamente sin imprimirla:

```bash
export GUEST_COOKIE="$(awk '$6 == "s2r_guest" {print $7}' "$COOKIE_FILE")"
curl --fail-with-body -sS -H "Cookie: s2r_guest=${GUEST_COOKIE}" \
  -H 'Content-Type: application/json' \
  -d '{"lines":[{"variant_id":1,"quantity":5}],"delivery_mode":"RETIRO"}' \
  "$API_URL/pedidos"
```

Repite con cantidad 6: debe responder 409. Tras el primer pedido, cantidad 1
también debe responder 409 por el límite de pedido activo.

## JWT registrado con la base local

No hay ruta de suplantación. Usa una cuenta Auth de prueba existente y vincula su
UUID únicamente en Docker local. Antes de arrancar Uvicorn:

```bash
export SUPABASE_PROJECT_REF='<project-ref>'
export SUPABASE_URL="https://${SUPABASE_PROJECT_REF}.supabase.co"
read -rsp 'Supabase publishable key: ' SUPABASE_PUBLIC_KEY; echo
export SUPABASE_PUBLIC_KEY
```

Reinicia Uvicorn y autentica la cuenta de prueba:

```bash
read -rp 'Correo de prueba: ' TEST_EMAIL
read -rsp 'Contraseña: ' TEST_PASSWORD; echo
export LOGIN_JSON="$(curl --fail-with-body -sS \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"${TEST_EMAIL}\",\"password\":\"${TEST_PASSWORD}\"}" \
  "$API_URL/auth/login")"
export ACCESS_TOKEN="$(printf '%s' "$LOGIN_JSON" | \
  python -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"
unset LOGIN_JSON TEST_PASSWORD
```

Obtén el UUID del panel Auth y enlázalo localmente:

```bash
read -rp 'Auth UUID del cliente de prueba: ' CUSTOMER_AUTH_UID
docker exec -i "$F4_CONTAINER" psql -U postgres -d "$F4_DATABASE" \
  -v auth_uid="$CUSTOMER_AUTH_UID" \
  -c "update public.cuenta_acceso set identificador_autenticacion = :'auth_uid' where id_persona = 2;"
curl --fail-with-body -sS -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  "$API_URL/clientes/me"
```

Para confirmar pagos, aprobar diseños y registrar pérdidas necesitas otra cuenta
Auth de empleado vinculada localmente a `id_persona = 3`. Si no existe, ejecuta
las pruebas automatizadas; no conviertas el cliente en empleado.

## Cotización, pedido y total

```bash
export QUOTE_JSON="$(curl --fail-with-body -sS \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" -H 'Content-Type: application/json' \
  -d '{"lines":[{"variant_id":1,"quantity":2,"customization":"Logo ficticio"}],"observations":"Fase 4"}' \
  "$API_URL/cotizaciones")"
export QUOTE_ID="$(printf '%s' "$QUOTE_JSON" | \
  python -c 'import json,sys; print(json.load(sys.stdin)["id_cotizacion"])')"
unset QUOTE_JSON
```

Aún no hay endpoint para aceptar cotizaciones. Sólo en Docker local:

```bash
docker exec -i "$F4_CONTAINER" psql -U postgres -d "$F4_DATABASE" \
  -v quote_id="$QUOTE_ID" \
  -c "update public.cotizacion set estado='ACEPTADA' where id_cotizacion=:'quote_id';"
export ORDER_JSON="$(curl --fail-with-body -sS -X POST \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  "$API_URL/cotizaciones/${QUOTE_ID}/convertir")"
export ORDER_ID="$(printf '%s' "$ORDER_JSON" | \
  python -c 'import json,sys; print(json.load(sys.stdin)["id_pedido"])')"
unset ORDER_JSON
```

```bash
docker exec -i "$F4_CONTAINER" psql -U postgres -d "$F4_DATABASE" \
  -v order_id="$ORDER_ID" -c \
"select p.id_pedido,p.total_pedido,sum(d.importe_pactado) suma_detalle
 from public.pedido p join public.detalle_pedido d using(id_pedido)
 where p.id_pedido=:'order_id' group by p.id_pedido,p.total_pedido;"
```

La oferta C$170 requiere `promotion_id: 1` en un pedido; las cotizaciones
actuales no seleccionan promociones.

## Pago, verificación y reserva

```bash
export IDEM_KEY="$(python -c 'import uuid; print(uuid.uuid4())')"
export PAYMENT_JSON="$(curl --fail-with-body -sS \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" -H 'Content-Type: application/json' \
  -d "{\"milestone_number\":1,\"idempotency_key\":\"${IDEM_KEY}\",\"method\":\"TRANSFERENCIA\",\"bank\":\"BANCO-TEST\",\"reference\":\"REF-F4\"}" \
  "$API_URL/pagos/pedidos/${ORDER_ID}/reportar")"
export PAYMENT_ID="$(printf '%s' "$PAYMENT_JSON" | \
  python -c 'import json,sys; print(json.load(sys.stdin)["id_transaccion"])')"
unset PAYMENT_JSON
curl --fail-with-body -sS -X POST \
  -H "Authorization: Bearer ${EMPLOYEE_ACCESS_TOKEN}" \
  "$API_URL/pagos/${PAYMENT_ID}/confirmar"
```

```bash
docker exec -i "$F4_CONTAINER" psql -U postgres -d "$F4_DATABASE" \
  -v order_id="$ORDER_ID" -c \
"select t.id_transaccion,t.estado_verificacion,h.tipo_hito,h.estado,
        r.id_reserva,r.cantidad_reservada,r.estado estado_reserva
 from public.transaccion t join public.hito_pago h using(id_pedido,numero_hito)
 left join public.reserva_inventario r using(id_pedido)
 where t.id_pedido=:'order_id' order by t.id_transaccion;"
```

Repite el reporte con `IDEM_KEY`: debe devolver la misma transacción. El rechazo
está probado en el servicio, pero todavía no tiene endpoint HTTP.

## Diseño y producción sin Storage remoto

```bash
./backend/tests/run.sh tests/integration/test_supabase_phase3.py \
  tests/integration/test_phase4_end_to_end.py -k 'storage or design or scenario_a'
```

No configures `SUPABASE_SECRET_KEY` si apunta al remoto. Para preparar una
versión ficticia mediante los servicios locales, desde `backend/`:

```bash
uv run python - "$ORDER_ID" <<'PY'
import os, sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.security import Principal
from app.services.designs import DesignService
from app.services.orders import OrderService
order_id = int(sys.argv[1])
factory = sessionmaker(bind=create_engine(os.environ["DATABASE_URL"]), expire_on_commit=False)
with factory() as session, session.begin():
    employee, customer = Principal(3,"EMPLEADO"), Principal(2,"CLIENTE")
    OrderService().transition(session, order_id=order_id, target="EN_DISENO",
        principal=employee, reason="Preparación manual Fase 4")
    version = DesignService().add_version(session, order_id=order_id, line_number=1,
        file_name="ficticio.png", private_path="local/ficticio.png", principal=customer)
    print(version.numero_version)
PY
```

```bash
export VERSION_NUMBER=1
curl --fail-with-body -sS -X POST \
  -H "Authorization: Bearer ${EMPLOYEE_ACCESS_TOKEN}" -H 'Content-Type: application/json' \
  -d '{"approved":true,"medium":"PORTAL"}' \
  "$API_URL/disenos/pedidos/${ORDER_ID}/lineas/1/versiones/${VERSION_NUMBER}/decision"
curl --fail-with-body -sS -X POST \
  -H "Authorization: Bearer ${EMPLOYEE_ACCESS_TOKEN}" \
  "$API_URL/produccion/pedidos/${ORDER_ID}/iniciar"
```

## Pérdida y costo histórico

```bash
export LOSS_JSON="$(curl --fail-with-body -sS \
  -H "Authorization: Bearer ${EMPLOYEE_ACCESS_TOKEN}" -H 'Content-Type: application/json' \
  -d "{\"moment\":\"DURANTE_PRODUCCION\",\"incident_type\":\"SUBLIMACION_DEFECTUOSA\",\"reason\":\"Taza ficticia dañada\",\"order_id\":${ORDER_ID},\"stage_id\":3,\"description\":\"Fase 4\"}" \
  "$API_URL/perdidas")"
export LOSS_ID="$(printf '%s' "$LOSS_JSON" | \
  python -c 'import json,sys; print(json.load(sys.stdin)["id_perdida"])')"
unset LOSS_JSON
curl --fail-with-body -sS \
  -H "Authorization: Bearer ${EMPLOYEE_ACCESS_TOKEN}" -H 'Content-Type: application/json' \
  -d '{"lines":[{"article_id":1,"quantity":"1.000","damage_description":"Taza rota"}]}' \
  "$API_URL/perdidas/${LOSS_ID}/confirmar"
```

```bash
docker exec -i "$F4_CONTAINER" psql -U postgres -d "$F4_DATABASE" \
  -v loss_id="$LOSS_ID" -c \
"select p.id_perdida,p.estado_registro,d.cantidad_perdida,
 d.costo_unitario_historico,d.cantidad_perdida*d.costo_unitario_historico costo,
 m.tipo_movimiento from public.perdida p
 join public.detalle_perdida d using(id_perdida)
 join public.movimiento_inventario m using(id_movimiento)
 where p.id_perdida=:'loss_id';"
```

## Consultas SQL de control

```sql
select a.id_articulo,a.codigo,a.existencia_actual,
 a.existencia_actual-coalesce(sum(r.cantidad_pendiente)
 filter(where r.estado='ACTIVA'),0) disponible
from public.articulo_inventariable a
left join public.reserva_inventario r using(id_articulo)
group by a.id_articulo,a.codigo,a.existencia_actual;

select id_pedido,estado_anterior,estado_nuevo,motivo,origen_cambio,fecha_hora
from public.historial_pedido order by id_pedido,fecha_hora;

select accion,tipo_objeto_afectado,referencia_objeto,id_persona_actor,fecha_hora
from public.registro_auditoria order by fecha_hora desc;

select id_pedido,sum(monto_con_signo) flujo_verificado
from public.transaccion where estado_verificacion='VERIFICADO' group by id_pedido;

select id_articulo,sum(cantidad_perdida) cantidad,
 sum(cantidad_perdida*costo_unitario_historico) costo
from public.detalle_perdida group by id_articulo;
```

No presentes flujo menos pérdidas como beneficio: faltan costos consolidados,
gastos y una política aprobada.

## Preflight remoto permitido

```bash
export SUPABASE_PROJECT_REF='<project-ref>'
export SUPABASE_PROJECT_NAME='SublimacionDobleR-prueba'
./scripts/supabase/preflight.sh
```

El script ejecuta historial, `migration list` y `db push --dry-run`. No ejecutes
`db push`, `db reset`, seeds ni SQL de escritura. `GET /health` y `/catalogo`
son lectura. Los `POST` comerciales remotos quedan fuera de esta autorización.

## Limpieza

```bash
unset ACCESS_TOKEN EMPLOYEE_ACCESS_TOKEN SUPABASE_PUBLIC_KEY CUSTOMER_AUTH_UID
unset TEST_EMAIL IDEM_KEY GUEST_COOKIE
docker rm -f "$F4_CONTAINER"
unset F4_CONTAINER F4_DATABASE F4_PASSWORD F4_PORT DATABASE_URL
```

No borres usuarios Supabase para limpiar pruebas locales.
