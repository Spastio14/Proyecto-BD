from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import Conflict, InsufficientInventory
from app.domain.money import minimum_advance
from app.models.entities import (
    ArticuloInventariable,
    HitoPago,
    RegistroAuditoria,
    ReservaInventario,
    Transaccion,
    VarianteProducto,
)
from app.services.inventory import InventoryService
from app.services.orders import OrderService
from app.services.payments import PaymentService
from tests.helpers import add_client, create_order

pytestmark = pytest.mark.integration


def report_payment(session, order, principal):
    return PaymentService().report(
        session,
        order_id=order.id_pedido,
        milestone_number=1,
        idempotency_key=uuid4(),
        method="TRANSFERENCIA",
        principal=principal,
        bank="BANCO-TEST",
        reference=f"REF-{order.id_pedido}-{uuid4().hex}",
    )


def test_17_order_without_confirmed_advance_does_not_reserve(session, customer):
    order = create_order(session, customer)
    count = session.scalar(
        select(func.count())
        .select_from(ReservaInventario)
        .where(ReservaInventario.id_pedido == order.id_pedido)
    )
    assert count == 0


def test_18_confirmed_advance_creates_reservation(session, customer, employee):
    order = create_order(session, customer)
    payment = report_payment(session, order, customer)
    PaymentService().confirm(session, payment_id=payment.id_transaccion, principal=employee)
    reservation = session.scalar(
        select(ReservaInventario).where(ReservaInventario.id_pedido == order.id_pedido)
    )
    assert reservation is not None
    assert reservation.cantidad_reservada == Decimal("1.000")


@pytest.mark.concurrency
def test_19_concurrent_confirmations_do_not_oversell_last_units(engine, session, employee):
    first_client = add_client(session)
    second_client = add_client(session)
    first_order = create_order(session, first_client, quantity=5)
    second_order = create_order(session, second_client, quantity=5)
    first_payment = report_payment(session, first_order, first_client)
    second_payment = report_payment(session, second_order, second_client)
    session.get(ArticuloInventariable, 1).existencia_actual = Decimal("7.000")
    session.commit()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    barrier = Barrier(2)

    def confirm(payment_id: int) -> str:
        with factory() as worker:
            barrier.wait()
            try:
                PaymentService().confirm(worker, payment_id=payment_id, principal=employee)
                worker.commit()
                return "confirmed"
            except InsufficientInventory:
                worker.rollback()
                return "insufficient"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(confirm, [first_payment.id_transaccion, second_payment.id_transaccion])
        )
    assert sorted(results) == ["confirmed", "insufficient"]


def test_20_inventory_consumption_is_applied_once(session, customer, employee):
    order = create_order(session, customer)
    payment = report_payment(session, order, customer)
    PaymentService().confirm(session, payment_id=payment.id_transaccion, principal=employee)
    order.estado = "EN_PRODUCCION"
    before = session.get(ArticuloInventariable, 1).existencia_actual
    first = InventoryService().consume_order(session, order_id=order.id_pedido, principal=employee)
    after_first = session.get(ArticuloInventariable, 1).existencia_actual
    second = InventoryService().consume_order(session, order_id=order.id_pedido, principal=employee)
    after_second = session.get(ArticuloInventariable, 1).existencia_actual
    assert after_first == before - Decimal("1.000")
    assert after_second == after_first
    assert second[0].id_movimiento == first[0].id_movimiento


def test_21_cancellation_releases_active_reservations(session, customer, employee):
    order = create_order(session, customer)
    payment = report_payment(session, order, customer)
    PaymentService().confirm(session, payment_id=payment.id_transaccion, principal=employee)
    OrderService().cancel(session, order_id=order.id_pedido, principal=employee, reason="Prueba administrativa")
    reservation = session.scalar(
        select(ReservaInventario).where(ReservaInventario.id_pedido == order.id_pedido)
    )
    assert reservation.estado == "LIBERADA"
    assert reservation.fecha_liberacion is not None


def test_22_repeated_cancellation_does_not_change_physical_stock(session, customer, employee):
    order = create_order(session, customer)
    payment = report_payment(session, order, customer)
    PaymentService().confirm(session, payment_id=payment.id_transaccion, principal=employee)
    stock = session.get(ArticuloInventariable, 1).existencia_actual
    OrderService().cancel(session, order_id=order.id_pedido, principal=employee, reason="Prueba administrativa")
    with pytest.raises(Conflict, match="ya fue cancelado"):
        OrderService().cancel(session, order_id=order.id_pedido, principal=customer, reason="Otra")
    assert session.get(ArticuloInventariable, 1).existencia_actual == stock


def test_23_insufficient_inventory_leaves_no_partial_movements(session, customer, employee):
    order = create_order(session, customer)
    payment = report_payment(session, order, customer)
    session.commit()
    session.get(ArticuloInventariable, 1).existencia_actual = Decimal("2.000")
    session.commit()
    with pytest.raises(InsufficientInventory):
        PaymentService().confirm(session, payment_id=payment.id_transaccion, principal=employee)
        session.commit()
    session.rollback()
    assert session.get(Transaccion, payment.id_transaccion).estado_verificacion == "PENDIENTE"
    assert (
        session.scalar(
            select(func.count())
            .select_from(ReservaInventario)
            .where(ReservaInventario.id_pedido == order.id_pedido)
        )
        == 0
    )


def test_24_minimum_advance_is_exactly_half(session, customer):
    order = create_order(session, customer)
    milestone = session.get(HitoPago, (order.id_pedido, 1))
    assert milestone.monto_exigido == minimum_advance(order.total_pedido) == Decimal("45.00")


def test_25_money_uses_round_half_up(session, customer):
    session.get(VarianteProducto, 1).precio_detalle = Decimal("90.01")
    session.flush()
    order = create_order(session, customer)
    assert session.get(HitoPago, (order.id_pedido, 1)).monto_exigido == Decimal("45.01")


def test_26_reported_payment_does_not_create_reservation(session, customer):
    order = create_order(session, customer)
    payment = report_payment(session, order, customer)
    assert payment.estado_verificacion == "PENDIENTE"
    assert (
        session.scalar(
            select(func.count())
            .select_from(ReservaInventario)
            .where(ReservaInventario.id_pedido == order.id_pedido)
        )
        == 0
    )


def test_27_verified_payment_updates_order_and_reservation(session, customer, employee):
    order = create_order(session, customer)
    payment = report_payment(session, order, customer)
    PaymentService().confirm(session, payment_id=payment.id_transaccion, principal=employee)
    assert order.estado == "PAGADO_PARCIAL"
    assert session.get(HitoPago, (order.id_pedido, 1)).estado == "PAGADO"
    assert (
        session.scalar(
            select(func.count())
            .select_from(ReservaInventario)
            .where(ReservaInventario.id_pedido == order.id_pedido)
        )
        == 1
    )


def test_28_repeated_confirmation_has_no_duplicate_effect(session, customer, employee):
    order = create_order(session, customer)
    payment = report_payment(session, order, customer)
    service = PaymentService()
    service.confirm(session, payment_id=payment.id_transaccion, principal=employee)
    service.confirm(session, payment_id=payment.id_transaccion, principal=employee)
    assert (
        session.scalar(
            select(func.count())
            .select_from(ReservaInventario)
            .where(ReservaInventario.id_pedido == order.id_pedido)
        )
        == 1
    )


def test_29_payment_report_is_idempotent(session, customer):
    order = create_order(session, customer)
    key = uuid4()
    service = PaymentService()
    first = service.report(
        session,
        order_id=order.id_pedido,
        milestone_number=1,
        idempotency_key=key,
        method="TRANSFERENCIA",
        principal=customer,
        bank="BANCO-TEST",
        reference="IDEM-001",
    )
    second = service.report(
        session,
        order_id=order.id_pedido,
        milestone_number=1,
        idempotency_key=key,
        method="TRANSFERENCIA",
        principal=customer,
        bank="BANCO-TEST",
        reference="IDEM-001",
    )
    assert second.id_transaccion == first.id_transaccion


def test_30_failed_confirmation_rolls_back_audit_and_payment(session, customer, employee):
    order = create_order(session, customer, quantity=5)
    payment = report_payment(session, order, customer)
    session.commit()
    session.get(ArticuloInventariable, 1).existencia_actual = Decimal("2.000")
    session.commit()
    with pytest.raises(InsufficientInventory):
        PaymentService().confirm(session, payment_id=payment.id_transaccion, principal=employee)
        session.commit()
    session.rollback()
    assert session.get(Transaccion, payment.id_transaccion).estado_verificacion == "PENDIENTE"


def test_31_multiple_pending_payments_fit_within_same_milestone(session, customer):
    order = create_order(session, customer)
    service = PaymentService()
    first = service.report(
        session,
        order_id=order.id_pedido,
        milestone_number=1,
        amount=Decimal("20.00"),
        idempotency_key=uuid4(),
        method="TRANSFERENCIA",
        principal=customer,
        bank="BANCO-TEST",
        reference="PARCIAL-001",
    )
    second = service.report(
        session,
        order_id=order.id_pedido,
        milestone_number=1,
        amount=Decimal("25.00"),
        idempotency_key=uuid4(),
        method="TRANSFERENCIA",
        principal=customer,
        bank="BANCO-TEST",
        reference="PARCIAL-002",
    )
    assert first.estado_verificacion == second.estado_verificacion == "PENDIENTE"
    assert (
        session.scalar(
            select(func.count())
            .select_from(Transaccion)
            .where(
                Transaccion.id_pedido == order.id_pedido,
                Transaccion.numero_hito == 1,
                Transaccion.estado_verificacion == "PENDIENTE",
            )
        )
        == 2
    )


def test_32_financial_summary_tracks_pending_verified_and_zero_balance(session, customer, employee):
    service = PaymentService()
    order = create_order(session, customer)
    advance = report_payment(session, order, customer)
    pending = service.summary(session, order_id=order.id_pedido, principal=customer)
    assert pending["anticipo_exigido"] == Decimal("45.00")
    assert pending["anticipo_pendiente_verificacion"] == Decimal("45.00")
    assert pending["anticipo_verificado"] == Decimal("0.00")
    assert pending["saldo_pendiente"] == Decimal("90.00")

    service.confirm(session, payment_id=advance.id_transaccion, principal=employee)
    balance = service.report(
        session,
        order_id=order.id_pedido,
        milestone_number=2,
        idempotency_key=uuid4(),
        method="TRANSFERENCIA",
        principal=customer,
        bank="BANCO-TEST",
        reference="SALDO-001",
    )
    assert balance.monto_con_signo == Decimal("45.00")
    service.confirm(session, payment_id=balance.id_transaccion, principal=employee)
    completed = service.summary(session, order_id=order.id_pedido, principal=customer)
    assert completed["total_verificado"] == Decimal("90.00")
    assert completed["saldo_pendiente"] == Decimal("0.00")
    assert completed["completamente_pagado"] is True
    assert all(not item["puede_reportar"] for item in completed["hitos"])
    with pytest.raises(Conflict, match="importe|pagado|completado"):
        service.report(
            session,
            order_id=order.id_pedido,
            milestone_number=2,
            idempotency_key=uuid4(),
            method="TRANSFERENCIA",
            principal=customer,
            bank="BANCO-TEST",
            reference="SALDO-002",
        )


def test_33_excessive_payment_is_not_verified(session, customer, employee):
    order = create_order(session, customer)
    payment = report_payment(session, order, customer)
    payment.monto_con_signo = Decimal("45.01")
    session.flush()
    with pytest.raises(Conflict, match="distribución|supera"):
        PaymentService().confirm(session, payment_id=payment.id_transaccion, principal=employee)
    assert payment.estado_verificacion == "PENDIENTE"
    assert payment.id_empleado_verificador is None


def test_34_confirmation_writes_payment_and_order_audit(session, customer, employee):
    order = create_order(session, customer)
    payment = report_payment(session, order, customer)
    PaymentService().confirm(session, payment_id=payment.id_transaccion, principal=employee)
    actions = set(
        session.scalars(
            select(RegistroAuditoria.accion).where(
                RegistroAuditoria.referencia_objeto.in_(
                    (str(payment.id_transaccion), order.codigo_pedido)
                )
            )
        )
    )
    assert {"VERIFICAR_PAGO", "CAMBIAR_ESTADO_PEDIDO"} <= actions


@pytest.mark.concurrency
def test_35_concurrent_distinct_reports_leave_one_pending_hito(engine, session, customer):
    order = create_order(session, customer)
    order_id = order.id_pedido
    session.commit()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    barrier = Barrier(2)

    def report() -> str:
        with factory() as worker:
            barrier.wait()
            try:
                PaymentService().report(
                    worker,
                    order_id=order_id,
                    milestone_number=1,
                    idempotency_key=uuid4(),
                    method="TRANSFERENCIA",
                    principal=customer,
                    bank="BANCO-TEST",
                    reference=f"CONCURRENT-{uuid4().hex}",
                    amount=Decimal("30.00"),
                )
                worker.commit()
                return "created"
            except Conflict:
                worker.rollback()
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: report(), range(2)))
    assert sorted(results) == ["conflict", "created"]
