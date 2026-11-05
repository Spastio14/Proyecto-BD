-- Relaciones, exclusión de escalas e índices operativos.

begin;

create schema if not exists extensions;
create extension if not exists btree_gist with schema extensions;

alter table public.cliente
    add constraint fk_cliente_persona
    foreign key (id_persona) references public.persona (id_persona);

alter table public.empleado
    add constraint fk_empleado_persona
    foreign key (id_persona) references public.persona (id_persona);

alter table public.cuenta_acceso
    add constraint fk_cuenta_persona
    foreign key (id_persona) references public.persona (id_persona);

alter table public.asignacion_rol
    add constraint fk_asig_rol_empleado
    foreign key (id_empleado) references public.empleado (id_persona);

alter table public.asignacion_rol
    add constraint fk_asig_rol_rol
    foreign key (id_rol) references public.rol (id_rol);

alter table public.rol_permiso
    add constraint fk_rol_permiso_rol
    foreign key (id_rol) references public.rol (id_rol) on delete cascade;

alter table public.rol_permiso
    add constraint fk_rol_permiso_permiso
    foreign key (id_permiso) references public.permiso (id_permiso) on delete cascade;

alter table public.producto
    add constraint fk_producto_categoria
    foreign key (id_categoria) references public.categoria (id_categoria);

alter table public.variante_producto
    add constraint fk_variante_producto
    foreign key (id_producto) references public.producto (id_producto);

alter table public.escala_precio
    add constraint fk_escala_variante
    foreign key (id_variante) references public.variante_producto (id_variante)
    on delete cascade;

alter table public.promocion_variante
    add constraint fk_promo_var_promocion
    foreign key (id_promocion) references public.promocion (id_promocion)
    on delete cascade;

alter table public.promocion_variante
    add constraint fk_promo_var_variante
    foreign key (id_variante) references public.variante_producto (id_variante)
    on delete cascade;

alter table public.composicion_producto
    add constraint fk_composicion_variante
    foreign key (id_variante) references public.variante_producto (id_variante)
    on delete cascade;

alter table public.composicion_producto
    add constraint fk_composicion_articulo
    foreign key (id_articulo) references public.articulo_inventariable (id_articulo);

alter table public.pedido
    add constraint fk_pedido_cliente
    foreign key (id_cliente) references public.cliente (id_persona);

alter table public.pedido
    add constraint fk_pedido_empleado
    foreign key (id_empleado_registro) references public.empleado (id_persona)
    on delete set null;

alter table public.pedido
    add constraint fk_pedido_etapa
    foreign key (id_etapa_actual) references public.etapa_proceso (id_etapa);

alter table public.pedido
    add constraint fk_pedido_cotizacion
    foreign key (id_cotizacion, id_cliente)
    references public.cotizacion (id_cotizacion, id_cliente);

alter table public.detalle_pedido
    add constraint fk_det_pedido_pedido
    foreign key (id_pedido) references public.pedido (id_pedido);

alter table public.detalle_pedido
    add constraint fk_det_pedido_variante
    foreign key (id_variante) references public.variante_producto (id_variante);

alter table public.version_diseno
    add constraint fk_version_det_pedido
    foreign key (id_pedido, numero_linea)
    references public.detalle_pedido (id_pedido, numero_linea);

alter table public.aprobacion_diseno
    add constraint fk_aprobacion_version
    foreign key (id_pedido, numero_linea, numero_version)
    references public.version_diseno (id_pedido, numero_linea, numero_version);

alter table public.aprobacion_diseno
    add constraint fk_aprobacion_empleado
    foreign key (id_empleado_registro) references public.empleado (id_persona);

alter table public.historial_pedido
    add constraint fk_historial_pedido
    foreign key (id_pedido) references public.pedido (id_pedido);

alter table public.historial_pedido
    add constraint fk_historial_empleado
    foreign key (id_empleado) references public.empleado (id_persona);

alter table public.historial_pedido
    add constraint fk_historial_etapa_anterior
    foreign key (id_etapa_anterior) references public.etapa_proceso (id_etapa);

alter table public.historial_pedido
    add constraint fk_historial_etapa_nueva
    foreign key (id_etapa_nueva) references public.etapa_proceso (id_etapa);

alter table public.asignacion_etapa
    add constraint fk_asig_etapa_pedido
    foreign key (id_pedido) references public.pedido (id_pedido);

alter table public.asignacion_etapa
    add constraint fk_asig_etapa_etapa
    foreign key (id_etapa) references public.etapa_proceso (id_etapa);

alter table public.asignacion_etapa
    add constraint fk_asig_etapa_empleado
    foreign key (id_empleado) references public.empleado (id_persona);

alter table public.solicitud_cambio
    add constraint fk_solicitud_pedido
    foreign key (id_pedido) references public.pedido (id_pedido);

alter table public.cotizacion
    add constraint fk_cotizacion_cliente
    foreign key (id_cliente) references public.cliente (id_persona);

alter table public.detalle_cotizacion
    add constraint fk_det_cot_cotizacion
    foreign key (id_cotizacion) references public.cotizacion (id_cotizacion);

alter table public.detalle_cotizacion
    add constraint fk_det_cot_variante
    foreign key (id_variante) references public.variante_producto (id_variante);

alter table public.hito_pago
    add constraint fk_hito_pedido
    foreign key (id_pedido) references public.pedido (id_pedido);

alter table public.transaccion
    add constraint fk_transaccion_pedido
    foreign key (id_pedido) references public.pedido (id_pedido);

alter table public.transaccion
    add constraint fk_transaccion_hito
    foreign key (id_pedido, numero_hito)
    references public.hito_pago (id_pedido, numero_hito);

alter table public.transaccion
    add constraint fk_transaccion_empleado
    foreign key (id_empleado_verificador) references public.empleado (id_persona);

alter table public.transaccion
    add constraint fk_transaccion_compensada
    foreign key (id_transaccion_compensada, id_pedido)
    references public.transaccion (id_transaccion, id_pedido);

alter table public.transaccion
    add constraint fk_transaccion_reembolso
    foreign key (id_reembolso) references public.reembolso (id_reembolso);

alter table public.cancelacion
    add constraint fk_cancelacion_pedido
    foreign key (id_pedido) references public.pedido (id_pedido);

alter table public.cancelacion
    add constraint fk_cancelacion_empleado
    foreign key (id_empleado_autoriza) references public.empleado (id_persona);

alter table public.reembolso
    add constraint fk_reembolso_cancelacion
    foreign key (id_cancelacion) references public.cancelacion (id_cancelacion);

alter table public.reserva_inventario
    add constraint fk_reserva_pedido
    foreign key (id_pedido) references public.pedido (id_pedido);

alter table public.reserva_inventario
    add constraint fk_reserva_articulo
    foreign key (id_articulo) references public.articulo_inventariable (id_articulo);

alter table public.movimiento_inventario
    add constraint fk_movimiento_articulo
    foreign key (id_articulo) references public.articulo_inventariable (id_articulo);

alter table public.movimiento_inventario
    add constraint fk_movimiento_pedido
    foreign key (id_pedido) references public.pedido (id_pedido);

alter table public.movimiento_inventario
    add constraint fk_movimiento_reserva
    foreign key (id_reserva, id_pedido, id_articulo)
    references public.reserva_inventario (id_reserva, id_pedido, id_articulo);

alter table public.movimiento_inventario
    add constraint fk_movimiento_det_compra
    foreign key (id_compra, numero_linea_compra, id_articulo)
    references public.detalle_compra (id_compra, numero_linea, id_articulo);

alter table public.movimiento_inventario
    add constraint fk_movimiento_empleado
    foreign key (id_empleado) references public.empleado (id_persona);

alter table public.perdida
    add constraint fk_perdida_pedido
    foreign key (id_pedido) references public.pedido (id_pedido);

alter table public.perdida
    add constraint fk_perdida_empleado
    foreign key (id_empleado_reporta) references public.empleado (id_persona);

alter table public.perdida
    add constraint fk_perdida_etapa
    foreign key (id_etapa) references public.etapa_proceso (id_etapa);

alter table public.detalle_perdida
    add constraint fk_det_perdida_perdida
    foreign key (id_perdida) references public.perdida (id_perdida);

alter table public.detalle_perdida
    add constraint fk_det_perdida_articulo
    foreign key (id_articulo) references public.articulo_inventariable (id_articulo);

alter table public.detalle_perdida
    add constraint fk_det_perdida_movimiento
    foreign key (id_movimiento, id_articulo)
    references public.movimiento_inventario (id_movimiento, id_articulo);

alter table public.compra
    add constraint fk_compra_proveedor
    foreign key (id_proveedor) references public.proveedor (id_proveedor);

alter table public.detalle_compra
    add constraint fk_det_compra_compra
    foreign key (id_compra) references public.compra (id_compra);

alter table public.detalle_compra
    add constraint fk_det_compra_articulo
    foreign key (id_articulo) references public.articulo_inventariable (id_articulo);

alter table public.gasto
    add constraint fk_gasto_empleado
    foreign key (id_empleado) references public.empleado (id_persona);

alter table public.envio
    add constraint fk_envio_pedido
    foreign key (id_pedido) references public.pedido (id_pedido);

alter table public.envio
    add constraint fk_envio_agencia
    foreign key (id_agencia) references public.agencia_envio (id_agencia)
    on delete set null;

alter table public.registro_auditoria
    add constraint fk_auditoria_persona
    foreign key (id_persona_actor) references public.persona (id_persona);

alter table public.detalle_pedido
    add constraint fk_det_pedido_promocion
    foreign key (id_promocion) references public.promocion (id_promocion);

-- Dos rangos mayoristas activos de una variante no pueden solaparse.
alter table public.escala_precio
    add constraint ex_escala_precio_sin_solapamiento
    exclude using gist (
        id_variante with =,
        int8range(
            cantidad_minima::bigint,
            coalesce(cantidad_maxima::bigint, 2147483647),
            '[]'
        ) with &&
    ) where (estado = 'ACTIVA');

-- Índices de FK y búsquedas operativas. Se omiten los cubiertos por PK/UQ.
create index ix_asig_rol_empleado on public.asignacion_rol (id_empleado);
create index ix_asig_rol_rol on public.asignacion_rol (id_rol);
create index ix_rol_permiso_permiso on public.rol_permiso (id_permiso);
create index ix_producto_categoria on public.producto (id_categoria);
create index ix_variante_producto on public.variante_producto (id_producto);
create index ix_promo_var_variante on public.promocion_variante (id_variante);
create index ix_composicion_articulo on public.composicion_producto (id_articulo);
create index ix_pedido_empleado on public.pedido (id_empleado_registro);
create index ix_pedido_etapa on public.pedido (id_etapa_actual);
create index ix_pedido_cliente_estado on public.pedido (id_cliente, estado);
create index ix_pedido_vencimiento on public.pedido (vencimiento_pago)
    where estado = 'PENDIENTE_PAGO';
create index ix_det_pedido_variante on public.detalle_pedido (id_variante);
create index ix_det_pedido_promocion on public.detalle_pedido (id_promocion)
    where id_promocion is not null;
create index ix_aprobacion_version
    on public.aprobacion_diseno (id_pedido, numero_linea, numero_version);
create index ix_aprobacion_empleado on public.aprobacion_diseno (id_empleado_registro);
create index ix_historial_pedido_fecha on public.historial_pedido (id_pedido, fecha_hora);
create index ix_historial_empleado on public.historial_pedido (id_empleado);
create index ix_historial_etapa_anterior on public.historial_pedido (id_etapa_anterior);
create index ix_historial_etapa_nueva on public.historial_pedido (id_etapa_nueva);
create index ix_asig_etapa_pedido on public.asignacion_etapa (id_pedido);
create index ix_asig_etapa_etapa on public.asignacion_etapa (id_etapa);
create index ix_asig_etapa_empleado on public.asignacion_etapa (id_empleado);
create index ix_solicitud_pedido on public.solicitud_cambio (id_pedido);
create index ix_cotizacion_cliente on public.cotizacion (id_cliente);
create index ix_det_cot_variante on public.detalle_cotizacion (id_variante);
create index ix_transaccion_hito on public.transaccion (id_pedido, numero_hito);
create index ix_transaccion_empleado on public.transaccion (id_empleado_verificador);
create index ix_transaccion_compensada on public.transaccion (id_transaccion_compensada);
create index ix_transaccion_reembolso on public.transaccion (id_reembolso);
create index ix_transaccion_pedido_estado
    on public.transaccion (id_pedido, estado_verificacion, fecha_hora);
create index ix_cancelacion_empleado on public.cancelacion (id_empleado_autoriza);
create index ix_reembolso_cancelacion on public.reembolso (id_cancelacion);
create index ix_reserva_pedido on public.reserva_inventario (id_pedido);
create index ix_reserva_articulo_estado
    on public.reserva_inventario (id_articulo, estado);
create index ix_movimiento_pedido on public.movimiento_inventario (id_pedido);
create index ix_movimiento_reserva on public.movimiento_inventario (id_reserva);
create index ix_movimiento_compra
    on public.movimiento_inventario (id_compra, numero_linea_compra);
create index ix_movimiento_empleado on public.movimiento_inventario (id_empleado);
create index ix_movimiento_articulo_fecha
    on public.movimiento_inventario (id_articulo, fecha_hora desc);
create index ix_perdida_pedido on public.perdida (id_pedido);
create index ix_perdida_empleado on public.perdida (id_empleado_reporta);
create index ix_perdida_etapa on public.perdida (id_etapa);
create index ix_perdida_fecha on public.perdida (fecha_hora desc);
create index ix_det_perdida_articulo on public.detalle_perdida (id_articulo);
create index ix_compra_proveedor_fecha on public.compra (id_proveedor, fecha_compra desc);
create index ix_det_compra_articulo on public.detalle_compra (id_articulo);
create index ix_gasto_empleado_fecha on public.gasto (id_empleado, fecha desc);
create index ix_envio_agencia on public.envio (id_agencia);
create index ix_auditoria_actor_fecha
    on public.registro_auditoria (id_persona_actor, fecha_hora desc);
create index ix_auditoria_objeto
    on public.registro_auditoria (tipo_objeto_afectado, referencia_objeto);
create index ix_promocion_vigencia on public.promocion (estado, fecha_inicio, fecha_fin);

commit;
