from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

money = Numeric(19, 2)
quantity = Numeric(18, 3)
unit_cost = Numeric(19, 4)
instant = DateTime(timezone=True)


class Persona(Base):
    __tablename__ = "persona"
    id_persona: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombres: Mapped[str] = mapped_column(String(120))
    apellidos: Mapped[str | None] = mapped_column(String(120))
    telefono_contacto: Mapped[str | None] = mapped_column(String(30))
    correo_electronico: Mapped[str | None] = mapped_column(String(254))
    documento_identificacion: Mapped[str | None] = mapped_column(String(120))
    direccion_habitual: Mapped[str | None] = mapped_column(String(500))


class CuentaAcceso(Base):
    __tablename__ = "cuenta_acceso"
    id_cuenta: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_persona: Mapped[int] = mapped_column(ForeignKey("persona.id_persona"))
    identificador_autenticacion: Mapped[str] = mapped_column(String(255))
    fecha_activacion: Mapped[datetime] = mapped_column(instant)
    estado_cuenta: Mapped[str] = mapped_column(String(80))
    ultimo_acceso: Mapped[datetime | None] = mapped_column(instant)


class Cliente(Base):
    __tablename__ = "cliente"
    id_persona: Mapped[int] = mapped_column(ForeignKey("persona.id_persona"), primary_key=True)
    tipo_cliente: Mapped[str] = mapped_column(String(80))
    condicion_comercial: Mapped[str] = mapped_column(String(255))
    fecha_registro: Mapped[datetime] = mapped_column(instant)
    origen_registro: Mapped[str] = mapped_column(String(80))
    estado: Mapped[str] = mapped_column(String(80))


class Empleado(Base):
    __tablename__ = "empleado"
    id_persona: Mapped[int] = mapped_column(ForeignKey("persona.id_persona"), primary_key=True)
    codigo_empleado: Mapped[str] = mapped_column(String(64))
    fecha_ingreso: Mapped[datetime] = mapped_column(instant)
    estado_laboral: Mapped[str] = mapped_column(String(80))
    capacidad_maxima_asignaciones: Mapped[int] = mapped_column(Integer)


class Rol(Base):
    __tablename__ = "rol"
    id_rol: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(180))
    descripcion: Mapped[str] = mapped_column(String(500))
    estado: Mapped[str] = mapped_column(String(80))


class Permiso(Base):
    __tablename__ = "permiso"
    id_permiso: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo_permiso: Mapped[str] = mapped_column(String(64))
    descripcion: Mapped[str] = mapped_column(String(500))
    modulo: Mapped[str] = mapped_column(String(255))


class AsignacionRol(Base):
    __tablename__ = "asignacion_rol"
    id_asignacion_rol: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_empleado: Mapped[int] = mapped_column(ForeignKey("empleado.id_persona"))
    id_rol: Mapped[int] = mapped_column(ForeignKey("rol.id_rol"))
    fecha_asignacion: Mapped[datetime] = mapped_column(instant)
    fecha_finalizacion: Mapped[datetime | None] = mapped_column(instant)
    estado: Mapped[str] = mapped_column(String(80))


class RolPermiso(Base):
    __tablename__ = "rol_permiso"
    id_rol: Mapped[int] = mapped_column(ForeignKey("rol.id_rol"), primary_key=True)
    id_permiso: Mapped[int] = mapped_column(ForeignKey("permiso.id_permiso"), primary_key=True)


class Categoria(Base):
    __tablename__ = "categoria"
    id_categoria: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(180))
    descripcion: Mapped[str | None] = mapped_column(String(500))
    estado: Mapped[str] = mapped_column(String(80))


class Producto(Base):
    __tablename__ = "producto"
    id_producto: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_categoria: Mapped[int] = mapped_column(ForeignKey("categoria.id_categoria"))
    nombre: Mapped[str] = mapped_column(String(180))
    descripcion: Mapped[str | None] = mapped_column(String(500))
    informacion_comercial: Mapped[str] = mapped_column(Text)
    estado_publicacion: Mapped[str] = mapped_column(String(80))
    ruta_imagen_principal: Mapped[str | None] = mapped_column(String(1000))
    imagen_mime: Mapped[str | None] = mapped_column(String(100))
    imagen_tamano_bytes: Mapped[int | None] = mapped_column(BigInteger)


class VarianteProducto(Base):
    __tablename__ = "variante_producto"
    id_variante: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_producto: Mapped[int] = mapped_column(ForeignKey("producto.id_producto"))
    codigo_variante: Mapped[str] = mapped_column(String(64))
    caracteristicas: Mapped[str | None] = mapped_column(String(500))
    precio_detalle: Mapped[Decimal] = mapped_column(money)
    requiere_produccion: Mapped[bool] = mapped_column(Boolean)
    estado: Mapped[str] = mapped_column(String(80))


class EscalaPrecio(Base):
    __tablename__ = "escala_precio"
    id_variante: Mapped[int] = mapped_column(
        ForeignKey("variante_producto.id_variante"), primary_key=True
    )
    numero_rango: Mapped[int] = mapped_column(Integer, primary_key=True)
    cantidad_minima: Mapped[int] = mapped_column(Integer)
    cantidad_maxima: Mapped[int | None] = mapped_column(Integer)
    precio_unitario_mayorista: Mapped[Decimal] = mapped_column(money)
    estado: Mapped[str] = mapped_column(String(80))


class Promocion(Base):
    __tablename__ = "promocion"
    id_promocion: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(180))
    tipo: Mapped[str] = mapped_column(String(255))
    cantidad_requerida: Mapped[int] = mapped_column(Integer)
    beneficio: Mapped[str] = mapped_column(Text)
    fecha_inicio: Mapped[datetime] = mapped_column(instant)
    fecha_fin: Mapped[datetime] = mapped_column(instant)
    condiciones: Mapped[str | None] = mapped_column(Text)
    permite_combinacion_mayorista: Mapped[bool] = mapped_column(Boolean)
    valor_beneficio: Mapped[Decimal] = mapped_column(money)
    estado: Mapped[str] = mapped_column(String(20))


class PromocionVariante(Base):
    __tablename__ = "promocion_variante"
    id_promocion: Mapped[int] = mapped_column(
        ForeignKey("promocion.id_promocion"), primary_key=True
    )
    id_variante: Mapped[int] = mapped_column(
        ForeignKey("variante_producto.id_variante"), primary_key=True
    )


class ArticuloInventariable(Base):
    __tablename__ = "articulo_inventariable"
    id_articulo: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(64))
    nombre: Mapped[str] = mapped_column(String(180))
    tipo_articulo: Mapped[str] = mapped_column(String(80))
    unidad_medida: Mapped[str] = mapped_column(String(80))
    existencia_actual: Mapped[Decimal] = mapped_column(quantity)
    existencia_minima: Mapped[Decimal] = mapped_column(quantity)
    costo_referencia: Mapped[Decimal] = mapped_column(unit_cost)
    estado: Mapped[str] = mapped_column(String(80))


class ComposicionProducto(Base):
    __tablename__ = "composicion_producto"
    id_variante: Mapped[int] = mapped_column(
        ForeignKey("variante_producto.id_variante"), primary_key=True
    )
    id_articulo: Mapped[int] = mapped_column(
        ForeignKey("articulo_inventariable.id_articulo"), primary_key=True
    )
    cantidad_estandar: Mapped[Decimal] = mapped_column(quantity)
    observaciones: Mapped[str] = mapped_column(Text)


class Cotizacion(Base):
    __tablename__ = "cotizacion"
    id_cotizacion: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_cliente: Mapped[int] = mapped_column(ForeignKey("cliente.id_persona"))
    fecha_emision: Mapped[datetime] = mapped_column(instant)
    fecha_vencimiento: Mapped[datetime] = mapped_column(instant)
    estado: Mapped[str] = mapped_column(String(80))
    total_ofrecido: Mapped[Decimal] = mapped_column(money)
    observaciones: Mapped[str | None] = mapped_column(Text)


class DetalleCotizacion(Base):
    __tablename__ = "detalle_cotizacion"
    id_cotizacion: Mapped[int] = mapped_column(
        ForeignKey("cotizacion.id_cotizacion"), primary_key=True
    )
    numero_linea: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_variante: Mapped[int] = mapped_column(ForeignKey("variante_producto.id_variante"))
    cantidad: Mapped[int] = mapped_column(Integer)
    descripcion_personalizacion: Mapped[str | None] = mapped_column(Text)
    precio_ofrecido: Mapped[Decimal] = mapped_column(money)
    descuento_ofrecido: Mapped[Decimal] = mapped_column(money)


class Pedido(Base):
    __tablename__ = "pedido"
    id_pedido: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_cliente: Mapped[int] = mapped_column(ForeignKey("cliente.id_persona"))
    id_empleado_registro: Mapped[int | None] = mapped_column(ForeignKey("empleado.id_persona"))
    id_etapa_actual: Mapped[int | None] = mapped_column(Integer)
    id_cotizacion: Mapped[int | None] = mapped_column(ForeignKey("cotizacion.id_cotizacion"))
    codigo_pedido: Mapped[str] = mapped_column(String(64))
    fecha_creacion: Mapped[datetime] = mapped_column(instant)
    vencimiento_pago: Mapped[datetime] = mapped_column(instant)
    fecha_inicio_revision_pago: Mapped[datetime | None] = mapped_column(instant)
    canal_origen: Mapped[str] = mapped_column(String(80))
    estado: Mapped[str] = mapped_column(String(80))
    fecha_entrega_prevista: Mapped[datetime] = mapped_column(instant)
    modalidad_entrega: Mapped[str] = mapped_column(String(80))
    nombre_persona_retiro: Mapped[str | None] = mapped_column(String(120))
    total_pedido: Mapped[Decimal] = mapped_column(money)
    token_seguimiento: Mapped[UUID] = mapped_column(Uuid)


class DetallePedido(Base):
    __tablename__ = "detalle_pedido"
    id_pedido: Mapped[int] = mapped_column(ForeignKey("pedido.id_pedido"), primary_key=True)
    numero_linea: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_variante: Mapped[int] = mapped_column(ForeignKey("variante_producto.id_variante"))
    cantidad: Mapped[int] = mapped_column(Integer)
    precio_unitario_aplicado: Mapped[Decimal] = mapped_column(money)
    descuento_aplicado: Mapped[Decimal] = mapped_column(money)
    importe_pactado: Mapped[Decimal] = mapped_column(money)
    costo_estimado: Mapped[Decimal] = mapped_column(money)
    costo_real_consolidado: Mapped[Decimal | None] = mapped_column(money)
    modo_precio: Mapped[str] = mapped_column(String(20))
    id_promocion: Mapped[int | None] = mapped_column(ForeignKey("promocion.id_promocion"))
    descripcion_personalizacion: Mapped[str | None] = mapped_column(Text)


class HistorialPedido(Base):
    __tablename__ = "historial_pedido"
    id_historial: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_pedido: Mapped[int] = mapped_column(ForeignKey("pedido.id_pedido"))
    id_empleado: Mapped[int | None] = mapped_column(ForeignKey("empleado.id_persona"))
    id_etapa_anterior: Mapped[int | None] = mapped_column(Integer)
    id_etapa_nueva: Mapped[int | None] = mapped_column(Integer)
    fecha_hora: Mapped[datetime] = mapped_column(instant)
    estado_anterior: Mapped[str | None] = mapped_column(String(80))
    estado_nuevo: Mapped[str] = mapped_column(String(80))
    motivo: Mapped[str | None] = mapped_column(String(500))
    origen_cambio: Mapped[str] = mapped_column(String(80))


class HitoPago(Base):
    __tablename__ = "hito_pago"
    id_pedido: Mapped[int] = mapped_column(ForeignKey("pedido.id_pedido"), primary_key=True)
    numero_hito: Mapped[int] = mapped_column(Integer, primary_key=True)
    tipo_hito: Mapped[str] = mapped_column(String(80))
    monto_exigido: Mapped[Decimal] = mapped_column(money)
    fecha_vencimiento: Mapped[datetime] = mapped_column(instant)
    estado: Mapped[str] = mapped_column(String(80))


class Transaccion(Base):
    __tablename__ = "transaccion"
    id_transaccion: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_pedido: Mapped[int] = mapped_column(ForeignKey("pedido.id_pedido"))
    numero_hito: Mapped[int | None] = mapped_column(Integer)
    id_empleado_verificador: Mapped[int | None] = mapped_column(ForeignKey("empleado.id_persona"))
    id_transaccion_compensada: Mapped[int | None] = mapped_column(Integer)
    id_reembolso: Mapped[int | None] = mapped_column(Integer)
    fecha_hora: Mapped[datetime] = mapped_column(instant)
    tipo_transaccion: Mapped[str] = mapped_column(String(80))
    monto_con_signo: Mapped[Decimal] = mapped_column(money)
    metodo_pago: Mapped[str] = mapped_column(String(80))
    banco_origen: Mapped[str | None] = mapped_column(String(120))
    banco_receptor: Mapped[str | None] = mapped_column(String(120))
    referencia_bancaria: Mapped[str | None] = mapped_column(String(120))
    estado_verificacion: Mapped[str] = mapped_column(String(80))
    fecha_verificacion: Mapped[datetime | None] = mapped_column(instant)
    clave_idem: Mapped[UUID] = mapped_column(Uuid)
    ruta_comprobante: Mapped[str | None] = mapped_column(String(1000))
    comprobante_mime: Mapped[str | None] = mapped_column(String(100))
    comprobante_tamano_bytes: Mapped[int | None] = mapped_column(BigInteger)


class AplicacionTransaccionHito(Base):
    __tablename__ = "aplicacion_transaccion_hito"
    id_transaccion: Mapped[int] = mapped_column(
        ForeignKey("transaccion.id_transaccion"), primary_key=True
    )
    id_pedido: Mapped[int] = mapped_column(ForeignKey("pedido.id_pedido"))
    numero_hito: Mapped[int] = mapped_column(Integer, primary_key=True)
    monto_aplicado: Mapped[Decimal] = mapped_column(money)


class Caja(Base):
    __tablename__ = "caja"
    id_caja: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_empleado_apertura: Mapped[int] = mapped_column(ForeignKey("empleado.id_persona"))
    id_empleado_cierre: Mapped[int | None] = mapped_column(ForeignKey("empleado.id_persona"))
    fecha_apertura: Mapped[datetime] = mapped_column(instant)
    fecha_cierre: Mapped[datetime | None] = mapped_column(instant)
    saldo_inicial: Mapped[Decimal] = mapped_column(money)
    saldo_cierre_declarado: Mapped[Decimal | None] = mapped_column(money)
    estado: Mapped[str] = mapped_column(String(20))


class MovimientoCaja(Base):
    __tablename__ = "movimiento_caja"
    id_movimiento_caja: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_caja: Mapped[int] = mapped_column(ForeignKey("caja.id_caja"))
    id_transaccion: Mapped[int] = mapped_column(ForeignKey("transaccion.id_transaccion"))
    id_empleado: Mapped[int] = mapped_column(ForeignKey("empleado.id_persona"))
    fecha_hora: Mapped[datetime] = mapped_column(instant)
    tipo_movimiento: Mapped[str] = mapped_column(String(40))
    monto: Mapped[Decimal] = mapped_column(money)
    folio_recibo: Mapped[str] = mapped_column(String(80))


class ReservaInventario(Base):
    __tablename__ = "reserva_inventario"
    id_reserva: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_pedido: Mapped[int] = mapped_column(ForeignKey("pedido.id_pedido"))
    id_articulo: Mapped[int] = mapped_column(ForeignKey("articulo_inventariable.id_articulo"))
    cantidad_reservada: Mapped[Decimal] = mapped_column(quantity)
    cantidad_pendiente: Mapped[Decimal] = mapped_column(quantity)
    fecha_reserva: Mapped[datetime] = mapped_column(instant)
    fecha_liberacion: Mapped[datetime | None] = mapped_column(instant)
    estado: Mapped[str] = mapped_column(String(80))


class MovimientoInventario(Base):
    __tablename__ = "movimiento_inventario"
    id_movimiento: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_articulo: Mapped[int] = mapped_column(ForeignKey("articulo_inventariable.id_articulo"))
    id_pedido: Mapped[int | None] = mapped_column(ForeignKey("pedido.id_pedido"))
    id_reserva: Mapped[int | None] = mapped_column(ForeignKey("reserva_inventario.id_reserva"))
    id_compra: Mapped[int | None] = mapped_column(Integer)
    numero_linea_compra: Mapped[int | None] = mapped_column(Integer)
    id_empleado: Mapped[int | None] = mapped_column(ForeignKey("empleado.id_persona"))
    fecha_hora: Mapped[datetime] = mapped_column(instant)
    tipo_movimiento: Mapped[str] = mapped_column(String(80))
    cantidad: Mapped[Decimal] = mapped_column(quantity)
    costo_unitario_aplicado: Mapped[Decimal] = mapped_column(unit_cost)
    motivo: Mapped[str] = mapped_column(String(500))
    observaciones: Mapped[str | None] = mapped_column(Text)


class Cancelacion(Base):
    __tablename__ = "cancelacion"
    id_cancelacion: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_pedido: Mapped[int] = mapped_column(ForeignKey("pedido.id_pedido"))
    id_empleado_autoriza: Mapped[int | None] = mapped_column(ForeignKey("empleado.id_persona"))
    fecha_hora: Mapped[datetime] = mapped_column(instant)
    motivo: Mapped[str] = mapped_column(String(500))
    etapa_cancelacion: Mapped[str] = mapped_column(String(255))
    monto_retenido: Mapped[Decimal] = mapped_column(money)
    resultado: Mapped[str] = mapped_column(String(80))
    fecha_confirmacion_autenticacion: Mapped[datetime | None] = mapped_column(instant)


class VersionDiseno(Base):
    __tablename__ = "version_diseno"
    id_pedido: Mapped[int] = mapped_column(ForeignKey("pedido.id_pedido"), primary_key=True)
    numero_linea: Mapped[int] = mapped_column(Integer, primary_key=True)
    numero_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre_archivo: Mapped[str] = mapped_column(String(180))
    ruta_archivo: Mapped[str] = mapped_column(String(1000))
    fecha_creacion: Mapped[datetime] = mapped_column(instant)
    observaciones: Mapped[str | None] = mapped_column(Text)
    es_aprobado: Mapped[bool] = mapped_column(Boolean)


class AprobacionDiseno(Base):
    __tablename__ = "aprobacion_diseno"
    id_aprobacion: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_pedido: Mapped[int] = mapped_column(Integer)
    numero_linea: Mapped[int] = mapped_column(Integer)
    numero_version: Mapped[int] = mapped_column(Integer)
    id_empleado_registro: Mapped[int | None] = mapped_column(ForeignKey("empleado.id_persona"))
    fecha_aprobacion: Mapped[datetime] = mapped_column(instant)
    medio_confirmacion: Mapped[str] = mapped_column(String(255))
    observacion: Mapped[str | None] = mapped_column(String(500))
    tipo_decision: Mapped[str] = mapped_column(String(80))


class Perdida(Base):
    __tablename__ = "perdida"
    id_perdida: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_pedido: Mapped[int | None] = mapped_column(ForeignKey("pedido.id_pedido"))
    id_empleado_reporta: Mapped[int] = mapped_column(ForeignKey("empleado.id_persona"))
    id_etapa: Mapped[int | None] = mapped_column(Integer)
    fecha_hora: Mapped[datetime] = mapped_column(instant)
    momento_ocurrencia: Mapped[str] = mapped_column(String(80))
    tipo_incidente: Mapped[str] = mapped_column(String(80))
    motivo: Mapped[str] = mapped_column(String(500))
    descripcion: Mapped[str | None] = mapped_column(String(500))
    estado_registro: Mapped[str] = mapped_column(String(80))


class DetallePerdida(Base):
    __tablename__ = "detalle_perdida"
    id_perdida: Mapped[int] = mapped_column(ForeignKey("perdida.id_perdida"), primary_key=True)
    numero_linea: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_articulo: Mapped[int] = mapped_column(ForeignKey("articulo_inventariable.id_articulo"))
    id_movimiento: Mapped[int] = mapped_column(ForeignKey("movimiento_inventario.id_movimiento"))
    cantidad_perdida: Mapped[Decimal] = mapped_column(quantity)
    costo_unitario_historico: Mapped[Decimal] = mapped_column(unit_cost)
    descripcion_dano: Mapped[str | None] = mapped_column(String(500))


class RegistroAuditoria(Base):
    __tablename__ = "registro_auditoria"
    id_auditoria: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_persona_actor: Mapped[int | None] = mapped_column(ForeignKey("persona.id_persona"))
    fecha_hora: Mapped[datetime] = mapped_column(instant)
    accion: Mapped[str] = mapped_column(String(255))
    tipo_objeto_afectado: Mapped[str] = mapped_column(String(80))
    referencia_objeto: Mapped[str] = mapped_column(String(120))
    valor_anterior: Mapped[str | None] = mapped_column(Text)
    valor_nuevo: Mapped[str | None] = mapped_column(Text)
    motivo: Mapped[str] = mapped_column(String(500))
    origen_accion: Mapped[str] = mapped_column(String(80))


class EtapaProceso(Base):
    __tablename__ = "etapa_proceso"
    id_etapa: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(180))
    descripcion: Mapped[str | None] = mapped_column(String(500))
    orden_referencia: Mapped[int] = mapped_column(Integer)
    estado: Mapped[str] = mapped_column(String(80))


class AsignacionEtapa(Base):
    __tablename__ = "asignacion_etapa"
    id_asignacion: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_pedido: Mapped[int] = mapped_column(ForeignKey("pedido.id_pedido"))
    id_etapa: Mapped[int] = mapped_column(ForeignKey("etapa_proceso.id_etapa"))
    id_empleado: Mapped[int] = mapped_column(ForeignKey("empleado.id_persona"))
    fecha_inicio: Mapped[datetime] = mapped_column(instant)
    fecha_fin: Mapped[datetime | None] = mapped_column(instant)
    origen_asignacion: Mapped[str] = mapped_column(String(80))
    estado: Mapped[str] = mapped_column(String(80))
    motivo_reasignacion: Mapped[str | None] = mapped_column(String(500))


class SolicitudCambio(Base):
    __tablename__ = "solicitud_cambio"
    id_solicitud_cambio: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_pedido: Mapped[int] = mapped_column(ForeignKey("pedido.id_pedido"))
    fecha_solicitud: Mapped[datetime] = mapped_column(instant)
    descripcion: Mapped[str] = mapped_column(String(500))
    motivo: Mapped[str | None] = mapped_column(String(500))
    decision: Mapped[str | None] = mapped_column(String(80))
    costo_adicional_estimado: Mapped[Decimal] = mapped_column(money)
    cargo_adicional_aprobado: Mapped[Decimal | None] = mapped_column(money)


class Reembolso(Base):
    __tablename__ = "reembolso"
    id_reembolso: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_cancelacion: Mapped[int] = mapped_column(ForeignKey("cancelacion.id_cancelacion"))
    fecha_solicitud: Mapped[datetime] = mapped_column(instant)
    monto_solicitado: Mapped[Decimal] = mapped_column(money)
    monto_aprobado: Mapped[Decimal] = mapped_column(money)
    motivo: Mapped[str] = mapped_column(String(500))
    estado: Mapped[str] = mapped_column(String(80))
    fecha_resolucion: Mapped[datetime | None] = mapped_column(instant)


class Proveedor(Base):
    __tablename__ = "proveedor"
    id_proveedor: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(180))
    telefono: Mapped[str | None] = mapped_column(String(30))
    correo: Mapped[str | None] = mapped_column(String(254))
    direccion: Mapped[str | None] = mapped_column(String(500))
    estado: Mapped[str] = mapped_column(String(80))


class Compra(Base):
    __tablename__ = "compra"
    id_compra: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_proveedor: Mapped[int] = mapped_column(ForeignKey("proveedor.id_proveedor"))
    fecha_compra: Mapped[datetime] = mapped_column(instant)
    numero_documento: Mapped[str | None] = mapped_column(String(120))
    estado: Mapped[str] = mapped_column(String(80))
    total_compra: Mapped[Decimal] = mapped_column(money)


class DetalleCompra(Base):
    __tablename__ = "detalle_compra"
    id_compra: Mapped[int] = mapped_column(ForeignKey("compra.id_compra"), primary_key=True)
    numero_linea: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_articulo: Mapped[int] = mapped_column(ForeignKey("articulo_inventariable.id_articulo"))
    cantidad_comprada: Mapped[Decimal] = mapped_column(quantity)
    costo_unitario_compra: Mapped[Decimal] = mapped_column(unit_cost)
    importe: Mapped[Decimal] = mapped_column(money)


class Gasto(Base):
    __tablename__ = "gasto"
    id_gasto: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_empleado: Mapped[int] = mapped_column(ForeignKey("empleado.id_persona"))
    concepto: Mapped[str] = mapped_column(String(80))
    categoria: Mapped[str] = mapped_column(String(80))
    monto: Mapped[Decimal] = mapped_column(money)
    fecha: Mapped[datetime] = mapped_column(instant)
    metodo_pago: Mapped[str] = mapped_column(String(80))
    banco_receptor: Mapped[str | None] = mapped_column(String(120))
    referencia_bancaria: Mapped[str | None] = mapped_column(String(120))
    observaciones: Mapped[str | None] = mapped_column(Text)


class AgenciaEnvio(Base):
    __tablename__ = "agencia_envio"
    id_agencia: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(180))
    tipo_agencia: Mapped[str] = mapped_column(String(80))
    telefono: Mapped[str | None] = mapped_column(String(30))
    estado: Mapped[str] = mapped_column(String(80))


class Envio(Base):
    __tablename__ = "envio"
    id_envio: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_pedido: Mapped[int] = mapped_column(ForeignKey("pedido.id_pedido"))
    id_agencia: Mapped[int | None] = mapped_column(ForeignKey("agencia_envio.id_agencia"))
    direccion_entrega: Mapped[str] = mapped_column(String(500))
    nombre_receptor: Mapped[str] = mapped_column(String(120))
    telefono_receptor: Mapped[str | None] = mapped_column(String(30))
    tarifa_acordada: Mapped[Decimal] = mapped_column(money)
    fecha_programada: Mapped[datetime | None] = mapped_column(instant)
    fecha_entrega_real: Mapped[datetime | None] = mapped_column(instant)
    estado: Mapped[str] = mapped_column(String(80))
