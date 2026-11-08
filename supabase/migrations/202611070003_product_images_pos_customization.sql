-- Fase 4.5.2: referencias de imágenes comerciales y personalización presencial.
-- Conserva las 41 tablas; sólo añade atributos opcionales reproducibles.

begin;

alter table public.producto
    add column if not exists ruta_imagen_principal varchar(1000),
    add column if not exists imagen_mime varchar(100),
    add column if not exists imagen_tamano_bytes bigint;

alter table public.producto
    drop constraint if exists ck_producto_imagen_metadatos;

alter table public.producto
    add constraint ck_producto_imagen_metadatos check (
        (ruta_imagen_principal is null and imagen_mime is null and imagen_tamano_bytes is null)
        or
        (ruta_imagen_principal is not null
         and imagen_mime in ('image/png', 'image/jpeg', 'image/webp')
         and imagen_tamano_bytes between 1 and 5242880)
    );

alter table public.detalle_pedido
    add column if not exists descripcion_personalizacion text;

do $$
begin
    if to_regclass('storage.buckets') is not null then
        insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
        values (
            'catalogo-productos',
            'catalogo-productos',
            true,
            5242880,
            array['image/png', 'image/jpeg', 'image/webp']
        )
        on conflict (id) do update
        set public = excluded.public,
            file_size_limit = excluded.file_size_limit,
            allowed_mime_types = excluded.allowed_mime_types;
    end if;
end
$$;

commit;
