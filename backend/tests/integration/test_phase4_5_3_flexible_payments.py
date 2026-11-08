from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import Conflict
from app.models.entities import (
    AplicacionTransaccionHito,
    Caja,
    HitoPago,
    MovimientoCaja,
    Pedido,
    RegistroAuditoria,
    ReservaInventario,
    Transaccion,
)
from app.services.orders import OrderLineInput, OrderService
from app.services.payments import PaymentService
from app.services.portal import PortalService
from tests.helpers import add_client, create_order

pytestmark = pytest.mark.integration


def large_order(session, principal):
    order = create_order(session, principal)
    order.total_pedido = Decimal("4180.00")
    advance = session.get(HitoPago, (order.id_pedido, 1))
    balance = session.get(HitoPago, (order.id_pedido, 2))
    advance.monto_exigido = Decimal("2090.00")
    balance.monto_exigido = Decimal("2090.00")
    session.flush()
    return order


def transfer(
    session,
    order,
    principal,
    amount,
    scope="TOTAL",
    *,
    bank="BANCO A",
    reference=None,
):
    return PaymentService().report(
        session,
        order_id=order.id_pedido,
        amount=Decimal(amount),
        payment_scope=scope,
        idempotency_key=uuid4(),
        method="TRANSFERENCIA",
        principal=principal,
        bank_origin=bank,
        reference=reference or f"REF-{uuid4().hex}",
    )


def test_registered_and_wholesale_clients_share_two_active_order_limit(session, customer):
    create_order(session, customer)
    with pytest.raises(Conflict, match="dos pedidos activos"):
        create_order(session, customer)

    wholesale = add_client(session, commercial_condition="MAYORISTA")
    first = create_order(session, wholesale)
    second = create_order(session, wholesale)
    first.estado = "EN_PRODUCCION"
    second.estado = "LISTO"
    session.flush()
    with pytest.raises(Conflict, match="dos pedidos activos"):
        create_order(session, wholesale)

    first.estado = "ENTREGADO"
    replacement = create_order(session, wholesale)
    assert replacement.estado == "PENDIENTE_PAGO"


@pytest.mark.concurrency
def test_active_order_limit_is_serialized_per_client(engine, session):
    principal = add_client(session)
    create_order(session, principal)
    session.commit()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    barrier = Barrier(2)

    def create_concurrently():
        with factory() as worker:
            barrier.wait()
            try:
                order = OrderService().create(
                    worker,
                    principal=principal,
                    lines=[OrderLineInput(variant_id=1, quantity=1)],
                )
                worker.commit()
                return order.id_pedido
            except Conflict:
                worker.rollback()
                return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: create_concurrently(), range(2)))
    assert sum(result is not None for result in results) == 1
    with factory() as verification:
        active = verification.scalar(
            select(func.count())
            .select_from(Pedido)
            .where(
                Pedido.id_cliente == principal.persona_id,
                Pedido.estado.not_in(("ENTREGADO", "CANCELADO", "EXPIRADO")),
            )
        )
        assert active == 2


def test_advance_accepts_multiple_verified_installments_and_reserves_once(
    session, customer, employee
):
    order = large_order(session, customer)
    service = PaymentService()
    payments = [
        transfer(session, order, customer, "1000.00", "ANTICIPO"),
        transfer(session, order, customer, "590.00", "ANTICIPO"),
        transfer(session, order, customer, "500.00", "ANTICIPO"),
    ]
    service.confirm(session, payment_id=payments[0].id_transaccion, principal=employee)
    service.confirm(session, payment_id=payments[1].id_transaccion, principal=employee)
    partial = service.summary(session, order_id=order.id_pedido, principal=customer)
    assert partial["anticipo_verificado"] == Decimal("1590.00")
    assert partial["anticipo_completado"] is False
    assert session.scalar(
        select(func.count())
        .select_from(ReservaInventario)
        .where(ReservaInventario.id_pedido == order.id_pedido)
    ) == 0

    service.confirm(session, payment_id=payments[2].id_transaccion, principal=employee)
    complete = service.summary(session, order_id=order.id_pedido, principal=customer)
    assert complete["anticipo_verificado"] == Decimal("2090.00")
    assert complete["anticipo_completado"] is True
    service.confirm(session, payment_id=payments[2].id_transaccion, principal=employee)
    assert session.scalar(
        select(func.count())
        .select_from(ReservaInventario)
        .where(ReservaInventario.id_pedido == order.id_pedido)
    ) == 1


def test_balance_can_be_split_across_transfer_and_cash(session, customer, employee):
    order = large_order(session, customer)
    service = PaymentService()
    advance = transfer(session, order, customer, "2090.00", "ANTICIPO")
    service.confirm(session, payment_id=advance.id_transaccion, principal=employee)
    first = transfer(session, order, customer, "800.00", "SALDO")
    second = transfer(session, order, customer, "290.00", "SALDO")
    service.confirm(session, payment_id=first.id_transaccion, principal=employee)
    service.confirm(session, payment_id=second.id_transaccion, principal=employee)
    register = service.open_cash_register(
        session, opening_amount=Decimal("0"), principal=employee
    )
    cash = service.register_cash_payment(
        session,
        order_id=order.id_pedido,
        cash_register_id=register.id_caja,
        amount=Decimal("1000.00"),
        payment_scope="SALDO",
        idempotency_key=uuid4(),
        principal=employee,
    )
    summary = service.summary(session, order_id=order.id_pedido, principal=customer)
    assert summary["total_verificado"] == Decimal("4180.00")
    assert summary["saldo_pendiente"] == Decimal("0.00")
    assert cash.folio_recibo.startswith("REC-")
    assert order.estado == "PAGADO"


def test_single_full_payment_is_distributed_without_double_counting(
    session, customer, employee
):
    order = large_order(session, customer)
    payment = transfer(session, order, customer, "4180.00", "TOTAL")
    applications = list(
        session.scalars(
            select(AplicacionTransaccionHito)
            .where(AplicacionTransaccionHito.id_transaccion == payment.id_transaccion)
            .order_by(AplicacionTransaccionHito.numero_hito)
        )
    )
    assert [item.monto_aplicado for item in applications] == [
        Decimal("2090.00"),
        Decimal("2090.00"),
    ]
    assert (
        sum((item.monto_aplicado for item in applications), Decimal(0))
        == payment.monto_con_signo
    )
    PaymentService().confirm(session, payment_id=payment.id_transaccion, principal=employee)
    summary = PaymentService.summary(session, order_id=order.id_pedido, principal=customer)
    assert summary["total_verificado"] == Decimal("4180.00")
    assert session.scalar(
        select(func.sum(Transaccion.monto_con_signo)).where(
            Transaccion.id_transaccion == payment.id_transaccion
        )
    ) == Decimal("4180.00")
    assert all(item.estado == "PAGADO" for item in (
        session.get(HitoPago, (order.id_pedido, 1)),
        session.get(HitoPago, (order.id_pedido, 2)),
    ))


def test_full_payment_can_use_multiple_operations_confirmed_out_of_order(
    session, customer, employee
):
    order = large_order(session, customer)
    first = transfer(session, order, customer, "1000.00", "TOTAL")
    second = transfer(session, order, customer, "2000.00", "TOTAL")
    third = transfer(session, order, customer, "1180.00", "TOTAL")
    service = PaymentService()
    service.confirm(session, payment_id=third.id_transaccion, principal=employee)
    service.confirm(session, payment_id=second.id_transaccion, principal=employee)
    interim = service.summary(session, order_id=order.id_pedido, principal=customer)
    assert interim["total_verificado"] == Decimal("3180.00")
    assert interim["anticipo_completado"] is False
    service.confirm(session, payment_id=first.id_transaccion, principal=employee)
    final = service.summary(session, order_id=order.id_pedido, principal=customer)
    assert final["total_verificado"] == Decimal("4180.00")
    assert final["anticipo_completado"] is True


def test_rejected_payment_releases_amount_for_new_attempt(session, customer, employee):
    order = large_order(session, customer)
    failed = transfer(session, order, customer, "1000.00", "ANTICIPO")
    service = PaymentService()
    service.reject(
        session,
        payment_id=failed.id_transaccion,
        principal=employee,
        reason="No aparece en el estado de cuenta",
    )
    retry = transfer(session, order, customer, "2090.00", "ANTICIPO")
    assert retry.estado_verificacion == "PENDIENTE"
    assert service.summary(session, order_id=order.id_pedido, principal=customer)[
        "total_verificado"
    ] == Decimal("0.00")


def test_pending_operations_prevent_overreporting_and_invalid_amounts(session, customer):
    order = large_order(session, customer)
    transfer(session, order, customer, "2000.00", "ANTICIPO")
    with pytest.raises(Conflict, match="máximo disponible"):
        transfer(session, order, customer, "100.00", "ANTICIPO")
    with pytest.raises(Conflict, match="mayor que cero"):
        transfer(session, order, customer, "0.00", "TOTAL")
    with pytest.raises(Conflict, match="mayor que cero"):
        transfer(session, order, customer, "-1.00", "TOTAL")
    with pytest.raises(Conflict, match="máximo disponible"):
        transfer(session, order, customer, "3000.00", "TOTAL")


def test_bank_reference_is_unique_per_bank_and_card_is_rejected(session, customer):
    order = large_order(session, customer)
    transfer(
        session,
        order,
        customer,
        "100.00",
        "TOTAL",
        bank="BANCO A",
        reference="ABC-123",
    )
    with pytest.raises(Conflict, match="referencia ya fue reportada"):
        transfer(
            session,
            order,
            customer,
            "100.00",
            "TOTAL",
            bank="BANCO A",
            reference="ABC-123",
        )
    accepted = transfer(
        session,
        order,
        customer,
        "100.00",
        "TOTAL",
        bank="BANCO B",
        reference="ABC-123",
    )
    assert accepted.banco_origen == "BANCO B"
    with pytest.raises(Conflict, match="banco emisor"):
        transfer(
            session,
            order,
            customer,
            "10.00",
            "TOTAL",
            bank="   ",
            reference="VALIDA",
        )
    with pytest.raises(Conflict, match="referencia bancaria"):
        transfer(
            session,
            order,
            customer,
            "10.00",
            "TOTAL",
            bank="BANCO C",
            reference="   ",
        )
    with pytest.raises(Conflict, match="efectivo se registra en caja"):
        PaymentService().report(
            session,
            order_id=order.id_pedido,
            amount=Decimal("10"),
            payment_scope="TOTAL",
            idempotency_key=uuid4(),
            method="TARJETA",
            principal=customer,
        )


def test_cash_requires_open_register_and_creates_folio_movement_and_audit(
    session, customer, employee
):
    order = create_order(session, customer)
    service = PaymentService()
    with pytest.raises(Conflict, match="caja abierta"):
        service.register_cash_payment(
            session,
            order_id=order.id_pedido,
            cash_register_id=999,
            amount=Decimal("90.00"),
            payment_scope="TOTAL",
            idempotency_key=uuid4(),
            principal=employee,
        )
    register = service.open_cash_register(
        session, opening_amount=Decimal("200.00"), principal=employee
    )
    movement = service.register_cash_payment(
        session,
        order_id=order.id_pedido,
        cash_register_id=register.id_caja,
        amount=Decimal("90.00"),
        payment_scope="TOTAL",
        idempotency_key=uuid4(),
        principal=employee,
    )
    payment = session.get(Transaccion, movement.id_transaccion)
    assert payment.metodo_pago == "EFECTIVO"
    assert payment.estado_verificacion == "VERIFICADO"
    assert movement.folio_recibo == f"REC-{movement.fecha_hora:%Y%m%d}-{payment.id_transaccion:08d}"
    actions = set(
        session.scalars(
            select(RegistroAuditoria.accion).where(
                RegistroAuditoria.referencia_objeto.in_(
                    (movement.folio_recibo, str(payment.id_transaccion))
                )
            )
        )
    )
    assert {"REGISTRAR_EFECTIVO", "VERIFICAR_PAGO"} <= actions
    closed = service.close_cash_register(
        session,
        cash_register_id=register.id_caja,
        closing_amount=Decimal("290.00"),
        principal=employee,
    )
    assert closed.estado == "CERRADA"


def test_idempotent_cash_retry_does_not_duplicate_income(session, customer, employee):
    order = create_order(session, customer)
    service = PaymentService()
    register = service.open_cash_register(
        session, opening_amount=Decimal("0"), principal=employee
    )
    key = uuid4()
    first = service.register_cash_payment(
        session,
        order_id=order.id_pedido,
        cash_register_id=register.id_caja,
        amount=Decimal("90.00"),
        payment_scope="TOTAL",
        idempotency_key=key,
        principal=employee,
    )
    second = service.register_cash_payment(
        session,
        order_id=order.id_pedido,
        cash_register_id=register.id_caja,
        amount=Decimal("90.00"),
        payment_scope="TOTAL",
        idempotency_key=key,
        principal=employee,
    )
    assert second.id_movimiento_caja == first.id_movimiento_caja
    assert session.scalar(
        select(func.count()).select_from(MovimientoCaja).where(
            MovimientoCaja.id_transaccion == first.id_transaccion
        )
    ) == 1
    with pytest.raises(Conflict, match="datos diferentes"):
        service.register_cash_payment(
            session,
            order_id=order.id_pedido,
            cash_register_id=register.id_caja,
            amount=Decimal("10.00"),
            payment_scope="TOTAL",
            idempotency_key=key,
            principal=employee,
        )


def test_financial_summary_uses_verified_movements_not_stale_milestone_flags(
    session, customer, employee
):
    order = create_order(session, customer)
    payment = transfer(session, order, customer, "90.00", "TOTAL")
    PaymentService().confirm(session, payment_id=payment.id_transaccion, principal=employee)
    session.get(HitoPago, (order.id_pedido, 1)).estado = "PENDIENTE"
    session.get(HitoPago, (order.id_pedido, 2)).estado = "PENDIENTE"
    summary = PaymentService.summary(session, order_id=order.id_pedido, principal=customer)
    assert summary["anticipo_completado"] is True
    assert summary["completamente_pagado"] is True
    assert [item["estado"] for item in summary["hitos"]] == ["PAGADO", "PAGADO"]


def test_portal_explains_active_order_limit(session, customer):
    create_order(session, customer)
    summary = PortalService.summary(session, customer)
    assert summary.pedidos_activos == 2
    assert summary.limite_pedidos_activos == 2
    assert summary.puede_crear_pedido is False
    assert "límite" in summary.motivo_bloqueo_pedido.lower()


def test_historical_payment_methods_remain_untouched(session):
    historical = Transaccion(
        id_pedido=1,
        numero_hito=None,
        id_empleado_verificador=3,
        id_transaccion_compensada=None,
        id_reembolso=None,
        fecha_hora=session.get(Transaccion, 1).fecha_hora,
        tipo_transaccion="PAGO",
        monto_con_signo=Decimal("1.00"),
        metodo_pago="TARJETA",
        banco_origen=None,
        banco_receptor=None,
        referencia_bancaria="HISTORICA",
        estado_verificacion="VERIFICADO",
        fecha_verificacion=None,
        clave_idem=uuid4(),
    )
    session.add(historical)
    session.flush()
    assert session.get(Transaccion, historical.id_transaccion).metodo_pago == "TARJETA"
    assert session.get(Caja, 1) is None


def test_portal_transfer_confirmation_identifies_operation_and_whatsapp_message(
    api_client_factory, customer
):
    client = api_client_factory(customer)
    response = client.post(
        "/api/v1/portal/pedidos/PED-DEMO-001/pagos",
        json={
            "idempotency_key": str(uuid4()),
            "amount": "10.00",
            "payment_scope": "TOTAL",
            "method": "TRANSFERENCIA",
            "bank_origin": "BANCO PRUEBA",
            "bank_receiver": None,
            "reference": "PORTAL-WHATSAPP-001",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["id_transaccion"] > 0
    assert payload["fecha_reporte"]
    assert payload["estado"] == "PENDIENTE"
    assert payload["banco_origen"] == "BANCO PRUEBA"
    assert payload["referencia"] == "PORTAL-WHATSAPP-001"
    assert "C$10.00" in payload["mensaje_whatsapp"]
    assert "PED-DEMO-001" in payload["mensaje_whatsapp"]
    assert "PORTAL-WHATSAPP-001" in payload["mensaje_whatsapp"]
    assert payload["whatsapp_url"] is None
