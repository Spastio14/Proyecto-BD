#!/usr/bin/env bash
set -euo pipefail

backend_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
repo_dir="$(cd "$backend_dir/.." && pwd)"
container_name="s2r-fase2-postgres"
postgres_image="${POSTGRES_IMAGE:-postgres:17-alpine}"
postgres_port="${S2R_TEST_PORT:-55432}"
test_password="s2r_backend_test"
api_pid=""

cleanup() {
    if [ -n "$api_pid" ]; then
        kill "$api_pid" >/dev/null 2>&1 || true
    fi
    docker rm -f "$container_name" >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup

docker run --detach --name "$container_name" \
    --publish "127.0.0.1:${postgres_port}:5432" \
    --env "POSTGRES_PASSWORD=${test_password}" \
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
    docker exec -i "$container_name" psql --quiet \
        --username postgres --dbname "$database" --set ON_ERROR_STOP=1 < "$file"
}

template_database="s2r_backend_template"
database_created=false
for _ in $(seq 1 60); do
    if docker exec "$container_name" createdb --username postgres "$template_database" \
        >/dev/null 2>&1; then
        database_created=true
        break
    fi
    sleep 1
done
if [ "$database_created" != true ]; then
    echo "FALLO: PostgreSQL no permitió crear la plantilla" >&2
    exit 1
fi
docker exec "$container_name" psql --username postgres --dbname "$template_database" \
    --tuples-only --no-align --command "select 1" | grep --quiet '^1$'
apply_file "$template_database" "$repo_dir/database/tests/bootstrap_supabase.sql"
for migration in "$repo_dir"/supabase/migrations/[0-9]*.sql; do
    apply_file "$template_database" "$migration"
done
apply_file "$template_database" "$repo_dir/database/seeds/001_demo.sql"
apply_file "$template_database" "$backend_dir/tests/fixtures_permissions.sql"

export TEST_ADMIN_DATABASE_URL="postgresql+psycopg://postgres:${test_password}@127.0.0.1:${postgres_port}/postgres"
export TEST_TEMPLATE_DATABASE="$template_database"
export DATABASE_URL="postgresql+psycopg://postgres:${test_password}@127.0.0.1:${postgres_port}/${template_database}"
export APP_ENV="test"
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"

cd "$backend_dir"
uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 18000 \
    >/tmp/s2r-fase2-uvicorn.log 2>&1 &
api_pid="$!"
for _ in $(seq 1 30); do
    if curl --fail --silent http://127.0.0.1:18000/api/v1/health \
        | grep --quiet '"status":"ok"'; then
        break
    fi
    sleep 1
done
curl --fail --silent http://127.0.0.1:18000/api/v1/health \
    | grep --quiet '"database":"postgresql"'
kill "$api_pid"
wait "$api_pid" || true
api_pid=""
echo "OK: Uvicorn inició y /api/v1/health respondió contra PostgreSQL."

uv run --locked pytest "$@"
