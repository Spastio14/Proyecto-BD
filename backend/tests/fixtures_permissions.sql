-- Permisos ficticios exclusivos del entorno de prueba de Fase 2.
insert into public.permiso (id_permiso, codigo_permiso, descripcion, modulo)
values
    (2, 'PAGO_VERIFICAR', 'Verificar pagos de prueba', 'PAGOS'),
    (3, 'INVENTARIO_GESTIONAR', 'Gestionar inventario de prueba', 'INVENTARIO'),
    (4, 'DISENO_APROBAR', 'Aprobar diseños de prueba', 'DISENOS'),
    (5, 'PRODUCCION_INICIAR', 'Iniciar producción de prueba', 'PRODUCCION'),
    (6, 'PERDIDA_REGISTRAR', 'Registrar pérdidas de prueba', 'INVENTARIO')
on conflict do nothing;

insert into public.rol_permiso (id_rol, id_permiso)
values (1, 2), (1, 3), (1, 4), (1, 5), (1, 6)
on conflict do nothing;
