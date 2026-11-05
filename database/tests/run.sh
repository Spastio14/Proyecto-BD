#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
container_name="s2r-fase1-postgres"
postgres_image="${POSTGRES_IMAGE:-postgres:17-alpine}"

cleanup() {
    docker rm -f "$container_name" >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup

docker run --detach --name "$container_name" \
    --env POSTGRES_PASSWORD=s2r_local_test \
    "$postgres_image" >/dev/null

for _ in $(seq 1 60); do
    if docker exec "$container_name" pg_isready -U postgres >/dev/null 2>&1; then
        break
    fi
    sleep 1
done
docker exec "$container_name" pg_isready -U postgres >/dev/null
docker exec "$container_name" postgres --version

apply_file() {
    local database="$1"
    local file="$2"
    docker exec -i "$container_name" psql \
        --quiet --username postgres --dbname "$database" --set ON_ERROR_STOP=1 \
        < "$file"
}

for database in s2r_rebuild_1 s2r_rebuild_2; do
    docker exec "$container_name" createdb --username postgres "$database"
    apply_file "$database" "$repo_dir/database/tests/bootstrap_supabase.sql"
    for migration in "$repo_dir"/supabase/migrations/[0-9]*.sql; do
        apply_file "$database" "$migration"
    done
done

apply_file s2r_rebuild_1 "$repo_dir/database/seeds/001_demo.sql"
apply_file s2r_rebuild_1 "$repo_dir/database/tests/001_schema_integrity.sql"

catalog_rows="$(docker exec "$container_name" psql --username postgres \
    --dbname s2r_rebuild_1 --quiet --tuples-only --no-align \
    --command "set role anon; select concat_ws('|',
      (select count(*) from public.categoria),
      (select count(*) from public.producto),
      (select count(*) from public.variante_producto),
      (select count(*) from public.escala_precio),
      (select count(*) from public.promocion),
      (select count(*) from public.promocion_variante));")"
test "$catalog_rows" = "1|1|1|2|1|1"

if docker exec "$container_name" psql --username postgres \
    --dbname s2r_rebuild_1 --set ON_ERROR_STOP=1 \
    --command "set role anon; select count(*) from public.persona;" \
    >/dev/null 2>&1; then
    echo "FALLO: anon pudo leer persona" >&2
    exit 1
fi

echo "OK: dos reconstrucciones limpias y pruebas PostgreSQL/RLS completadas."
