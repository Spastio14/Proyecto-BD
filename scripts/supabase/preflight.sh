#!/usr/bin/env bash
set -euo pipefail

expected_ref="iwvmbdfkxrssduoqobgy"
expected_name="SublimacionDobleR-prueba"
configured_ref="${SUPABASE_PROJECT_REF:-}"
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_dir"

if command -v supabase >/dev/null 2>&1; then
    supabase_cli=(supabase)
elif command -v npx >/dev/null 2>&1; then
    supabase_cli=(npx --yes supabase@3.0.0)
else
    echo "FALLO: instala Supabase CLI 3.x o Node.js/npx antes del preflight" >&2
    exit 1
fi
if [ "$configured_ref" != "$expected_ref" ]; then
    echo "FALLO: SUPABASE_PROJECT_REF no coincide con el proyecto de desarrollo" >&2
    exit 1
fi

cli_version="$("${supabase_cli[@]}" --version)"
case "$cli_version" in
    3.*) ;;
    *)
        echo "FALLO: este preflight requiere Supabase CLI 3.x; detectado $cli_version" >&2
        exit 1
        ;;
esac

if [ ! -f supabase/.temp/project-ref ]; then
    echo "FALLO: enlaza primero el proyecto con supabase link --project-ref $expected_ref" >&2
    exit 1
fi
linked_ref="$(tr -d '\r\n' < supabase/.temp/project-ref)"
if [ "$linked_ref" != "$expected_ref" ]; then
    echo "FALLO: el proyecto enlazado no coincide con $expected_ref" >&2
    exit 1
fi

projects_json="$("${supabase_cli[@]}" projects list --output-format json)"
PROJECTS_JSON="$projects_json" EXPECTED_REF="$expected_ref" EXPECTED_NAME="$expected_name" \
python -c 'import json, os, sys
projects = json.loads(os.environ["PROJECTS_JSON"])
expected_ref = os.environ["EXPECTED_REF"]
expected_name = os.environ["EXPECTED_NAME"]
matches = [p for p in projects if p.get("id") == expected_ref or p.get("ref") == expected_ref]
if len(matches) != 1 or matches[0].get("name") != expected_name:
    sys.exit("FALLO: el ref no corresponde exactamente a SublimacionDobleR-prueba")
project = matches[0]
status = project.get("status", "DESCONOCIDO")
if status != "ACTIVE_HEALTHY":
    sys.exit(f"FALLO: el proyecto no está ACTIVE_HEALTHY; estado={status}")
print(f"Proyecto verificado: {expected_name} ({expected_ref}); estado={status}")'
unset projects_json

mapfile -t local_migrations < <(
    for migration in supabase/migrations/[0-9]*.sql; do
        basename "$migration"
    done | sort
)
expected_migrations=(
    202611040001_core_schema.sql
    202611040002_relations_indexes.sql
    202611040003_row_level_security.sql
    202611050001_restrict_wholesale_price_rls.sql
    202611050002_supabase_auth_storage.sql
)
if [ "${#local_migrations[@]}" -ne 5 ]; then
    echo "FALLO: deben existir exactamente cinco migraciones locales" >&2
    exit 1
fi
for index in "${!expected_migrations[@]}"; do
    if [ "${local_migrations[$index]}" != "${expected_migrations[$index]}" ]; then
        echo "FALLO: el conjunto local de migraciones no es el aprobado" >&2
        exit 1
    fi
done

echo "Supabase CLI: $cli_version"
echo "Estado PostgreSQL, extensiones, privilegios, policies y buckets (solo lectura):"
"${supabase_cli[@]}" db query --remote --read-only \
    --file scripts/supabase/preflight_readonly.sql
echo "Historial remoto (solo lectura):"
"${supabase_cli[@]}" migration list --remote
echo "Plan remoto (dry-run; no aplica migraciones):"
dry_run_output="$("${supabase_cli[@]}" db push --remote --dry-run --skip-vault 2>&1)"
printf '%s\n' "$dry_run_output"
for migration in "${expected_migrations[@]}"; do
    if ! grep -Fq "$migration" <<< "$dry_run_output"; then
        echo "FALLO: el dry-run no incluye exactamente $migration" >&2
        exit 1
    fi
done
unset dry_run_output

echo "Metadatos públicos de las claves JWT (sin imprimir material de clave):"
jwks_json="$(curl --fail --silent --show-error \
    "https://${expected_ref}.supabase.co/auth/v1/.well-known/jwks.json")"
JWKS_JSON="$jwks_json" python -c 'import json, os, sys
keys = json.loads(os.environ["JWKS_JSON"]).get("keys", [])
if not keys:
    sys.exit("FALLO: el proyecto no publicó claves JWKS; revisar si aún usa HS256 legado")
metadata = [{k: key.get(k) for k in ("kid", "kty", "alg", "use")} for key in keys]
unsupported = [key for key in metadata if key.get("alg") not in {"ES256", "RS256"}]
print(json.dumps(metadata, ensure_ascii=False, indent=2))
if unsupported:
    sys.exit("FALLO: existe un algoritmo JWT no admitido por FastAPI")'
unset jwks_json

echo "OK: preflight de solo lectura completado; no se aplicó ninguna migración."
