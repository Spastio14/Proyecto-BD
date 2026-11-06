# Demostración final de bases de datos — Fase 4.1

Esta guía usa Git Bash en Windows, Docker Desktop, VS Code, Python 3.12 y `uv`.
Todos los datos de ejemplo son ficticios. Los comandos locales no usan SQLite,
no cambian las 41 tablas y no ejecutan migraciones ni seeds en Supabase remoto.

## 1. Preparación y validación local

Desde Git Bash, en la raíz del repositorio:

```bash
git switch feat/fase-4-1-sistema-funcional
docker version
python --version
python -m pip install uv
cd backend
uv sync --locked --all-groups
cp .env.example .env
cd ..
./database/tests/run.sh
./backend/tests/run.sh
```

Los runners crean contenedores efímeros, reconstruyen PostgreSQL 17 desde las
cinco migraciones y los eliminan al terminar. La segunda reconstrucción también
valida el seed opcional, los 18 reportes y el script CRUD reversible.

## 2. Base local persistente para la exposición

```bash
docker rm -f s2r-demo 2>/dev/null || true
docker run --name s2r-demo -d \
  -p 5432:5432 \
  -e POSTGRES_PASSWORD=local_password \
  -e POSTGRES_DB=sublimacion2r \
  postgres:17-alpine

until docker exec s2r-demo pg_isready -U postgres >/dev/null 2>&1; do sleep 1; done

docker exec -i s2r-demo psql -U postgres -d sublimacion2r \
  -v ON_ERROR_STOP=1 < database/tests/bootstrap_supabase.sql

for file in supabase/migrations/[0-9]*.sql; do
  docker exec -i s2r-demo psql -U postgres -d sublimacion2r \
    -v ON_ERROR_STOP=1 < "$file"
done

docker exec -i s2r-demo psql -U postgres -d sublimacion2r \
  -v ON_ERROR_STOP=1 < database/seeds/001_demo.sql
docker exec -i s2r-demo psql -U postgres -d sublimacion2r \
  -v ON_ERROR_STOP=1 < database/seeds/002_fase_4_1_demo.sql
docker exec -i s2r-demo psql -U postgres -d sublimacion2r \
  -v ON_ERROR_STOP=1 < backend/tests/fixtures_permissions.sql
```

Comprobar el punto de partida aislado: 20 unidades.

```bash
docker exec s2r-demo psql -U postgres -d sublimacion2r -c \
  "select id_articulo, codigo, existencia_actual from public.articulo_inventariable where id_articulo=4101;"
```

Editar `backend/.env`; mantener la contraseña local y completar únicamente las
variables del proyecto de desarrollo Supabase mediante el gestor local de
secretos. Nunca pegar esos valores en Git, capturas ni la consola compartida.

```dotenv
DATABASE_URL=postgresql+psycopg://postgres:local_password@localhost:5432/sublimacion2r
APP_ENV=development
DATABASE_SSLMODE=prefer
SUPABASE_URL=https://iwvmbdfkxrssduoqobgy.supabase.co
SUPABASE_PROJECT_REF=iwvmbdfkxrssduoqobgy
SUPABASE_JWT_AUDIENCE=authenticated
SUPABASE_PUBLIC_KEY=<clave_publicable_local>
SUPABASE_SECRET_KEY=<clave_secreta_local>
GUEST_COOKIE_SECRET=<valor_aleatorio_local>
```

Para que un usuario Auth de desarrollo actúe como el empleado ficticio local,
copiar su UUID desde Supabase Authentication. El comando valida el formato antes
de modificar sólo la base Docker:

```bash
read -rsp "UUID Auth del empleado de demostración: " EMPLOYEE_AUTH_SUB; echo
[[ "$EMPLOYEE_AUTH_SUB" =~ ^[0-9a-fA-F-]{36}$ ]] || { echo "UUID inválido"; exit 1; }
docker exec s2r-demo psql -U postgres -d sublimacion2r -v ON_ERROR_STOP=1 -c \
  "update public.cuenta_acceso set identificador_autenticacion='$EMPLOYEE_AUTH_SUB'::uuid where id_persona=3;"
unset EMPLOYEE_AUTH_SUB
```

No se crea un administrador falso: Supabase verifica el JWT y el backend carga
los permisos del empleado desde `EMPLEADO`, `ASIGNACION_ROL`, `ROL_PERMISO` y
`PERMISO`. Un cliente debe registrarse en `/app/`, confirmar su correo e iniciar
sesión. Si Auth ya existía sin vínculo comercial, debe iniciar sesión y usar
“Completar vínculo”; conocer un correo no basta.

## 3. Iniciar API e interfaz

```bash
cd backend
uv run uvicorn app.main:app --reload
```

Abrir:

- Interfaz: `http://127.0.0.1:8000/app/`
- Swagger: `http://127.0.0.1:8000/docs`
- Salud: `http://127.0.0.1:8000/api/v1/health`

El catálogo es público. Cotizaciones, pedidos y pagos requieren un JWT válido.
Compras, inventario, pérdidas, reportes y decisiones requieren permisos vigentes.

## 4. Flujo integral de la demostración

Iniciar sesión en dos ventanas, una como cliente y otra como empleado. En las
herramientas del navegador, copiar cada `access_token` sólo a variables de la
terminal privada. Los siguientes comandos no imprimen los tokens:

```bash
read -rsp "Token cliente: " CLIENT_TOKEN; echo
read -rsp "Token empleado: " EMPLOYEE_TOKEN; echo
API=http://127.0.0.1:8000/api/v1
```

### 4.1 Compra de 30 unidades: existencia 20 → 50

```bash
curl -fsS -X POST "$API/compras" \
  -H "Authorization: Bearer $EMPLOYEE_TOKEN" -H "Content-Type: application/json" \
  -d '{"provider_id":4101,"document_number":"DEMO-COMPRA-30","lines":[{"article_id":4101,"quantity":"30.000","unit_cost":"30.0000"}]}' \
  > /tmp/s2r-compra.json
PURCHASE_ID=$(python -c 'import json; print(json.load(open("/tmp/s2r-compra.json"))["id_compra"])')
curl -fsS -X POST "$API/compras/$PURCHASE_ID/confirmar" \
  -H "Authorization: Bearer $EMPLOYEE_TOKEN"
curl -fsS "$API/inventario/articulos/4101/disponibilidad" \
  -H "Authorization: Bearer $EMPLOYEE_TOKEN"
```

Repetir la confirmación devuelve la misma compra y no genera otra entrada. La
prueba concurrente automatizada también confirma que el stock aumenta una sola
vez.

### 4.2 Pedido de 5, anticipo y reserva

```bash
curl -fsS -X POST "$API/pedidos" \
  -H "Authorization: Bearer $CLIENT_TOKEN" -H "Content-Type: application/json" \
  -d '{"lines":[{"variant_id":4101,"quantity":5,"promotion_id":null}],"delivery_mode":"RETIRO"}' \
  > /tmp/s2r-pedido.json
ORDER_ID=$(python -c 'import json; print(json.load(open("/tmp/s2r-pedido.json"))["id_pedido"])')
IDEMPOTENCY_KEY=$(python -c 'import uuid; print(uuid.uuid4())')
curl -fsS -X POST "$API/pagos/pedidos/$ORDER_ID/reportar" \
  -H "Authorization: Bearer $CLIENT_TOKEN" -H "Content-Type: application/json" \
  -d "{\"milestone_number\":1,\"idempotency_key\":\"$IDEMPOTENCY_KEY\",\"method\":\"TRANSFERENCIA\",\"bank\":\"BANCO-DEMO\",\"reference\":\"REF-DEMO\"}" \
  > /tmp/s2r-pago.json
PAYMENT_ID=$(python -c 'import json; print(json.load(open("/tmp/s2r-pago.json"))["id_transaccion"])')
curl -fsS -X POST "$API/pagos/$PAYMENT_ID/confirmar" \
  -H "Authorization: Bearer $EMPLOYEE_TOKEN"
curl -fsS "$API/inventario/articulos/4101/disponibilidad" \
  -H "Authorization: Bearer $EMPLOYEE_TOKEN"
```

La disponibilidad pasa de 50 a 45 porque el anticipo verificado reserva cinco
unidades. Reenviar exactamente la misma clave idempotente devuelve el pago ya
creado. Un pago pendiente o rechazado no reserva inventario.

### 4.3 Diseño, producción, consumo, pérdida y entrega

Esta parte usa el bucket privado del proyecto de desarrollo configurado en el
backend. Es un procedimiento independiente y deliberadamente no automático.

```bash
curl -fsS -X POST "$API/pedidos/$ORDER_ID/estado" \
  -H "Authorization: Bearer $EMPLOYEE_TOKEN" -H "Content-Type: application/json" \
  -d '{"target":"EN_DISENO","reason":"Anticipo verificado"}'

printf '\x89PNG\r\n\x1a\nDEMO' > /tmp/diseno-demo.png
curl -fsS -X POST "$API/disenos/pedidos/$ORDER_ID/lineas/1/versiones" \
  -H "Authorization: Bearer $EMPLOYEE_TOKEN" \
  -F "file=@/tmp/diseno-demo.png;type=image/png" -F "observations=Diseño ficticio"
curl -fsS -X POST "$API/disenos/pedidos/$ORDER_ID/lineas/1/versiones/1/decision" \
  -H "Authorization: Bearer $EMPLOYEE_TOKEN" -H "Content-Type: application/json" \
  -d '{"approved":true,"medium":"PORTAL"}'
curl -fsS -X POST "$API/produccion/pedidos/$ORDER_ID/iniciar" \
  -H "Authorization: Bearer $EMPLOYEE_TOKEN"
curl -fsS -X POST "$API/inventario/pedidos/$ORDER_ID/consumir" \
  -H "Authorization: Bearer $EMPLOYEE_TOKEN"

curl -fsS -X POST "$API/perdidas" \
  -H "Authorization: Bearer $EMPLOYEE_TOKEN" -H "Content-Type: application/json" \
  -d "{\"moment\":\"EN_PRODUCCION\",\"incident_type\":\"ROTURA_ARTICULO\",\"reason\":\"Pérdida ficticia\",\"order_id\":$ORDER_ID,\"stage_id\":null,\"description\":\"Una unidad de demostración\"}" \
  > /tmp/s2r-perdida.json
LOSS_ID=$(python -c 'import json; print(json.load(open("/tmp/s2r-perdida.json"))["id_perdida"])')
curl -fsS -X POST "$API/perdidas/$LOSS_ID/confirmar" \
  -H "Authorization: Bearer $EMPLOYEE_TOKEN" -H "Content-Type: application/json" \
  -d '{"lines":[{"article_id":4101,"quantity":"1.000","damage_description":"Rotura ficticia"}]}'
curl -fsS -X POST "$API/pedidos/$ORDER_ID/estado" \
  -H "Authorization: Bearer $EMPLOYEE_TOKEN" -H "Content-Type: application/json" \
  -d '{"target":"LISTO","reason":"Producción terminada"}'
curl -fsS -X POST "$API/entregas/pedidos/$ORDER_ID/completar" \
  -H "Authorization: Bearer $EMPLOYEE_TOKEN" -H "Content-Type: application/json" \
  -d '{"reason":"Retiro confirmado"}'
```

El consumo convierte la reserva en salida de producción una vez; la pérdida
genera otra salida con costo histórico. Consultar evidencia final:

```bash
curl -fsS "$API/pedidos/$ORDER_ID/historial" -H "Authorization: Bearer $EMPLOYEE_TOKEN"
curl -fsS "$API/reportes/resumen" -H "Authorization: Bearer $EMPLOYEE_TOKEN"
docker exec s2r-demo psql -U postgres -d sublimacion2r -c \
  "select id_movimiento,tipo_movimiento,cantidad,id_pedido,id_compra from public.movimiento_inventario where id_articulo=4101 order by id_movimiento;"
unset CLIENT_TOKEN EMPLOYEE_TOKEN API
```

## 5. Reportes y operaciones SQL académicas

Los 18 reportes son de lectura y se pueden abrir en VS Code o ejecutar así:

```bash
docker exec -i s2r-demo psql -U postgres -d sublimacion2r \
  -v ON_ERROR_STOP=1 < database/queries/fase_4_1_reportes.sql
```

El archivo CRUD crea datos y vistas únicamente dentro de una transacción que
termina en `ROLLBACK`:

```bash
docker exec -i s2r-demo psql -U postgres -d sublimacion2r \
  -v ON_ERROR_STOP=1 < database/queries/fase_4_1_crud_demo.sql
```

`database/queries/fase_4_1_transacciones_demo.sql` contiene la violación FK
esperada, rollback, instrucciones para dos sesiones concurrentes y verificación
de idempotencia. Como uno de sus pasos debe fallar, se ejecuta bloque por bloque
en dos terminales o en Supabase SQL Editor, no desde un runner automático.

Los reportes diferencian total documentado e ingreso verificado. No calculan
“utilidad neta”: el modelo no respalda todavía una fórmula definitiva que
integre compras, pérdidas, gastos, retenciones, reembolsos y periodo contable.

## 6. Supabase remoto: procedimiento independiente

No ejecutar seeds, scripts CRUD ni `db reset` contra Supabase. Para revisar el
estado sin aplicar cambios:

```bash
supabase login
supabase link --project-ref iwvmbdfkxrssduoqobgy
./scripts/supabase/preflight.sh
```

La salida debe identificar exactamente `SublimacionDobleR-prueba`, listar las
cinco migraciones aplicadas y mostrar un `db push --dry-run` sin migraciones
nuevas. La Fase 4.1 no añade migraciones ni vistas remotas.

La carga de diseño y comprobantes modifica sólo los buckets privados del
proyecto de desarrollo cuando una persona ejecuta expresamente los pasos de la
sección 4.3. Para una exposición totalmente local, se puede omitir la carga y
mostrar las pruebas automatizadas del servicio de diseño.

## 7. Alcance pendiente por decisión de negocio

Los reembolsos siguen bloqueados para escritura. El esquema conserva
`REEMBOLSO` y las transacciones compensatorias, pero los documentos definitivos
no fijan porcentajes de retención, autoridad de aprobación, estados que admiten
reembolso, método de devolución ni tratamiento de pagos parciales y pérdidas.
Implementarlo supondría inventar reglas financieras. La devolución debe
autorizarse en una fase separada con esas decisiones explícitas.

## 8. Cierre y limpieza

```bash
docker rm -f s2r-demo
rm -f /tmp/s2r-compra.json /tmp/s2r-pedido.json /tmp/s2r-pago.json \
  /tmp/s2r-perdida.json /tmp/diseno-demo.png
```

No borrar usuarios Auth para “reiniciar” una exposición. Las operaciones
comerciales son trazables y los pagos se conservan como historial append-only.
