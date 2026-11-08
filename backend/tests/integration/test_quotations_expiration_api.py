from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.exceptions import Conflict, PermissionDenied
from app.models.entities import (
    ArticuloInventariable,
    DetallePedido,
    HistorialPedido,
    ReservaInventario,
)
from app.services.designs import DesignService
from app.services.expiration import OrderExpirationService
from app.services.orders import OrderService
from app.services.payments import PaymentService
from app.services.production import ProductionService
from app.services.quotations import QuotationService, QuoteLineInput
from tests.helpers import create_order
from tests.integration.test_payments_inventory import report_payment

pytestmark = pytest.mark.integration


def test_41_quotation_does_not_modify_inventory(session, customer):
    before_stock = session.get(ArticuloInventariable, 1).existencia_actual
    before_reservations = session.scalar(select(func.count()).select_from(ReservaInventario))
    quote = QuotationService().create(
        session,
        principal=customer,
        lines=[QuoteLineInput(variant_id=1, quantity=2, customization="Texto")],
    )
    assert quote.total_ofrecido == Decimal("180.00")
    assert session.get(ArticuloInventariable, 1).existencia_actual == before_stock
    assert (
        session.scalar(select(func.count()).select_from(ReservaInventario)) == before_reservations
    )


def test_42_accepted_quote_converts_only_once(session, customer):
    service = QuotationService()
    quote = service.create(
        session, principal=customer, lines=[QuoteLineInput(variant_id=1, quantity=2)]
    )
    quote.estado = "ACEPTADA"
    session.flush()
    order = service.convert(session, quote_id=quote.id_cotizacion, principal=customer)
    detail = session.get(DetallePedido, (order.id_pedido, 1))
    assert detail.modo_precio == "COTIZADO"
    assert order.id_cotizacion == quote.id_cotizacion
    with pytest.raises(Conflict, match="ya fue convertida"):
        service.convert(session, quote_id=quote.id_cotizacion, principal=customer)


def test_43_quote_of_another_customer_cannot_be_converted(session, customer, guest):
    quote = QuotationService().create(
        session, principal=customer, lines=[QuoteLineInput(variant_id=1, quantity=1)]
    )
    quote.estado = "ACEPTADA"
    session.flush()
    with pytest.raises(PermissionDenied):
        QuotationService().convert(session, quote_id=quote.id_cotizacion, principal=guest)


def test_44_expiration_is_repeatable_without_duplicate_history(session, customer):
    order = create_order(session, customer)
    current = datetime.now(UTC)
    order.fecha_creacion = current - timedelta(hours=25)
    order.vencimiento_pago = current - timedelta(hours=1)
    session.flush()
    service = OrderExpirationService()
    assert service.expire_due(session, now=current) == 1
    assert service.expire_due(session, now=current) == 0
    assert order.estado == "EXPIRADO"
    assert (
        session.scalar(
            select(func.count())
            .select_from(HistorialPedido)
            .where(
                HistorialPedido.id_pedido == order.id_pedido,
                HistorialPedido.estado_nuevo == "EXPIRADO",
            )
        )
        == 1
    )


def test_45_pending_payment_review_expires_after_single_24h_window(session, customer):
    order = create_order(session, customer)
    payment = report_payment(session, order, customer)
    current = datetime.now(UTC)
    order.fecha_creacion = current - timedelta(hours=49)
    order.vencimiento_pago = current - timedelta(hours=25)
    order.fecha_inicio_revision_pago = current - timedelta(hours=25, minutes=1)
    session.flush()
    assert payment.estado_verificacion == "PENDIENTE"
    assert OrderExpirationService().expire_due(session, now=current) == 1
    assert order.estado == "EXPIRADO"


def test_46_health_and_openapi_are_available(api_client_factory):
    client = api_client_factory(None)
    assert client.get("/api/v1/health").json() == {"status": "ok", "database": "postgresql"}
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    assert "/api/v1/pedidos" in schema.json()["paths"]


def test_47_public_catalog_does_not_expose_wholesale_scales(api_client_factory):
    response = api_client_factory(None).get("/api/v1/catalogo")
    assert response.status_code == 200
    assert response.json()[0]["precio_detalle"] == "90.00"
    assert "precio_unitario_mayorista" not in response.json()[0]


def test_48_production_starts_after_advance_and_current_approval(session, customer, employee):
    order = create_order(session, customer)
    payment = report_payment(session, order, customer)
    PaymentService().confirm(session, payment_id=payment.id_transaccion, principal=employee)
    OrderService().transition(
        session,
        order_id=order.id_pedido,
        target="EN_DISENO",
        principal=employee,
        reason="Diseño",
    )
    design = DesignService().add_version(
        session,
        order_id=order.id_pedido,
        line_number=1,
        file_name="v1.png",
        private_path="privado/test/v1.png",
        principal=employee,
    )
    DesignService().decide(
        session,
        order_id=order.id_pedido,
        line_number=1,
        version_number=design.numero_version,
        approved=True,
        principal=customer,
    )
    ProductionService().start(session, order_id=order.id_pedido, principal=employee)
    assert order.estado == "EN_PRODUCCION"


def test_49_late_payment_requires_explicit_administrative_permission(session, customer, employee):
    order = create_order(session, customer)
    payment = report_payment(session, order, customer)
    current = datetime.now(UTC)
    order.fecha_creacion = current - timedelta(hours=49)
    order.vencimiento_pago = current - timedelta(hours=25)
    order.fecha_inicio_revision_pago = current - timedelta(hours=25, minutes=1)
    session.flush()
    with pytest.raises(PermissionDenied, match="PAGO_TARDIO_AUTORIZAR"):
        PaymentService().confirm(session, payment_id=payment.id_transaccion, principal=employee)


def test_50_later_balance_never_regresses_production_state(session, customer, employee):
    order = create_order(session, customer)
    advance = report_payment(session, order, customer)
    PaymentService().confirm(session, payment_id=advance.id_transaccion, principal=employee)
    OrderService().transition(
        session,
        order_id=order.id_pedido,
        target="EN_DISENO",
        principal=employee,
        reason="Diseño",
    )
    design = DesignService().add_version(
        session,
        order_id=order.id_pedido,
        line_number=1,
        file_name="v1.png",
        private_path="privado/test/v1.png",
        principal=employee,
    )
    DesignService().decide(
        session,
        order_id=order.id_pedido,
        line_number=1,
        version_number=design.numero_version,
        approved=True,
        principal=customer,
    )
    ProductionService().start(session, order_id=order.id_pedido, principal=employee)
    balance = PaymentService().report(
        session,
        order_id=order.id_pedido,
        milestone_number=2,
        idempotency_key=uuid4(),
        method="TRANSFERENCIA",
        principal=customer,
        bank_origin="BANCO-TEST",
        reference="PRODUCCION-SALDO-001",
    )
    PaymentService().confirm(session, payment_id=balance.id_transaccion, principal=employee)
    assert order.estado == "EN_PRODUCCION"
