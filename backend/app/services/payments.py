from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.exceptions import Conflict, NotFound, PermissionDenied
from app.core.security import Principal
from app.domain.money import ZERO, money
from app.models.entities import (
    AplicacionTransaccionHito,
    Caja,
    HitoPago,
    MovimientoCaja,
    Pedido,
    Transaccion,
)
from app.repositories.locks import lock_order, lock_payment
from app.services.audit import AuditService
from app.services.authorization import AuthorizationService
from app.services.inventory import InventoryReservationService
from app.services.orders import OrderService

PAYMENT_SCOPES = frozenset({"ANTICIPO", "SALDO", "TOTAL"})
CLOSED_ORDER_STATES = frozenset({"CANCELADO", "EXPIRADO", "ENTREGADO"})


class PaymentService:
    def __init__(self, reservations: InventoryReservationService | None = None):
        self.reservations = reservations or InventoryReservationService()

    def report(
        self,
        session: Session,
        *,
        order_id: int,
        idempotency_key: UUID,
        method: str,
        principal: Principal,
        amount: Decimal | None = None,
        payment_scope: str | None = None,
        milestone_number: int | None = None,
        bank: str | None = None,
        bank_origin: str | None = None,
        bank_receiver: str | None = None,
        reference: str | None = None,
    ) -> Transaccion:
        if method != "TRANSFERENCIA":
            raise Conflict(
                "Las transferencias se reportan en línea; el efectivo se registra en caja"
            )
        origin = self._required_text(bank_origin or bank, "Indica el banco emisor")
        normalized_reference = self._required_text(
            reference, "Indica la referencia bancaria"
        )
        self._lock_reference(session, origin, normalized_reference)
        duplicate = session.scalar(
            select(Transaccion.id_transaccion).where(
                Transaccion.tipo_transaccion == "PAGO",
                Transaccion.metodo_pago == "TRANSFERENCIA",
                func.lower(Transaccion.banco_origen) == origin.lower(),
                func.lower(Transaccion.referencia_bancaria) == normalized_reference.lower(),
                Transaccion.estado_verificacion != "RECHAZADO",
                Transaccion.clave_idem != idempotency_key,
            )
        )
        if duplicate is not None:
            raise Conflict("La referencia ya fue reportada para ese banco")
        return self._create_report(
            session,
            order_id=order_id,
            idempotency_key=idempotency_key,
            method=method,
            principal=principal,
            amount=amount,
            payment_scope=payment_scope,
            milestone_number=milestone_number,
            bank_origin=origin,
            bank_receiver=self._optional_text(bank_receiver),
            reference=normalized_reference,
        )

    def _create_report(
        self,
        session: Session,
        *,
        order_id: int,
        idempotency_key: UUID,
        method: str,
        principal: Principal,
        amount: Decimal | None,
        payment_scope: str | None,
        milestone_number: int | None,
        bank_origin: str | None,
        bank_receiver: str | None,
        reference: str | None,
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
            self._authorize_order(session, existing_order, principal)
            expected_amount = money(amount) if amount is not None else existing.monto_con_signo
            if (
                existing.metodo_pago != method
                or existing.monto_con_signo != expected_amount
                or existing.banco_origen != bank_origin
                or existing.banco_receptor != bank_receiver
                or existing.referencia_bancaria != reference
            ):
                raise Conflict("La clave idempotente fue reutilizada con datos diferentes")
            return existing

        order = lock_order(session, order_id)
        self._authorize_order(session, order, principal)
        if order.estado in CLOSED_ORDER_STATES:
            raise Conflict("El estado del pedido no admite pagos ordinarios")
        milestones = list(
            session.scalars(
                select(HitoPago)
                .where(HitoPago.id_pedido == order_id)
                .order_by(HitoPago.numero_hito)
                .with_for_update()
            )
        )
        if not milestones:
            raise NotFound("Hitos de pago no encontrados")

        scope = self._scope(payment_scope, milestone_number)
        committed = self._allocated_by_milestone(
            session, order_id=order_id, states=("PENDIENTE", "VERIFICADO")
        )
        verified = self._allocated_by_milestone(
            session, order_id=order_id, states=("VERIFICADO",)
        )
        available = {
            item.numero_hito: money(
                max(item.monto_exigido - committed.get(item.numero_hito, ZERO), 0)
            )
            for item in milestones
        }
        advance = next((item for item in milestones if item.tipo_hito == "ANTICIPO"), None)
        if scope == "SALDO" and advance is not None:
            if verified.get(advance.numero_hito, ZERO) < advance.monto_exigido:
                raise Conflict(
                    "El saldo puede abonarse por separado después de completar el anticipo"
                )

        eligible = self._eligible_milestones(milestones, scope)
        maximum = money(sum((available[item.numero_hito] for item in eligible), ZERO))
        requested = maximum if amount is None else self._positive_amount(amount)
        pending_total = self._pending_for_order(session, order_id=order_id)
        verified_total = self._verified_for_order(session, order_id=order_id)
        order_available = money(max(order.total_pedido - verified_total - pending_total, 0))
        allowed = min(maximum, order_available)
        if requested > allowed:
            raise Conflict(f"El importe supera el máximo disponible para reportar: {allowed}")
        if requested <= 0 or allowed <= 0:
            raise Conflict("El pedido no tiene importe disponible para reportar")

        allocations: list[tuple[int, Decimal]] = []
        remainder = requested
        for milestone in eligible:
            applied = min(available[milestone.numero_hito], remainder)
            if applied > 0:
                allocations.append((milestone.numero_hito, money(applied)))
                remainder = money(remainder - applied)
            if remainder == 0:
                break
        if remainder != 0:
            raise Conflict("No fue posible distribuir el importe entre los hitos")

        now = datetime.now(UTC)
        transaction = Transaccion(
            id_pedido=order_id,
            numero_hito=allocations[0][0] if len(allocations) == 1 else None,
            id_empleado_verificador=None,
            id_transaccion_compensada=None,
            id_reembolso=None,
            fecha_hora=now,
            tipo_transaccion="PAGO",
            monto_con_signo=requested,
            metodo_pago=method,
            banco_origen=bank_origin,
            banco_receptor=bank_receiver,
            referencia_bancaria=reference,
            estado_verificacion="PENDIENTE",
            fecha_verificacion=None,
            clave_idem=idempotency_key,
        )
        session.add(transaction)
        session.flush()
        session.add_all(
            [
                AplicacionTransaccionHito(
                    id_transaccion=transaction.id_transaccion,
                    id_pedido=order_id,
                    numero_hito=number,
                    monto_aplicado=applied,
                )
                for number, applied in allocations
            ]
        )
        if now <= order.vencimiento_pago and order.fecha_inicio_revision_pago is None:
            order.fecha_inicio_revision_pago = now
        AuditService.record(
            session,
            principal=principal,
            action="REPORTAR_PAGO",
            object_type="TRANSACCION",
            object_reference=str(transaction.id_transaccion),
            reason="Abono reportado; pendiente de verificación",
            after={
                "estado_verificacion": "PENDIENTE",
                "monto": requested,
                "metodo": method,
                "aplicaciones": [
                    {"numero_hito": number, "monto": applied}
                    for number, applied in allocations
                ],
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
        if order.estado in CLOSED_ORDER_STATES:
            raise Conflict("El estado del pedido no admite confirmar pagos ordinarios")
        effective_deadline = (
            order.fecha_inicio_revision_pago + timedelta(hours=24)
            if order.fecha_inicio_revision_pago is not None
            else order.vencimiento_pago
        )
        if datetime.now(UTC) > effective_deadline:
            AuthorizationService.require(session, principal, "PAGO_TARDIO_AUTORIZAR")

        applications = self._payment_applications(session, payment)
        allocated_total = money(
            sum((application.monto_aplicado for application in applications), ZERO)
        )
        if allocated_total != payment.monto_con_signo:
            raise Conflict("La distribución del pago no coincide con el importe registrado")
        milestones = {
            item.numero_hito: item
            for item in session.scalars(
                select(HitoPago)
                .where(HitoPago.id_pedido == payment.id_pedido)
                .order_by(HitoPago.numero_hito)
                .with_for_update()
            )
        }
        verified_before = self._allocated_by_milestone(
            session, order_id=payment.id_pedido, states=("VERIFICADO",)
        )
        for application in applications:
            milestone = milestones.get(application.numero_hito)
            if milestone is None:
                raise NotFound("Hito de pago no encontrado")
            after = money(
                verified_before.get(application.numero_hito, ZERO)
                + application.monto_aplicado
            )
            if after > milestone.monto_exigido:
                raise Conflict("El pago supera el monto exigido para el hito")
        verified_total_before = self._verified_for_order(session, order_id=payment.id_pedido)
        verified_total = money(verified_total_before + payment.monto_con_signo)
        if verified_total > order.total_pedido:
            raise Conflict("El pago supera el total pendiente del pedido")

        previous = payment.estado_verificacion
        payment.estado_verificacion = "VERIFICADO"
        payment.id_empleado_verificador = principal.persona_id
        payment.fecha_verificacion = datetime.now(UTC)
        session.flush()

        advance_completed_now = False
        for application in applications:
            milestone = milestones[application.numero_hito]
            before = verified_before.get(application.numero_hito, ZERO)
            after = money(before + application.monto_aplicado)
            if after >= milestone.monto_exigido:
                milestone.estado = "PAGADO"
                if milestone.tipo_hito == "ANTICIPO" and before < milestone.monto_exigido:
                    advance_completed_now = True
            else:
                milestone.estado = "PENDIENTE"
        if advance_completed_now:
            self.reservations.reserve_for_order(session, order_id=order.id_pedido)

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
        payment.fecha_verificacion = datetime.now(UTC)
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

    def open_cash_register(
        self, session: Session, *, opening_amount: Decimal, principal: Principal
    ) -> Caja:
        AuthorizationService.require(session, principal, "PAGO_VERIFICAR")
        session.execute(text("select pg_advisory_xact_lock(hashtextextended('cash-register', 0))"))
        if session.scalar(select(Caja.id_caja).where(Caja.estado == "ABIERTA")) is not None:
            raise Conflict("Ya existe una caja abierta")
        amount = self._nonnegative_amount(opening_amount)
        register = Caja(
            id_empleado_apertura=principal.persona_id,
            id_empleado_cierre=None,
            fecha_apertura=datetime.now(UTC),
            fecha_cierre=None,
            saldo_inicial=amount,
            saldo_cierre_declarado=None,
            estado="ABIERTA",
        )
        session.add(register)
        session.flush()
        AuditService.record(
            session,
            principal=principal,
            action="ABRIR_CAJA",
            object_type="CAJA",
            object_reference=str(register.id_caja),
            reason="Apertura de caja para recepción de efectivo",
            after={"saldo_inicial": amount},
        )
        return register

    def close_cash_register(
        self,
        session: Session,
        *,
        cash_register_id: int,
        closing_amount: Decimal,
        principal: Principal,
    ) -> Caja:
        AuthorizationService.require(session, principal, "PAGO_VERIFICAR")
        register = session.scalar(
            select(Caja).where(Caja.id_caja == cash_register_id).with_for_update()
        )
        if register is None:
            raise NotFound("Caja no encontrada")
        if register.estado != "ABIERTA":
            raise Conflict("La caja ya está cerrada")
        register.estado = "CERRADA"
        register.fecha_cierre = datetime.now(UTC)
        register.id_empleado_cierre = principal.persona_id
        register.saldo_cierre_declarado = self._nonnegative_amount(closing_amount)
        AuditService.record(
            session,
            principal=principal,
            action="CERRAR_CAJA",
            object_type="CAJA",
            object_reference=str(register.id_caja),
            reason="Cierre de caja declarado por empleado autorizado",
            after={"saldo_cierre_declarado": register.saldo_cierre_declarado},
        )
        return register

    def register_cash_payment(
        self,
        session: Session,
        *,
        order_id: int,
        cash_register_id: int,
        amount: Decimal,
        payment_scope: str,
        idempotency_key: UUID,
        principal: Principal,
    ) -> MovimientoCaja:
        AuthorizationService.require(session, principal, "PAGO_VERIFICAR")
        register = session.scalar(
            select(Caja).where(Caja.id_caja == cash_register_id).with_for_update()
        )
        if register is None or register.estado != "ABIERTA":
            raise Conflict("Se requiere una caja abierta")
        payment = self._create_report(
            session,
            order_id=order_id,
            idempotency_key=idempotency_key,
            method="EFECTIVO",
            principal=principal,
            amount=amount,
            payment_scope=payment_scope,
            milestone_number=None,
            bank_origin=None,
            bank_receiver=None,
            reference=None,
        )
        existing_movement = session.scalar(
            select(MovimientoCaja).where(
                MovimientoCaja.id_transaccion == payment.id_transaccion
            )
        )
        if existing_movement is not None:
            return existing_movement
        self.confirm(session, payment_id=payment.id_transaccion, principal=principal)
        folio = f"REC-{datetime.now(UTC):%Y%m%d}-{payment.id_transaccion:08d}"
        movement = MovimientoCaja(
            id_caja=register.id_caja,
            id_transaccion=payment.id_transaccion,
            id_empleado=principal.persona_id,
            fecha_hora=datetime.now(UTC),
            tipo_movimiento="INGRESO_PAGO",
            monto=payment.monto_con_signo,
            folio_recibo=folio,
        )
        session.add(movement)
        session.flush()
        AuditService.record(
            session,
            principal=principal,
            action="REGISTRAR_EFECTIVO",
            object_type="MOVIMIENTO_CAJA",
            object_reference=folio,
            reason="Efectivo recibido y verificado en caja",
            after={
                "id_caja": register.id_caja,
                "id_transaccion": payment.id_transaccion,
                "monto": payment.monto_con_signo,
            },
        )
        return movement

    @classmethod
    def summary(cls, session: Session, *, order_id: int, principal: Principal) -> dict[str, object]:
        order = session.get(Pedido, order_id)
        if order is None:
            raise NotFound("Pedido no encontrado")
        if principal.is_employee:
            if not AuthorizationService.has_permission(session, principal, "PAGO_CONSULTAR"):
                AuthorizationService.require(session, principal, "PEDIDO_GESTIONAR")
        elif order.id_cliente != principal.persona_id:
            raise PermissionDenied("El pedido pertenece a otro cliente")
        milestones = list(
            session.scalars(
                select(HitoPago)
                .where(HitoPago.id_pedido == order_id)
                .order_by(HitoPago.numero_hito)
            )
        )
        verified_by_hito = cls._allocated_by_milestone(
            session, order_id=order_id, states=("VERIFICADO",)
        )
        pending_by_hito = cls._allocated_by_milestone(
            session, order_id=order_id, states=("PENDIENTE",)
        )
        rows: list[dict[str, object]] = []
        advance_verified = ZERO
        advance_required = ZERO
        for milestone in milestones:
            verified = verified_by_hito.get(milestone.numero_hito, ZERO)
            pending = pending_by_hito.get(milestone.numero_hito, ZERO)
            remaining = money(max(milestone.monto_exigido - verified, 0))
            reportable = money(max(milestone.monto_exigido - verified - pending, 0))
            if milestone.tipo_hito == "ANTICIPO":
                advance_verified = verified
                advance_required = milestone.monto_exigido
            rows.append(
                {
                    "numero_hito": milestone.numero_hito,
                    "tipo_hito": milestone.tipo_hito,
                    "monto_exigido": milestone.monto_exigido,
                    "monto_pendiente_verificacion": pending,
                    "monto_verificado": verified,
                    "monto_restante": remaining,
                    "monto_disponible_reportar": reportable,
                    "estado": "PAGADO" if remaining == 0 else "PENDIENTE",
                    "puede_reportar": (
                        reportable > 0 and order.estado not in CLOSED_ORDER_STATES
                    ),
                }
            )
        total_verified = cls._verified_for_order(session, order_id=order_id)
        total_pending = cls._pending_for_order(session, order_id=order_id)
        return {
            "id_pedido": order.id_pedido,
            "codigo_pedido": order.codigo_pedido,
            "estado_pedido": order.estado,
            "total_pedido": order.total_pedido,
            "anticipo_exigido": advance_required,
            "anticipo_pendiente_verificacion": next(
                (
                    row["monto_pendiente_verificacion"]
                    for row in rows
                    if row["tipo_hito"] == "ANTICIPO"
                ),
                ZERO,
            ),
            "anticipo_verificado": advance_verified,
            "anticipo_faltante": money(max(advance_required - advance_verified, 0)),
            "anticipo_completado": advance_verified >= advance_required,
            "total_verificado": total_verified,
            "total_pendiente_verificacion": total_pending,
            "saldo_pendiente": money(max(order.total_pedido - total_verified, 0)),
            "disponible_reportar": money(
                max(order.total_pedido - total_verified - total_pending, 0)
            ),
            "completamente_pagado": total_verified >= order.total_pedido,
            "hitos": rows,
        }

    @staticmethod
    def _allocated_by_milestone(
        session: Session, *, order_id: int, states: tuple[str, ...]
    ) -> dict[int, Decimal]:
        rows = session.execute(
            select(
                AplicacionTransaccionHito.numero_hito,
                func.coalesce(func.sum(AplicacionTransaccionHito.monto_aplicado), 0),
            )
            .join(
                Transaccion,
                Transaccion.id_transaccion == AplicacionTransaccionHito.id_transaccion,
            )
            .where(
                AplicacionTransaccionHito.id_pedido == order_id,
                Transaccion.tipo_transaccion == "PAGO",
                Transaccion.estado_verificacion.in_(states),
            )
            .group_by(AplicacionTransaccionHito.numero_hito)
        ).all()
        return {number: money(amount) for number, amount in rows}

    @staticmethod
    def _verified_for_order(session: Session, *, order_id: int) -> Decimal:
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
    def _pending_for_order(session: Session, *, order_id: int) -> Decimal:
        return money(
            session.scalar(
                select(func.coalesce(func.sum(Transaccion.monto_con_signo), 0)).where(
                    Transaccion.id_pedido == order_id,
                    Transaccion.tipo_transaccion == "PAGO",
                    Transaccion.estado_verificacion == "PENDIENTE",
                )
            )
            or 0
        )

    @staticmethod
    def _payment_applications(
        session: Session, payment: Transaccion
    ) -> list[AplicacionTransaccionHito]:
        applications = list(
            session.scalars(
                select(AplicacionTransaccionHito)
                .where(AplicacionTransaccionHito.id_transaccion == payment.id_transaccion)
                .order_by(AplicacionTransaccionHito.numero_hito)
                .with_for_update()
            )
        )
        if applications:
            return applications
        if payment.numero_hito is None:
            raise Conflict("La transacción no tiene distribución contable")
        legacy = AplicacionTransaccionHito(
            id_transaccion=payment.id_transaccion,
            id_pedido=payment.id_pedido,
            numero_hito=payment.numero_hito,
            monto_aplicado=payment.monto_con_signo,
        )
        session.add(legacy)
        session.flush()
        return [legacy]

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

    @staticmethod
    def _authorize_order(session: Session, order: Pedido, principal: Principal) -> None:
        if principal.is_employee:
            AuthorizationService.require(session, principal, "PAGO_VERIFICAR")
        elif order.id_cliente != principal.persona_id:
            raise PermissionDenied("El pedido pertenece a otro cliente")

    @staticmethod
    def _scope(payment_scope: str | None, milestone_number: int | None) -> str:
        scope = (payment_scope or "").strip().upper()
        if not scope:
            scope = {1: "ANTICIPO", 2: "SALDO"}.get(milestone_number, "TOTAL")
        if scope not in PAYMENT_SCOPES:
            raise Conflict("Modalidad de pago inválida")
        return scope

    @staticmethod
    def _eligible_milestones(milestones: list[HitoPago], scope: str) -> list[HitoPago]:
        if scope == "TOTAL":
            return milestones
        selected = [item for item in milestones if item.tipo_hito == scope]
        if not selected:
            raise NotFound(f"Hito {scope.lower()} no encontrado")
        return selected

    @staticmethod
    def _positive_amount(value: Decimal) -> Decimal:
        try:
            amount = money(value)
        except (InvalidOperation, ValueError) as exc:
            raise Conflict("El importe no es válido") from exc
        if amount <= 0:
            raise Conflict("El importe debe ser mayor que cero")
        return amount

    @staticmethod
    def _nonnegative_amount(value: Decimal) -> Decimal:
        try:
            amount = money(value)
        except (InvalidOperation, ValueError) as exc:
            raise Conflict("El importe no es válido") from exc
        if amount < 0:
            raise Conflict("El importe no puede ser negativo")
        return amount

    @staticmethod
    def _required_text(value: str | None, message: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            raise Conflict(message)
        return normalized

    @staticmethod
    def _optional_text(value: str | None) -> str | None:
        normalized = (value or "").strip()
        return normalized or None

    @staticmethod
    def _lock_reference(session: Session, bank: str, reference: str) -> None:
        session.execute(
            text("select pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"bank-reference:{bank.lower()}:{reference.lower()}"},
        )
