from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import Conflict, NotFound
from app.core.security import Principal
from app.models.entities import AgenciaEnvio, Envio, HitoPago, Pedido, Persona
from app.repositories.locks import lock_order
from app.services.audit import AuditService
from app.services.authorization import AuthorizationService
from app.services.orders import OrderService


class DeliveryService:
    @staticmethod
    def defaults(
        session: Session, *, order_id: int, principal: Principal
    ) -> dict[str, object]:
        order = OrderService.get_owned(session, order_id=order_id, principal=principal)
        person = session.get(Persona, order.id_cliente)
        if person is None:
            raise NotFound("El pedido no tiene una persona receptora válida")
        return {
            "id_pedido": order.id_pedido,
            "id_cliente": order.id_cliente,
            "nombre_receptor": " ".join(
                value for value in (person.nombres, person.apellidos) if value
            ),
            "telefono_receptor": person.telefono_contacto,
            "direccion_habitual": person.direccion_habitual,
        }

    @staticmethod
    def list_agencies(session: Session, principal: Principal) -> list[AgenciaEnvio]:
        AuthorizationService.require(session, principal, "PEDIDO_GESTIONAR")
        return list(
            session.scalars(
                select(AgenciaEnvio)
                .where(AgenciaEnvio.estado == "ACTIVA")
                .order_by(AgenciaEnvio.nombre)
            )
        )

    def schedule(
        self,
        session: Session,
        *,
        order_id: int,
        agency_id: int | None,
        address: str,
        recipient_name: str,
        recipient_phone: str | None,
        agreed_fee: Decimal,
        scheduled_at: datetime | None,
        principal: Principal,
    ) -> Envio:
        AuthorizationService.require(session, principal, "PEDIDO_GESTIONAR")
        order = lock_order(session, order_id)
        if order.modalidad_entrega != "ENVIO":
            raise Conflict("El pedido está configurado para retiro")
        if order.estado in {"CANCELADO", "EXPIRADO", "ENTREGADO"}:
            raise Conflict("El estado del pedido no admite programar entrega")
        existing = session.scalar(select(Envio).where(Envio.id_pedido == order_id))
        if existing is not None:
            raise Conflict("El pedido ya tiene un envío")
        if agency_id is not None:
            agency = session.get(AgenciaEnvio, agency_id)
            if agency is None or agency.estado != "ACTIVA":
                raise NotFound("Agencia activa no encontrada")
        delivery = Envio(
            id_pedido=order_id,
            id_agencia=agency_id,
            direccion_entrega=address.strip(),
            nombre_receptor=recipient_name.strip(),
            telefono_receptor=recipient_phone.strip() if recipient_phone else None,
            tarifa_acordada=agreed_fee,
            fecha_programada=scheduled_at,
            fecha_entrega_real=None,
            estado="PROGRAMADO" if scheduled_at else "PENDIENTE",
        )
        session.add(delivery)
        session.flush()
        AuditService.record(
            session,
            principal=principal,
            action="PROGRAMAR_ENVIO",
            object_type="ENVIO",
            object_reference=str(delivery.id_envio),
            reason="Entrega registrada para el pedido",
            after={
                "id_pedido": order_id,
                "estado": delivery.estado,
                "nombre_receptor": delivery.nombre_receptor,
                "direccion_entrega": delivery.direccion_entrega,
            },
        )
        return delivery

    def complete(
        self,
        session: Session,
        *,
        order_id: int,
        principal: Principal,
        reason: str,
    ) -> Pedido:
        AuthorizationService.require(session, principal, "PEDIDO_GESTIONAR")
        order = lock_order(session, order_id)
        if order.estado == "ENTREGADO":
            return order
        if order.estado != "LISTO":
            raise Conflict("Sólo un pedido listo puede entregarse")
        unpaid_milestone = session.scalar(
            select(HitoPago.numero_hito).where(
                HitoPago.id_pedido == order_id,
                HitoPago.estado != "PAGADO",
            )
        )
        if unpaid_milestone is not None:
            raise Conflict("El pedido debe estar completamente pagado antes de la entrega")
        if order.modalidad_entrega == "ENVIO":
            delivery = session.scalar(
                select(Envio).where(Envio.id_pedido == order_id).with_for_update()
            )
            if delivery is None:
                raise Conflict("El pedido requiere un envío programado")
            if delivery.estado == "CANCELADO":
                raise Conflict("El envío fue cancelado")
            now = datetime.now(UTC)
            if delivery.fecha_programada is not None and delivery.fecha_programada > now:
                raise Conflict("La fecha programada del envío todavía no ha llegado")
            delivery.estado = "ENTREGADO"
            delivery.fecha_entrega_real = now
        return OrderService().transition(
            session,
            order_id=order_id,
            target="ENTREGADO",
            principal=principal,
            reason=reason,
        )
