-- Consultas exclusivamente de lectura para el preflight remoto de Fase 3.
-- Ejecutar mediante `supabase db query --remote --read-only --file ...`.

select
    current_database() as database_name,
    current_setting('server_version') as server_version,
    current_setting('server_version_num') as server_version_num;

select count(*) as public_base_tables
from information_schema.tables
where table_schema = 'public'
  and table_type = 'BASE TABLE';

select
    extname,
    extversion,
    n.nspname as extension_schema
from pg_extension e
join pg_namespace n on n.oid = e.extnamespace
where extname in ('btree_gist', 'pgcrypto')
order by extname;

select
    table_name,
    grantee,
    privilege_type
from information_schema.role_table_grants
where table_schema = 'storage'
  and table_name in ('buckets', 'objects')
  and grantee in ('anon', 'authenticated', 'service_role')
order by table_name, grantee, privilege_type;

select
    schemaname,
    tablename,
    policyname,
    roles,
    cmd,
    permissive,
    qual,
    with_check
from pg_policies
where schemaname = 'storage'
  and tablename in ('buckets', 'objects')
order by tablename, policyname;

select
    id,
    name,
    public,
    file_size_limit,
    allowed_mime_types
from storage.buckets
where id in ('disenos', 'comprobantes')
order by id;
