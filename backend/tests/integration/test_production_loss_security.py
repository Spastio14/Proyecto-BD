from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.exceptions import Conflict, PermissionDenied
from app.core.security import Principal
from app.models.entities import (
    ArticuloInventariable,
    DetallePerdida,
)
from app.services.designs import DesignService
from app.services.losses import LossLineInput, LossService
from app.services.orders import OrderService
from app.services.payments import PaymentService
from app.services.production import ProductionService
from tests.helpers import create_order
from tests.integration.test_payments_inventory import report_payment

pytestmark = pytest.mark.integration


def prepare_design_order(session, customer, employee):
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
    return order


def test_31_production_requires_current_design_approval(session, customer, employee):
    order = prepare_design_order(session, customer, employee)
    DesignService().add_version(
        session,
        order_id=order.id_pedido,
        line_number=1,
        file_name="v1.png",
        private_path="privado/test/v1.png",
        principal=customer,
    )
    with pytest.raises(Conflict, match="no está aprobada"):
        ProductionService().start(session, order_id=order.id_pedido, principal=employee)


def test_32_approval_of_v1_does_not_approve_v2(session, customer, employee):
    order = prepare_design_order(session, customer, employee)
    designs = DesignService()
    v1 = designs.add_version(
        session,
        order_id=order.id_pedido,
        line_number=1,
        file_name="v1.png",
        private_path="privado/test/v1.png",
        principal=customer,
    )
    designs.decide(
        session,
        order_id=order.id_pedido,
        line_number=1,
        version_number=v1.numero_version,
        approved=True,
        principal=employee,
    )
    designs.add_version(
        session,
        order_id=order.id_pedido,
        line_number=1,
        file_name="v2.png",
        private_path="privado/test/v2.png",
        principal=customer,
    )
    with pytest.raises(Conflict, match="versión vigente"):
        ProductionService().start(session, order_id=order.id_pedido, principal=employee)


def test_33_confirmed_loss_affects_inventory_once(session, employee):
    service = LossService()
    loss = service.report(
        session,
        principal=employee,
        moment="FUERA_PRODUCCION",
        incident_type="DANO_ALMACENAMIENTO",
        reason="Daño de prueba",
    )
    before = session.get(ArticuloInventariable, 1).existencia_actual
    lines = [LossLineInput(article_id=1, quantity=Decimal("1.000"))]
    service.confirm(session, loss_id=loss.id_perdida, lines=lines, principal=employee)
    after_first = session.get(ArticuloInventariable, 1).existencia_actual
    service.confirm(session, loss_id=loss.id_perdida, lines=lines, principal=employee)
    after_second = session.get(ArticuloInventariable, 1).existencia_actual
    assert after_first == before - Decimal("1.000")
    assert after_second == after_first
    assert (
        session.scalar(
            select(func.count())
            .select_from(DetallePerdida)
            .where(DetallePerdida.id_perdida == loss.id_perdida)
        )
        == 1
    )


def test_34_loss_outside_production_needs_no_order(session, employee):
    loss = LossService().report(
        session,
        principal=employee,
        moment="FUERA_PRODUCCION",
        incident_type="OTRO",
        reason="Incidente explicado",
    )
    LossService().confirm(
        session,
        loss_id=loss.id_perdida,
        lines=[LossLineInput(article_id=1, quantity=Decimal("0.500"))],
        principal=employee,
    )
    assert loss.id_pedido is None
    assert loss.estado_registro == "CONFIRMADA"


def test_35_loss_cost_remains_historical(session, employee):
    article = session.get(ArticuloInventariable, 1)
    original_cost = article.costo_referencia
    loss = LossService().report(
        session,
        principal=employee,
        moment="FUERA_PRODUCCION",
        incident_type="ROTURA_ARTICULO",
        reason="Rotura",
    )
    LossService().confirm(
        session,
        loss_id=loss.id_perdida,
        lines=[LossLineInput(article_id=1, quantity=Decimal("1.000"))],
        principal=employee,
    )
    detail = session.scalar(
        select(DetallePerdida).where(DetallePerdida.id_perdida == loss.id_perdida)
    )
    article.costo_referencia = Decimal("99.0000")
    session.flush()
    assert detail.costo_unitario_historico == original_cost


def test_36_customer_cannot_read_another_customers_order(api_client_factory, guest):
    response = api_client_factory(guest).get("/api/v1/pedidos/1")
    assert response.status_code == 403


def test_37_employee_without_permission_cannot_start_production(session, customer):
    order = create_order(session, customer)
    unauthorized = Principal(persona_id=2, origin="EMPLEADO")
    with pytest.raises(PermissionDenied):
        ProductionService().start(session, order_id=order.id_pedido, principal=unauthorized)


def test_38_protected_route_without_authentication_returns_401(api_client_factory):
    response = api_client_factory(None).get("/api/v1/pedidos")
    assert response.status_code == 401
    assert response.json()["error"] == "authentication_required"


def test_39_api_rejects_client_supplied_prices(api_client_factory, customer):
    response = api_client_factory(customer).post(
        "/api/v1/pedidos",
        json={"lines": [{"variant_id": 1, "quantity": 1, "price": "0.01"}]},
    )
    assert response.status_code == 422


def test_40_api_has_no_open_identity_impersonation(api_client_factory, customer):
    response = api_client_factory(customer).post(
        "/api/v1/pedidos",
        json={"id_cliente": 1, "lines": [{"variant_id": 1, "quantity": 1}]},
    )
    assert response.status_code == 422
