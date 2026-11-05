from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import Conflict, NotFound, PermissionDenied
from app.core.security import Principal
from app.domain.money import ZERO, minimum_advance, money
from app.domain.orders import ACTIVE_GUEST_STATES, ALLOWED_TRANSITIONS
from app.models.entities import (
    Cancelacion,
    DetallePedido,
    HistorialPedido,
    HitoPago,
    Pedido,
    ReservaInventario,
)
from app.repositories.locks import lock_client, lock_order
from app.services.audit import AuditService
from app.services.authorization import AuthorizationService
from app.services.pricing import PricingService


@dataclass(frozen=True, slots=True)
class OrderLineInput:
    variant_id: int
    quantity: int
    promotion_id: int | None = None


class OrderService:
    def __init__(self, pricing: PricingService | None = None):
        self.pricing = pricing or PricingService()

    def create(
        self,
        session: Session,
        *,
        principal: Principal,
        lines: list[OrderLineInput],
        channel: str = "WEB",
        delivery_mode: str = "RETIRO",
    ) -> Pedido:
        client = lock_client(session, principal.persona_id)
        if client.estado != "ACTIVO":
            raise Conflict("El cliente no está activo")
        if not lines:
            raise Conflict("El pedido requiere al menos una línea")
        if any(line.quantity <= 0 for line in lines):
            raise Conflict("Todas las cantidades deben ser positivas")
        total_units = sum(line.quantity for line in lines)
        if client.tipo_cliente == "INVITADO":
            if total_units > 5:
                raise Conflict("Un invitado puede solicitar como máximo 5 unidades")
            self._enforce_guest_limit(session, client.id_persona)
        elif client.tipo_cliente == "REGISTRADO":
            self._enforce_registered_limit(session, client.id_persona)

        priced = [
            self.pricing.price_line(
                session,
                client_type=client.tipo_cliente,
                variant_id=line.variant_id,
                quantity=line.quantity,
                promotion_id=line.promotion_id,
            )
            for line in lines
        ]
        now = datetime.now(UTC)
        total = money(sum((line.total for line in priced), ZERO))
        order = Pedido(
            id_cliente=client.id_persona,
            id_empleado_registro=None,
            id_etapa_actual=None,
            id_cotizacion=None,
            codigo_pedido=f"PED-{uuid4().hex[:16].upper()}",
            fecha_creacion=now,
            vencimiento_pago=now + timedelta(hours=24),
            fecha_inicio_revision_pago=None,
            canal_origen=channel,
            estado="PENDIENTE_PAGO",
            fecha_entrega_prevista=now + timedelta(days=7),
            modalidad_entrega=delivery_mode,
            nombre_persona_retiro=None,
            total_pedido=total,
            token_seguimiento=uuid4(),
        )
        session.add(order)
        session.flush()
        for number, (source, result) in enumerate(zip(lines, priced, strict=True), start=1):
            session.add(
                DetallePedido(
                    id_pedido=order.id_pedido,
                    numero_linea=number,
                    id_variante=source.variant_id,
                    cantidad=source.quantity,
                    precio_unitario_aplicado=result.unit_price,
                    descuento_aplicado=result.discount,
                    importe_pactado=result.total,
                    costo_estimado=result.estimated_cost,
                    costo_real_consolidado=None,
                    modo_precio=result.mode,
                    id_promocion=result.promotion_id,
                )
            )
        advance = minimum_advance(total)
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
                    monto_exigido=money(total - advance),
                    fecha_vencimiento=order.fecha_entrega_prevista,
                    estado="PENDIENTE",
                ),
                HistorialPedido(
                    id_pedido=order.id_pedido,
                    id_empleado=None,
                    id_etapa_anterior=None,
                    id_etapa_nueva=None,
                    fecha_hora=now,
                    estado_anterior=None,
                    estado_nuevo="PENDIENTE_PAGO",
                    motivo="Creación de pedido",
                    origen_cambio=principal.origin,
                ),
            ]
        )
        AuditService.record(
            session,
            principal=principal,
            action="CREAR_PEDIDO",
            object_type="PEDIDO",
            object_reference=order.codigo_pedido,
            reason="Pedido calculado por el backend",
            after={"id_pedido": order.id_pedido, "total": total},
        )
        session.flush()
        return order

    @staticmethod
    def _enforce_guest_limit(session: Session, client_id: int) -> None:
        count = session.scalar(
            select(func.count())
            .select_from(Pedido)
            .where(
                Pedido.id_cliente == client_id,
                Pedido.estado.in_(ACTIVE_GUEST_STATES),
            )
        )
        if count:
            raise Conflict("El invitado ya tiene un pedido activo")

    @staticmethod
    def _enforce_registered_limit(session: Session, client_id: int) -> None:
        count = session.scalar(
            select(func.count())
            .select_from(Pedido)
            .where(
                Pedido.id_cliente == client_id,
                Pedido.estado == "PENDIENTE_PAGO",
            )
        )
        if (count or 0) >= 2:
            raise Conflict("El cliente ya tiene dos pedidos pendientes de pago")

    @staticmethod
    def get_owned(session: Session, *, order_id: int, principal: Principal) -> Pedido:
        order = session.get(Pedido, order_id)
        if order is None:
            raise NotFound("Pedido no encontrado")
        if principal.is_employee:
            AuthorizationService.require(session, principal, "PEDIDO_GESTIONAR")
        elif order.id_cliente != principal.persona_id:
            raise PermissionDenied("El pedido pertenece a otro cliente")
        return order

    @staticmethod
    def list_owned(session: Session, principal: Principal) -> list[Pedido]:
        statement = select(Pedido).order_by(Pedido.fecha_creacion.desc())
        if principal.is_employee:
            AuthorizationService.require(session, principal, "PEDIDO_GESTIONAR")
        else:
            statement = statement.where(Pedido.id_cliente == principal.persona_id)
        return list(session.scalars(statement))

    def transition(
        self,
        session: Session,
        *,
        order_id: int,
        target: str,
        principal: Principal | None,
        reason: str,
    ) -> Pedido:
        order = lock_order(session, order_id)
        if target not in ALLOWED_TRANSITIONS.get(order.estado, frozenset()):
            raise Conflict(f"Transición inválida: {order.estado} → {target}")
        previous = order.estado
        order.estado = target
        session.add(
            HistorialPedido(
                id_pedido=order.id_pedido,
                id_empleado=principal.persona_id if principal and principal.is_employee else None,
                id_etapa_anterior=None,
                id_etapa_nueva=None,
                fecha_hora=datetime.now(UTC),
                estado_anterior=previous,
                estado_nuevo=target,
                motivo=reason,
                origen_cambio=principal.origin if principal else "SISTEMA",
            )
        )
        AuditService.record(
            session,
            principal=principal,
            action="CAMBIAR_ESTADO_PEDIDO",
            object_type="PEDIDO",
            object_reference=order.codigo_pedido,
            reason=reason,
            before={"estado": previous},
            after={"estado": target},
        )
        return order

    def cancel(
        self, session: Session, *, order_id: int, principal: Principal, reason: str
    ) -> Pedido:
        order = lock_order(session, order_id)
        if principal.is_employee:
            AuthorizationService.require(session, principal, "PEDIDO_GESTIONAR")
        elif order.id_cliente != principal.persona_id:
            raise PermissionDenied("El pedido pertenece a otro cliente")
        existing = session.scalar(select(Cancelacion).where(Cancelacion.id_pedido == order_id))
        if existing is not None or order.estado == "CANCELADO":
            raise Conflict("El pedido ya fue cancelado")
        if "CANCELADO" not in ALLOWED_TRANSITIONS.get(order.estado, frozenset()):
            raise Conflict("El pedido ya no admite cancelación")
        now = datetime.now(UTC)
        session.add(
            Cancelacion(
                id_pedido=order_id,
                id_empleado_autoriza=principal.persona_id if principal.is_employee else None,
                fecha_hora=now,
                motivo=reason,
                etapa_cancelacion=order.estado,
                monto_retenido=ZERO,
                resultado="APROBADA",
                fecha_confirmacion_autenticacion=now,
            )
        )
        reservations = list(
            session.scalars(
                select(ReservaInventario)
                .where(
                    ReservaInventario.id_pedido == order_id,
                    ReservaInventario.estado == "ACTIVA",
                )
                .with_for_update()
            )
        )
        for reservation in reservations:
            reservation.estado = "LIBERADA"
            reservation.fecha_liberacion = now
        return self.transition(
            session, order_id=order_id, target="CANCELADO", principal=principal, reason=reason
        )
