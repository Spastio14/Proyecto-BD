\set ON_ERROR_STOP on

begin;

create function pg_temp.assert_true(condition boolean, message text)
returns void
language plpgsql
as $$
begin
    if condition is not true then
        raise exception 'FALLO: %', message;
    end if;
end
$$;

select pg_temp.assert_true(
    (select count(*) = 41
     from information_schema.tables
     where table_schema = 'public' and table_type = 'BASE TABLE'),
    'deben existir exactamente 41 tablas públicas'
);

select pg_temp.assert_true(
    (select count(*) = 41
     from pg_constraint c
     join pg_namespace n on n.oid = c.connamespace
     where n.nspname = 'public' and c.contype = 'p'),
    'cada tabla debe conservar su PK (41 en total)'
);

select pg_temp.assert_true(
    (select count(*) = 3
     from information_schema.columns
     where table_schema = 'public'
       and table_name = 'transaccion'
       and column_name in (
           'ruta_comprobante', 'comprobante_mime', 'comprobante_tamano_bytes'
       ))
    and exists (
        select 1
        from pg_constraint
        where conrelid = 'public.transaccion'::regclass
          and conname = 'ck_transaccion_comprobante_integridad'
          and contype = 'c'
    ),
    'transaccion debe conservar la referencia coherente del comprobante'
);

select pg_temp.assert_true(
    (select count(*) = 64
     from pg_constraint c
     join pg_namespace n on n.oid = c.connamespace
     where n.nspname = 'public' and c.contype = 'f'),
    'deben existir las 64 FK conciliadas'
);

select pg_temp.assert_true(
    (select count(*) = 41
     from pg_class c
     join pg_namespace n on n.oid = c.relnamespace
     where n.nspname = 'public' and c.relkind = 'r' and c.relrowsecurity),
    'RLS debe estar habilitado en las 41 tablas'
);

select pg_temp.assert_true(
    has_table_privilege('anon', 'public.categoria', 'SELECT')
    and has_table_privilege('authenticated', 'public.promocion', 'SELECT'),
    'anon y authenticated deben poder leer únicamente el catálogo autorizado'
);

select pg_temp.assert_true(
    not has_table_privilege('anon', 'public.persona', 'SELECT')
    and not has_table_privilege('authenticated', 'public.pedido', 'SELECT')
    and not has_table_privilege('anon', 'public.escala_precio', 'SELECT')
    and not has_table_privilege('authenticated', 'public.escala_precio', 'SELECT')
    and not has_table_privilege('anon', 'public.categoria', 'INSERT'),
    'las tablas privadas, escalas mayoristas y escrituras deben permanecer denegadas'
);

with expected(table_name, column_name) as (
    values
      ('persona','telefono_contacto'), ('persona','correo_electronico'),
      ('persona','documento_identificacion'),
      ('cuenta_acceso','identificador_autenticacion'),
      ('cuenta_acceso','fecha_activacion'), ('cuenta_acceso','ultimo_acceso'),
      ('cliente','fecha_registro'), ('empleado','capacidad_maxima_asignaciones'),
      ('asignacion_rol','fecha_asignacion'), ('asignacion_rol','fecha_finalizacion'),
      ('cotizacion','fecha_emision'), ('cotizacion','fecha_vencimiento'),
      ('pedido','id_empleado_registro'), ('pedido','fecha_creacion'),
      ('pedido','fecha_entrega_prevista'), ('historial_pedido','fecha_hora'),
      ('detalle_pedido','precio_unitario_aplicado'),
      ('detalle_pedido','descuento_aplicado'), ('detalle_pedido','importe_pactado'),
      ('detalle_pedido','costo_estimado'),
      ('detalle_pedido','costo_real_consolidado'),
      ('asignacion_etapa','fecha_inicio'), ('asignacion_etapa','fecha_fin'),
      ('version_diseno','fecha_creacion'), ('solicitud_cambio','fecha_solicitud'),
      ('aprobacion_diseno','id_empleado_registro'),
      ('aprobacion_diseno','fecha_aprobacion'),
      ('escala_precio','cantidad_minima'), ('escala_precio','cantidad_maxima'),
      ('escala_precio','precio_unitario_mayorista'),
      ('composicion_producto','cantidad_estandar'),
      ('promocion','cantidad_requerida'), ('promocion','fecha_inicio'),
      ('promocion','fecha_fin'), ('registro_auditoria','fecha_hora'),
      ('envio','fecha_entrega_real'), ('hito_pago','fecha_vencimiento'),
      ('transaccion','id_empleado_verificador'),
      ('transaccion','id_transaccion_compensada'), ('transaccion','fecha_hora'),
      ('transaccion','monto_con_signo'), ('cancelacion','id_empleado_autoriza'),
      ('cancelacion','fecha_hora'), ('reembolso','fecha_solicitud'),
      ('compra','fecha_compra'), ('detalle_compra','cantidad_comprada'),
      ('detalle_compra','costo_unitario_compra'),
      ('movimiento_inventario','fecha_hora'),
      ('movimiento_inventario','costo_unitario_aplicado'),
      ('reserva_inventario','cantidad_reservada'),
      ('reserva_inventario','cantidad_pendiente'),
      ('reserva_inventario','fecha_reserva'),
      ('reserva_inventario','fecha_liberacion'),
      ('perdida','id_empleado_reporta'), ('perdida','fecha_hora'),
      ('detalle_perdida','cantidad_perdida'),
      ('detalle_perdida','costo_unitario_historico')
), present as (
    select e.*
    from expected e
    join information_schema.columns c
      on c.table_schema = 'public'
     and c.table_name = e.table_name
     and c.column_name = e.column_name
)
select pg_temp.assert_true(
    (select count(*) = 57 from present),
    'deben existir los 57 nombres completos conciliados'
);

select pg_temp.assert_true(
    (select column_default like '%0%'
     from information_schema.columns
     where table_schema = 'public' and table_name = 'detalle_cotizacion'
       and column_name = 'descuento_ofrecido')
    and
    (select column_default like '%0%'
     from information_schema.columns
     where table_schema = 'public' and table_name = 'detalle_pedido'
       and column_name = 'descuento_aplicado'),
    'los descuentos deben tener DEFAULT 0'
);

select pg_temp.assert_true(
    (select data_type = 'text'
     from information_schema.columns
     where table_schema = 'public' and table_name = 'promocion'
       and column_name = 'beneficio')
    and
    (select numeric_precision = 19 and numeric_scale = 2
     from information_schema.columns
     where table_schema = 'public' and table_name = 'promocion'
       and column_name = 'valor_beneficio'),
    'beneficio debe ser text y valor_beneficio numeric(19,2)'
);

do $$
begin
    begin
        insert into public.escala_precio
            (id_variante, numero_rango, cantidad_minima, cantidad_maxima,
             precio_unitario_mayorista, estado)
        values (1, 99, 20, 40, 70, 'ACTIVA');
        raise exception 'FALLO: se aceptó un rango mayorista activo solapado';
    exception when exclusion_violation then null;
    end;

    begin
        insert into public.pedido
            (id_cliente, id_cotizacion, codigo_pedido, fecha_creacion,
             vencimiento_pago, canal_origen, estado, fecha_entrega_prevista,
             modalidad_entrega, total_pedido)
        values (2, 1, 'PED-DUP-COT', '2026-11-04 10:00+00',
                '2026-11-05 10:00+00', 'WEB', 'PENDIENTE_PAGO',
                '2026-11-10 10:00+00', 'RETIRO', 170);
        raise exception 'FALLO: una cotización originó más de un pedido';
    exception when unique_violation then null;
    end;

    begin
        insert into public.pedido
            (id_cliente, codigo_pedido, fecha_creacion, vencimiento_pago,
             fecha_inicio_revision_pago, canal_origen, estado,
             fecha_entrega_prevista, modalidad_entrega, total_pedido)
        values (2, 'PED-REV-TARDIA', '2026-11-04 10:00+00',
                '2026-11-05 10:00+00', '2026-11-05 10:01+00', 'WEB',
                'PENDIENTE_PAGO', '2026-11-10 10:00+00', 'RETIRO', 10);
        raise exception 'FALLO: se aceptó una revisión iniciada después del vencimiento';
    exception when check_violation then null;
    end;

    begin
        insert into public.pedido
            (id_cliente, codigo_pedido, fecha_creacion, vencimiento_pago,
             canal_origen, estado, fecha_entrega_prevista,
             modalidad_entrega, total_pedido)
        values (2, 'PED-VENTANA-CORTA', '2026-11-04 10:00+00',
                '2026-11-05 09:59+00', 'WEB', 'PENDIENTE_PAGO',
                '2026-11-10 10:00+00', 'RETIRO', 10);
        raise exception 'FALLO: se aceptó una ventana inicial distinta de 24 horas';
    exception when check_violation then null;
    end;

    begin
        insert into public.promocion
            (nombre, tipo, cantidad_requerida, beneficio, fecha_inicio, fecha_fin,
             permite_combinacion_mayorista, valor_beneficio, estado)
        values ('Inválida', 'PORCENTAJE', 1, 'Más de cien', now(), now() + interval '1 day',
                false, 100.01, 'ACTIVA');
        raise exception 'FALLO: se aceptó un porcentaje mayor que 100';
    exception when check_violation then null;
    end;

    insert into public.promocion
        (nombre, tipo, cantidad_requerida, beneficio, fecha_inicio, fecha_fin,
         permite_combinacion_mayorista, valor_beneficio, estado)
    values ('Porcentaje cero permitido', 'PORCENTAJE', 1, 'Sin rebaja',
            now(), now() + interval '1 day', false, 0.00, 'INACTIVA');

    begin
        insert into public.promocion
            (nombre, tipo, cantidad_requerida, beneficio, fecha_inicio, fecha_fin,
             permite_combinacion_mayorista, valor_beneficio, estado)
        values ('Porcentaje negativo', 'PORCENTAJE', 1, 'Inválida',
                now(), now() + interval '1 day', false, -0.01, 'INACTIVA');
        raise exception 'FALLO: se aceptó un porcentaje negativo';
    exception when check_violation then null;
    end;

    begin
        insert into public.reembolso
            (id_cancelacion, fecha_solicitud, monto_solicitado, monto_aprobado,
             motivo, estado)
        values (1, now(), 1, 0, '   ', 'PENDIENTE');
        raise exception 'FALLO: se aceptó un motivo de reembolso vacío';
    exception when check_violation then null;
    end;

    begin
        insert into public.registro_auditoria
            (id_persona_actor, fecha_hora, accion, tipo_objeto_afectado,
             referencia_objeto, motivo, origen_accion)
        values (3, now(), 'PRUEBA', 'PEDIDO', 'X', 'Prueba', 'SISTEMA');
        raise exception 'FALLO: SISTEMA conservó una persona actora';
    exception when check_violation then null;
    end;

    begin
        insert into public.detalle_pedido
            (id_pedido, numero_linea, id_variante, cantidad,
             precio_unitario_aplicado, descuento_aplicado, importe_pactado,
             costo_estimado, modo_precio, id_promocion)
        values (1, 99, 1, 1, 90, 0, 90, 25, 'PROMOCION', 99999);
        raise exception 'FALLO: se aceptó una promoción inexistente en el detalle';
    exception when foreign_key_violation then null;
    end;

    begin
        insert into public.perdida
            (id_empleado_reporta, fecha_hora, momento_ocurrencia,
             tipo_incidente, motivo, estado_registro)
        values (3, now(), 'DURANTE_VENTA', 'OTRO', 'Prueba', 'REPORTADA');
        raise exception 'FALLO: se aceptó un momento de pérdida no autorizado';
    exception when check_violation then null;
    end;
end
$$;

-- Una compensación puede ajustar en cualquiera de los dos sentidos.
insert into public.transaccion
    (id_transaccion, id_pedido, id_transaccion_compensada, fecha_hora,
     tipo_transaccion, monto_con_signo, metodo_pago, estado_verificacion, clave_idem)
values
    (9001, 1, 1, now(), 'COMPENSACION', 1.00, 'OTRO', 'VERIFICADO',
     '90010000-0000-4000-8000-000000000001'),
    (9002, 1, 1, now(), 'COMPENSACION', -1.00, 'OTRO', 'VERIFICADO',
     '90020000-0000-4000-8000-000000000002');

select pg_temp.assert_true(
    (select count(*) = 2 from public.transaccion where id_transaccion in (9001, 9002)),
    'las compensaciones deben admitir ambos signos'
);

rollback;

\echo 'OK: 41 tablas, 64 FK, nombres conciliados, integridad y RLS verificados.'
