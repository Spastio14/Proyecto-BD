CREATE DATABASE [S2R]
    COLLATE Latin1_General_100_CI_AS_SC_UTF8;
GO
USE [S2R];
GO
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
SET ANSI_PADDING ON;
SET ANSI_WARNINGS ON;
SET ARITHABORT ON;
SET CONCAT_NULL_YIELDS_NULL ON;
SET NUMERIC_ROUNDABORT OFF;
SET XACT_ABORT ON;
GO

-- 1. TABLAS

CREATE TABLE [dbo].[PERSONA] (
    [id_persona] INT IDENTITY(1,1) NOT NULL,
    [nombres] VARCHAR(120) NOT NULL,
    [apellidos] VARCHAR(120) NULL,
    [tel] VARCHAR(30) NULL, --telefono_contacto
    [correo] VARCHAR(254) NULL, --correo_electronico
    [documento] VARCHAR(120) NULL, --documento_identificacion
    CONSTRAINT [PK_PERSONA] PRIMARY KEY ([id_persona]),
    CONSTRAINT [CK_PERSONA_CORREO] CHECK ([correo] IS NULL OR [correo] LIKE '%_@_%._%')
);
GO

CREATE TABLE [dbo].[CUENTA_ACCESO] (
    [id_cuenta] INT IDENTITY(1,1) NOT NULL,
    [id_persona] INT NOT NULL,
    [auth_uid] VARCHAR(255) NOT NULL, -- nombre completo: identificador_autenticacion
    [fec_alta] DATETIME2(0) NOT NULL, -- nombre completo: fecha_activacion
    [estado_cuenta] VARCHAR(80) NOT NULL,
    [ult_acceso] DATETIME2(0) NULL, -- nombre completo: ultimo_acceso
    CONSTRAINT [PK_CUENTA_ACCESO] PRIMARY KEY ([id_cuenta]),
    CONSTRAINT [UQ_CUENTA_ACCESO_id_persona] UNIQUE ([id_persona]),
    CONSTRAINT [UQ_CUENTA_ACCESO_identificador_autenticacion] UNIQUE ([auth_uid]),
    CONSTRAINT [CK_CUENTA_ESTADO] CHECK ([estado_cuenta] IN ('ACTIVA','SUSPENDIDA','BLOQUEADA'))
);
GO

CREATE TABLE [dbo].[CLIENTE] (
    [id_persona] INT NOT NULL,
    [tipo_cliente] VARCHAR(80) NOT NULL,
    [condicion_comercial] VARCHAR(255) NOT NULL,
    [fec_registro] DATETIME2(0) NOT NULL, -- nombre completo: fecha_registro
    [origen_registro] VARCHAR(80) NOT NULL,
    [estado] VARCHAR(80) NOT NULL,
    CONSTRAINT [PK_CLIENTE] PRIMARY KEY ([id_persona]),
    CONSTRAINT [CK_CLIENTE_TIPO] CHECK ([tipo_cliente] IN ('INVITADO','REGISTRADO','EMPRESA')),
    CONSTRAINT [CK_CLIENTE_ESTADO] CHECK ([estado] IN ('ACTIVO','INACTIVO'))
);
GO

CREATE TABLE [dbo].[EMPLEADO] (
    [id_persona] INT NOT NULL,
    [codigo_empleado] VARCHAR(64) NOT NULL,
    [fecha_ingreso] DATETIME2(0) NOT NULL,
    [estado_laboral] VARCHAR(80) NOT NULL,
    [max_asignaciones] INT NOT NULL, -- nombre completo: capacidad_maxima_asignaciones
    CONSTRAINT [PK_EMPLEADO] PRIMARY KEY ([id_persona]),
    CONSTRAINT [UQ_EMPLEADO_codigo_empleado] UNIQUE ([codigo_empleado]),
    CONSTRAINT [CK_EMPLEADO_capacidad_maxima_asignaciones_NNEG] CHECK ([max_asignaciones] >= 0),
    CONSTRAINT [CK_EMPLEADO_ESTADO] CHECK ([estado_laboral] IN ('ACTIVO','INACTIVO','SUSPENDIDO'))
);
GO

CREATE TABLE [dbo].[ASIGNACION_ROL] (
    [id_asignacion_rol] INT IDENTITY(1,1) NOT NULL,
    [id_empleado] INT NOT NULL,
    [id_rol] INT NOT NULL,
    [fec_asig] DATETIME2(0) NOT NULL, -- nombre completo: fecha_asignacion
    [fec_fin] DATETIME2(0) NULL, -- nombre completo: fecha_finalizacion
    [estado] VARCHAR(80) NOT NULL,
    CONSTRAINT [PK_ASIGNACION_ROL] PRIMARY KEY ([id_asignacion_rol]),
    CONSTRAINT [CK_ASIGNACION_ROL_REGLA_1] CHECK ([fec_fin] IS NULL OR [fec_fin] >= [fec_asig]),
    CONSTRAINT [CK_ASIG_ROL_ESTADO] CHECK ([estado] IN ('ACTIVA','FINALIZADA'))
);
GO

CREATE TABLE [dbo].[ROL] (
    [id_rol] INT IDENTITY(1,1) NOT NULL,
    [nombre] VARCHAR(180) NOT NULL,
    [descripcion] VARCHAR(500) NOT NULL,
    [estado] VARCHAR(80) NOT NULL,
    CONSTRAINT [PK_ROL] PRIMARY KEY ([id_rol]),
    CONSTRAINT [UQ_ROL_nombre] UNIQUE ([nombre])
);
GO

CREATE TABLE [dbo].[ROL_PERMISO] (
    [id_rol] INT NOT NULL,
    [id_permiso] INT NOT NULL,
    CONSTRAINT [PK_ROL_PERMISO] PRIMARY KEY ([id_rol], [id_permiso])
);
GO

CREATE TABLE [dbo].[PERMISO] (
    [id_permiso] INT IDENTITY(1,1) NOT NULL,
    [codigo_permiso] VARCHAR(64) NOT NULL,
    [descripcion] VARCHAR(500) NOT NULL,
    [modulo] VARCHAR(255) NOT NULL,
    CONSTRAINT [PK_PERMISO] PRIMARY KEY ([id_permiso]),
    CONSTRAINT [UQ_PERMISO_codigo_permiso] UNIQUE ([codigo_permiso])
);
GO

CREATE TABLE [dbo].[COTIZACION] (
    [id_cotizacion] INT IDENTITY(1,1) NOT NULL,
    [id_cliente] INT NOT NULL,
    [fec_emision] DATETIME2(0) NOT NULL, -- nombre completo: fecha_emision
    [fec_venc] DATETIME2(0) NOT NULL, -- nombre completo: fecha_vencimiento
    [estado] VARCHAR(80) NOT NULL,
    [total_ofrecido] DECIMAL(19,2) NOT NULL,
    [observaciones] VARCHAR(MAX) NULL,
    CONSTRAINT [PK_COTIZACION] PRIMARY KEY ([id_cotizacion]),
    CONSTRAINT [CK_COTIZACION_total_ofrecido_NNEG] CHECK ([total_ofrecido] >= 0),
    CONSTRAINT [CK_COTIZACION_REGLA_1] CHECK ([fec_venc] >= [fec_emision]),
    CONSTRAINT [CK_COTIZACION_ESTADO] CHECK ([estado] IN ('BORRADOR','EMITIDA','ACEPTADA','RECHAZADA','VENCIDA')),
    CONSTRAINT [UQ_COT_ID_CLIENTE] UNIQUE ([id_cotizacion], [id_cliente])
);
GO

CREATE TABLE [dbo].[PEDIDO] (
    [id_pedido] INT IDENTITY(1,1) NOT NULL,
    [id_cliente] INT NOT NULL,
    [id_emp_reg] INT NULL, -- nombre completo: id_empleado_registro
    [id_etapa_actual] INT NULL,
    [id_cotizacion] INT NULL,
    [codigo_pedido] VARCHAR(64) NOT NULL,
    [fec_crea] DATETIME2(0) NOT NULL, -- nombre completo: fecha_creacion
    [vencimiento_pago] DATETIME2(0) NOT NULL,
    [canal_origen] VARCHAR(80) NOT NULL,
    [estado] VARCHAR(80) NOT NULL,
    [fec_entrega_prev] DATETIME2(0) NOT NULL, -- nombre completo: fecha_entrega_prevista
    [modalidad_entrega] VARCHAR(80) NOT NULL,
    [nombre_persona_retiro] VARCHAR(120) NULL,
    [total_pedido] DECIMAL(19,2) NOT NULL CONSTRAINT [DF_PEDIDO_TOTAL] DEFAULT (0), -- total acordado, calculado por backend
    [token_seguimiento] UNIQUEIDENTIFIER NOT NULL CONSTRAINT [DF_PEDIDO_token_seguimiento] DEFAULT NEWID(),
    CONSTRAINT [PK_PEDIDO] PRIMARY KEY ([id_pedido]),
    CONSTRAINT [UQ_PEDIDO_codigo_pedido] UNIQUE ([codigo_pedido]),
    CONSTRAINT [UQ_PEDIDO_token_seguimiento] UNIQUE ([token_seguimiento]),
    CONSTRAINT [CK_PEDIDO_FECHAS] CHECK ([vencimiento_pago] >= [fec_crea] AND [fec_entrega_prev] >= [fec_crea]),
    CONSTRAINT [CK_PEDIDO_ESTADO] CHECK ([estado] IN ('PENDIENTE_PAGO','PAGADO_PARCIAL','PAGADO','EN_DISENO','EN_PRODUCCION','LISTO','ENTREGADO','CANCELADO','EXPIRADO')),
    CONSTRAINT [CK_PEDIDO_ENTREGA] CHECK ([modalidad_entrega] IN ('RETIRO','ENVIO')),
    CONSTRAINT [CK_PEDIDO_TOTAL_NNEG] CHECK ([total_pedido] >= 0)
);
GO

CREATE TABLE [dbo].[HISTORIAL_PEDIDO] (
    [id_historial] INT IDENTITY(1,1) NOT NULL,
    [id_pedido] INT NOT NULL,
    [id_empleado] INT NULL,
    [id_etapa_anterior] INT NULL,
    [id_etapa_nueva] INT NULL,
    [fec_hora] DATETIME2(0) NOT NULL, -- nombre completo: fecha_hora
    [estado_anterior] VARCHAR(80) NULL,
    [estado_nuevo] VARCHAR(80) NOT NULL,
    [motivo] VARCHAR(500) NULL,
    [origen_cambio] VARCHAR(80) NOT NULL,
    CONSTRAINT [PK_HISTORIAL_PEDIDO] PRIMARY KEY ([id_historial])
);
GO

CREATE TABLE [dbo].[DETALLE_COTIZACION] (
    [id_cotizacion] INT NOT NULL,
    [numero_linea] INT NOT NULL,
    [id_variante] INT NOT NULL,
    [cantidad] INT NOT NULL,
    [descripcion_personalizacion] VARCHAR(MAX) NULL,
    [precio_ofrecido] DECIMAL(19,2) NOT NULL,
    [descuento_ofrecido] DECIMAL(19,2) NULL,
    CONSTRAINT [PK_DETALLE_COTIZACION] PRIMARY KEY ([id_cotizacion], [numero_linea]),
    CONSTRAINT [CK_DETALLE_COTIZACION_numero_linea_POS] CHECK ([numero_linea] > 0),
    CONSTRAINT [CK_DETALLE_COTIZACION_cantidad_POS] CHECK ([cantidad] > 0),
    CONSTRAINT [CK_DETALLE_COTIZACION_precio_ofrecido_NNEG] CHECK ([precio_ofrecido] >= 0),
    CONSTRAINT [CK_DETALLE_COTIZACION_descuento_ofrecido_NNEG] CHECK ([descuento_ofrecido] >= 0)
);
GO

CREATE TABLE [dbo].[DETALLE_PEDIDO] (
    [id_pedido] INT NOT NULL,
    [numero_linea] INT NOT NULL,
    [id_variante] INT NOT NULL,
    [cantidad] INT NOT NULL,
    [precio_unit] DECIMAL(19,2) NOT NULL, -- nombre completo: precio_unitario_aplicado
    [descuento] DECIMAL(19,2) NULL, -- nombre completo: descuento_aplicado
    [importe] DECIMAL(19,2) NOT NULL, -- nombre completo: importe_pactado
    [costo_est] DECIMAL(19,2) NOT NULL, -- nombre completo: costo_estimado
    [costo_real] DECIMAL(19,2) NULL, -- nombre completo: costo_real_consolidado
    [modo_precio] VARCHAR(20) NOT NULL, -- DETALLE / MAYORISTA / PROMOCION / MAYORISTA_PROMO / COTIZADO
    [id_promocion] INT NULL,
    CONSTRAINT [PK_DETALLE_PEDIDO] PRIMARY KEY ([id_pedido], [numero_linea]),
    CONSTRAINT [CK_DETALLE_PEDIDO_numero_linea_POS] CHECK ([numero_linea] > 0),
    CONSTRAINT [CK_DETALLE_PEDIDO_cantidad_POS] CHECK ([cantidad] > 0),
    CONSTRAINT [CK_DETALLE_PEDIDO_precio_unitario_aplicado_NNEG] CHECK ([precio_unit] >= 0),
    CONSTRAINT [CK_DETALLE_PEDIDO_descuento_aplicado_NNEG] CHECK ([descuento] >= 0),
    CONSTRAINT [CK_DETALLE_PEDIDO_importe_pactado_NNEG] CHECK ([importe] >= 0),
    CONSTRAINT [CK_DETALLE_PEDIDO_costo_estimado_NNEG] CHECK ([costo_est] >= 0),
    CONSTRAINT [CK_DETALLE_PEDIDO_costo_real_consolidado_NNEG] CHECK ([costo_real] >= 0),
    CONSTRAINT [CK_DP_MODO] CHECK ([modo_precio] IN ('DETALLE','MAYORISTA','PROMOCION','MAYORISTA_PROMO','COTIZADO'))
);
GO

CREATE TABLE [dbo].[ETAPA_PROCESO] (
    [id_etapa] INT IDENTITY(1,1) NOT NULL,
    [nombre] VARCHAR(180) NOT NULL,
    [descripcion] VARCHAR(500) NULL,
    [orden_referencia] INT NOT NULL,
    [estado] VARCHAR(80) NOT NULL,
    CONSTRAINT [PK_ETAPA_PROCESO] PRIMARY KEY ([id_etapa]),
    CONSTRAINT [CK_ETAPA_PROCESO_orden_referencia_NNEG] CHECK ([orden_referencia] >= 0),
    CONSTRAINT [CK_ETAPA_ESTADO] CHECK ([estado] IN ('ACTIVA','INACTIVA'))
);
GO

CREATE TABLE [dbo].[ASIGNACION_ETAPA] (
    [id_asignacion] INT IDENTITY(1,1) NOT NULL,
    [id_pedido] INT NOT NULL,
    [id_etapa] INT NOT NULL,
    [id_empleado] INT NOT NULL,
    [fec_inicio] DATETIME2(0) NOT NULL, -- nombre completo: fecha_inicio
    [fec_fin] DATETIME2(0) NULL, -- nombre completo: fecha_fin
    [origen_asignacion] VARCHAR(80) NOT NULL,
    [estado] VARCHAR(80) NOT NULL,
    [motivo_reasignacion] VARCHAR(500) NULL,
    CONSTRAINT [PK_ASIGNACION_ETAPA] PRIMARY KEY ([id_asignacion]),
    CONSTRAINT [CK_ASIGNACION_ETAPA_REGLA_1] CHECK ([fec_fin] IS NULL OR [fec_fin] >= [fec_inicio]),
    CONSTRAINT [CK_ASIG_ETAPA_ESTADO] CHECK ([estado] IN ('ACTIVA','FINALIZADA'))
);
GO

CREATE TABLE [dbo].[VERSION_DISENO] (
    [id_pedido] INT NOT NULL,
    [numero_linea] INT NOT NULL,
    [numero_version] INT NOT NULL,
    [nombre_archivo] VARCHAR(180) NOT NULL,
    [ruta_archivo] VARCHAR(1000) NOT NULL,
    [fec_crea] DATETIME2(0) NOT NULL, -- nombre completo: fecha_creacion
    [observaciones] VARCHAR(MAX) NULL,
    [es_aprobado] BIT NOT NULL,
    CONSTRAINT [PK_VERSION_DISENO] PRIMARY KEY ([id_pedido], [numero_linea], [numero_version]),
    CONSTRAINT [CK_VERSION_DISENO_numero_linea_POS] CHECK ([numero_linea] > 0),
    CONSTRAINT [CK_VERSION_DISENO_numero_version_POS] CHECK ([numero_version] > 0),
    CONSTRAINT [CK_VERSION_APROB] CHECK ([es_aprobado] IN (0,1))
);
GO

CREATE TABLE [dbo].[SOLICITUD_CAMBIO] (
    [id_solicitud_cambio] INT IDENTITY(1,1) NOT NULL,
    [id_pedido] INT NOT NULL,
    [fec_solicitud] DATETIME2(0) NOT NULL, -- nombre completo: fecha_solicitud
    [descripcion] VARCHAR(500) NOT NULL,
    [motivo] VARCHAR(500) NULL,
    [decision] VARCHAR(80) NULL,
    [costo_adicional_estimado] DECIMAL(19,2) NOT NULL,
    [cargo_adicional_aprobado] DECIMAL(19,2) NULL,
    CONSTRAINT [PK_SOLICITUD_CAMBIO] PRIMARY KEY ([id_solicitud_cambio]),
    CONSTRAINT [CK_SOLICITUD_CAMBIO_costo_adicional_estimado_NNEG] CHECK ([costo_adicional_estimado] >= 0),
    CONSTRAINT [CK_SOL_CAMBIO_CARGO] CHECK ([cargo_adicional_aprobado] IS NULL OR [cargo_adicional_aprobado] >= 0)
);
GO

CREATE TABLE [dbo].[APROBACION_DISENO] (
    [id_aprobacion] INT IDENTITY(1,1) NOT NULL,
    [id_pedido] INT NOT NULL,
    [numero_linea] INT NOT NULL,
    [numero_version] INT NOT NULL,
    [id_emp_reg] INT NULL, -- nombre completo: id_empleado_registro
    [fec_aprobacion] DATETIME2(0) NOT NULL, -- nombre completo: fecha_aprobacion
    [medio_confirmacion] VARCHAR(255) NOT NULL,
    [observacion] VARCHAR(500) NULL,
    [tipo_decision] VARCHAR(80) NOT NULL,
    CONSTRAINT [PK_APROBACION_DISENO] PRIMARY KEY ([id_aprobacion]),
    CONSTRAINT [CK_APROBACION_DISENO_numero_linea_POS] CHECK ([numero_linea] > 0),
    CONSTRAINT [CK_APROBACION_DISENO_numero_version_POS] CHECK ([numero_version] > 0),
    CONSTRAINT [CK_APROB_TIPO] CHECK ([tipo_decision] IN ('APROBADO','RECHAZADO'))
);
GO

CREATE TABLE [dbo].[CATEGORIA] (
    [id_categoria] INT IDENTITY(1,1) NOT NULL,
    [nombre] VARCHAR(180) NOT NULL,
    [descripcion] VARCHAR(500) NULL,
    [estado] VARCHAR(80) NOT NULL,
    CONSTRAINT [PK_CATEGORIA] PRIMARY KEY ([id_categoria])
);
GO

CREATE TABLE [dbo].[PRODUCTO] (
    [id_producto] INT IDENTITY(1,1) NOT NULL,
    [id_categoria] INT NOT NULL,
    [nombre] VARCHAR(180) NOT NULL,
    [descripcion] VARCHAR(500) NULL,
    [informacion_comercial] VARCHAR(MAX) NOT NULL,
    [estado_publicacion] VARCHAR(80) NOT NULL,
    CONSTRAINT [PK_PRODUCTO] PRIMARY KEY ([id_producto])
);
GO

CREATE TABLE [dbo].[VARIANTE_PRODUCTO] (
    [id_variante] INT IDENTITY(1,1) NOT NULL,
    [id_producto] INT NOT NULL,
    [codigo_variante] VARCHAR(64) NOT NULL,
    [caracteristicas] VARCHAR(500) NULL,
    [precio_detalle] DECIMAL(19,2) NOT NULL,
    [requiere_produccion] BIT NOT NULL,
    [estado] VARCHAR(80) NOT NULL,
    CONSTRAINT [PK_VARIANTE_PRODUCTO] PRIMARY KEY ([id_variante]),
    CONSTRAINT [UQ_VARIANTE_PRODUCTO_codigo_variante] UNIQUE ([codigo_variante]),
    CONSTRAINT [CK_VARIANTE_PRODUCTO_precio_detalle_NNEG] CHECK ([precio_detalle] >= 0)
);
GO

CREATE TABLE [dbo].[ARTICULO_INVENTARIABLE] (
    [id_articulo] INT IDENTITY(1,1) NOT NULL,
    [codigo] VARCHAR(64) NOT NULL,
    [nombre] VARCHAR(180) NOT NULL,
    [tipo_articulo] VARCHAR(80) NOT NULL,
    [unidad_medida] VARCHAR(80) NOT NULL,
    [existencia_actual] DECIMAL(18,3) NOT NULL CONSTRAINT [DF_ART_EXISTENCIA] DEFAULT (0), -- saldo fisico: actualizado por backend
    [existencia_minima] DECIMAL(18,3) NOT NULL,
    [costo_referencia] DECIMAL(19,4) NOT NULL,
    [estado] VARCHAR(80) NOT NULL,
    CONSTRAINT [PK_ARTICULO_INVENTARIABLE] PRIMARY KEY ([id_articulo]),
    CONSTRAINT [UQ_ARTICULO_INVENTARIABLE_codigo] UNIQUE ([codigo]),
    CONSTRAINT [CK_ARTICULO_INVENTARIABLE_existencia_minima_NNEG] CHECK ([existencia_minima] >= 0),
    CONSTRAINT [CK_ART_COSTO] CHECK ([costo_referencia] >= 0),
    CONSTRAINT [CK_ART_UNIDAD] CHECK ([unidad_medida] IN ('UNIDAD','ML','L','G','KG','M','M2','HOJA')),
    CONSTRAINT [CK_ART_EXISTENCIA_NNEG] CHECK ([existencia_actual] >= 0)
);
GO

CREATE TABLE [dbo].[ESCALA_PRECIO] (
    [id_variante] INT NOT NULL,
    [numero_rango] INT NOT NULL,
    [cant_min] INT NOT NULL, -- nombre completo: cantidad_minima
    [cant_max] INT NULL, -- nombre completo: cantidad_maxima
    [precio_mayorista] DECIMAL(19,2) NOT NULL, -- nombre completo: precio_unitario_mayorista
    [estado] VARCHAR(80) NOT NULL,
    CONSTRAINT [PK_ESCALA_PRECIO] PRIMARY KEY ([id_variante], [numero_rango]),
    CONSTRAINT [CK_ESCALA_PRECIO_numero_rango_POS] CHECK ([numero_rango] > 0),
    CONSTRAINT [CK_ESCALA_PRECIO_cantidad_minima_POS] CHECK ([cant_min] > 0),
    CONSTRAINT [CK_ESCALA_PRECIO_precio_unitario_mayorista_NNEG] CHECK ([precio_mayorista] >= 0),
    CONSTRAINT [CK_ESCALA_PRECIO_REGLA_1] CHECK ([cant_max] IS NULL OR [cant_max] >= [cant_min]),
    CONSTRAINT [CK_ESC_ESTADO] CHECK ([estado] IN ('ACTIVA','INACTIVA'))
);
GO

CREATE TABLE [dbo].[COMPOSICION_PRODUCTO] (
    [id_variante] INT NOT NULL,
    [id_articulo] INT NOT NULL,
    [cant_estandar] DECIMAL(18,3) NOT NULL, -- nombre completo: cantidad_estandar
    [observaciones] VARCHAR(MAX) NOT NULL,
    CONSTRAINT [PK_COMPOSICION_PRODUCTO] PRIMARY KEY ([id_variante], [id_articulo]),
    CONSTRAINT [CK_COMPOSICION_PRODUCTO_cantidad_estandar_POS] CHECK ([cant_estandar] > 0)
);
GO

CREATE TABLE [dbo].[PROMOCION] (
    [id_promocion] INT IDENTITY(1,1) NOT NULL,
    [nombre] VARCHAR(180) NOT NULL,
    [tipo] VARCHAR(255) NOT NULL,
    [cant_req] INT NOT NULL, -- nombre completo: cantidad_requerida
    [beneficio] VARCHAR(255) NOT NULL,
    [fec_inicio] DATETIME2(0) NOT NULL, -- nombre completo: fecha_inicio
    [fec_fin] DATETIME2(0) NOT NULL, -- nombre completo: fecha_fin
    [condiciones] VARCHAR(MAX) NULL,
    [permite_combinacion_mayorista] BIT NOT NULL,
    [valor_beneficio] DECIMAL(19,2) NOT NULL, -- Valor monetario o porcentaje segun tipo
    [estado] VARCHAR(20) NOT NULL,
    CONSTRAINT [PK_PROMOCION] PRIMARY KEY ([id_promocion]),
    CONSTRAINT [CK_PROMOCION_cantidad_requerida_POS] CHECK ([cant_req] > 0),
    CONSTRAINT [CK_PROMOCION_REGLA_1] CHECK ([fec_fin] >= [fec_inicio]),
    CONSTRAINT [CK_PROMO_TIPO] CHECK ([tipo] IN ('PRECIO_PAQUETE','DESCUENTO_FIJO','PORCENTAJE')),
    CONSTRAINT [CK_PROMO_VALOR] CHECK ([valor_beneficio] >= 0),
    CONSTRAINT [CK_PROMO_ESTADO] CHECK ([estado] IN ('ACTIVA','INACTIVA'))
);
GO

CREATE TABLE [dbo].[PROMOCION_VARIANTE] (
    [id_promocion] INT NOT NULL,
    [id_variante] INT NOT NULL,
    CONSTRAINT [PK_PROMOCION_VARIANTE] PRIMARY KEY ([id_promocion], [id_variante])
);
GO

CREATE TABLE [dbo].[GASTO] (
    [id_gasto] INT IDENTITY(1,1) NOT NULL,
    [id_empleado] INT NOT NULL,
    [concepto] VARCHAR(80) NOT NULL,
    [categoria] VARCHAR(80) NOT NULL,
    [monto] DECIMAL(19,2) NOT NULL,
    [fecha] DATETIME2(0) NOT NULL,
    [metodo_pago] VARCHAR(80) NOT NULL,
    [banco_receptor] VARCHAR(120) NULL,
    [referencia_bancaria] VARCHAR(120) NULL,
    [observaciones] VARCHAR(MAX) NULL,
    CONSTRAINT [PK_GASTO] PRIMARY KEY ([id_gasto]),
    CONSTRAINT [CK_GASTO_monto_NNEG] CHECK ([monto] >= 0),
    CONSTRAINT [CK_GASTO_METODO] CHECK ([metodo_pago] IN ('EFECTIVO','TRANSFERENCIA','TARJETA','OTRO')),
    CONSTRAINT [CK_GASTO_CAT] CHECK ([categoria] IN ('FIJO','VARIABLE','OPERATIVO','PUBLICIDAD','TRANSPORTE','SALARIO','SERVICIO','IMPUESTO','OTRO'))
);
GO

CREATE TABLE [dbo].[REGISTRO_AUDITORIA] (
    [id_auditoria] INT IDENTITY(1,1) NOT NULL,
    [id_empleado] INT NULL,
    [fec_hora] DATETIME2(0) NOT NULL, -- nombre completo: fecha_hora
    [accion] VARCHAR(255) NOT NULL,
    [tipo_objeto_afectado] VARCHAR(80) NOT NULL,
    [referencia_objeto] VARCHAR(120) NOT NULL,
    [valor_anterior] VARCHAR(MAX) NULL,
    [valor_nuevo] VARCHAR(MAX) NULL,
    [motivo] VARCHAR(500) NOT NULL,
    [origen_accion] VARCHAR(80) NOT NULL,
    CONSTRAINT [PK_REGISTRO_AUDITORIA] PRIMARY KEY ([id_auditoria])
);
GO

CREATE TABLE [dbo].[AGENCIA_ENVIO] (
    [id_agencia] INT IDENTITY(1,1) NOT NULL,
    [nombre] VARCHAR(180) NOT NULL,
    [tipo_agencia] VARCHAR(80) NOT NULL,
    [telefono] VARCHAR(30) NULL,
    [estado] VARCHAR(80) NOT NULL,
    CONSTRAINT [PK_AGENCIA_ENVIO] PRIMARY KEY ([id_agencia])
);
GO

CREATE TABLE [dbo].[ENVIO] (
    [id_envio] INT IDENTITY(1,1) NOT NULL,
    [id_pedido] INT NOT NULL,
    [id_agencia] INT NULL,
    [direccion_entrega] VARCHAR(500) NOT NULL,
    [nombre_receptor] VARCHAR(120) NOT NULL,
    [telefono_receptor] VARCHAR(30) NULL,
    [tarifa_acordada] DECIMAL(19,2) NOT NULL,
    [fecha_programada] DATETIME2(0) NULL,
    [fec_entrega_real] DATETIME2(0) NULL, -- nombre completo: fecha_entrega_real
    [estado] VARCHAR(80) NOT NULL,
    CONSTRAINT [PK_ENVIO] PRIMARY KEY ([id_envio]),
    CONSTRAINT [UQ_ENVIO_id_pedido] UNIQUE ([id_pedido]),
    CONSTRAINT [CK_ENVIO_tarifa_acordada_NNEG] CHECK ([tarifa_acordada] >= 0)
);
GO

CREATE TABLE [dbo].[HITO_PAGO] (
    [id_pedido] INT NOT NULL,
    [numero_hito] INT NOT NULL,
    [tipo_hito] VARCHAR(80) NOT NULL,
    [monto_exigido] DECIMAL(19,2) NOT NULL,
    [fec_venc] DATETIME2(0) NOT NULL, -- nombre completo: fecha_vencimiento
    [estado] VARCHAR(80) NOT NULL,
    CONSTRAINT [PK_HITO_PAGO] PRIMARY KEY ([id_pedido], [numero_hito]),
    CONSTRAINT [CK_HITO_PAGO_numero_hito_POS] CHECK ([numero_hito] > 0),
    CONSTRAINT [CK_HITO_PAGO_monto_exigido_NNEG] CHECK ([monto_exigido] >= 0),
    CONSTRAINT [CK_HITO_TIPO] CHECK ([tipo_hito] IN ('ANTICIPO','SALDO','EXTRA')),
    CONSTRAINT [CK_HITO_ESTADO] CHECK ([estado] IN ('PENDIENTE','PAGADO','VENCIDO'))
);
GO

CREATE TABLE [dbo].[TRANSACCION] (
    [id_transaccion] INT IDENTITY(1,1) NOT NULL,
    [id_pedido] INT NOT NULL,
    [numero_hito] INT NULL,
    [id_emp_verif] INT NULL, -- nombre completo: id_empleado_verificador
    [id_tx_comp] INT NULL, -- nombre completo: id_transaccion_compensada
    [id_reembolso] INT NULL,
    [fec_hora] DATETIME2(0) NOT NULL, -- nombre completo: fecha_hora
    [tipo_transaccion] VARCHAR(80) NOT NULL,
    [monto] DECIMAL(19,2) NOT NULL, -- nombre completo: monto_con_signo
    [metodo_pago] VARCHAR(80) NOT NULL,
    [banco_receptor] VARCHAR(120) NULL,
    [referencia_bancaria] VARCHAR(120) NULL,
    [estado_verificacion] VARCHAR(80) NOT NULL,
    [clave_idem] UNIQUEIDENTIFIER NOT NULL, -- Clave de idempotencia de la solicitud

    CONSTRAINT [PK_TRANSACCION] PRIMARY KEY ([id_transaccion]),
    CONSTRAINT [CK_TRANSACCION_numero_hito_NNEG] CHECK ([numero_hito] IS NULL OR [numero_hito] > 0),
    CONSTRAINT [CK_TRANSACCION_REGLA_1] CHECK ([monto] <> 0),
    CONSTRAINT [CK_TRANSACCION_REGLA_2] CHECK ([id_tx_comp] IS NULL OR [id_tx_comp] <> [id_transaccion]),
    CONSTRAINT [UQ_TX_IDEM] UNIQUE ([clave_idem]),
    CONSTRAINT [UQ_TX_PEDIDO] UNIQUE ([id_transaccion],[id_pedido]),
    CONSTRAINT [CK_TX_ESTADO] CHECK ([estado_verificacion] IN ('PENDIENTE','VERIFICADO','RECHAZADO')),
    CONSTRAINT [CK_TX_METODO] CHECK ([metodo_pago] IN ('EFECTIVO','TRANSFERENCIA','TARJETA','OTRO')),
    CONSTRAINT [CK_TX_TIPO] CHECK ([tipo_transaccion] IN ('PAGO','REEMBOLSO','COMPENSACION'))
);
GO

CREATE TABLE [dbo].[CANCELACION] (
    [id_cancelacion] INT IDENTITY(1,1) NOT NULL,
    [id_pedido] INT NOT NULL,
    [id_emp_autoriza] INT NULL, -- nombre completo: id_empleado_autoriza
    [fec_hora] DATETIME2(0) NOT NULL, -- nombre completo: fecha_hora
    [motivo] VARCHAR(500) NOT NULL,
    [etapa_cancelacion] VARCHAR(255) NOT NULL,
    [monto_retenido] DECIMAL(19,2) NOT NULL,
    [resultado] VARCHAR(80) NOT NULL,
    [fecha_confirmacion_autenticacion] DATETIME2(0) NULL,
    CONSTRAINT [PK_CANCELACION] PRIMARY KEY ([id_cancelacion]),
    CONSTRAINT [UQ_CANCELACION_id_pedido] UNIQUE ([id_pedido]),
    CONSTRAINT [CK_CANCELACION_monto_retenido_NNEG] CHECK ([monto_retenido] >= 0),
    CONSTRAINT [CK_CANCELACION_RESULTADO] CHECK ([resultado] IN ('PENDIENTE','APROBADA','RECHAZADA'))
);
GO

CREATE TABLE [dbo].[REEMBOLSO] (
    [id_reembolso] INT IDENTITY(1,1) NOT NULL,
    [id_cancelacion] INT NOT NULL,
    [fec_solicitud] DATETIME2(0) NOT NULL, -- nombre completo: fecha_solicitud
    [monto_solicitado] DECIMAL(19,2) NOT NULL,
    [monto_aprobado] DECIMAL(19,2) NOT NULL,
    [motivo] VARCHAR(500) NULL,
    [estado] VARCHAR(80) NOT NULL,
    [fecha_resolucion] DATETIME2(0) NULL,
    CONSTRAINT [PK_REEMBOLSO] PRIMARY KEY ([id_reembolso]),
    CONSTRAINT [CK_REEMBOLSO_monto_solicitado_NNEG] CHECK ([monto_solicitado] >= 0),
    CONSTRAINT [CK_REEMBOLSO_monto_aprobado_NNEG] CHECK ([monto_aprobado] >= 0),
    CONSTRAINT [CK_REEMBOLSO_REGLA_1] CHECK ([monto_aprobado] <= [monto_solicitado]),
    CONSTRAINT [CK_REEMB_ESTADO] CHECK ([estado] IN ('PENDIENTE','APROBADO','RECHAZADO','PAGADO'))
);
GO

CREATE TABLE [dbo].[PROVEEDOR] (
    [id_proveedor] INT IDENTITY(1,1) NOT NULL,
    [nombre] VARCHAR(180) NOT NULL,
    [telefono] VARCHAR(30) NULL,
    [correo] VARCHAR(254) NULL, -- nombre completo: correo_electronico
    [direccion] VARCHAR(500) NULL,
    [estado] VARCHAR(80) NOT NULL,
    CONSTRAINT [PK_PROVEEDOR] PRIMARY KEY ([id_proveedor])
);
GO

CREATE TABLE [dbo].[COMPRA] (
    [id_compra] INT IDENTITY(1,1) NOT NULL,
    [id_proveedor] INT NOT NULL,
    [fec_compra] DATETIME2(0) NOT NULL, -- nombre completo: fecha_compra
    [numero_documento] VARCHAR(120) NULL,
    [estado] VARCHAR(80) NOT NULL,
    [total_compra] DECIMAL(19,2) NOT NULL,
    CONSTRAINT [PK_COMPRA] PRIMARY KEY ([id_compra]),
    CONSTRAINT [CK_COMPRA_total_compra_NNEG] CHECK ([total_compra] >= 0),
    CONSTRAINT [CK_COMPRA_ESTADO] CHECK ([estado] IN ('BORRADOR','CONFIRMADA','ANULADA'))
);
GO

CREATE TABLE [dbo].[DETALLE_COMPRA] (
    [id_compra] INT NOT NULL,
    [numero_linea] INT NOT NULL,
    [id_articulo] INT NOT NULL,
    [cant_comprada] DECIMAL(18,3) NOT NULL, -- nombre completo: cantidad_comprada
    [costo_unit_compra] DECIMAL(19,4) NOT NULL, -- nombre completo: costo_unitario_compra
    [importe] DECIMAL(19,2) NOT NULL, -- nombre completo: importe_pactado
    CONSTRAINT [PK_DETALLE_COMPRA] PRIMARY KEY ([id_compra], [numero_linea]),
    CONSTRAINT [CK_DETALLE_COMPRA_numero_linea_POS] CHECK ([numero_linea] > 0),
    CONSTRAINT [CK_DETALLE_COMPRA_cantidad_comprada_POS] CHECK ([cant_comprada] > 0),
    CONSTRAINT [CK_DETALLE_COMPRA_importe_NNEG] CHECK ([importe] >= 0),
    CONSTRAINT [CK_DC_COSTO] CHECK ([costo_unit_compra] >= 0),
    CONSTRAINT [UQ_DC_COMP_LINEA_ART] UNIQUE ([id_compra], [numero_linea], [id_articulo])
);
GO

CREATE TABLE [dbo].[MOVIMIENTO_INVENTARIO] (
    [id_movimiento] INT IDENTITY(1,1) NOT NULL,
    [id_articulo] INT NOT NULL,
    [id_pedido] INT NULL,
    [id_reserva] INT NULL,
    [id_compra] INT NULL,
    [numero_linea_compra] INT NULL,
    [id_empleado] INT NULL,
    [fec_hora] DATETIME2(0) NOT NULL, -- nombre completo: fecha_hora
    [tipo_movimiento] VARCHAR(80) NOT NULL,
    [cantidad] DECIMAL(18,3) NOT NULL,
    [costo_unit] DECIMAL(19,4) NOT NULL, -- nombre completo: costo_unitario_aplicado
    [motivo] VARCHAR(500) NOT NULL,
    [observaciones] VARCHAR(MAX) NULL,
    CONSTRAINT [PK_MOVIMIENTO_INVENTARIO] PRIMARY KEY ([id_movimiento]),
    CONSTRAINT [CK_MOVIMIENTO_INVENTARIO_numero_linea_compra_POS] CHECK ([numero_linea_compra] > 0),
    CONSTRAINT [CK_MOVIMIENTO_INVENTARIO_cantidad_POS] CHECK ([cantidad] > 0),
    CONSTRAINT [CK_MOVIMIENTO_INVENTARIO_REGLA_1] CHECK (([id_compra] IS NULL AND [numero_linea_compra] IS NULL) OR ([id_compra] IS NOT NULL AND [numero_linea_compra] IS NOT NULL)),
    CONSTRAINT [CK_MI_COSTO] CHECK ([costo_unit] >= 0),
    CONSTRAINT [CK_MI_TIPO] CHECK ([tipo_movimiento] IN ('ENTRADA_COMPRA','ENTRADA_AJUSTE','ENTRADA_DEVOLUCION','SALIDA_PRODUCCION','SALIDA_PERDIDA','SALIDA_AJUSTE')),
    CONSTRAINT [UQ_MI_ID_ART] UNIQUE ([id_movimiento], [id_articulo]),
    CONSTRAINT [CK_MI_RES_REQ_PED] CHECK ([id_reserva] IS NULL OR [id_pedido] IS NOT NULL)
);
GO

CREATE TABLE [dbo].[RESERVA_INVENTARIO] (
    [id_reserva] INT IDENTITY(1,1) NOT NULL,
    [id_pedido] INT NOT NULL,
    [id_articulo] INT NOT NULL,
    [cant_reservada] DECIMAL(18,3) NOT NULL, -- nombre completo: cantidad_reservada
    [cant_pendiente] DECIMAL(18,3) NOT NULL, -- nombre completo: cantidad_pendiente
    [fec_reserva] DATETIME2(0) NOT NULL, -- nombre completo: fecha_reserva
    [fec_liberacion] DATETIME2(0) NULL, -- nombre completo: fecha_liberacion
    [estado] VARCHAR(80) NOT NULL,
    CONSTRAINT [PK_RESERVA_INVENTARIO] PRIMARY KEY ([id_reserva]),
    CONSTRAINT [CK_RESERVA_INVENTARIO_cantidad_reservada_POS] CHECK ([cant_reservada] > 0),
    CONSTRAINT [CK_RESERVA_INVENTARIO_cantidad_pendiente_NNEG] CHECK ([cant_pendiente] >= 0),
    CONSTRAINT [CK_RESERVA_INVENTARIO_REGLA_1] CHECK ([cant_pendiente] <= [cant_reservada]),
    CONSTRAINT [CK_RESERVA_ESTADO] CHECK ([estado] IN ('ACTIVA','AGOTADA','LIBERADA')),
    CONSTRAINT [UQ_RES_ID_PED_ART] UNIQUE ([id_reserva], [id_pedido], [id_articulo])
);
GO

CREATE TABLE [dbo].[PERDIDA] (
    [id_perdida] INT IDENTITY(1,1) NOT NULL,
    [id_pedido] INT NULL,
    [id_emp_reporta] INT NOT NULL, -- nombre completo: id_empleado_reporta
    [id_etapa] INT NULL,
    [fec_hora] DATETIME2(0) NOT NULL, -- nombre completo: fecha_hora
    [tipo_incidente] VARCHAR(80) NOT NULL,
    [motivo] VARCHAR(500) NOT NULL,
    [descripcion] VARCHAR(500) NULL,
    [estado_registro] VARCHAR(80) NOT NULL,
    CONSTRAINT [PK_PERDIDA] PRIMARY KEY ([id_perdida])
);
GO

CREATE TABLE [dbo].[DETALLE_PERDIDA] (
    [id_perdida] INT NOT NULL,
    [numero_linea] INT NOT NULL,
    [id_articulo] INT NOT NULL,
    [id_movimiento] INT NOT NULL,
    [cant_perdida] DECIMAL(18,3) NOT NULL, -- nombre completo: cantidad_perdida
    [costo_unit_hist] DECIMAL(19,4) NOT NULL, -- nombre completo: costo_unitario_historico
    [descripcion_dano] VARCHAR(500) NULL,
    CONSTRAINT [PK_DETALLE_PERDIDA] PRIMARY KEY ([id_perdida], [numero_linea]),
    CONSTRAINT [UQ_DETALLE_PERDIDA_id_movimiento] UNIQUE ([id_movimiento]),
    CONSTRAINT [CK_DETALLE_PERDIDA_numero_linea_POS] CHECK ([numero_linea] > 0),
    CONSTRAINT [CK_DETALLE_PERDIDA_cantidad_perdida_POS] CHECK ([cant_perdida] > 0),
    CONSTRAINT [CK_DP_COSTO_HIST] CHECK ([costo_unit_hist] >= 0)
);
GO


-- 2. CLAVES FORANEAS

ALTER TABLE [dbo].[CLIENTE] WITH CHECK
    ADD CONSTRAINT [FK_01_CLIENTE_PERSONA]
    FOREIGN KEY ([id_persona]) REFERENCES [dbo].[PERSONA] ([id_persona])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[EMPLEADO] WITH CHECK
    ADD CONSTRAINT [FK_02_EMPLEADO_PERSONA]
    FOREIGN KEY ([id_persona]) REFERENCES [dbo].[PERSONA] ([id_persona])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[CUENTA_ACCESO] WITH CHECK
    ADD CONSTRAINT [FK_03_CUENTA_ACCESO_PERSONA]
    FOREIGN KEY ([id_persona]) REFERENCES [dbo].[PERSONA] ([id_persona])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[ASIGNACION_ROL] WITH CHECK
    ADD CONSTRAINT [FK_04_ASIGNACION_ROL_EMPLEADO]
    FOREIGN KEY ([id_empleado]) REFERENCES [dbo].[EMPLEADO] ([id_persona])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[ASIGNACION_ROL] WITH CHECK
    ADD CONSTRAINT [FK_05_ASIGNACION_ROL_ROL]
    FOREIGN KEY ([id_rol]) REFERENCES [dbo].[ROL] ([id_rol])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[ROL_PERMISO] WITH CHECK
    ADD CONSTRAINT [FK_06_ROL_PERMISO_ROL]
    FOREIGN KEY ([id_rol]) REFERENCES [dbo].[ROL] ([id_rol])
    ON DELETE CASCADE;
GO

ALTER TABLE [dbo].[ROL_PERMISO] WITH CHECK
    ADD CONSTRAINT [FK_07_ROL_PERMISO_PERMISO]
    FOREIGN KEY ([id_permiso]) REFERENCES [dbo].[PERMISO] ([id_permiso])
    ON DELETE CASCADE;
GO

ALTER TABLE [dbo].[PRODUCTO] WITH CHECK
    ADD CONSTRAINT [FK_08_PRODUCTO_CATEGORIA]
    FOREIGN KEY ([id_categoria]) REFERENCES [dbo].[CATEGORIA] ([id_categoria])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[VARIANTE_PRODUCTO] WITH CHECK
    ADD CONSTRAINT [FK_09_VARIANTE_PRODUCTO_PRODUCTO]
    FOREIGN KEY ([id_producto]) REFERENCES [dbo].[PRODUCTO] ([id_producto])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[ESCALA_PRECIO] WITH CHECK
    ADD CONSTRAINT [FK_10_ESCALA_PRECIO_VARIANTE_PRODUCTO]
    FOREIGN KEY ([id_variante]) REFERENCES [dbo].[VARIANTE_PRODUCTO] ([id_variante])
    ON DELETE CASCADE;
GO

ALTER TABLE [dbo].[PROMOCION_VARIANTE] WITH CHECK
    ADD CONSTRAINT [FK_11_PROMOCION_VARIANTE_PROMOCION]
    FOREIGN KEY ([id_promocion]) REFERENCES [dbo].[PROMOCION] ([id_promocion])
    ON DELETE CASCADE;
GO

ALTER TABLE [dbo].[PROMOCION_VARIANTE] WITH CHECK
    ADD CONSTRAINT [FK_12_PROMOCION_VARIANTE_VARIANTE_PRODUCTO]
    FOREIGN KEY ([id_variante]) REFERENCES [dbo].[VARIANTE_PRODUCTO] ([id_variante])
    ON DELETE CASCADE;
GO

ALTER TABLE [dbo].[COMPOSICION_PRODUCTO] WITH CHECK
    ADD CONSTRAINT [FK_13_COMPOSICION_PRODUCTO_VARIANTE_PRODUCTO]
    FOREIGN KEY ([id_variante]) REFERENCES [dbo].[VARIANTE_PRODUCTO] ([id_variante])
    ON DELETE CASCADE;
GO

ALTER TABLE [dbo].[COMPOSICION_PRODUCTO] WITH CHECK
    ADD CONSTRAINT [FK_14_COMPOSICION_PRODUCTO_ARTICULO_INVENTARIABLE]
    FOREIGN KEY ([id_articulo]) REFERENCES [dbo].[ARTICULO_INVENTARIABLE] ([id_articulo])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[PEDIDO] WITH CHECK
    ADD CONSTRAINT [FK_15_PEDIDO_CLIENTE]
    FOREIGN KEY ([id_cliente]) REFERENCES [dbo].[CLIENTE] ([id_persona])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[PEDIDO] WITH CHECK
    ADD CONSTRAINT [FK_16_PEDIDO_EMPLEADO]
    FOREIGN KEY ([id_emp_reg]) REFERENCES [dbo].[EMPLEADO] ([id_persona])
    ON DELETE SET NULL;
GO

ALTER TABLE [dbo].[PEDIDO] WITH CHECK
    ADD CONSTRAINT [FK_17_PEDIDO_ETAPA_PROCESO]
    FOREIGN KEY ([id_etapa_actual]) REFERENCES [dbo].[ETAPA_PROCESO] ([id_etapa])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[PEDIDO] WITH CHECK
    ADD CONSTRAINT [FK_18_PEDIDO_COTIZACION]
    FOREIGN KEY ([id_cotizacion], [id_cliente]) REFERENCES [dbo].[COTIZACION] ([id_cotizacion], [id_cliente])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[DETALLE_PEDIDO] WITH CHECK
    ADD CONSTRAINT [FK_19_DETALLE_PEDIDO_PEDIDO]
    FOREIGN KEY ([id_pedido]) REFERENCES [dbo].[PEDIDO] ([id_pedido])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[DETALLE_PEDIDO] WITH CHECK
    ADD CONSTRAINT [FK_20_DETALLE_PEDIDO_VARIANTE_PRODUCTO]
    FOREIGN KEY ([id_variante]) REFERENCES [dbo].[VARIANTE_PRODUCTO] ([id_variante])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[VERSION_DISENO] WITH CHECK
    ADD CONSTRAINT [FK_21_VERSION_DISENO_DETALLE_PEDIDO]
    FOREIGN KEY ([id_pedido], [numero_linea]) REFERENCES [dbo].[DETALLE_PEDIDO] ([id_pedido], [numero_linea])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[APROBACION_DISENO] WITH CHECK
    ADD CONSTRAINT [FK_22_APROBACION_DISENO_VERSION_DISENO]
    FOREIGN KEY ([id_pedido], [numero_linea], [numero_version]) REFERENCES [dbo].[VERSION_DISENO] ([id_pedido], [numero_linea], [numero_version])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[APROBACION_DISENO] WITH CHECK
    ADD CONSTRAINT [FK_23_APROBACION_DISENO_EMPLEADO]
    FOREIGN KEY ([id_emp_reg]) REFERENCES [dbo].[EMPLEADO] ([id_persona])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[HISTORIAL_PEDIDO] WITH CHECK
    ADD CONSTRAINT [FK_24_HISTORIAL_PEDIDO_PEDIDO]
    FOREIGN KEY ([id_pedido]) REFERENCES [dbo].[PEDIDO] ([id_pedido])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[HISTORIAL_PEDIDO] WITH CHECK
    ADD CONSTRAINT [FK_25_HISTORIAL_PEDIDO_EMPLEADO]
    FOREIGN KEY ([id_empleado]) REFERENCES [dbo].[EMPLEADO] ([id_persona])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[HISTORIAL_PEDIDO] WITH CHECK
    ADD CONSTRAINT [FK_26_HISTORIAL_PEDIDO_ETAPA_PROCESO]
    FOREIGN KEY ([id_etapa_anterior]) REFERENCES [dbo].[ETAPA_PROCESO] ([id_etapa])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[HISTORIAL_PEDIDO] WITH CHECK
    ADD CONSTRAINT [FK_27_HISTORIAL_PEDIDO_ETAPA_PROCESO]
    FOREIGN KEY ([id_etapa_nueva]) REFERENCES [dbo].[ETAPA_PROCESO] ([id_etapa])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[ASIGNACION_ETAPA] WITH CHECK
    ADD CONSTRAINT [FK_28_ASIGNACION_ETAPA_PEDIDO]
    FOREIGN KEY ([id_pedido]) REFERENCES [dbo].[PEDIDO] ([id_pedido])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[ASIGNACION_ETAPA] WITH CHECK
    ADD CONSTRAINT [FK_29_ASIGNACION_ETAPA_ETAPA_PROCESO]
    FOREIGN KEY ([id_etapa]) REFERENCES [dbo].[ETAPA_PROCESO] ([id_etapa])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[ASIGNACION_ETAPA] WITH CHECK
    ADD CONSTRAINT [FK_30_ASIGNACION_ETAPA_EMPLEADO]
    FOREIGN KEY ([id_empleado]) REFERENCES [dbo].[EMPLEADO] ([id_persona])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[SOLICITUD_CAMBIO] WITH CHECK
    ADD CONSTRAINT [FK_31_SOLICITUD_CAMBIO_PEDIDO]
    FOREIGN KEY ([id_pedido]) REFERENCES [dbo].[PEDIDO] ([id_pedido])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[COTIZACION] WITH CHECK
    ADD CONSTRAINT [FK_32_COTIZACION_CLIENTE]
    FOREIGN KEY ([id_cliente]) REFERENCES [dbo].[CLIENTE] ([id_persona])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[DETALLE_COTIZACION] WITH CHECK
    ADD CONSTRAINT [FK_33_DETALLE_COTIZACION_COTIZACION]
    FOREIGN KEY ([id_cotizacion]) REFERENCES [dbo].[COTIZACION] ([id_cotizacion])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[DETALLE_COTIZACION] WITH CHECK
    ADD CONSTRAINT [FK_34_DETALLE_COTIZACION_VARIANTE_PRODUCTO]
    FOREIGN KEY ([id_variante]) REFERENCES [dbo].[VARIANTE_PRODUCTO] ([id_variante])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[HITO_PAGO] WITH CHECK
    ADD CONSTRAINT [FK_35_HITO_PAGO_PEDIDO]
    FOREIGN KEY ([id_pedido]) REFERENCES [dbo].[PEDIDO] ([id_pedido])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[TRANSACCION] WITH CHECK
    ADD CONSTRAINT [FK_36_TRANSACCION_PEDIDO]
    FOREIGN KEY ([id_pedido]) REFERENCES [dbo].[PEDIDO] ([id_pedido])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[TRANSACCION] WITH CHECK
    ADD CONSTRAINT [FK_37_TRANSACCION_HITO_PAGO]
    FOREIGN KEY ([id_pedido], [numero_hito]) REFERENCES [dbo].[HITO_PAGO] ([id_pedido], [numero_hito])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[TRANSACCION] WITH CHECK
    ADD CONSTRAINT [FK_38_TRANSACCION_EMPLEADO]
    FOREIGN KEY ([id_emp_verif]) REFERENCES [dbo].[EMPLEADO] ([id_persona])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[TRANSACCION] WITH CHECK
    ADD CONSTRAINT [FK_39_TRANSACCION_TRANSACCION]
    FOREIGN KEY ([id_tx_comp], [id_pedido]) REFERENCES [dbo].[TRANSACCION] ([id_transaccion], [id_pedido])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[TRANSACCION] WITH CHECK
    ADD CONSTRAINT [FK_40_TRANSACCION_REEMBOLSO]
    FOREIGN KEY ([id_reembolso]) REFERENCES [dbo].[REEMBOLSO] ([id_reembolso])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[CANCELACION] WITH CHECK
    ADD CONSTRAINT [FK_41_CANCELACION_PEDIDO]
    FOREIGN KEY ([id_pedido]) REFERENCES [dbo].[PEDIDO] ([id_pedido])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[CANCELACION] WITH CHECK
    ADD CONSTRAINT [FK_42_CANCELACION_EMPLEADO]
    FOREIGN KEY ([id_emp_autoriza]) REFERENCES [dbo].[EMPLEADO] ([id_persona])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[REEMBOLSO] WITH CHECK
    ADD CONSTRAINT [FK_43_REEMBOLSO_CANCELACION]
    FOREIGN KEY ([id_cancelacion]) REFERENCES [dbo].[CANCELACION] ([id_cancelacion])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[RESERVA_INVENTARIO] WITH CHECK
    ADD CONSTRAINT [FK_44_RESERVA_INVENTARIO_PEDIDO]
    FOREIGN KEY ([id_pedido]) REFERENCES [dbo].[PEDIDO] ([id_pedido])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[RESERVA_INVENTARIO] WITH CHECK
    ADD CONSTRAINT [FK_45_RESERVA_INVENTARIO_ARTICULO_INVENTARIABLE]
    FOREIGN KEY ([id_articulo]) REFERENCES [dbo].[ARTICULO_INVENTARIABLE] ([id_articulo])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[MOVIMIENTO_INVENTARIO] WITH CHECK
    ADD CONSTRAINT [FK_46_MOVIMIENTO_INVENTARIO_ARTICULO_INVENTARIABLE]
    FOREIGN KEY ([id_articulo]) REFERENCES [dbo].[ARTICULO_INVENTARIABLE] ([id_articulo])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[MOVIMIENTO_INVENTARIO] WITH CHECK
    ADD CONSTRAINT [FK_47_MOVIMIENTO_INVENTARIO_PEDIDO]
    FOREIGN KEY ([id_pedido]) REFERENCES [dbo].[PEDIDO] ([id_pedido])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[MOVIMIENTO_INVENTARIO] WITH CHECK
    ADD CONSTRAINT [FK_48_MOVIMIENTO_INVENTARIO_RESERVA_INVENTARIO]
    FOREIGN KEY ([id_reserva], [id_pedido], [id_articulo]) REFERENCES [dbo].[RESERVA_INVENTARIO] ([id_reserva], [id_pedido], [id_articulo])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[MOVIMIENTO_INVENTARIO] WITH CHECK
    ADD CONSTRAINT [FK_49_MOVIMIENTO_INVENTARIO_DETALLE_COMPRA]
    FOREIGN KEY ([id_compra], [numero_linea_compra], [id_articulo]) REFERENCES [dbo].[DETALLE_COMPRA] ([id_compra], [numero_linea], [id_articulo])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[MOVIMIENTO_INVENTARIO] WITH CHECK
    ADD CONSTRAINT [FK_50_MOVIMIENTO_INVENTARIO_EMPLEADO]
    FOREIGN KEY ([id_empleado]) REFERENCES [dbo].[EMPLEADO] ([id_persona])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[PERDIDA] WITH CHECK
    ADD CONSTRAINT [FK_51_PERDIDA_PEDIDO]
    FOREIGN KEY ([id_pedido]) REFERENCES [dbo].[PEDIDO] ([id_pedido])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[PERDIDA] WITH CHECK
    ADD CONSTRAINT [FK_52_PERDIDA_EMPLEADO]
    FOREIGN KEY ([id_emp_reporta]) REFERENCES [dbo].[EMPLEADO] ([id_persona])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[PERDIDA] WITH CHECK
    ADD CONSTRAINT [FK_53_PERDIDA_ETAPA_PROCESO]
    FOREIGN KEY ([id_etapa]) REFERENCES [dbo].[ETAPA_PROCESO] ([id_etapa])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[DETALLE_PERDIDA] WITH CHECK
    ADD CONSTRAINT [FK_54_DETALLE_PERDIDA_PERDIDA]
    FOREIGN KEY ([id_perdida]) REFERENCES [dbo].[PERDIDA] ([id_perdida])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[DETALLE_PERDIDA] WITH CHECK
    ADD CONSTRAINT [FK_55_DETALLE_PERDIDA_ARTICULO_INVENTARIABLE]
    FOREIGN KEY ([id_articulo]) REFERENCES [dbo].[ARTICULO_INVENTARIABLE] ([id_articulo])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[DETALLE_PERDIDA] WITH CHECK
    ADD CONSTRAINT [FK_56_DETALLE_PERDIDA_MOVIMIENTO_INVENTARIO]
    FOREIGN KEY ([id_movimiento], [id_articulo]) REFERENCES [dbo].[MOVIMIENTO_INVENTARIO] ([id_movimiento], [id_articulo])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[COMPRA] WITH CHECK
    ADD CONSTRAINT [FK_57_COMPRA_PROVEEDOR]
    FOREIGN KEY ([id_proveedor]) REFERENCES [dbo].[PROVEEDOR] ([id_proveedor])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[DETALLE_COMPRA] WITH CHECK
    ADD CONSTRAINT [FK_58_DETALLE_COMPRA_COMPRA]
    FOREIGN KEY ([id_compra]) REFERENCES [dbo].[COMPRA] ([id_compra])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[DETALLE_COMPRA] WITH CHECK
    ADD CONSTRAINT [FK_59_DETALLE_COMPRA_ARTICULO_INVENTARIABLE]
    FOREIGN KEY ([id_articulo]) REFERENCES [dbo].[ARTICULO_INVENTARIABLE] ([id_articulo])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[GASTO] WITH CHECK
    ADD CONSTRAINT [FK_60_GASTO_EMPLEADO]
    FOREIGN KEY ([id_empleado]) REFERENCES [dbo].[EMPLEADO] ([id_persona])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[ENVIO] WITH CHECK
    ADD CONSTRAINT [FK_61_ENVIO_PEDIDO]
    FOREIGN KEY ([id_pedido]) REFERENCES [dbo].[PEDIDO] ([id_pedido])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[ENVIO] WITH CHECK
    ADD CONSTRAINT [FK_62_ENVIO_AGENCIA_ENVIO]
    FOREIGN KEY ([id_agencia]) REFERENCES [dbo].[AGENCIA_ENVIO] ([id_agencia])
    ON DELETE SET NULL;
GO

ALTER TABLE [dbo].[REGISTRO_AUDITORIA] WITH CHECK
    ADD CONSTRAINT [FK_63_REGISTRO_AUDITORIA_EMPLEADO]
    FOREIGN KEY ([id_empleado]) REFERENCES [dbo].[EMPLEADO] ([id_persona])
    ON DELETE NO ACTION;
GO

ALTER TABLE [dbo].[DETALLE_PEDIDO] WITH CHECK
    ADD CONSTRAINT [FK_64_DET_PED_PROMO]
    FOREIGN KEY ([id_promocion]) REFERENCES [dbo].[PROMOCION] ([id_promocion])
    ON DELETE NO ACTION;
GO

-- 3. INDICES GENERALES DE CONSULTA

CREATE INDEX [IX_ASIGNACION_ROL_id_empleado] ON [dbo].[ASIGNACION_ROL] ([id_empleado]);
GO

CREATE INDEX [IX_ASIGNACION_ROL_id_rol] ON [dbo].[ASIGNACION_ROL] ([id_rol]);
GO

CREATE INDEX [IX_ROL_PERMISO_id_permiso] ON [dbo].[ROL_PERMISO] ([id_permiso]);
GO

CREATE INDEX [IX_PRODUCTO_id_categoria] ON [dbo].[PRODUCTO] ([id_categoria]);
GO

CREATE INDEX [IX_VARIANTE_PRODUCTO_id_producto] ON [dbo].[VARIANTE_PRODUCTO] ([id_producto]);
GO

CREATE INDEX [IX_PROMOCION_VARIANTE_id_variante] ON [dbo].[PROMOCION_VARIANTE] ([id_variante]);
GO

CREATE INDEX [IX_COMPOSICION_PRODUCTO_id_articulo] ON [dbo].[COMPOSICION_PRODUCTO] ([id_articulo]);
GO

CREATE INDEX [IX_PEDIDO_id_empleado_registro] ON [dbo].[PEDIDO] ([id_emp_reg]);
GO

CREATE INDEX [IX_PEDIDO_id_etapa_actual] ON [dbo].[PEDIDO] ([id_etapa_actual]);
GO

CREATE INDEX [IX_DETALLE_PEDIDO_id_variante] ON [dbo].[DETALLE_PEDIDO] ([id_variante]);
GO

CREATE INDEX [IX_APROBACION_DISENO_id_pedido_numero_linea_numero_version] ON [dbo].[APROBACION_DISENO] ([id_pedido], [numero_linea], [numero_version]);
GO

CREATE INDEX [IX_APROBACION_DISENO_id_empleado_registro] ON [dbo].[APROBACION_DISENO] ([id_emp_reg]);
GO

CREATE INDEX [IX_HISTORIAL_PEDIDO_id_pedido] ON [dbo].[HISTORIAL_PEDIDO] ([id_pedido]);
GO

CREATE INDEX [IX_HISTORIAL_PEDIDO_id_empleado] ON [dbo].[HISTORIAL_PEDIDO] ([id_empleado]);
GO

CREATE INDEX [IX_HISTORIAL_PEDIDO_id_etapa_anterior] ON [dbo].[HISTORIAL_PEDIDO] ([id_etapa_anterior]);
GO

CREATE INDEX [IX_HISTORIAL_PEDIDO_id_etapa_nueva] ON [dbo].[HISTORIAL_PEDIDO] ([id_etapa_nueva]);
GO

CREATE INDEX [IX_ASIGNACION_ETAPA_id_pedido] ON [dbo].[ASIGNACION_ETAPA] ([id_pedido]);
GO

CREATE INDEX [IX_ASIGNACION_ETAPA_id_etapa] ON [dbo].[ASIGNACION_ETAPA] ([id_etapa]);
GO

CREATE INDEX [IX_ASIGNACION_ETAPA_id_empleado] ON [dbo].[ASIGNACION_ETAPA] ([id_empleado]);
GO

CREATE INDEX [IX_SOLICITUD_CAMBIO_id_pedido] ON [dbo].[SOLICITUD_CAMBIO] ([id_pedido]);
GO

CREATE INDEX [IX_COTIZACION_id_cliente] ON [dbo].[COTIZACION] ([id_cliente]);
GO

CREATE INDEX [IX_DETALLE_COTIZACION_id_variante] ON [dbo].[DETALLE_COTIZACION] ([id_variante]);
GO

CREATE INDEX [IX_TRANSACCION_id_pedido_numero_hito] ON [dbo].[TRANSACCION] ([id_pedido], [numero_hito]);
GO

CREATE INDEX [IX_TRANSACCION_id_empleado_verificador] ON [dbo].[TRANSACCION] ([id_emp_verif]);
GO

CREATE INDEX [IX_TRANSACCION_id_transaccion_compensada] ON [dbo].[TRANSACCION] ([id_tx_comp]);
GO

CREATE INDEX [IX_TRANSACCION_id_reembolso] ON [dbo].[TRANSACCION] ([id_reembolso]);
GO

CREATE INDEX [IX_CANCELACION_id_empleado_autoriza] ON [dbo].[CANCELACION] ([id_emp_autoriza]);
GO

CREATE INDEX [IX_REEMBOLSO_id_cancelacion] ON [dbo].[REEMBOLSO] ([id_cancelacion]);
GO

CREATE INDEX [IX_RESERVA_INVENTARIO_id_pedido] ON [dbo].[RESERVA_INVENTARIO] ([id_pedido]);
GO

CREATE INDEX [IX_RESERVA_INVENTARIO_id_articulo] ON [dbo].[RESERVA_INVENTARIO] ([id_articulo]);
GO

CREATE INDEX [IX_MOVIMIENTO_INVENTARIO_id_pedido] ON [dbo].[MOVIMIENTO_INVENTARIO] ([id_pedido]);
GO

CREATE INDEX [IX_MOVIMIENTO_INVENTARIO_id_reserva] ON [dbo].[MOVIMIENTO_INVENTARIO] ([id_reserva]);
GO

CREATE INDEX [IX_MOVIMIENTO_INVENTARIO_id_compra_numero_linea_compra] ON [dbo].[MOVIMIENTO_INVENTARIO] ([id_compra], [numero_linea_compra]);
GO

CREATE INDEX [IX_MOVIMIENTO_INVENTARIO_id_empleado] ON [dbo].[MOVIMIENTO_INVENTARIO] ([id_empleado]);
GO

CREATE INDEX [IX_PERDIDA_id_pedido] ON [dbo].[PERDIDA] ([id_pedido]);
GO

CREATE INDEX [IX_PERDIDA_id_empleado_reporta] ON [dbo].[PERDIDA] ([id_emp_reporta]);
GO

CREATE INDEX [IX_PERDIDA_id_etapa] ON [dbo].[PERDIDA] ([id_etapa]);
GO

CREATE INDEX [IX_DETALLE_PERDIDA_id_articulo] ON [dbo].[DETALLE_PERDIDA] ([id_articulo]);
GO

CREATE INDEX [IX_COMPRA_id_proveedor] ON [dbo].[COMPRA] ([id_proveedor]);
GO

CREATE INDEX [IX_DETALLE_COMPRA_id_articulo] ON [dbo].[DETALLE_COMPRA] ([id_articulo]);
GO

CREATE INDEX [IX_GASTO_id_empleado] ON [dbo].[GASTO] ([id_empleado]);
GO

CREATE INDEX [IX_ENVIO_id_agencia] ON [dbo].[ENVIO] ([id_agencia]);
GO

CREATE INDEX [IX_REGISTRO_AUDITORIA_id_empleado] ON [dbo].[REGISTRO_AUDITORIA] ([id_empleado]);
GO

CREATE INDEX [IX_PEDIDO_CLIENTE_ESTADO] ON [dbo].[PEDIDO] ([id_cliente], [estado]);
GO

CREATE INDEX [IX_MI_ART_TIPO] ON [dbo].[MOVIMIENTO_INVENTARIO] ([id_articulo], [tipo_movimiento]);
GO

CREATE INDEX [IX_TX_PEDIDO_ESTADO] ON [dbo].[TRANSACCION] ([id_pedido], [estado_verificacion]);
GO

-- 4. DIAGNOSTICO DEL ESQUEMA (solo lectura)
SELECT COUNT(*) AS tablas FROM sys.tables WHERE is_ms_shipped = 0 AND schema_id = SCHEMA_ID('dbo');
SELECT COUNT(*) AS claves_foraneas FROM sys.foreign_keys WHERE is_ms_shipped = 0;
SELECT COUNT(*) AS triggers_dml FROM sys.triggers WHERE parent_class = 1 AND is_ms_shipped = 0;
SELECT COUNT(*) AS procedimientos_usuario FROM sys.procedures WHERE is_ms_shipped = 0;
SELECT COUNT(*) AS vistas_usuario FROM sys.views WHERE is_ms_shipped = 0;
SELECT name AS collation_actual FROM sys.databases WHERE name = DB_NAME();
GO

-- DATOS

-- 1. PERSONAS, CLIENTES, EMPLEADOS Y SEGURIDAD
SET IDENTITY_INSERT dbo.PERSONA ON;
INSERT INTO dbo.PERSONA (id_persona, nombres, apellidos, tel, correo, documento) VALUES
(1,  'Ana',             'Lopez',       '8888-1001', 'ana.lopez@correo.test',       '001-010101-0001A'),
(2,  'Carlos',          'Martinez',    '8888-1002', 'carlos.martinez@correo.test', '001-020202-0002B'),
(3,  'Maria',           'Garcia',      '8888-1003', 'maria.garcia@correo.test',    '001-030303-0003C'),
(4,  'Jose',            'Hernandez',   '8888-1004', 'jose.hernandez@correo.test',  '001-040404-0004D'),
(5,  'Daniela',         'Ruiz',        '8888-1005', 'daniela.ruiz@correo.test',    '001-050505-0005E'),
(6,  'Luis',            'Perez',       '8888-1006', 'luis.perez@correo.test',      '001-060606-0006F'),
(7,  'Sofia',           'Castillo',    '8888-1007', 'sofia.castillo@correo.test',  '001-070707-0007G'),
(8,  'Empresa Creativa','S.A.',        '8888-1008', 'compras@creativa.test',       'RUC-J031000000001'),
(9,  'Roberto',         'Mendez',      '8888-2001', 'roberto@dobler.test',         '001-090909-0009H'),
(10, 'Elena',           'Torres',      '8888-2002', 'elena@dobler.test',           '001-101010-0010J'),
(11, 'Miguel',          'Rojas',       '8888-2003', 'miguel@dobler.test',          '001-111111-0011K'),
(12, 'Paola',           'Vargas',      '8888-2004', 'paola@dobler.test',           '001-121212-0012L');
SET IDENTITY_INSERT dbo.PERSONA OFF;

INSERT INTO dbo.CLIENTE
    (id_persona, tipo_cliente, condicion_comercial, fec_registro, origen_registro, estado)
VALUES
(1, 'INVITADO',   'PRECIO_DETALLE',              '2026-10-01T10:00:00', 'WEB',      'ACTIVO'),
(2, 'REGISTRADO', 'DETALLE_Y_MAYORISTA',         '2026-08-10T09:00:00', 'WHATSAPP', 'ACTIVO'),
(3, 'REGISTRADO', 'DETALLE_Y_MAYORISTA',         '2026-08-12T11:30:00', 'FACEBOOK', 'ACTIVO'),
(4, 'REGISTRADO', 'PRECIO_DETALLE',              '2026-08-15T14:10:00', 'TIENDA',   'ACTIVO'),
(5, 'REGISTRADO', 'DETALLE_Y_PROMOCIONES',       '2026-09-01T08:40:00', 'WHATSAPP', 'ACTIVO'),
(6, 'REGISTRADO', 'DETALLE_Y_MAYORISTA',         '2026-09-05T16:20:00', 'WEB',      'ACTIVO'),
(7, 'REGISTRADO', 'DETALLE_Y_PROMOCIONES',       '2026-09-12T12:15:00', 'FACEBOOK', 'ACTIVO'),
(8, 'EMPRESA',    'MAYORISTA_EMPRESARIAL',       '2026-07-20T09:00:00', 'VENTAS',   'ACTIVO');

INSERT INTO dbo.EMPLEADO
    (id_persona, codigo_empleado, fecha_ingreso, estado_laboral, max_asignaciones)
VALUES
(9,  'EMP-001', '2025-01-10T08:00:00', 'ACTIVO', 20),
(10, 'EMP-002', '2025-03-15T08:00:00', 'ACTIVO', 12),
(11, 'EMP-003', '2025-05-01T08:00:00', 'ACTIVO', 8),
(12, 'EMP-004', '2025-05-01T08:00:00', 'ACTIVO', 10);

SET IDENTITY_INSERT dbo.CUENTA_ACCESO ON;
INSERT INTO dbo.CUENTA_ACCESO
    (id_cuenta, id_persona, auth_uid, fec_alta, estado_cuenta, ult_acceso)
VALUES
(1,  2,  'auth-carlos-002',  '2026-08-10T09:05:00', 'ACTIVA', '2026-10-25T15:10:00'),
(2,  3,  'auth-maria-003',   '2026-08-12T11:35:00', 'ACTIVA', '2026-10-26T18:20:00'),
(3,  4,  'auth-jose-004',    '2026-08-15T14:15:00', 'ACTIVA', '2026-10-20T09:00:00'),
(4,  5,  'auth-daniela-005', '2026-09-01T08:45:00', 'ACTIVA', '2026-10-24T13:30:00'),
(5,  6,  'auth-luis-006',    '2026-09-05T16:25:00', 'ACTIVA', '2026-10-19T17:10:00'),
(6,  7,  'auth-sofia-007',   '2026-09-12T12:20:00', 'ACTIVA', '2026-10-23T08:45:00'),
(7,  8,  'auth-empresa-008', '2026-07-20T09:05:00', 'ACTIVA', '2026-10-26T10:00:00'),
(8,  9,  'auth-emp-001',     '2025-01-10T08:05:00', 'ACTIVA', '2026-10-27T08:00:00'),
(9,  10, 'auth-emp-002',     '2025-03-15T08:05:00', 'ACTIVA', '2026-10-27T08:05:00'),
(10, 11, 'auth-emp-003',     '2025-05-01T08:05:00', 'ACTIVA', '2026-10-27T08:10:00'),
(11, 12, 'auth-emp-004',     '2025-05-01T08:05:00', 'ACTIVA', '2026-10-27T08:15:00');
SET IDENTITY_INSERT dbo.CUENTA_ACCESO OFF;

SET IDENTITY_INSERT dbo.ROL ON;
INSERT INTO dbo.ROL (id_rol, nombre, descripcion, estado) VALUES
(1, 'ADMINISTRADOR', 'Acceso administrativo general', 'ACTIVO'),
(2, 'VENDEDOR',      'Gestion de clientes, cotizaciones y pedidos', 'ACTIVO'),
(3, 'DISENADOR',     'Gestion de disenos y aprobaciones', 'ACTIVO'),
(4, 'PRODUCCION',    'Produccion, inventario y registro de perdidas', 'ACTIVO');
SET IDENTITY_INSERT dbo.ROL OFF;

SET IDENTITY_INSERT dbo.PERMISO ON;
INSERT INTO dbo.PERMISO (id_permiso, codigo_permiso, descripcion, modulo) VALUES
(1, 'PEDIDO_VER',        'Consultar pedidos',                    'PEDIDOS'),
(2, 'PEDIDO_CREAR',      'Crear pedidos',                        'PEDIDOS'),
(3, 'INVENTARIO_VER',    'Consultar inventario',                 'INVENTARIO'),
(4, 'INVENTARIO_EDITAR', 'Modificar existencias y movimientos',  'INVENTARIO'),
(5, 'PRECIO_EDITAR',     'Modificar precios comerciales',        'PRODUCTOS'),
(6, 'PAGO_VERIFICAR',    'Verificar pagos reportados',           'PAGOS'),
(7, 'PERDIDA_REGISTRAR', 'Registrar perdidas de produccion',      'PRODUCCION'),
(8, 'USUARIO_ADMIN',     'Administrar usuarios, roles y permisos','SEGURIDAD');
SET IDENTITY_INSERT dbo.PERMISO OFF;

INSERT INTO dbo.ROL_PERMISO (id_rol, id_permiso) VALUES
(1,1),(1,2),(1,3),(1,4),(1,5),(1,6),(1,7),(1,8),
(2,1),(2,2),(2,3),(2,6),
(3,1),(3,3),
(4,1),(4,3),(4,4),(4,7);

SET IDENTITY_INSERT dbo.ASIGNACION_ROL ON;
INSERT INTO dbo.ASIGNACION_ROL
    (id_asignacion_rol, id_empleado, id_rol, fec_asig, fec_fin, estado)
VALUES
(1, 9,  1, '2025-01-10T08:10:00', NULL, 'ACTIVA'),
(2, 10, 2, '2025-03-15T08:10:00', NULL, 'ACTIVA'),
(3, 11, 3, '2025-05-01T08:10:00', NULL, 'ACTIVA'),
(4, 12, 4, '2025-05-01T08:10:00', NULL, 'ACTIVA');
SET IDENTITY_INSERT dbo.ASIGNACION_ROL OFF;

--2. CATALOGO DE PRODUCTOS, INVENTARIO Y PRECIOS

SET IDENTITY_INSERT dbo.CATEGORIA ON;
INSERT INTO dbo.CATEGORIA (id_categoria, nombre, descripcion, estado) VALUES
(1, 'Tazas',      'Productos ceramicos sublimables', 'ACTIVA'),
(2, 'Textiles',   'Prendas para sublimacion',         'ACTIVA'),
(3, 'Accesorios', 'Llaveros y articulos pequenos',    'ACTIVA'),
(4, 'Bebidas',    'Termos y botellas deportivas',     'ACTIVA'),
(5, 'Oficina',    'Mouse pads y articulos de escritorio', 'ACTIVA');
SET IDENTITY_INSERT dbo.CATEGORIA OFF;

SET IDENTITY_INSERT dbo.PRODUCTO ON;
INSERT INTO dbo.PRODUCTO
    (id_producto, id_categoria, nombre, descripcion, informacion_comercial, estado_publicacion)
VALUES
(1, 1, 'Taza sublimable',      'Taza para personalizacion por sublimacion', 'Disponible al detalle y mayorista', 'PUBLICADO'),
(2, 2, 'Camiseta sublimable',  'Camiseta poliester para sublimacion',       'Personalizacion incluida',         'PUBLICADO'),
(3, 5, 'Mouse pad sublimable', 'Mouse pad para impresion personalizada',    'Formato estandar',                 'PUBLICADO'),
(4, 3, 'Llavero MDF',          'Llavero sublimable de MDF',                 'Venta individual y por docena',    'PUBLICADO'),
(5, 4, 'Termo sublimable',     'Termo metalico para sublimacion',           'Incluye empaque basico',           'PUBLICADO'),
(6, 4, 'Botella deportiva',    'Botella deportiva sublimable',              'Varios disenos disponibles',       'PUBLICADO');
SET IDENTITY_INSERT dbo.PRODUCTO OFF;

SET IDENTITY_INSERT dbo.VARIANTE_PRODUCTO ON;
INSERT INTO dbo.VARIANTE_PRODUCTO
    (id_variante, id_producto, codigo_variante, caracteristicas, precio_detalle, requiere_produccion, estado)
VALUES
(1, 1, 'TAZA11-BLANCA',  '11 oz, blanca',            90.00, 1, 'ACTIVA'),
(2, 1, 'TAZA11-MAGICA',  '11 oz, magica negra',     130.00, 1, 'ACTIVA'),
(3, 2, 'CAMISETA-M-BLA', 'Talla M, blanca',          250.00, 1, 'ACTIVA'),
(4, 3, 'MOUSEPAD-20X24', '20 x 24 cm',                80.00, 1, 'ACTIVA'),
(5, 4, 'LLAVERO-MDF',    'MDF rectangular',           60.00, 1, 'ACTIVA'),
(6, 5, 'TERMO-20OZ',     'Termo metalico 20 oz',     220.00, 1, 'ACTIVA'),
(7, 6, 'BOTELLA-SPORT',  'Botella deportiva 600 ml', 150.00, 1, 'ACTIVA'),
(8, 1, 'TAZA15-BLANCA',  '15 oz, blanca',            120.00, 1, 'ACTIVA');
SET IDENTITY_INSERT dbo.VARIANTE_PRODUCTO OFF;

SET IDENTITY_INSERT dbo.ARTICULO_INVENTARIABLE ON;
INSERT INTO dbo.ARTICULO_INVENTARIABLE
    (id_articulo, codigo, nombre, tipo_articulo, unidad_medida, existencia_actual, existencia_minima, costo_referencia, estado)
VALUES
(1,  'INS-TAZA11', 'Taza blanca 11 oz',       'PRODUCTO_BASE', 'UNIDAD', 80.000, 20.000, 25.0000, 'ACTIVO'),
(2,  'INS-PAPELA4','Papel sublimacion A4',    'INSUMO',        'HOJA',  177.000, 50.000,  2.0000, 'ACTIVO'),
(3,  'INS-TINTA',  'Tinta sublimacion',       'INSUMO',        'ML',    929.000,100.000,  0.4000, 'ACTIVO'),
(4,  'INS-CAM-M',  'Camiseta blanca talla M', 'PRODUCTO_BASE', 'UNIDAD', 48.000, 10.000, 70.0000, 'ACTIVO'),
(5,  'INS-MOUSE',  'Mouse pad en blanco',     'PRODUCTO_BASE', 'UNIDAD', 27.000,  8.000, 45.0000, 'ACTIVO'),
(6,  'INS-LLAVERO','Llavero MDF en blanco',   'PRODUCTO_BASE', 'UNIDAD', 40.000, 10.000, 20.0000, 'ACTIVO'),
(7,  'INS-TERMO',  'Termo 20 oz en blanco',   'PRODUCTO_BASE', 'UNIDAD', 24.000,  6.000, 90.0000, 'ACTIVO'),
(8,  'INS-BOTELLA','Botella deportiva blanca','PRODUCTO_BASE', 'UNIDAD', 34.000,  8.000, 55.0000, 'ACTIVO'),
(9,  'INS-CAJA',   'Caja individual para taza','EMPAQUE',      'UNIDAD', 82.000, 20.000, 10.0000, 'ACTIVO'),
(10, 'INS-CINTA',  'Cinta termica',           'INSUMO',        'M',      27.500,  5.000, 50.0000, 'ACTIVO');
SET IDENTITY_INSERT dbo.ARTICULO_INVENTARIABLE OFF;

INSERT INTO dbo.ESCALA_PRECIO
    (id_variante, numero_rango, cant_min, cant_max, precio_mayorista, estado)
VALUES
(1, 1,  6, 11, 85.00, 'ACTIVA'),
(1, 2, 12, 35, 80.00, 'ACTIVA'),
(1, 3, 36, NULL,75.00,'ACTIVA'),
(4, 1, 12, NULL,70.00,'ACTIVA'),
(5, 1, 12, NULL,50.00,'ACTIVA');

INSERT INTO dbo.COMPOSICION_PRODUCTO (id_variante, id_articulo, cant_estandar, observaciones) VALUES
(1, 1, 1.000, 'Una taza base por unidad terminada'),
(1, 2, 1.000, 'Una hoja A4 por impresion'),
(1, 3, 3.000, 'Consumo estimado de tinta en ml'),
(1, 9, 1.000, 'Una caja por taza'),
(1,10, 0.100, 'Cinta termica estimada por taza'),
(3, 4, 1.000, 'Una camiseta por unidad'),
(3, 2, 1.000, 'Una hoja por camiseta'),
(3, 3, 5.000, 'Consumo estimado de tinta'),
(4, 5, 1.000, 'Un mouse pad por unidad'),
(4, 2, 1.000, 'Una hoja por unidad'),
(4, 3, 4.000, 'Consumo estimado de tinta'),
(5, 6, 1.000, 'Un llavero por unidad'),
(6, 7, 1.000, 'Un termo por unidad'),
(7, 8, 1.000, 'Una botella por unidad');

SET IDENTITY_INSERT dbo.PROMOCION ON;
INSERT INTO dbo.PROMOCION
    (id_promocion, nombre, tipo, cant_req, beneficio, fec_inicio, fec_fin, condiciones, permite_combinacion_mayorista, valor_beneficio, estado)
VALUES
(1, '2 tazas por C$170', 'PRECIO_PAQUETE', 2, 'Dos tazas blancas de 11 oz por C$170',
 '2026-10-01T00:00:00','2026-11-30T23:59:59','Aplicable a precio detalle',0,170.00,'ACTIVA'),
(2, '10% en camisetas', 'PORCENTAJE', 2, 'Diez por ciento de descuento en camisetas',
 '2026-10-01T00:00:00','2026-12-31T23:59:59','Minimo dos camisetas',0,10.00,'ACTIVA');
SET IDENTITY_INSERT dbo.PROMOCION OFF;

INSERT INTO dbo.PROMOCION_VARIANTE (id_promocion, id_variante) VALUES
(1,1),(2,3);

--3. PROVEEDORES Y COMPRAS
SET IDENTITY_INSERT dbo.PROVEEDOR ON;
INSERT INTO dbo.PROVEEDOR (id_proveedor, nombre, telefono, correo, direccion, estado) VALUES
(1, 'Suministros Creativos', '2222-1001', 'ventas@suministros.test', 'Managua', 'ACTIVO'),
(2, 'Textiles del Pacifico', '2222-1002', 'pedidos@textiles.test',   'Masaya',  'ACTIVO'),
(3, 'Publicidad Nicaragua',  '2222-1003', 'info@publicidad.test',   'Managua', 'ACTIVO');
SET IDENTITY_INSERT dbo.PROVEEDOR OFF;

SET IDENTITY_INSERT dbo.COMPRA ON;
INSERT INTO dbo.COMPRA (id_compra, id_proveedor, fec_compra, numero_documento, estado, total_compra) VALUES
(1, 1, '2026-09-15T09:00:00', 'FAC-1001', 'CONFIRMADA', 4300.00),
(2, 2, '2026-09-18T10:30:00', 'FAC-2001', 'CONFIRMADA', 4850.00),
(3, 3, '2026-09-20T11:00:00', 'FAC-3001', 'CONFIRMADA', 4975.00),
(4, 1, '2026-09-22T14:00:00', 'FAC-1002', 'CONFIRMADA', 1500.00);
SET IDENTITY_INSERT dbo.COMPRA OFF;

INSERT INTO dbo.DETALLE_COMPRA
    (id_compra, numero_linea, id_articulo, cant_comprada, costo_unit_compra, importe)
VALUES
(1,1,1, 100.000, 25.0000, 2500.00),
(1,2,2, 200.000,  2.0000,  400.00),
(1,3,3,1000.000,  0.4000,  400.00),
(1,4,9, 100.000, 10.0000, 1000.00),
(2,1,4,  50.000, 70.0000, 3500.00),
(2,2,5,  30.000, 45.0000, 1350.00),
(3,1,6,  40.000, 20.0000,  800.00),
(3,2,7,  25.000, 90.0000, 2250.00),
(3,3,8,  35.000, 55.0000, 1925.00),
(4,1,10, 30.000, 50.0000, 1500.00);

--4. ETAPAS, COTIZACIONES Y PEDIDOS

SET IDENTITY_INSERT dbo.ETAPA_PROCESO ON;
INSERT INTO dbo.ETAPA_PROCESO (id_etapa, nombre, descripcion, orden_referencia, estado) VALUES
(1, 'Registro',         'Pedido recibido y registrado',               1, 'ACTIVA'),
(2, 'Diseno',           'Preparacion y aprobacion del diseno',        2, 'ACTIVA'),
(3, 'Produccion',       'Sublimacion y elaboracion',                   3, 'ACTIVA'),
(4, 'Control calidad',  'Revision del producto terminado',            4, 'ACTIVA'),
(5, 'Listo',            'Pedido listo para retiro o envio',           5, 'ACTIVA'),
(6, 'Entregado',        'Pedido entregado al cliente',                 6, 'ACTIVA');
SET IDENTITY_INSERT dbo.ETAPA_PROCESO OFF;

SET IDENTITY_INSERT dbo.COTIZACION ON;
INSERT INTO dbo.COTIZACION
    (id_cotizacion, id_cliente, fec_emision, fec_venc, estado, total_ofrecido, observaciones)
VALUES
(1, 2, '2026-10-02T09:00:00','2026-10-07T23:59:59','ACEPTADA', 960.00,'Cotizacion por 12 tazas'),
(2, 3, '2026-10-05T10:00:00','2026-10-10T23:59:59','ACEPTADA', 670.00,'Tazas y mouse pads'),
(3, 5, '2026-10-08T11:00:00','2026-10-13T23:59:59','ACEPTADA', 370.00,'Termo y botella'),
(4, 8, '2026-10-10T08:30:00','2026-10-15T23:59:59','ACEPTADA',1600.00,'Pedido empresarial');
SET IDENTITY_INSERT dbo.COTIZACION OFF;

INSERT INTO dbo.DETALLE_COTIZACION
    (id_cotizacion, numero_linea, id_variante, cantidad, descripcion_personalizacion, precio_ofrecido, descuento_ofrecido)
VALUES
(1,1,1,12,'Logo de empresa a una cara',80.00,0.00),
(2,1,1, 6,'Fotografia y nombre',85.00,0.00),
(2,2,4, 2,'Logo rectangular',80.00,0.00),
(3,1,6, 1,'Nombre y fotografia',220.00,0.00),
(3,2,7, 1,'Nombre',150.00,0.00),
(4,1,1,20,'Logo corporativo',80.00,0.00);

SET IDENTITY_INSERT dbo.PEDIDO ON;
INSERT INTO dbo.PEDIDO
    (id_pedido, id_cliente, id_emp_reg, id_etapa_actual, id_cotizacion, codigo_pedido,
     fec_crea, vencimiento_pago, canal_origen, estado, fec_entrega_prev,
     modalidad_entrega, nombre_persona_retiro, total_pedido, token_seguimiento)
VALUES
(1, 1, 10, 1, NULL, 'PED-0001', '2026-10-12T09:00:00','2026-10-13T18:00:00','WEB','PENDIENTE_PAGO','2026-10-16T17:00:00','RETIRO','Ana Lopez',170.00,'11111111-1111-1111-1111-111111111111'),
(2, 2, 10, 6, 1,    'PED-0002', '2026-10-03T09:30:00','2026-10-04T18:00:00','WHATSAPP','ENTREGADO','2026-10-08T17:00:00','RETIRO','Carlos Martinez',960.00,'22222222-2222-2222-2222-222222222222'),
(3, 3, 10, 3, 2,    'PED-0003', '2026-10-06T10:30:00','2026-10-07T18:00:00','FACEBOOK','EN_PRODUCCION','2026-10-12T17:00:00','RETIRO','Maria Garcia',670.00,'33333333-3333-3333-3333-333333333333'),
(4, 4, 10, 6, NULL, 'PED-0004', '2026-10-07T14:00:00','2026-10-08T18:00:00','TIENDA','ENTREGADO','2026-10-11T12:00:00','RETIRO','Jose Hernandez',450.00,'44444444-4444-4444-4444-444444444444'),
(5, 5, 10, 2, 3,    'PED-0005', '2026-10-09T11:30:00','2026-10-10T18:00:00','WHATSAPP','EN_DISENO','2026-10-15T17:00:00','ENVIO',NULL,370.00,'55555555-5555-5555-5555-555555555555'),
(6, 6, 10, 1, NULL, 'PED-0006', '2026-10-10T09:15:00','2026-10-11T18:00:00','WEB','CANCELADO','2026-10-14T17:00:00','RETIRO','Luis Perez',270.00,'66666666-6666-6666-6666-666666666666'),
(7, 7, 10, 5, NULL, 'PED-0007', '2026-10-11T10:00:00','2026-10-12T18:00:00','FACEBOOK','LISTO','2026-10-16T16:00:00','RETIRO','Sofia Castillo',240.00,'77777777-7777-7777-7777-777777777777'),
(8, 8, 10, 2, 4,    'PED-0008', '2026-10-12T08:30:00','2026-10-13T18:00:00','VENTAS','PAGADO_PARCIAL','2026-10-20T16:00:00','ENVIO',NULL,1600.00,'88888888-8888-8888-8888-888888888888'),
(9, 2, 10, 6, NULL, 'PED-0009', '2026-10-14T09:00:00','2026-10-15T18:00:00','WEB','ENTREGADO','2026-10-18T12:00:00','RETIRO','Carlos Martinez',240.00,'99999999-9999-9999-9999-999999999999'),
(10,3, 10, 1, NULL, 'PED-0010', '2026-10-20T15:00:00','2026-10-21T18:00:00','WHATSAPP','PENDIENTE_PAGO','2026-10-24T17:00:00','RETIRO','Maria Garcia',90.00,'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa');
SET IDENTITY_INSERT dbo.PEDIDO OFF;

INSERT INTO dbo.DETALLE_PEDIDO
    (id_pedido, numero_linea, id_variante, cantidad, precio_unit, descuento, importe, costo_est, costo_real, modo_precio, id_promocion)
VALUES
(1,1,1, 2, 90.00,10.00,170.00, 70.00,NULL,'PROMOCION',1),
(2,1,1,12, 80.00, 0.00,960.00,420.00,432.00,'MAYORISTA',NULL),
(3,1,1, 6, 85.00, 0.00,510.00,210.00,275.00,'MAYORISTA',NULL),
(3,2,4, 2, 80.00, 0.00,160.00,110.00,112.00,'DETALLE',NULL),
(4,1,3, 2,250.00,50.00,450.00,160.00,165.00,'PROMOCION',2),
(5,1,6, 1,220.00, 0.00,220.00,110.00,NULL,'COTIZADO',NULL),
(5,2,7, 1,150.00, 0.00,150.00, 75.00,NULL,'COTIZADO',NULL),
(6,1,1, 3, 90.00, 0.00,270.00,105.00,NULL,'DETALLE',NULL),
(7,1,5, 4, 60.00, 0.00,240.00,100.00,102.00,'DETALLE',NULL),
(8,1,1,20, 80.00, 0.00,1600.00,700.00,NULL,'MAYORISTA',NULL),
(9,1,4, 3, 80.00, 0.00,240.00,165.00,168.00,'DETALLE',NULL),
(10,1,1,1, 90.00, 0.00, 90.00, 35.00,NULL,'DETALLE',NULL);

--5. DISENO, HISTORIAL Y ASIGNACIONES

INSERT INTO dbo.VERSION_DISENO
    (id_pedido, numero_linea, numero_version, nombre_archivo, ruta_archivo, fec_crea, observaciones, es_aprobado)
VALUES
(3,1,1,'pedido3_tazas_v1.png','/disenos/pedido3/tazas_v1.png','2026-10-06T14:00:00','Primera propuesta',0),
(3,1,2,'pedido3_tazas_v2.png','/disenos/pedido3/tazas_v2.png','2026-10-07T09:00:00','Correccion solicitada',1),
(4,1,1,'pedido4_camisas_v1.png','/disenos/pedido4/camisas_v1.png','2026-10-07T16:00:00','Diseno aprobado',1),
(5,1,1,'pedido5_termo_v1.png','/disenos/pedido5/termo_v1.png','2026-10-09T15:00:00','Pendiente de aprobacion',0),
(7,1,1,'pedido7_llaveros_v1.png','/disenos/pedido7/llaveros_v1.png','2026-10-11T13:00:00','Diseno aprobado',1);

SET IDENTITY_INSERT dbo.APROBACION_DISENO ON;
INSERT INTO dbo.APROBACION_DISENO
    (id_aprobacion, id_pedido, numero_linea, numero_version, id_emp_reg, fec_aprobacion, medio_confirmacion, observacion, tipo_decision)
VALUES
(1,3,1,2,11,'2026-10-07T10:00:00','WHATSAPP','Cliente confirma version 2','APROBADO'),
(2,4,1,1,11,'2026-10-07T17:00:00','WHATSAPP','Cliente confirma diseno','APROBADO'),
(3,7,1,1,11,'2026-10-11T14:00:00','MESSENGER','Cliente confirma diseno','APROBADO');
SET IDENTITY_INSERT dbo.APROBACION_DISENO OFF;

SET IDENTITY_INSERT dbo.HISTORIAL_PEDIDO ON;
INSERT INTO dbo.HISTORIAL_PEDIDO
    (id_historial, id_pedido, id_empleado, id_etapa_anterior, id_etapa_nueva, fec_hora, estado_anterior, estado_nuevo, motivo, origen_cambio)
VALUES
(1, 2,10,1,2,'2026-10-03T12:00:00','PAGADO','EN_DISENO','Pago confirmado','SISTEMA'),
(2, 2,11,2,3,'2026-10-04T09:00:00','EN_DISENO','EN_PRODUCCION','Diseno aprobado','EMPLEADO'),
(3, 2,12,3,6,'2026-10-08T16:00:00','EN_PRODUCCION','ENTREGADO','Pedido terminado y retirado','EMPLEADO'),
(4, 3,10,1,2,'2026-10-06T12:00:00','PAGADO_PARCIAL','EN_DISENO','Anticipo confirmado','SISTEMA'),
(5, 3,11,2,3,'2026-10-07T10:30:00','EN_DISENO','EN_PRODUCCION','Diseno aprobado','EMPLEADO'),
(6, 5,10,1,2,'2026-10-09T13:00:00','PAGADO_PARCIAL','EN_DISENO','Anticipo confirmado','SISTEMA'),
(7, 7,12,4,5,'2026-10-15T15:00:00','EN_PRODUCCION','LISTO','Control de calidad aprobado','EMPLEADO'),
(8, 9,12,5,6,'2026-10-18T11:30:00','LISTO','ENTREGADO','Retiro en tienda','EMPLEADO');
SET IDENTITY_INSERT dbo.HISTORIAL_PEDIDO OFF;

SET IDENTITY_INSERT dbo.ASIGNACION_ETAPA ON;
INSERT INTO dbo.ASIGNACION_ETAPA
    (id_asignacion, id_pedido, id_etapa, id_empleado, fec_inicio, fec_fin, origen_asignacion, estado, motivo_reasignacion)
VALUES
(1,3,2,11,'2026-10-06T12:10:00','2026-10-07T10:20:00','MANUAL','FINALIZADA',NULL),
(2,3,3,12,'2026-10-07T10:30:00',NULL,'MANUAL','ACTIVA',NULL),
(3,5,2,11,'2026-10-09T13:10:00',NULL,'MANUAL','ACTIVA',NULL),
(4,7,4,12,'2026-10-15T13:00:00','2026-10-15T15:00:00','MANUAL','FINALIZADA',NULL),
(5,8,2,11,'2026-10-13T10:00:00',NULL,'MANUAL','ACTIVA',NULL);
SET IDENTITY_INSERT dbo.ASIGNACION_ETAPA OFF;

SET IDENTITY_INSERT dbo.SOLICITUD_CAMBIO ON;
INSERT INTO dbo.SOLICITUD_CAMBIO
    (id_solicitud_cambio, id_pedido, fec_solicitud, descripcion, motivo, decision, costo_adicional_estimado, cargo_adicional_aprobado)
VALUES
(1,3,'2026-10-06T18:00:00','Cambiar color del texto principal','Preferencia del cliente','APROBADA',20.00,20.00),
(2,5,'2026-10-10T09:30:00','Mover nombre al centro del termo','Ajuste visual','PENDIENTE',0.00,NULL);
SET IDENTITY_INSERT dbo.SOLICITUD_CAMBIO OFF;

--6. PAGOS, CANCELACION, REEMBOLSO Y ENVIO

INSERT INTO dbo.HITO_PAGO (id_pedido, numero_hito, tipo_hito, monto_exigido, fec_venc, estado) VALUES
(1,1,'ANTICIPO', 85.00,'2026-10-13T18:00:00','PENDIENTE'),
(1,2,'SALDO',    85.00,'2026-10-16T16:00:00','PENDIENTE'),
(2,1,'ANTICIPO',480.00,'2026-10-04T18:00:00','PAGADO'),
(2,2,'SALDO',   480.00,'2026-10-08T16:00:00','PAGADO'),
(3,1,'ANTICIPO',335.00,'2026-10-07T18:00:00','PAGADO'),
(3,2,'SALDO',   335.00,'2026-10-12T16:00:00','PENDIENTE'),
(4,1,'ANTICIPO',225.00,'2026-10-08T18:00:00','PAGADO'),
(4,2,'SALDO',   225.00,'2026-10-11T11:00:00','PAGADO'),
(5,1,'ANTICIPO',185.00,'2026-10-10T18:00:00','PAGADO'),
(5,2,'SALDO',   185.00,'2026-10-15T16:00:00','PENDIENTE'),
(6,1,'ANTICIPO',135.00,'2026-10-11T18:00:00','PAGADO'),
(6,2,'SALDO',   135.00,'2026-10-14T16:00:00','PAGADO'),
(7,1,'ANTICIPO',120.00,'2026-10-12T18:00:00','PAGADO'),
(7,2,'SALDO',   120.00,'2026-10-16T15:00:00','PAGADO'),
(8,1,'ANTICIPO',800.00,'2026-10-13T18:00:00','PAGADO'),
(8,2,'SALDO',   800.00,'2026-10-20T15:00:00','PENDIENTE'),
(9,1,'ANTICIPO',120.00,'2026-10-15T18:00:00','PAGADO'),
(9,2,'SALDO',   120.00,'2026-10-18T11:00:00','PAGADO'),
(10,1,'ANTICIPO',45.00,'2026-10-21T18:00:00','PENDIENTE'),
(10,2,'SALDO',   45.00,'2026-10-24T16:00:00','PENDIENTE');

SET IDENTITY_INSERT dbo.CANCELACION ON;
INSERT INTO dbo.CANCELACION
    (id_cancelacion, id_pedido, id_emp_autoriza, fec_hora, motivo, etapa_cancelacion, monto_retenido, resultado, fecha_confirmacion_autenticacion)
VALUES
(1,6,9,'2026-10-12T10:00:00','Cliente cancela antes de iniciar produccion','REGISTRO',50.00,'APROBADA','2026-10-12T10:02:00');
SET IDENTITY_INSERT dbo.CANCELACION OFF;

SET IDENTITY_INSERT dbo.REEMBOLSO ON;
INSERT INTO dbo.REEMBOLSO
    (id_reembolso, id_cancelacion, fec_solicitud, monto_solicitado, monto_aprobado, motivo, estado, fecha_resolucion)
VALUES
(1,1,'2026-10-12T10:05:00',220.00,220.00,'Devolucion luego de retener costos administrativos','PAGADO','2026-10-12T15:00:00');
SET IDENTITY_INSERT dbo.REEMBOLSO OFF;

SET IDENTITY_INSERT dbo.TRANSACCION ON;
INSERT INTO dbo.TRANSACCION
    (id_transaccion, id_pedido, numero_hito, id_emp_verif, id_tx_comp, id_reembolso, fec_hora,
     tipo_transaccion, monto, metodo_pago, banco_receptor, referencia_bancaria, estado_verificacion, clave_idem)
VALUES
(1, 2,1,10,NULL,NULL,'2026-10-03T10:00:00','PAGO',480.00,'TRANSFERENCIA','BAC','TRX-2001-A','VERIFICADO','00000000-0000-0000-0000-000000000001'),
(2, 2,2,10,NULL,NULL,'2026-10-08T10:00:00','PAGO',480.00,'EFECTIVO',NULL,NULL,'VERIFICADO','00000000-0000-0000-0000-000000000002'),
(3, 3,1,10,NULL,NULL,'2026-10-06T11:00:00','PAGO',335.00,'TRANSFERENCIA','BANPRO','TRX-3001-A','VERIFICADO','00000000-0000-0000-0000-000000000003'),
(4, 4,1,10,NULL,NULL,'2026-10-07T15:00:00','PAGO',225.00,'EFECTIVO',NULL,NULL,'VERIFICADO','00000000-0000-0000-0000-000000000004'),
(5, 4,2,10,NULL,NULL,'2026-10-11T10:30:00','PAGO',225.00,'EFECTIVO',NULL,NULL,'VERIFICADO','00000000-0000-0000-0000-000000000005'),
(6, 5,1,10,NULL,NULL,'2026-10-09T12:00:00','PAGO',185.00,'TRANSFERENCIA','BDF','TRX-5001-A','VERIFICADO','00000000-0000-0000-0000-000000000006'),
(7, 6,1,10,NULL,NULL,'2026-10-10T10:00:00','PAGO',135.00,'TRANSFERENCIA','BAC','TRX-6001-A','VERIFICADO','00000000-0000-0000-0000-000000000007'),
(8, 6,2,10,NULL,NULL,'2026-10-11T12:00:00','PAGO',135.00,'EFECTIVO',NULL,NULL,'VERIFICADO','00000000-0000-0000-0000-000000000008'),
(9, 7,1,10,NULL,NULL,'2026-10-11T11:00:00','PAGO',120.00,'EFECTIVO',NULL,NULL,'VERIFICADO','00000000-0000-0000-0000-000000000009'),
(10,7,2,10,NULL,NULL,'2026-10-15T14:00:00','PAGO',120.00,'EFECTIVO',NULL,NULL,'VERIFICADO','00000000-0000-0000-0000-000000000010'),
(11,8,1,10,NULL,NULL,'2026-10-12T09:00:00','PAGO',800.00,'TRANSFERENCIA','BANPRO','TRX-8001-A','VERIFICADO','00000000-0000-0000-0000-000000000011'),
(12,9,1,10,NULL,NULL,'2026-10-14T10:00:00','PAGO',120.00,'TARJETA',NULL,'POS-9001-A','VERIFICADO','00000000-0000-0000-0000-000000000012'),
(13,9,2,10,NULL,NULL,'2026-10-18T10:30:00','PAGO',120.00,'EFECTIVO',NULL,NULL,'VERIFICADO','00000000-0000-0000-0000-000000000013'),
(14,6,NULL,9,NULL,1,'2026-10-12T15:00:00','REEMBOLSO',-220.00,'TRANSFERENCIA','BAC','REF-6001','VERIFICADO','00000000-0000-0000-0000-000000000014');
SET IDENTITY_INSERT dbo.TRANSACCION OFF;

SET IDENTITY_INSERT dbo.AGENCIA_ENVIO ON;
INSERT INTO dbo.AGENCIA_ENVIO (id_agencia, nombre, tipo_agencia, telefono, estado) VALUES
(1,'Cargo Express Demo','PAQUETERIA','2255-0101','ACTIVA'),
(2,'Mensajeria Capital','MOTORIZADO','2255-0102','ACTIVA');
SET IDENTITY_INSERT dbo.AGENCIA_ENVIO OFF;

SET IDENTITY_INSERT dbo.ENVIO ON;
INSERT INTO dbo.ENVIO
    (id_envio, id_pedido, id_agencia, direccion_entrega, nombre_receptor, telefono_receptor, tarifa_acordada, fecha_programada, fec_entrega_real, estado)
VALUES
(1,5,2,'Villa Fontana, Managua','Daniela Ruiz','8888-1005',80.00,'2026-10-15T15:00:00',NULL,'PROGRAMADO'),
(2,8,1,'Carretera Norte, Managua','Recepcion Empresa Creativa','8888-1008',150.00,'2026-10-20T14:00:00',NULL,'PROGRAMADO');
SET IDENTITY_INSERT dbo.ENVIO OFF;

--7. RESERVAS, MOVIMIENTOS Y PERDIDAS

SET IDENTITY_INSERT dbo.RESERVA_INVENTARIO ON;
INSERT INTO dbo.RESERVA_INVENTARIO
    (id_reserva, id_pedido, id_articulo, cant_reservada, cant_pendiente, fec_reserva, fec_liberacion, estado)
VALUES
(1,3,1, 8.000, 0.000,'2026-10-07T10:40:00','2026-10-08T16:00:00','AGOTADA'),
(2,3,2, 8.000, 0.000,'2026-10-07T10:40:00','2026-10-08T16:00:00','AGOTADA'),
(3,3,3,35.000, 0.000,'2026-10-07T10:40:00','2026-10-08T16:00:00','AGOTADA'),
(4,3,9, 6.000, 0.000,'2026-10-07T10:40:00','2026-10-08T16:00:00','AGOTADA'),
(5,8,1,20.000,20.000,'2026-10-13T10:10:00',NULL,'ACTIVA');
SET IDENTITY_INSERT dbo.RESERVA_INVENTARIO OFF;

SET IDENTITY_INSERT dbo.MOVIMIENTO_INVENTARIO ON;
INSERT INTO dbo.MOVIMIENTO_INVENTARIO
    (id_movimiento,id_articulo,id_pedido,id_reserva,id_compra,numero_linea_compra,id_empleado,fec_hora,tipo_movimiento,cantidad,costo_unit,motivo,observaciones)
VALUES
(1, 1,NULL,NULL,1,1,9,'2026-09-15T10:00:00','ENTRADA_COMPRA',100.000,25.0000,'Compra de inventario','FAC-1001'),
(2, 2,NULL,NULL,1,2,9,'2026-09-15T10:01:00','ENTRADA_COMPRA',200.000, 2.0000,'Compra de inventario','FAC-1001'),
(3, 3,NULL,NULL,1,3,9,'2026-09-15T10:02:00','ENTRADA_COMPRA',1000.000,0.4000,'Compra de inventario','FAC-1001'),
(4, 9,NULL,NULL,1,4,9,'2026-09-15T10:03:00','ENTRADA_COMPRA',100.000,10.0000,'Compra de inventario','FAC-1001'),
(5, 4,NULL,NULL,2,1,9,'2026-09-18T11:00:00','ENTRADA_COMPRA',50.000,70.0000,'Compra de inventario','FAC-2001'),
(6, 5,NULL,NULL,2,2,9,'2026-09-18T11:01:00','ENTRADA_COMPRA',30.000,45.0000,'Compra de inventario','FAC-2001'),
(7, 6,NULL,NULL,3,1,9,'2026-09-20T12:00:00','ENTRADA_COMPRA',40.000,20.0000,'Compra de inventario','FAC-3001'),
(8, 7,NULL,NULL,3,2,9,'2026-09-20T12:01:00','ENTRADA_COMPRA',25.000,90.0000,'Compra de inventario','FAC-3001'),
(9, 8,NULL,NULL,3,3,9,'2026-09-20T12:02:00','ENTRADA_COMPRA',35.000,55.0000,'Compra de inventario','FAC-3001'),
(10,10,NULL,NULL,4,1,9,'2026-09-22T15:00:00','ENTRADA_COMPRA',30.000,50.0000,'Compra de inventario','FAC-1002'),
(11,1,3,1,NULL,NULL,12,'2026-10-08T09:00:00','SALIDA_PRODUCCION',6.000,25.0000,'Produccion pedido PED-0003','Tazas utilizadas'),
(12,2,3,2,NULL,NULL,12,'2026-10-08T09:01:00','SALIDA_PRODUCCION',8.000,2.0000,'Produccion pedido PED-0003','Papel utilizado'),
(13,3,3,3,NULL,NULL,12,'2026-10-08T09:02:00','SALIDA_PRODUCCION',30.000,0.4000,'Produccion pedido PED-0003','Tinta utilizada'),
(14,9,3,4,NULL,NULL,12,'2026-10-08T09:03:00','SALIDA_PRODUCCION',6.000,10.0000,'Produccion pedido PED-0003','Cajas utilizadas'),
(15,5,9,NULL,NULL,NULL,12,'2026-10-17T09:00:00','SALIDA_PRODUCCION',3.000,45.0000,'Produccion pedido PED-0009','Mouse pads utilizados'),
(16,4,4,NULL,NULL,NULL,12,'2026-10-09T09:00:00','SALIDA_PRODUCCION',2.000,70.0000,'Produccion pedido PED-0004','Camisetas utilizadas'),
(17,7,5,NULL,NULL,NULL,12,'2026-10-13T09:00:00','SALIDA_PRODUCCION',1.000,90.0000,'Produccion pedido PED-0005','Termo utilizado'),
(18,8,5,NULL,NULL,NULL,12,'2026-10-13T09:01:00','SALIDA_PRODUCCION',1.000,55.0000,'Produccion pedido PED-0005','Botella utilizada'),
(19,1,2,NULL,NULL,NULL,12,'2026-10-05T09:00:00','SALIDA_PRODUCCION',12.000,25.0000,'Produccion pedido PED-0002','Tazas utilizadas'),
(20,2,2,NULL,NULL,NULL,12,'2026-10-05T09:01:00','SALIDA_PRODUCCION',12.000,2.0000,'Produccion pedido PED-0002','Papel utilizado'),
(21,3,2,NULL,NULL,NULL,12,'2026-10-05T09:02:00','SALIDA_PRODUCCION',36.000,0.4000,'Produccion pedido PED-0002','Tinta utilizada'),
(22,9,2,NULL,NULL,NULL,12,'2026-10-05T09:03:00','SALIDA_PRODUCCION',12.000,10.0000,'Produccion pedido PED-0002','Cajas utilizadas'),
(23,1,3,1,NULL,NULL,12,'2026-10-08T10:00:00','SALIDA_PERDIDA',2.000,25.0000,'Tazas rotas durante produccion','Merma del pedido PED-0003'),
(24,2,NULL,NULL,NULL,NULL,12,'2026-10-09T08:00:00','SALIDA_PERDIDA',3.000,2.0000,'Papel danado por humedad','Perdida general de almacen'),
(25,3,3,3,NULL,NULL,12,'2026-10-08T10:01:00','SALIDA_PERDIDA',5.000,0.4000,'Tinta asociada a impresiones fallidas','Merma del pedido PED-0003'),
(26,10,3,NULL,NULL,NULL,12,'2026-10-08T09:04:00','SALIDA_PRODUCCION',1.000,50.0000,'Produccion pedido PED-0003','Cinta utilizada'),
(27,10,3,NULL,NULL,NULL,12,'2026-10-08T10:02:00','SALIDA_PERDIDA',1.500,50.0000,'Cinta descartada por pruebas','Merma del pedido PED-0003');
SET IDENTITY_INSERT dbo.MOVIMIENTO_INVENTARIO OFF;

SET IDENTITY_INSERT dbo.PERDIDA ON;
INSERT INTO dbo.PERDIDA
    (id_perdida, id_pedido, id_emp_reporta, id_etapa, fec_hora, tipo_incidente, motivo, descripcion, estado_registro)
VALUES
(1,3,12,3,'2026-10-08T10:05:00','PRODUCCION','Material danado durante sublimacion','Dos tazas rotas y tinta desperdiciada','CONFIRMADA'),
(2,NULL,12,NULL,'2026-10-09T08:05:00','ALMACENAMIENTO','Humedad en material','Tres hojas de papel inutilizables','CONFIRMADA'),
(3,3,12,3,'2026-10-08T10:06:00','PRODUCCION','Pruebas de posicionamiento','Cinta termica descartada','CONFIRMADA');
SET IDENTITY_INSERT dbo.PERDIDA OFF;

INSERT INTO dbo.DETALLE_PERDIDA
    (id_perdida, numero_linea, id_articulo, id_movimiento, cant_perdida, costo_unit_hist, descripcion_dano)
VALUES
(1,1,1,23,2.000,25.0000,'Tazas rotas durante prensado'),
(1,2,3,25,5.000, 0.4000,'Tinta consumida en impresiones fallidas'),
(2,1,2,24,3.000, 2.0000,'Papel afectado por humedad'),
(3,1,10,27,1.500,50.0000,'Cinta usada en pruebas no aprovechables');

--8. GASTOS Y AUDITORIA

SET IDENTITY_INSERT dbo.GASTO ON;
INSERT INTO dbo.GASTO
    (id_gasto,id_empleado,concepto,categoria,monto,fecha,metodo_pago,banco_receptor,referencia_bancaria,observaciones)
VALUES
(1,9,'Internet del local','SERVICIO',1200.00,'2026-10-01T09:00:00','TRANSFERENCIA','BAC','SERV-1001','Pago mensual'),
(2,9,'Publicidad Facebook','PUBLICIDAD',800.00,'2026-10-05T10:00:00','TARJETA',NULL,'META-1001','Campana de octubre'),
(3,12,'Transporte de materiales','TRANSPORTE',250.00,'2026-10-09T16:00:00','EFECTIVO',NULL,NULL,'Traslado desde proveedor'),
(4,9,'Energia electrica','SERVICIO',1800.00,'2026-10-20T09:00:00','TRANSFERENCIA','BANPRO','ENER-1001','Factura mensual');
SET IDENTITY_INSERT dbo.GASTO OFF;

SET IDENTITY_INSERT dbo.REGISTRO_AUDITORIA ON;
INSERT INTO dbo.REGISTRO_AUDITORIA
    (id_auditoria,id_empleado,fec_hora,accion,tipo_objeto_afectado,referencia_objeto,valor_anterior,valor_nuevo,motivo,origen_accion)
VALUES
(1,10,'2026-10-03T09:30:00','CREAR','PEDIDO','PED-0002',NULL,'Pedido creado','Solicitud del cliente','BACKEND'),
(2,11,'2026-10-07T10:00:00','APROBAR_DISENO','VERSION_DISENO','PED-0003-L1-V2','Pendiente','Aprobado','Confirmacion del cliente','BACKEND'),
(3,12,'2026-10-08T10:05:00','REGISTRAR_PERDIDA','PERDIDA','1',NULL,'Perdida registrada','Incidente de produccion','BACKEND'),
(4,9,'2026-10-12T10:00:00','AUTORIZAR_CANCELACION','PEDIDO','PED-0006','Activo','Cancelado','Solicitud del cliente','BACKEND');
SET IDENTITY_INSERT dbo.REGISTRO_AUDITORIA OFF;

COMMIT TRANSACTION;
GO

SELECT COUNT(*) AS CANTIDAD FROM dbo.PERSONA;

SELECT apellidos FROM PERSONA;
SELECT apellidos + ' ' + nombres AS nombrecompleto
FROM PERSONA
WHERE nombres LIKE 'A%'
GO

SELECT nombres + ' ' + apellidos AS NombreCompleto FROM PERSONA WHERE id_persona = 6 OR id_persona = 7;

SELECT nombres + ' ' + apellidos AS completo FROM PERSONA ORDER BY apellidos, nombres;

SELECT nombres, COUNT(*) AS completo FROM PERSONA GROUP BY nombres;

SELECT codigo_pedido FROM PEDIDO 

SELECT nombres, apellidos FROM PERSONA WHERE nombres LIKE 'M%'; 

SELECT id_cliente,fec_crea,estado,fec_entrega_prev FROM PEDIDO 

SELECT * FROM CLIENTE WHERE estado='ACTIVO'

SELECT * FROM PEDIDO 

SELECT * FROM PEDIDO WHERE total_pedido > 500

SELECT * FROM EMPLEADO WHERE fecha_ingreso >= '2024'

SELECT * FROM PRODUCTO ORDER BY nombre

SELECT * FROM VARIANTE_PRODUCTO ORDER BY precio_detalle DESC

SELECT* FROM PEDIDO WHERE estado IN ('ENTREGADO','LISTO')

SELECT id_producto, estado_publicacion,nombre FROM PRODUCTO ORDER BY nombre ASC



SELECT estado, COUNT(*) AS cant_pedido FROM PEDIDO GROUP BY estado  

SELECT estado, COUNT(*) AS estado_cl FROM CLIENTE GROUP BY estado

SElECT estado_publicacion, COUNT(*) AS publicadp FROM PRODUCTO GROUP BY estado_publicacion

SELECT AVG(precio_detalle)AS precio_promedio, MIN(precio_detalle) AS pre_min,MAX(precio_detalle)AS prec_max FROM VARIANTE_PRODUCTO

SELECT P.id_persona, P.nombres + ' ' + P.apellidos AS cliente FROM PERSONA AS P ON P.id_persona = C.id_persona 
LEFT JOIN PEDIDO AS PE
    ON C.id_persona = PE.id_cliente
GROUP BY P.id_persona, P.nombres, P.apellidos
ORDER BY nombres

SELECT e.id_persona, COUNT(*) AS cant_rol FROM EMPLEADO AS e 
INNER JOIN ASIGNACION_ROL AS asig ON e.id_persona = asig.id_empleado 
GROUP BY id_persona

SELECT TOP 1 p.id_producto, p.nombre AS producto, SUM(DP.cantidad) AS unidades_vendidas FROM PRODUCTO AS P
INNER JOIN VARIANTE_PRODUCTO AS v ON p.id_producto = v.id_producto
INNER JOIN DETALLE_PEDIDO AS DP ON v.id_variante = DP.id_variante
INNER JOIN PEDIDO AS pe ON DP.id_pedido = pe.id_pedido
WHERE pe.estado IN ('PAGADO', 'PRODUCCION', 'LISTO', 'ENTREGADO')
GROUP BY p.id_producto, p.nombre
ORDER BY unidades_vendidas DESC;

SELECT p.id_persona, p.nombres, p.apellidos, r.nombre AS Rol FROM PERSONA AS p
INNER JOIN  EMPLEADO AS E ON p.id_persona = E.id_persona
INNER JOIN ASIGNACION_ROL AS ar ON E.id_persona = ar.id_empleado
INNER JOIN ROL AS r ON ar.id_rol = r.id_rol 
ORDER BY P.nombres, p.apellidos