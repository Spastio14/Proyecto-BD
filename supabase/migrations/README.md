# Migraciones canónicas

Los archivos numerados se aplican en orden y son la única fuente canónica del
esquema PostgreSQL:

1. `202611040001_core_schema.sql`: 41 tablas, PK, UQ, NOT NULL y CHECK.
2. `202611040002_relations_indexes.sql`: 64 FK, exclusión de escalas e índices.
3. `202611040003_row_level_security.sql`: revocación por defecto, RLS en las 41
   tablas y lectura pública del catálogo activo.
4. `202611050001_restrict_wholesale_price_rls.sql`: retira la lectura directa de
   escalas mayoristas; su aplicación queda exclusivamente en FastAPI.
5. `202611050002_supabase_auth_storage.sql`: añade la referencia opcional y
   coherente del comprobante a `transaccion` y configura dos buckets privados
   cuando corre dentro de Supabase. Conserva las 41 tablas y no modifica los
   grants globales administrados de `storage.buckets` o `storage.objects`.

No contienen datos. Supabase proporciona los roles `anon` y `authenticated`; el
runner local los crea antes de aplicar las migraciones. La extensión
`btree_gist`, disponible en Supabase, impide rangos mayoristas activos
solapados.

`scripts/supabase/preflight.sh` consulta el historial enlazado y ejecuta
`db push --dry-run`; no aplica migraciones. La aplicación remota requiere una
autorización separada.

La forma verificada de aplicar todo desde cero es `./database/tests/run.sh` desde
la raíz. No se debe ejecutar el seed como parte de una migración de producción.
