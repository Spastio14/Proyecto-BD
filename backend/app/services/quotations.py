from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import Conflict, NotFound, PermissionDenied
from app.core.security import Principal
from app.domain.money import ZERO, minimum_advance, money
from app.models.entities import (
    Cotizacion,
    DetalleCotizacion,
    DetallePedido,
    HistorialPedido,
    HitoPago,
    Pedido,
)
from app.repositories.locks import lock_client
from app.services.audit import AuditService
from app.services.authorization import AuthorizationService
from app.services.pricing import PricingService


@dataclass(frozen=True, slots=True)
class QuoteLineInput:
    variant_id: int
    quantity: int
    customization: str | None = None


class QuotationService:
    def __init__(self, pricing: PricingService | None = None):
        self.pricing = pricing or PricingService()

    def create(
        self,
        session: Session,
        *,
        principal: Principal,
        lines: list[QuoteLineInput],
        observations: str | None = None,
    ) -> Cotizacion:
        client = lock_client(session, principal.persona_id)
        if not lines:
            raise Conflict("La cotización requiere líneas")
        priced = [
            self.pricing.price_line(
                session,
                client_type=client.tipo_cliente,
                variant_id=line.variant_id,
                quantity=line.quantity,
            )
            for line in lines
        ]
        now = datetime.now(UTC)
        quote = Cotizacion(
            id_cliente=client.id_persona,
            fecha_emision=now,
            fecha_vencimiento=now + timedelta(days=7),
            estado="EMITIDA",
            total_ofrecido=money(sum((item.total for item in priced), ZERO)),
            observaciones=observations,
        )
        session.add(quote)
        session.flush()
        for number, (line, result) in enumerate(zip(lines, priced, strict=True), start=1):
            session.add(
                DetalleCotizacion(
                    id_cotizacion=quote.id_cotizacion,
                    numero_linea=number,
                    id_variante=line.variant_id,
                    cantidad=line.quantity,
                    descripcion_personalizacion=line.customization,
                    precio_ofrecido=result.unit_price,
                    descuento_ofrecido=result.discount,
                )
            )
        session.flush()
        return quote

    @staticmethod
    def list_owned(session: Session, principal: Principal) -> list[Cotizacion]:
        statement = select(Cotizacion).order_by(Cotizacion.fecha_emision.desc())
        if principal.is_employee:
            AuthorizationService.require(session, principal, "PEDIDO_GESTIONAR")
        else:
            statement = statement.where(Cotizacion.id_cliente == principal.persona_id)
        return list(session.scalars(statement))

    def convert(self, session: Session, *, quote_id: int, principal: Principal) -> Pedido:
        quote = session.scalar(
            select(Cotizacion).where(Cotizacion.id_cotizacion == quote_id).with_for_update()
        )
        if quote is None:
            raise NotFound("Cotización no encontrada")
        if principal.is_employee:
            AuthorizationService.require(session, principal, "PEDIDO_GESTIONAR")
        elif quote.id_cliente != principal.persona_id:
            raise PermissionDenied("La cotización pertenece a otro cliente")
        if quote.estado != "ACEPTADA" or quote.fecha_vencimiento < datetime.now(UTC):
            raise Conflict("La cotización no está aceptada y vigente")
        if session.scalar(select(Pedido.id_pedido).where(Pedido.id_cotizacion == quote_id)):
            raise Conflict("La cotización ya fue convertida")
        lock_client(session, quote.id_cliente)
        details = list(
            session.scalars(
                select(DetalleCotizacion)
                .where(DetalleCotizacion.id_cotizacion == quote_id)
                .order_by(DetalleCotizacion.numero_linea)
            )
        )
        now = datetime.now(UTC)
        order = Pedido(
            id_cliente=quote.id_cliente,
            id_empleado_registro=principal.persona_id if principal.is_employee else None,
            id_etapa_actual=None,
            id_cotizacion=quote.id_cotizacion,
            codigo_pedido=f"PED-{uuid4().hex[:16].upper()}",
            fecha_creacion=now,
            vencimiento_pago=now + timedelta(hours=24),
            fecha_inicio_revision_pago=None,
            canal_origen="COTIZACION",
            estado="PENDIENTE_PAGO",
            fecha_entrega_prevista=now + timedelta(days=7),
            modalidad_entrega="RETIRO",
            nombre_persona_retiro=None,
            total_pedido=quote.total_ofrecido,
            token_seguimiento=uuid4(),
        )
        session.add(order)
        session.flush()
        for detail in details:
            total = money(detail.precio_ofrecido * detail.cantidad - detail.descuento_ofrecido)
            estimated = self.pricing._estimated_cost(session, detail.id_variante, detail.cantidad)
            session.add(
                DetallePedido(
                    id_pedido=order.id_pedido,
                    numero_linea=detail.numero_linea,
                    id_variante=detail.id_variante,
                    cantidad=detail.cantidad,
                    precio_unitario_aplicado=detail.precio_ofrecido,
                    descuento_aplicado=detail.descuento_ofrecido,
                    importe_pactado=total,
                    costo_estimado=estimated,
                    costo_real_consolidado=None,
                    modo_precio="COTIZADO",
                    id_promocion=None,
                )
            )
        advance = minimum_advance(quote.total_ofrecido)
        session.add_all(
            [
                HitoPago(
                    id_pedido=order.id_pedido,
                    numero_hito=1,
                    tipo_hito="ANTICIPO",
                    monto_exigido=advance,
                    fecha_vencimiento=order.vencimiento_pago,
                    estado="PENDIENTE",
                ),
                HitoPago(
                    id_pedido=order.id_pedido,
                    numero_hito=2,
                    tipo_hito="SALDO",
                    monto_exigido=money(quote.total_ofrecido - advance),
                    fecha_vencimiento=order.fecha_entrega_prevista,
                    estado="PENDIENTE",
                ),
                HistorialPedido(
                    id_pedido=order.id_pedido,
                    id_empleado=principal.persona_id if principal.is_employee else None,
                    id_etapa_anterior=None,
                    id_etapa_nueva=None,
                    fecha_hora=now,
                    estado_anterior=None,
                    estado_nuevo="PENDIENTE_PAGO",
                    motivo="Conversión de cotización",
                    origen_cambio=principal.origin,
                ),
            ]
        )
        AuditService.record(
            session,
            principal=principal,
            action="CONVERTIR_COTIZACION",
            object_type="COTIZACION",
            object_reference=str(quote.id_cotizacion),
            reason="Cotización aceptada convertida una sola vez",
            after={"id_pedido": order.id_pedido},
        )
        session.flush()
        return order
