from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.exceptions import Conflict, NotFound, PermissionDenied
from app.core.security import Principal
from app.domain.money import money
from app.models.entities import HitoPago, Transaccion
from app.repositories.locks import lock_order, lock_payment
from app.services.audit import AuditService
from app.services.authorization import AuthorizationService
from app.services.inventory import InventoryReservationService


class PaymentService:
    def __init__(self, reservations: InventoryReservationService | None = None):
        self.reservations = reservations or InventoryReservationService()

    def report(
        self,
        session: Session,
        *,
        order_id: int,
        milestone_number: int,
        idempotency_key: UUID,
        method: str,
        principal: Principal,
        bank: str | None = None,
        reference: str | None = None,
    ) -> Transaccion:
        session.execute(
            text("select pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"payment-idempotency:{idempotency_key}"},
        )
        existing = session.scalar(
            select(Transaccion).where(Transaccion.clave_idem == idempotency_key)
        )
        if existing is not None:
            if existing.id_pedido != order_id:
                raise Conflict("La clave idempotente pertenece a otra operación")
            existing_order = lock_order(session, existing.id_pedido)
            if principal.is_employee:
                AuthorizationService.require(session, principal, "PAGO_VERIFICAR")
            elif existing_order.id_cliente != principal.persona_id:
                raise PermissionDenied("El pedido pertenece a otro cliente")
            return existing
        order = lock_order(session, order_id)
        if principal.is_employee:
            AuthorizationService.require(session, principal, "PAGO_VERIFICAR")
        elif order.id_cliente != principal.persona_id:
            raise PermissionDenied("El pedido pertenece a otro cliente")
        if method not in {"EFECTIVO", "TRANSFERENCIA", "TARJETA", "OTRO"}:
            raise Conflict("Método de pago inválido")
        milestone = session.get(HitoPago, (order_id, milestone_number))
        if milestone is None:
            raise NotFound("Hito de pago no encontrado")
        if milestone.estado == "PAGADO":
            raise Conflict("El hito ya fue pagado")
        now = datetime.now(UTC)
        transaction = Transaccion(
            id_pedido=order_id,
            numero_hito=milestone_number,
            id_empleado_verificador=None,
            id_transaccion_compensada=None,
            id_reembolso=None,
            fecha_hora=now,
            tipo_transaccion="PAGO",
            monto_con_signo=milestone.monto_exigido,
            metodo_pago=method,
            banco_receptor=bank,
            referencia_bancaria=reference,
            estado_verificacion="PENDIENTE",
            clave_idem=idempotency_key,
        )
        session.add(transaction)
        if now <= order.vencimiento_pago and order.fecha_inicio_revision_pago is None:
            order.fecha_inicio_revision_pago = now
        session.flush()
        AuditService.record(
            session,
            principal=principal,
            action="REPORTAR_PAGO",
            object_type="TRANSACCION",
            object_reference=str(transaction.id_transaccion),
            reason="Comprobante reportado; pendiente de verificación",
            after={"estado_verificacion": "PENDIENTE"},
        )
        return transaction

    def confirm(
        self,
        session: Session,
        *,
        payment_id: int,
        principal: Principal,
    ) -> Transaccion:
        AuthorizationService.require(session, principal, "PAGO_VERIFICAR")
        payment = lock_payment(session, payment_id)
        if payment.estado_verificacion == "VERIFICADO":
            return payment
        if payment.estado_verificacion != "PENDIENTE" or payment.tipo_transaccion != "PAGO":
            raise Conflict("La transacción no admite confirmación")
        order = lock_order(session, payment.id_pedido)
        effective_deadline = (
            order.fecha_inicio_revision_pago + timedelta(hours=24)
            if order.fecha_inicio_revision_pago is not None
            else order.vencimiento_pago
        )
        if datetime.now(UTC) > effective_deadline:
            AuthorizationService.require(session, principal, "PAGO_TARDIO_AUTORIZAR")
        milestone = session.get(HitoPago, (payment.id_pedido, payment.numero_hito))
        if milestone is None:
            raise NotFound("Hito de pago no encontrado")

        verified_for_milestone = session.scalar(
            select(func.coalesce(func.sum(Transaccion.monto_con_signo), 0)).where(
                Transaccion.id_pedido == payment.id_pedido,
                Transaccion.numero_hito == payment.numero_hito,
                Transaccion.tipo_transaccion == "PAGO",
                Transaccion.estado_verificacion == "VERIFICADO",
            )
        )
        verified_for_order = session.scalar(
            select(func.coalesce(func.sum(Transaccion.monto_con_signo), 0)).where(
                Transaccion.id_pedido == payment.id_pedido,
                Transaccion.tipo_transaccion == "PAGO",
                Transaccion.estado_verificacion == "VERIFICADO",
            )
        )
        milestone_total = money(verified_for_milestone + payment.monto_con_signo)
        if milestone.numero_hito == 1:
            self.reservations.reserve_for_order(session, order_id=order.id_pedido)

        previous = payment.estado_verificacion
        payment.estado_verificacion = "VERIFICADO"
        payment.id_empleado_verificador = principal.persona_id
        if milestone_total >= milestone.monto_exigido:
            milestone.estado = "PAGADO"

        verified_total = money(verified_for_order + payment.monto_con_signo)
        if order.estado in {"PENDIENTE_PAGO", "PAGADO_PARCIAL", "PAGADO"}:
            order.estado = "PAGADO" if verified_total >= order.total_pedido else "PAGADO_PARCIAL"
        AuditService.record(
            session,
            principal=principal,
            action="VERIFICAR_PAGO",
            object_type="TRANSACCION",
            object_reference=str(payment.id_transaccion),
            reason="Verificación manual autorizada",
            before={"estado_verificacion": previous},
            after={"estado_verificacion": "VERIFICADO"},
        )
        session.flush()
        return payment

    def reject(
        self, session: Session, *, payment_id: int, principal: Principal, reason: str
    ) -> Transaccion:
        AuthorizationService.require(session, principal, "PAGO_VERIFICAR")
        payment = lock_payment(session, payment_id)
        if payment.estado_verificacion != "PENDIENTE":
            raise Conflict("La transacción ya fue resuelta")
        payment.estado_verificacion = "RECHAZADO"
        payment.id_empleado_verificador = principal.persona_id
        AuditService.record(
            session,
            principal=principal,
            action="RECHAZAR_PAGO",
            object_type="TRANSACCION",
            object_reference=str(payment.id_transaccion),
            reason=reason,
            before={"estado_verificacion": "PENDIENTE"},
            after={"estado_verificacion": "RECHAZADO"},
        )
        return payment
