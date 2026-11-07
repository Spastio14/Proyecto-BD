-- Fase 4.4: dirección habitual única de la persona.
-- Se conserva el domicilio usado en cada ENVIO como snapshot histórico.

begin;

alter table public.persona
    add column if not exists direccion_habitual varchar(500);

comment on column public.persona.direccion_habitual is
    'Dirección habitual editable; ENVIO.direccion_entrega conserva cada valor histórico.';

commit;
