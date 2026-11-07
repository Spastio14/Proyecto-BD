from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.exceptions import Conflict, NotFound, PermissionDenied
from app.core.security import Principal
from app.domain.money import money
from app.models.entities import HitoPago, Pedido, Transaccion
from app.repositories.locks import lock_order, lock_payment
from app.services.audit import AuditService
from app.services.authorization import AuthorizationService
from app.services.inventory import InventoryReservationService
from app.services.orders import OrderService


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
        if order.estado in {"CANCELADO", "EXPIRADO", "ENTREGADO"}:
            raise Conflict("El estado del pedido no admite pagos ordinarios")
        milestone = session.scalar(
            select(HitoPago)
            .where(
                HitoPago.id_pedido == order_id,
                HitoPago.numero_hito == milestone_number,
            )
            .with_for_update()
        )
        if milestone is None:
            raise NotFound("Hito de pago no encontrado")
        if milestone.estado == "PAGADO":
            raise Conflict("El hito ya fue pagado")
        pending = session.scalar(
            select(Transaccion.id_transaccion).where(
                Transaccion.id_pedido == order_id,
                Transaccion.numero_hito == milestone_number,
                Transaccion.tipo_transaccion == "PAGO",
                Transaccion.estado_verificacion == "PENDIENTE",
            )
        )
        if pending is not None:
            raise Conflict("El hito ya tiene un pago pendiente de verificación")
        verified_for_milestone = self._verified_for_milestone(
            session, order_id=order_id, milestone_number=milestone_number
        )
        amount_due = money(milestone.monto_exigido - verified_for_milestone)
        if amount_due <= 0:
            milestone.estado = "PAGADO"
            raise Conflict("El hito ya fue completado")
        verified_for_order = self._verified_for_order(session, order_id=order_id)
        if money(order.total_pedido - verified_for_order) <= 0:
            raise Conflict("El pedido ya está completamente pagado")
        now = datetime.now(UTC)
        transaction = Transaccion(
            id_pedido=order_id,
            numero_hito=milestone_number,
            id_empleado_verificador=None,
            id_transaccion_compensada=None,
            id_reembolso=None,
            fecha_hora=now,
            tipo_transaccion="PAGO",
            monto_con_signo=amount_due,
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
            after={
                "estado_verificacion": "PENDIENTE",
                "numero_hito": milestone_number,
                "monto": amount_due,
            },
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
        reference = session.get(Transaccion, payment_id)
        if reference is None:
            raise NotFound("Transacción no encontrada")
        order = lock_order(session, reference.id_pedido)
        payment = lock_payment(session, payment_id)
        if payment.estado_verificacion == "VERIFICADO":
            return payment
        if payment.estado_verificacion != "PENDIENTE" or payment.tipo_transaccion != "PAGO":
            raise Conflict("La transacción no admite confirmación")
        if order.estado in {"CANCELADO", "EXPIRADO", "ENTREGADO"}:
            raise Conflict("El estado del pedido no admite confirmar pagos ordinarios")
        effective_deadline = (
            order.fecha_inicio_revision_pago + timedelta(hours=24)
            if order.fecha_inicio_revision_pago is not None
            else order.vencimiento_pago
        )
        if datetime.now(UTC) > effective_deadline:
            AuthorizationService.require(session, principal, "PAGO_TARDIO_AUTORIZAR")
        milestone = session.scalar(
            select(HitoPago)
            .where(
                HitoPago.id_pedido == payment.id_pedido,
                HitoPago.numero_hito == payment.numero_hito,
            )
            .with_for_update()
        )
        if milestone is None:
            raise NotFound("Hito de pago no encontrado")

        verified_for_milestone = self._verified_for_milestone(
            session,
            order_id=payment.id_pedido,
            milestone_number=payment.numero_hito,
        )
        verified_for_order = self._verified_for_order(session, order_id=payment.id_pedido)
        milestone_total = money(verified_for_milestone + payment.monto_con_signo)
        if milestone_total > milestone.monto_exigido:
            raise Conflict("El pago supera el monto exigido para el hito")
        verified_total = money(verified_for_order + payment.monto_con_signo)
        if verified_total > order.total_pedido:
            raise Conflict("El pago supera el total pendiente del pedido")
        if milestone.numero_hito == 1:
            self.reservations.reserve_for_order(session, order_id=order.id_pedido)

        previous = payment.estado_verificacion
        payment.estado_verificacion = "VERIFICADO"
        payment.id_empleado_verificador = principal.persona_id
        if milestone_total >= milestone.monto_exigido:
            milestone.estado = "PAGADO"

        if order.estado in {"PENDIENTE_PAGO", "PAGADO_PARCIAL", "PAGADO"}:
            target = "PAGADO" if verified_total >= order.total_pedido else "PAGADO_PARCIAL"
            if target != order.estado:
                OrderService().transition(
                    session,
                    order_id=order.id_pedido,
                    target=target,
                    principal=principal,
                    reason=f"Pago #{payment.id_transaccion} verificado",
                )
        AuditService.record(
            session,
            principal=principal,
            action="VERIFICAR_PAGO",
            object_type="TRANSACCION",
            object_reference=str(payment.id_transaccion),
            reason="Verificación manual autorizada",
            before={"estado_verificacion": previous},
            after={
                "estado_verificacion": "VERIFICADO",
                "monto": payment.monto_con_signo,
                "total_verificado_pedido": verified_total,
            },
        )
        session.flush()
        return payment

    def reject(
        self, session: Session, *, payment_id: int, principal: Principal, reason: str
    ) -> Transaccion:
        AuthorizationService.require(session, principal, "PAGO_VERIFICAR")
        reference = session.get(Transaccion, payment_id)
        if reference is None:
            raise NotFound("Transacción no encontrada")
        lock_order(session, reference.id_pedido)
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

    @classmethod
    def summary(cls, session: Session, *, order_id: int, principal: Principal) -> dict[str, object]:
        order = session.get(Pedido, order_id)
        if order is None:
            raise NotFound("Pedido no encontrado")
        if principal.is_employee:
            AuthorizationService.require(session, principal, "PAGO_CONSULTAR")
        elif order.id_cliente != principal.persona_id:
            raise PermissionDenied("El pedido pertenece a otro cliente")
        milestones = list(
            session.scalars(
                select(HitoPago)
                .where(HitoPago.id_pedido == order_id)
                .order_by(HitoPago.numero_hito)
            )
        )
        rows: list[dict[str, object]] = []
        for milestone in milestones:
            verified = cls._verified_for_milestone(
                session,
                order_id=order_id,
                milestone_number=milestone.numero_hito,
            )
            pending = money(
                session.scalar(
                    select(func.coalesce(func.sum(Transaccion.monto_con_signo), 0)).where(
                        Transaccion.id_pedido == order_id,
                        Transaccion.numero_hito == milestone.numero_hito,
                        Transaccion.tipo_transaccion == "PAGO",
                        Transaccion.estado_verificacion == "PENDIENTE",
                    )
                )
                or 0
            )
            remaining = money(max(milestone.monto_exigido - verified, 0))
            rows.append(
                {
                    "numero_hito": milestone.numero_hito,
                    "tipo_hito": milestone.tipo_hito,
                    "monto_exigido": milestone.monto_exigido,
                    "monto_pendiente_verificacion": pending,
                    "monto_verificado": verified,
                    "monto_restante": remaining,
                    "estado": milestone.estado,
                    "puede_reportar": (
                        remaining > 0
                        and pending == 0
                        and order.estado not in {"CANCELADO", "EXPIRADO", "ENTREGADO"}
                    ),
                }
            )
        total_verified = cls._verified_for_order(session, order_id=order_id)
        advance = next((row for row in rows if row["tipo_hito"] == "ANTICIPO"), None)
        return {
            "id_pedido": order.id_pedido,
            "codigo_pedido": order.codigo_pedido,
            "estado_pedido": order.estado,
            "total_pedido": order.total_pedido,
            "anticipo_exigido": advance["monto_exigido"] if advance else money(0),
            "anticipo_pendiente_verificacion": (
                advance["monto_pendiente_verificacion"] if advance else money(0)
            ),
            "anticipo_verificado": advance["monto_verificado"] if advance else money(0),
            "total_verificado": total_verified,
            "saldo_pendiente": money(max(order.total_pedido - total_verified, 0)),
            "completamente_pagado": total_verified >= order.total_pedido,
            "hitos": rows,
        }

    @staticmethod
    def _verified_for_milestone(session: Session, *, order_id: int, milestone_number: int):
        return money(
            session.scalar(
                select(func.coalesce(func.sum(Transaccion.monto_con_signo), 0)).where(
                    Transaccion.id_pedido == order_id,
                    Transaccion.numero_hito == milestone_number,
                    Transaccion.tipo_transaccion == "PAGO",
                    Transaccion.estado_verificacion == "VERIFICADO",
                )
            )
            or 0
        )

    @staticmethod
    def _verified_for_order(session: Session, *, order_id: int):
        return money(
            session.scalar(
                select(func.coalesce(func.sum(Transaccion.monto_con_signo), 0)).where(
                    Transaccion.id_pedido == order_id,
                    Transaccion.tipo_transaccion == "PAGO",
                    Transaccion.estado_verificacion == "VERIFICADO",
                )
            )
            or 0
        )

    @staticmethod
    def get_owned(session: Session, *, payment_id: int, principal: Principal) -> Transaccion:
        payment = session.get(Transaccion, payment_id)
        if payment is None:
            raise NotFound("Transacción no encontrada")
        order = lock_order(session, payment.id_pedido)
        if principal.is_employee:
            AuthorizationService.require(session, principal, "PAGO_CONSULTAR")
        elif order.id_cliente != principal.persona_id:
            raise PermissionDenied("El pago pertenece a otro cliente")
        return payment

    @staticmethod
    def list_for_order(
        session: Session, *, order_id: int, principal: Principal
    ) -> list[Transaccion]:
        order = lock_order(session, order_id)
        if principal.is_employee:
            AuthorizationService.require(session, principal, "PAGO_CONSULTAR")
        elif order.id_cliente != principal.persona_id:
            raise PermissionDenied("El pedido pertenece a otro cliente")
        return list(
            session.scalars(
                select(Transaccion)
                .where(Transaccion.id_pedido == order_id)
                .order_by(Transaccion.fecha_hora.desc())
            )
        )

    @staticmethod
    def list_all(session: Session, principal: Principal) -> list[Transaccion]:
        AuthorizationService.require(session, principal, "PAGO_CONSULTAR")
        return list(
            session.scalars(select(Transaccion).order_by(Transaccion.fecha_hora.desc()).limit(200))
        )
