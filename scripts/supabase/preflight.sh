#!/usr/bin/env bash
set -euo pipefail

expected_ref="iwvmbdfkxrssduoqobgy"
configured_ref="${SUPABASE_PROJECT_REF:-}"

if ! command -v supabase >/dev/null 2>&1; then
    echo "FALLO: instala Supabase CLI antes del preflight" >&2
    exit 1
fi
if [ "$configured_ref" != "$expected_ref" ]; then
    echo "FALLO: SUPABASE_PROJECT_REF no coincide con el proyecto de desarrollo" >&2
    exit 1
fi

echo "Supabase CLI: $(supabase --version)"
echo "Historial remoto (solo lectura):"
supabase migration list --linked
echo "Plan remoto (dry-run; no aplica migraciones):"
supabase db push --linked --dry-run
