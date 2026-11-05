-- Datos ficticios para desarrollo y pruebas. Nunca ejecutar en producción.
-- El archivo es repetible: usa identidades estables y ON CONFLICT DO NOTHING.

begin;

insert into public.persona
    (id_persona, nombres, apellidos, telefono_contacto, correo_electronico, documento_identificacion)
values
    (1, 'Invitado', 'Demostración', '8888-0001', 'invitado@example.test', null),
    (2, 'Cliente', 'Registrado', '8888-0002', 'cliente@example.test', 'DEMO-CLIENTE'),
    (3, 'Empleado', 'Pruebas', '8888-0003', 'empleado@example.test', 'DEMO-EMPLEADO')
on conflict do nothing;

insert into public.cuenta_acceso
    (id_cuenta, id_persona, identificador_autenticacion, fecha_activacion, estado_cuenta)
values
    (1, 2, '11111111-1111-4111-8111-111111111111', '2026-11-01 14:00:00+00', 'ACTIVA'),
    (2, 3, '33333333-3333-4333-8333-333333333333', '2026-11-01 14:00:00+00', 'ACTIVA')
on conflict do nothing;

insert into public.cliente
    (id_persona, tipo_cliente, condicion_comercial, fecha_registro, origen_registro, estado)
values
    (1, 'INVITADO', 'DETALLE', '2026-11-01 14:00:00+00', 'WEB', 'ACTIVO'),
    (2, 'REGISTRADO', 'MAYORISTA', '2026-11-01 14:00:00+00', 'WEB', 'ACTIVO')
on conflict do nothing;

insert into public.empleado
    (id_persona, codigo_empleado, fecha_ingreso, estado_laboral, capacidad_maxima_asignaciones)
values (3, 'EMP-DEMO-001', '2026-01-02 14:00:00+00', 'ACTIVO', 10)
on conflict do nothing;

insert into public.rol (id_rol, nombre, descripcion, estado)
values (1, 'ADMINISTRACION', 'Rol ficticio de pruebas', 'ACTIVO')
on conflict do nothing;

insert into public.permiso (id_permiso, codigo_permiso, descripcion, modulo)
values (1, 'PEDIDO_GESTIONAR', 'Gestionar pedidos de prueba', 'PEDIDOS')
on conflict do nothing;

insert into public.asignacion_rol
    (id_asignacion_rol, id_empleado, id_rol, fecha_asignacion, estado)
values (1, 3, 1, '2026-11-01 14:00:00+00', 'ACTIVA')
on conflict do nothing;

insert into public.rol_permiso (id_rol, id_permiso)
values (1, 1)
on conflict do nothing;

insert into public.categoria (id_categoria, nombre, descripcion, estado)
values (1, 'Tazas', 'Categoría ficticia para pruebas', 'ACTIVA')
on conflict do nothing;

insert into public.producto
    (id_producto, id_categoria, nombre, descripcion, informacion_comercial, estado_publicacion)
values (1, 1, 'Taza 11 oz', 'Taza blanca', 'Producto ficticio para pruebas', 'PUBLICADO')
on conflict do nothing;

insert into public.variante_producto
    (id_variante, id_producto, codigo_variante, caracteristicas, precio_detalle, requiere_produccion, estado)
values (1, 1, 'TAZA-11-BLANCA', 'Blanca, 11 oz', 90.00, true, 'ACTIVA')
on conflict do nothing;

insert into public.articulo_inventariable
    (id_articulo, codigo, nombre, tipo_articulo, unidad_medida,
     existencia_actual, existencia_minima, costo_referencia, estado)
values (1, 'ART-TAZA-11', 'Taza blanca 11 oz', 'PRODUCTO', 'UNIDAD', 18.000, 5.000, 25.0000, 'ACTIVO')
on conflict do nothing;

insert into public.escala_precio
    (id_variante, numero_rango, cantidad_minima, cantidad_maxima, precio_unitario_mayorista, estado)
values
    (1, 1, 12, 35, 80.00, 'ACTIVA'),
    (1, 2, 36, null, 75.00, 'ACTIVA')
on conflict do nothing;

insert into public.composicion_producto
    (id_variante, id_articulo, cantidad_estandar, observaciones)
values (1, 1, 1.000, 'Una taza por unidad vendida')
on conflict do nothing;

insert into public.promocion
    (id_promocion, nombre, tipo, cantidad_requerida, beneficio, fecha_inicio,
     fecha_fin, condiciones, permite_combinacion_mayorista, valor_beneficio, estado)
values
    (1, 'Dos tazas por C$170', 'PRECIO_PAQUETE', 2,
     'Dos tazas blancas de 11 oz por C$170', '2026-01-01 06:00:00+00',
     '2030-01-01 05:59:59+00', 'Aplicable a precio detalle', false, 170.00, 'ACTIVA')
on conflict do nothing;

insert into public.promocion_variante (id_promocion, id_variante)
values (1, 1)
on conflict do nothing;

insert into public.etapa_proceso (id_etapa, nombre, descripcion, orden_referencia, estado)
values
    (1, 'Registro', 'Pedido registrado', 1, 'ACTIVA'),
    (2, 'Diseño', 'Preparación y aprobación', 2, 'ACTIVA'),
    (3, 'Producción', 'Sublimación', 3, 'ACTIVA')
on conflict do nothing;

insert into public.cotizacion
    (id_cotizacion, id_cliente, fecha_emision, fecha_vencimiento, estado, total_ofrecido, observaciones)
values (1, 2, '2026-11-01 14:00:00+00', '2026-11-08 14:00:00+00', 'ACEPTADA', 170.00, null)
on conflict do nothing;

insert into public.detalle_cotizacion
    (id_cotizacion, numero_linea, id_variante, cantidad, descripcion_personalizacion,
     precio_ofrecido, descuento_ofrecido)
values (1, 1, 1, 2, 'Diseño ficticio', 90.00, 10.00)
on conflict do nothing;

insert into public.pedido
    (id_pedido, id_cliente, id_empleado_registro, id_etapa_actual, id_cotizacion,
     codigo_pedido, fecha_creacion, vencimiento_pago, canal_origen, estado,
     fecha_entrega_prevista, modalidad_entrega, nombre_persona_retiro,
     total_pedido, token_seguimiento)
values
    (1, 2, 3, 2, 1, 'PED-DEMO-001', '2026-11-02 14:00:00+00',
     '2026-11-03 14:00:00+00', 'WEB', 'EN_DISENO', '2026-11-10 22:00:00+00',
     'ENVIO', null, 170.00, 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
    (2, 1, 3, 1, null, 'PED-DEMO-002', '2026-11-02 15:00:00+00',
     '2026-11-03 15:00:00+00', 'WEB', 'CANCELADO', '2026-11-08 22:00:00+00',
     'RETIRO', 'Invitado Demostración', 90.00, 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb')
on conflict do nothing;

insert into public.detalle_pedido
    (id_pedido, numero_linea, id_variante, cantidad, precio_unitario_aplicado,
     descuento_aplicado, importe_pactado, costo_estimado, costo_real_consolidado,
     modo_precio, id_promocion)
values
    (1, 1, 1, 2, 90.00, 10.00, 170.00, 50.00, null, 'PROMOCION', 1),
    (2, 1, 1, 1, 90.00, 0.00, 90.00, 25.00, null, 'DETALLE', null)
on conflict do nothing;

insert into public.version_diseno
    (id_pedido, numero_linea, numero_version, nombre_archivo, ruta_archivo,
     fecha_creacion, observaciones, es_aprobado)
values (1, 1, 1, 'diseno-demo-v1.png', 'privado/pedido-1/v1.png',
        '2026-11-03 16:00:00+00', 'Archivo ficticio', true)
on conflict do nothing;

insert into public.aprobacion_diseno
    (id_aprobacion, id_pedido, numero_linea, numero_version, id_empleado_registro,
     fecha_aprobacion, medio_confirmacion, observacion, tipo_decision)
values (1, 1, 1, 1, 3, '2026-11-03 18:00:00+00', 'PORTAL', null, 'APROBADO')
on conflict do nothing;

insert into public.solicitud_cambio
    (id_solicitud_cambio, id_pedido, fecha_solicitud, descripcion, motivo,
     decision, costo_adicional_estimado, cargo_adicional_aprobado)
values (1, 1, '2026-11-03 17:00:00+00', 'Ajustar color del texto', null,
        'PENDIENTE', 0.00, null)
on conflict do nothing;

insert into public.historial_pedido
    (id_historial, id_pedido, id_empleado, id_etapa_anterior, id_etapa_nueva,
     fecha_hora, estado_anterior, estado_nuevo, motivo, origen_cambio)
values (1, 1, 3, 1, 2, '2026-11-03 15:30:00+00', 'PAGADO_PARCIAL',
        'EN_DISENO', 'Anticipo confirmado', 'EMPLEADO')
on conflict do nothing;

insert into public.asignacion_etapa
    (id_asignacion, id_pedido, id_etapa, id_empleado, fecha_inicio, fecha_fin,
     origen_asignacion, estado, motivo_reasignacion)
values (1, 1, 2, 3, '2026-11-03 15:30:00+00', null, 'MANUAL', 'ACTIVA', null)
on conflict do nothing;

insert into public.hito_pago
    (id_pedido, numero_hito, tipo_hito, monto_exigido, fecha_vencimiento, estado)
values
    (1, 1, 'ANTICIPO', 85.00, '2026-11-03 14:00:00+00', 'PAGADO'),
    (1, 2, 'SALDO', 85.00, '2026-11-10 20:00:00+00', 'PENDIENTE'),
    (2, 1, 'ANTICIPO', 45.00, '2026-11-03 15:00:00+00', 'PAGADO')
on conflict do nothing;

insert into public.cancelacion
    (id_cancelacion, id_pedido, id_empleado_autoriza, fecha_hora, motivo,
     etapa_cancelacion, monto_retenido, resultado, fecha_confirmacion_autenticacion)
values (1, 2, 3, '2026-11-03 16:00:00+00', 'Cancelación ficticia',
        'REGISTRO', 5.00, 'APROBADA', '2026-11-03 16:01:00+00')
on conflict do nothing;

insert into public.reembolso
    (id_reembolso, id_cancelacion, fecha_solicitud, monto_solicitado,
     monto_aprobado, motivo, estado, fecha_resolucion)
values (1, 1, '2026-11-03 16:05:00+00', 40.00, 40.00,
        'Reembolso ficticio tras retención', 'PAGADO', '2026-11-03 20:00:00+00')
on conflict do nothing;

insert into public.transaccion
    (id_transaccion, id_pedido, numero_hito, id_empleado_verificador,
     id_transaccion_compensada, id_reembolso, fecha_hora, tipo_transaccion,
     monto_con_signo, metodo_pago, banco_receptor, referencia_bancaria,
     estado_verificacion, clave_idem)
values
    (1, 1, 1, 3, null, null, '2026-11-03 15:00:00+00', 'PAGO', 85.00,
     'TRANSFERENCIA', 'BANCO-DEMO', 'REF-DEMO-001', 'VERIFICADO',
     '10000000-0000-4000-8000-000000000001'),
    (2, 2, 1, 3, null, null, '2026-11-03 15:30:00+00', 'PAGO', 45.00,
     'EFECTIVO', null, null, 'VERIFICADO',
     '10000000-0000-4000-8000-000000000002'),
    (3, 2, null, 3, null, 1, '2026-11-03 20:00:00+00', 'REEMBOLSO', -40.00,
     'TRANSFERENCIA', 'BANCO-DEMO', 'REF-DEMO-REEMBOLSO', 'VERIFICADO',
     '10000000-0000-4000-8000-000000000003')
on conflict do nothing;

insert into public.proveedor (id_proveedor, nombre, telefono, correo, direccion, estado)
values (1, 'Proveedor Demostración', '2222-0001', 'proveedor@example.test',
        'Managua, Nicaragua', 'ACTIVO')
on conflict do nothing;

insert into public.compra
    (id_compra, id_proveedor, fecha_compra, numero_documento, estado, total_compra)
values (1, 1, '2026-10-20 15:00:00+00', 'FAC-DEMO-001', 'CONFIRMADA', 500.00)
on conflict do nothing;

insert into public.detalle_compra
    (id_compra, numero_linea, id_articulo, cantidad_comprada, costo_unitario_compra, importe)
values (1, 1, 1, 20.000, 25.0000, 500.00)
on conflict do nothing;

insert into public.movimiento_inventario
    (id_movimiento, id_articulo, id_pedido, id_reserva, id_compra,
     numero_linea_compra, id_empleado, fecha_hora, tipo_movimiento, cantidad,
     costo_unitario_aplicado, motivo, observaciones)
values
    (1, 1, null, null, 1, 1, 3, '2026-10-20 15:05:00+00',
     'ENTRADA_COMPRA', 20.000, 25.0000, 'Compra ficticia', 'FAC-DEMO-001'),
    (2, 1, null, null, null, null, 3, '2026-10-25 15:00:00+00',
     'SALIDA_PERDIDA', 2.000, 25.0000, 'Daño de almacenamiento', null)
on conflict do nothing;

insert into public.reserva_inventario
    (id_reserva, id_pedido, id_articulo, cantidad_reservada, cantidad_pendiente,
     fecha_reserva, fecha_liberacion, estado)
values (1, 1, 1, 2.000, 2.000, '2026-11-03 15:10:00+00', null, 'ACTIVA')
on conflict do nothing;

insert into public.perdida
    (id_perdida, id_pedido, id_empleado_reporta, id_etapa, fecha_hora,
     momento_ocurrencia, tipo_incidente, motivo, descripcion, estado_registro)
values (1, null, 3, null, '2026-10-25 15:05:00+00', 'FUERA_PRODUCCION',
        'DANO_ALMACENAMIENTO', 'Dos tazas dañadas en almacenamiento', null, 'CONFIRMADA')
on conflict do nothing;

insert into public.detalle_perdida
    (id_perdida, numero_linea, id_articulo, id_movimiento, cantidad_perdida,
     costo_unitario_historico, descripcion_dano)
values (1, 1, 1, 2, 2.000, 25.0000, 'Daño ficticio')
on conflict do nothing;

insert into public.gasto
    (id_gasto, id_empleado, concepto, categoria, monto, fecha, metodo_pago,
     banco_receptor, referencia_bancaria, observaciones)
values (1, 3, 'Internet de demostración', 'SERVICIO', 100.00,
        '2026-11-01 14:00:00+00', 'TRANSFERENCIA', 'BANCO-DEMO', 'SERV-DEMO', null)
on conflict do nothing;

insert into public.registro_auditoria
    (id_auditoria, id_persona_actor, fecha_hora, accion, tipo_objeto_afectado,
     referencia_objeto, valor_anterior, valor_nuevo, motivo, origen_accion)
values (1, 3, '2026-11-03 15:30:00+00', 'CAMBIAR_ESTADO', 'PEDIDO',
        'PED-DEMO-001', 'PAGADO_PARCIAL', 'EN_DISENO',
        'Anticipo confirmado', 'EMPLEADO')
on conflict do nothing;

insert into public.agencia_envio (id_agencia, nombre, tipo_agencia, telefono, estado)
values (1, 'Agencia Demostración', 'PAQUETERIA', '2222-0002', 'ACTIVA')
on conflict do nothing;

insert into public.envio
    (id_envio, id_pedido, id_agencia, direccion_entrega, nombre_receptor,
     telefono_receptor, tarifa_acordada, fecha_programada, fecha_entrega_real, estado)
values (1, 1, 1, 'Dirección ficticia, Managua', 'Cliente Registrado',
        '8888-0002', 80.00, '2026-11-10 20:00:00+00', null, 'PROGRAMADO')
on conflict do nothing;

-- Ajusta las secuencias después de insertar identidades estables.
do $$
declare
    item record;
begin
    for item in
        select table_name, column_name
        from information_schema.columns
        where table_schema = 'public'
          and is_identity = 'YES'
    loop
        execute format(
            'select setval(pg_get_serial_sequence(%L, %L), '
            || 'greatest((select coalesce(max(%I), 0) from public.%I), 1), true)',
            'public.' || item.table_name,
            item.column_name,
            item.column_name,
            item.table_name
        );
    end loop;
end
$$;

commit;
