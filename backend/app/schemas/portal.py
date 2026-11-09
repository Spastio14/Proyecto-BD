from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class PortalProductLine(BaseModel):
    producto: str
    variante: str
    cantidad: int
    precio_unitario: Decimal
    importe: Decimal
    personalizacion: str | None = None


class PortalHistoryItem(BaseModel):
    fecha: datetime
    estado: str
    detalle: str | None = None


class PortalPaymentMilestone(BaseModel):
    numero: int
    tipo: str
    monto: Decimal
    pagado: Decimal
    pendiente_verificacion: Decimal
    saldo: Decimal
    disponible_reportar: Decimal
    estado: str
    puede_reportar: bool


class PortalOrder(BaseModel):
    codigo: str
    fecha: datetime
    fecha_entrega_prevista: datetime
    estado: str
    total: Decimal
    pagado: Decimal
    saldo_pendiente: Decimal
    modalidad_entrega: str
    estado_entrega: str | None = None
    proxima_accion: str
    requiere_produccion: bool
    productos: list[PortalProductLine]
    puede_cancelar: bool = False
    motivo_bloqueo_cancelacion: str | None = None


class PortalOrderDetail(PortalOrder):
    historial: list[PortalHistoryItem]
    hitos_pago: list[PortalPaymentMilestone]


class PortalQuote(BaseModel):
    referencia: str
    fecha: datetime
    vencimiento: datetime
    estado: str
    total: Decimal
    productos: list[PortalProductLine]


class PortalPayment(BaseModel):
    id_transaccion: int
    pedido: str
    fecha: datetime
    monto: Decimal
    estado: str
    metodo: str
    banco_origen: str | None = None
    referencia: str | None = None


class PortalSummary(BaseModel):
    pedidos_activos: int
    cotizaciones_pendientes: int
    pagos_pendientes: int
    pedidos_listos: int
    saldo_total: Decimal
    limite_pedidos_activos: int
    puede_crear_pedido: bool
    motivo_bloqueo_pedido: str | None = None
    pedido_destacado: PortalOrder | None = None


class PortalCatalogItem(BaseModel):
    id_producto: int
    id_variante: int
    codigo: str
    producto: str
    categoria: str
    descripcion: str
    variante: str
    precio_referencia: Decimal
    disponibilidad: str
    causa_disponibilidad: str | None = None
    requiere_produccion: bool
    imagen_url: str | None = None


class PortalPricePreview(BaseModel):
    precio_unitario: Decimal
    descuento: Decimal
    total: Decimal
    modo_precio: str


class PortalPaymentReport(BaseModel):
    id_transaccion: int
    pedido: str
    fecha_reporte: datetime
    monto: Decimal
    estado: str
    total_verificado: Decimal
    saldo_pendiente: Decimal
    banco_origen: str
    referencia: str
    mensaje_whatsapp: str
    whatsapp_url: str | None = None
