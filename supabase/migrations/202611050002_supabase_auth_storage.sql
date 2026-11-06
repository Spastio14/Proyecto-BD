-- Fase 3: referencia estructural del comprobante y buckets privados administrados.
-- No agrega tablas al modelo aprobado de 41 entidades.

begin;

alter table public.transaccion
    add column ruta_comprobante varchar(1000),
    add column comprobante_mime varchar(100),
    add column comprobante_tamano_bytes bigint,
    add constraint ck_transaccion_comprobante_integridad check (
        (ruta_comprobante is null
            and comprobante_mime is null
            and comprobante_tamano_bytes is null)
        or
        (ruta_comprobante is not null
            and comprobante_mime is not null
            and comprobante_tamano_bytes > 0)
    ),
    add constraint ck_transaccion_comprobante_tipo check (
        comprobante_mime is null
        or comprobante_mime in ('image/png', 'image/jpeg', 'application/pdf')
    );

-- Storage no existe en el PostgreSQL aislado del runner. En Supabase, configura
-- los buckets sin volverlos públicos. El backend es el único emisor de URLs firmadas.
do $block$
begin
    if to_regclass('storage.buckets') is not null then
        execute $sql$
            insert into storage.buckets
                (id, name, public, file_size_limit, allowed_mime_types)
            values
                ('disenos', 'disenos', false, 10485760,
                    array['image/png', 'image/jpeg', 'application/pdf']),
                ('comprobantes', 'comprobantes', false, 5242880,
                    array['image/png', 'image/jpeg', 'application/pdf'])
            on conflict (id) do update
            set public = false,
                file_size_limit = excluded.file_size_limit,
                allowed_mime_types = excluded.allowed_mime_types
        $sql$;
        -- Los privilegios de estas tablas son administrados por Supabase y son
        -- globales, no por bucket. No se revocan aquí. Al no crear policies para
        -- estos IDs, la RLS administrada mantiene ambos buckets cerrados al
        -- acceso directo de anon/authenticated; FastAPI usa el servicio privado.
    end if;
end
$block$;

commit;
