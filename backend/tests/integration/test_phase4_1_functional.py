from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import NotFound
from app.models.entities import (
    ArticuloInventariable,
    Compra,
    Envio,
    HitoPago,
    MovimientoInventario,
    Pedido,
    Proveedor,
)
from app.services.deliveries import DeliveryService
from app.services.purchases import PurchaseService
from app.services.quotations import QuotationService, QuoteLineInput
from tests.helpers import create_order

pytestmark = pytest.mark.integration


def test_110_quote_decision_and_conversion_rules(session, customer):
    quote = QuotationService().create(
        session,
        principal=customer,
        lines=[QuoteLineInput(variant_id=1, quantity=2, customization="Demo")],
    )
    decided = QuotationService.decide(
        session,
        quote_id=quote.id_cotizacion,
        decision="ACEPTADA",
        principal=customer,
        reason="Cliente confirma la oferta",
    )
    assert decided.estado == "ACEPTADA"
    order = QuotationService().convert(session, quote_id=quote.id_cotizacion, principal=customer)
    assert order.id_cotizacion == quote.id_cotizacion


def test_111_quote_and_order_endpoints_are_scoped(api_client_factory, customer):
    client = api_client_factory(customer)
    quote = client.post(
        "/api/v1/cotizaciones",
        json={"lines": [{"variant_id": 1, "quantity": 1, "customization": None}]},
    )
    assert quote.status_code == 201
    quote_id = quote.json()["id_cotizacion"]
    assert (
        client.post(
            f"/api/v1/cotizaciones/{quote_id}/decision",
            json={"decision": "RECHAZADA", "reason": "Cambió el requerimiento"},
        ).status_code
        == 200
    )
    order = client.post(
        "/api/v1/pedidos",
        json={"lines": [{"variant_id": 1, "quantity": 1}], "delivery_mode": "RETIRO"},
    )
    assert order.status_code == 201
    order_id = order.json()["id_pedido"]
    assert client.get(f"/api/v1/pedidos/{order_id}/detalles").status_code == 200
    history = client.get(f"/api/v1/pedidos/{order_id}/historial")
    assert history.status_code == 200
    assert history.json()[0]["estado_nuevo"] == "PENDIENTE_PAGO"


def test_112_purchase_confirmation_increases_stock_once(session, employee):
    initial = session.get(ArticuloInventariable, 1).existencia_actual
    purchase = PurchaseService().create(
        session,
        principal=employee,
        provider_id=1,
        document_number="DEMO-COMPRA-30",
        lines=[(1, Decimal("30.000"), Decimal("25.0000"))],
    )
    assert purchase.estado == "BORRADOR"
    assert purchase.total_compra == Decimal("750.00")
    assert session.get(ArticuloInventariable, 1).existencia_actual == initial
    PurchaseService().confirm(session, purchase_id=purchase.id_compra, principal=employee)
    PurchaseService().confirm(session, purchase_id=purchase.id_compra, principal=employee)
    assert session.get(ArticuloInventariable, 1).existencia_actual == initial + Decimal("30.000")
    assert (
        session.scalar(
            select(func.count())
            .select_from(MovimientoInventario)
            .where(MovimientoInventario.id_compra == purchase.id_compra)
        )
        == 1
    )


@pytest.mark.concurrency
def test_113_concurrent_purchase_confirmation_is_idempotent(engine, session, employee):
    purchase = PurchaseService().create(
        session,
        principal=employee,
        provider_id=1,
        document_number="DEMO-CONCURRENCIA",
        lines=[(1, Decimal("3.000"), Decimal("25.0000"))],
    )
    purchase_id = purchase.id_compra
    initial = session.get(ArticuloInventariable, 1).existencia_actual
    session.commit()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    barrier = Barrier(2)

    def confirm() -> str:
        with factory() as worker:
            barrier.wait()
            PurchaseService().confirm(worker, purchase_id=purchase_id, principal=employee)
            worker.commit()
        return "ok"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(lambda _: confirm(), range(2))) == ["ok", "ok"]
    with factory() as verification:
        assert verification.get(ArticuloInventariable, 1).existencia_actual == initial + Decimal(
            "3.000"
        )
        assert (
            verification.scalar(
                select(func.count())
                .select_from(MovimientoInventario)
                .where(MovimientoInventario.id_compra == purchase_id)
            )
            == 1
        )


def test_114_purchase_api_validates_permissions_and_relations(
    api_client_factory, customer, employee
):
    denied = api_client_factory(customer).get("/api/v1/compras")
    assert denied.status_code == 403
    client = api_client_factory(employee)
    created = client.post(
        "/api/v1/compras",
        json={
            "provider_id": 1,
            "document_number": "API-DEMO",
            "lines": [{"article_id": 1, "quantity": "2.000", "unit_cost": "25.0000"}],
        },
    )
    assert created.status_code == 201
    purchase_id = created.json()["id_compra"]
    assert client.get(f"/api/v1/compras/{purchase_id}/detalles").status_code == 200
    assert client.post(f"/api/v1/compras/{purchase_id}/confirmar").json()["estado"] == "CONFIRMADA"


def test_115_delivery_requires_ready_order_and_closes_history(session, customer, employee):
    order = create_order(session, customer)
    order.modalidad_entrega = "ENVIO"
    order.estado = "LISTO"
    for milestone in session.scalars(select(HitoPago).where(HitoPago.id_pedido == order.id_pedido)):
        milestone.estado = "PAGADO"
    delivery = DeliveryService().schedule(
        session,
        order_id=order.id_pedido,
        agency_id=1,
        address="Dirección ficticia",
        recipient_name="Persona Ficticia",
        recipient_phone=None,
        agreed_fee=Decimal("50.00"),
        scheduled_at=None,
        principal=employee,
    )
    delivered = DeliveryService().complete(
        session,
        order_id=order.id_pedido,
        principal=employee,
        reason="Entrega demostrativa",
    )
    assert delivered.estado == "ENTREGADO"
    assert delivery.estado == "ENTREGADO"
    assert delivery.fecha_entrega_real is not None


def test_116_reports_and_static_frontend_are_available(api_client_factory, employee):
    client = api_client_factory(employee)
    report = client.get("/api/v1/reportes/resumen")
    assert report.status_code == 200
    assert {
        "productos_mas_vendidos",
        "pedidos_por_cliente",
        "ingresos_verificados",
        "compras_por_proveedor",
        "inventario",
    }.issubset(report.json())
    assert client.get("/").status_code == 200
    page = client.get("/app/")
    assert page.status_code == 200
    assert "Hazlo tuyo. Nosotros lo hacemos real." in page.text


def test_117_provider_and_purchase_listing_filters(session, employee):
    provider = PurchaseService.create_provider(
        session,
        principal=employee,
        name="Proveedor Aislado",
        phone=None,
        email="aislado@example.test",
        address=None,
    )
    PurchaseService().create(
        session,
        principal=employee,
        provider_id=provider.id_proveedor,
        document_number=None,
        lines=[(1, Decimal("1.000"), Decimal("20.0000"))],
    )
    rows = PurchaseService.list_purchases(
        session, principal=employee, provider_id=provider.id_proveedor
    )
    assert len(rows) == 1
    assert rows[0].id_proveedor == provider.id_proveedor


def test_118_failed_purchase_is_atomic(session, employee):
    before = session.scalar(select(func.count()).select_from(Compra))
    with pytest.raises(NotFound):
        with session.begin_nested():
            PurchaseService().create(
                session,
                principal=employee,
                provider_id=1,
                document_number="DEMO-ROLLBACK",
                lines=[(999999, Decimal("1.000"), Decimal("10.0000"))],
            )
    assert session.scalar(select(func.count()).select_from(Compra)) == before


def test_119_models_cover_purchase_and_delivery_tables(session):
    assert session.scalar(select(func.count()).select_from(Proveedor)) >= 1
    assert session.scalar(select(func.count()).select_from(Pedido)) >= 1
    assert session.scalar(select(func.count()).select_from(Envio)) >= 1


def test_120_payment_rejection_and_static_order_route(api_client_factory, customer, employee):
    customer_client = api_client_factory(customer)
    order = customer_client.post(
        "/api/v1/pedidos",
        json={"lines": [{"variant_id": 1, "quantity": 1}], "delivery_mode": "RETIRO"},
    )
    order_id = order.json()["id_pedido"]
    reported = customer_client.post(
        f"/api/v1/pagos/pedidos/{order_id}/reportar",
        json={
            "milestone_number": 1,
            "idempotency_key": str(uuid4()),
            "method": "TRANSFERENCIA",
            "bank": "BANCO-DEMO",
            "reference": "REF-DEMO",
        },
    )
    assert reported.status_code == 201
    payment_id = reported.json()["id_transaccion"]
    employee_client = api_client_factory(employee)
    rejected = employee_client.post(
        f"/api/v1/pagos/{payment_id}/rechazar",
        json={"reason": "Comprobante ficticio inválido"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["estado_verificacion"] == "RECHAZADO"
    listed = customer_client.get(f"/api/v1/pagos/pedidos/{order_id}")
    assert listed.status_code == 200
    assert listed.json()[0]["id_transaccion"] == payment_id
