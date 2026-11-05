-- Fase 2: las escalas mayoristas son una regla comercial calculada por FastAPI.
-- Evita exponerlas directamente a clientes anónimos o autenticados.

begin;

drop policy if exists catalogo_escala_lectura on public.escala_precio;
revoke select on public.escala_precio from anon, authenticated;

commit;
