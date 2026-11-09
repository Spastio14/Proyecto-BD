from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import Conflict
from app.core.security import Principal
from app.models.entities import (
    Cotizacion,
    HistorialPedido,
    Pedido,
    ReservaInventario,
    Transaccion,
    VersionDiseno,
)
from app.services.designs import DesignService
from app.services.inventory import InventoryReservationService
from app.services.orders import OrderLineInput, OrderService
from app.services.payments import PaymentService
from app.services.pricing import PricingService
from app.services.production import ProductionService
from app.services.quotations import QuotationService, QuoteLineInput
from tests.helpers import add_client, create_order
from tests.integration.test_payments_inventory import report_payment

pytestmark = pytest.mark.integration


def test_81_registered_retail_customer_does_not_receive_wholesale_price(session):
    result = PricingService().price_line(
        session,
        client_type="REGISTRADO",
        commercial_condition="DETALLE",
        variant_id=1,
        quantity=12,
    )
    assert result.mode == "DETALLE"
    assert str(result.unit_price) == "90.00"


def test_82_wholesale_price_requires_explicit_commercial_authorization(session):
    result = PricingService().price_line(
        session,
        client_type="REGISTRADO",
        commercial_condition="MAYORISTA",
        variant_id=1,
        quantity=12,
    )
    assert result.mode == "MAYORISTA"
    assert str(result.unit_price) == "80.00"


def test_83_guest_quote_cannot_bypass_five_unit_order_limit(session):
    guest = add_client(session, client_type="INVITADO")
    quote = QuotationService().create(
        session,
        principal=guest,
        lines=[QuoteLineInput(variant_id=1, quantity=6)],
    )
    quote.estado = "ACEPTADA"
    session.flush()

    with pytest.raises(Conflict, match="máximo 5"):
        QuotationService().convert(session, quote_id=quote.id_cotizacion, principal=guest)


def test_84_quote_conversion_obeys_registered_pending_order_limit(session):
    customer = add_client(session, commercial_condition="MAYORISTA")
    create_order(session, customer)
    create_order(session, customer)
    quote = QuotationService().create(
        session,
        principal=customer,
        lines=[QuoteLineInput(variant_id=1, quantity=1)],
    )
    quote.estado = "ACEPTADA"
    session.flush()

    with pytest.raises(Conflict, match="dos pedidos"):
        QuotationService().convert(session, quote_id=quote.id_cotizacion, principal=customer)


def test_85_latest_rejection_blocks_production_after_previous_approval(session, customer, employee):
    order = create_order(session, customer)
    payment = report_payment(session, order, customer)
    PaymentService().confirm(session, payment_id=payment.id_transaccion, principal=employee)
    OrderService().transition(
        session,
        order_id=order.id_pedido,
        target="EN_DISENO",
        principal=employee,
        reason="Preparar diseño",
    )
    designs = DesignService()
    version = designs.add_version(
        session,
        order_id=order.id_pedido,
        line_number=1,
        file_name="version.png",
        private_path="pedidos/prueba/version.png",
        principal=employee,
    )
    designs.decide(
        session,
        order_id=order.id_pedido,
        line_number=1,
        version_number=version.numero_version,
        approved=True,
        principal=customer,
    )
    designs.decide(
        session,
        order_id=order.id_pedido,
        line_number=1,
        version_number=version.numero_version,
        approved=False,
        principal=customer,
    )

    with pytest.raises(Conflict, match="no está aprobada"):
        ProductionService().start(session, order_id=order.id_pedido, principal=employee)


@pytest.mark.concurrency
def test_86_concurrent_payment_reports_share_one_idempotent_result(engine, session):
    customer = add_client(session)
    order = create_order(session, customer)
    order_id = order.id_pedido
    key = uuid4()
    session.commit()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    barrier = Barrier(2)

    def report() -> tuple[str, int | None]:
        with factory() as worker:
            barrier.wait()
            try:
                payment = PaymentService().report(
                    worker,
                    order_id=order_id,
                    milestone_number=1,
                    idempotency_key=key,
                    method="TRANSFERENCIA",
                    principal=customer,
                    bank_origin="BANCO-TEST",
                    reference="IDEMPOTENCIA-CONCURRENTE-001",
                )
                worker.commit()
                return "ok", payment.id_transaccion
            except Exception:
                worker.rollback()
                return "error", None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: report(), range(2)))

    assert [status for status, _ in results] == ["ok", "ok"]
    assert len({payment_id for _, payment_id in results}) == 1
    with factory() as verification:
        assert (
            verification.scalar(
                select(func.count()).select_from(Transaccion).where(Transaccion.clave_idem == key)
            )
            == 1
        )


@pytest.mark.concurrency
def test_87_concurrent_design_uploads_receive_consecutive_versions(engine, session):
    customer = add_client(session)
    employee = Principal(persona_id=3, origin="EMPLEADO")
    order = create_order(session, customer)
    order.estado = "EN_DISENO"
    order_id = order.id_pedido
    session.commit()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    barrier = Barrier(2)

    def add_version(suffix: int) -> tuple[str, int | None]:
        with factory() as worker:
            barrier.wait()
            try:
                version = DesignService().add_version(
                    worker,
                    order_id=order_id,
                    line_number=1,
                    file_name=f"v{suffix}.png",
                    private_path=f"pedidos/prueba/v{suffix}.png",
                    principal=employee,
                )
                worker.commit()
                return "ok", version.numero_version
            except Exception:
                worker.rollback()
                return "error", None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(add_version, [1, 2]))

    assert sorted(results) == [("ok", 1), ("ok", 2)]
    with factory() as verification:
        assert (
            verification.scalar(
                select(func.count())
                .select_from(VersionDiseno)
                .where(VersionDiseno.id_pedido == order_id)
            )
            == 2
        )


def test_88_quote_conversion_preserves_financial_total(session, customer):
    quote = QuotationService().create(
        session,
        principal=customer,
        lines=[
            QuoteLineInput(variant_id=1, quantity=2),
            QuoteLineInput(variant_id=1, quantity=1),
        ],
    )
    quote.estado = "ACEPTADA"
    session.flush()
    order = QuotationService().convert(session, quote_id=quote.id_cotizacion, principal=customer)
    assert order.total_pedido == quote.total_ofrecido


def test_89_invalid_transition_does_not_write_history(session, customer):
    order = create_order(session, customer)
    before = session.scalar(
        select(func.count())
        .select_from(HistorialPedido)
        .where(HistorialPedido.id_pedido == order.id_pedido)
    )
    with pytest.raises(Conflict, match="Transición inválida"):
        OrderService().transition(
            session,
            order_id=order.id_pedido,
            target="ENTREGADO",
            principal=customer,
            reason="Salto inválido",
        )
    assert order.estado == "PENDIENTE_PAGO"
    after = session.scalar(
        select(func.count())
        .select_from(HistorialPedido)
        .where(HistorialPedido.id_pedido == order.id_pedido)
    )
    assert after == before


def test_90_accepted_quote_stays_single_use_in_database(session, customer):
    quote = QuotationService().create(
        session,
        principal=customer,
        lines=[QuoteLineInput(variant_id=1, quantity=1)],
    )
    quote.estado = "ACEPTADA"
    session.flush()
    first = QuotationService().convert(session, quote_id=quote.id_cotizacion, principal=customer)
    assert (
        session.scalar(
            select(func.count())
            .select_from(Pedido)
            .where(Pedido.id_cotizacion == quote.id_cotizacion)
        )
        == 1
    )
    assert session.get(Cotizacion, quote.id_cotizacion).estado == "ACEPTADA"
    assert first.id_cotizacion == quote.id_cotizacion


def test_91_guest_limit_sums_all_order_lines(session):
    guest = add_client(session, client_type="INVITADO")
    with pytest.raises(Conflict, match="máximo 5"):
        OrderService().create(
            session,
            principal=guest,
            lines=[
                OrderLineInput(variant_id=1, quantity=3),
                OrderLineInput(variant_id=1, quantity=3),
            ],
        )


@pytest.mark.concurrency
def test_92_concurrent_registered_orders_cannot_exceed_two_pending(engine, session):
    customer = add_client(session)
    create_order(session, customer)
    session.commit()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    barrier = Barrier(2)

    def create() -> str:
        with factory() as worker:
            barrier.wait()
            try:
                create_order(worker, customer)
                worker.commit()
                return "created"
            except Conflict:
                worker.rollback()
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: create(), range(2)))
    assert sorted(results) == ["conflict", "created"]


@pytest.mark.concurrency
def test_93_concurrent_quote_conversion_creates_one_order(engine, session):
    customer = add_client(session)
    quote = QuotationService().create(
        session,
        principal=customer,
        lines=[QuoteLineInput(variant_id=1, quantity=1)],
    )
    quote.estado = "ACEPTADA"
    quote_id = quote.id_cotizacion
    session.commit()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    barrier = Barrier(2)

    def convert() -> str:
        with factory() as worker:
            barrier.wait()
            try:
                QuotationService().convert(worker, quote_id=quote_id, principal=customer)
                worker.commit()
                return "created"
            except Conflict:
                worker.rollback()
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: convert(), range(2)))
    assert sorted(results) == ["conflict", "created"]
    with factory() as verification:
        assert (
            verification.scalar(
                select(func.count()).select_from(Pedido).where(Pedido.id_cotizacion == quote_id)
            )
            == 1
        )


def test_94_promotion_cannot_combine_with_wholesale_without_authorization(session):
    with pytest.raises(Conflict, match="no puede combinarse"):
        PricingService().price_line(
            session,
            client_type="REGISTRADO",
            commercial_condition="MAYORISTA",
            variant_id=1,
            quantity=12,
            promotion_id=1,
        )


def test_95_promotion_requires_its_minimum_quantity(session):
    with pytest.raises(Conflict, match="mínimo"):
        PricingService().price_line(
            session,
            client_type="REGISTRADO",
            commercial_condition="DETALLE",
            variant_id=1,
            quantity=1,
            promotion_id=1,
        )


def test_96_customer_can_cancel_unpaid_order_and_reuse_active_limit(session):
    customer = add_client(session)
    first = create_order(session, customer)
    second = create_order(session, customer)
    with pytest.raises(Conflict, match="dos pedidos"):
        create_order(session, customer)
    OrderService().cancel(session, order_id=first.id_pedido, principal=customer, reason="Cambio de alcance")
    third = create_order(session, customer)
    assert third.id_pedido != first.id_pedido
    assert first.estado == "CANCELADO"


def test_97_customer_cancellation_requires_admin_review_after_payment(session):
    customer = add_client(session)
    employee = Principal(persona_id=3, origin="EMPLEADO")
    order = create_order(session, customer)
    report_payment(session, order, customer)
    with pytest.raises(Conflict, match="pagos reportados"):
        OrderService().cancel(session, order_id=order.id_pedido, principal=customer, reason="Ya no lo necesito")
    cancelled = OrderService().cancel(session, order_id=order.id_pedido, principal=employee, reason="Revisión administrativa")
    assert cancelled.estado == "CANCELADO"
    assert session.scalar(select(func.count()).select_from(Transaccion).where(Transaccion.id_pedido == order.id_pedido)) == 1


def test_98_customer_cancellation_rejects_started_production(session):
    customer = add_client(session)
    order = create_order(session, customer)
    order.estado = "EN_PRODUCCION"
    session.flush()
    with pytest.raises(Conflict, match="producción"):
        OrderService().cancel(session, order_id=order.id_pedido, principal=customer, reason="Cancelación")


def test_99_cancellation_releases_active_reservations_without_consuming_stock(session):
    customer = add_client(session)
    order = create_order(session, customer)
    InventoryReservationService().reserve_for_order(session, order_id=order.id_pedido)
    active = list(session.scalars(select(ReservaInventario).where(ReservaInventario.id_pedido == order.id_pedido)))
    assert active
    OrderService().cancel(session, order_id=order.id_pedido, principal=customer, reason="Cancelación sin pago")
    assert all(item.estado == "LIBERADA" for item in active)
