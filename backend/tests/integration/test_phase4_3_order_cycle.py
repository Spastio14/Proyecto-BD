from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.exceptions import Conflict
from app.models.entities import HistorialPedido, RegistroAuditoria
from app.services.deliveries import DeliveryService
from app.services.designs import DesignService
from app.services.inventory import InventoryService
from app.services.operations import OrderOperationService
from app.services.orders import OrderService
from app.services.payments import PaymentService
from app.services.production import ProductionService
from tests.helpers import create_order
from tests.integration.test_payments_inventory import report_payment
from tests.integration.test_phase4_2_roles_auth import add_employee

pytestmark = pytest.mark.integration


def prepare_production(session, customer, employee):
    order = create_order(session, customer)
    advance = report_payment(session, order, customer)
    PaymentService().confirm(session, payment_id=advance.id_transaccion, principal=employee)
    OrderService().transition_authorized(
        session,
        order_id=order.id_pedido,
        target="EN_DISENO",
        principal=employee,
        reason="Diseño iniciado",
    )
    version = DesignService().add_version(
        session,
        order_id=order.id_pedido,
        line_number=1,
        file_name="arte-fase-4-3.png",
        private_path="pedidos/prueba/arte-fase-4-3.png",
        principal=employee,
    )
    DesignService().decide(
        session,
        order_id=order.id_pedido,
        line_number=1,
        version_number=version.numero_version,
        approved=True,
        principal=customer,
    )
    ProductionService().start(session, order_id=order.id_pedido, principal=employee)
    return order


def test_208_complete_production_requires_material_consumption(session, customer, employee):
    order = prepare_production(session, customer, employee)
    with pytest.raises(Conflict, match="consumirse"):
        ProductionService().complete(session, order_id=order.id_pedido, principal=employee)
    InventoryService().consume_order(session, order_id=order.id_pedido, principal=employee)
    completed = ProductionService().complete(session, order_id=order.id_pedido, principal=employee)
    assert completed.estado == "LISTO"
    assert (
        session.scalar(
            select(HistorialPedido.estado_nuevo)
            .where(HistorialPedido.id_pedido == order.id_pedido)
            .order_by(HistorialPedido.id_historial.desc())
            .limit(1)
        )
        == "LISTO"
    )


def test_209_delivery_requires_verified_balance(session, customer, employee):
    order = prepare_production(session, customer, employee)
    InventoryService().consume_order(session, order_id=order.id_pedido, principal=employee)
    ProductionService().complete(session, order_id=order.id_pedido, principal=employee)
    with pytest.raises(Conflict, match="completamente pagado"):
        DeliveryService().complete(
            session,
            order_id=order.id_pedido,
            principal=employee,
            reason="Intento anticipado",
        )
    balance = PaymentService().report(
        session,
        order_id=order.id_pedido,
        milestone_number=2,
        idempotency_key=uuid4(),
        method="TRANSFERENCIA",
        principal=customer,
        bank_origin="BANCO-TEST",
        reference="CICLO-SALDO-001",
    )
    PaymentService().confirm(session, payment_id=balance.id_transaccion, principal=employee)
    delivered = DeliveryService().complete(
        session,
        order_id=order.id_pedido,
        principal=employee,
        reason="Retiro verificado",
    )
    assert delivered.estado == "ENTREGADO"


def test_210_operational_summary_exposes_next_safe_action(session, customer, employee):
    order = create_order(session, customer)
    initial = OrderOperationService.summary(session, order_id=order.id_pedido, principal=employee)
    assert initial["siguiente_accion"] == "REPORTAR_ANTICIPO"
    advance = report_payment(session, order, customer)
    PaymentService().confirm(session, payment_id=advance.id_transaccion, principal=employee)
    paid = OrderOperationService.summary(session, order_id=order.id_pedido, principal=employee)
    assert paid["pago"]["anticipo_verificado"] > 0
    assert paid["siguiente_accion"] == "INICIAR_DISENO"


def test_211_generic_state_endpoint_cannot_bypass_production(api_client_factory, employee):
    response = api_client_factory(employee).post(
        "/api/v1/pedidos/1/estado",
        json={"target": "LISTO", "reason": "Omitir controles"},
    )
    assert response.status_code == 422


def test_212_complete_cycle_is_audited(session, customer, employee):
    order = prepare_production(session, customer, employee)
    InventoryService().consume_order(session, order_id=order.id_pedido, principal=employee)
    ProductionService().complete(session, order_id=order.id_pedido, principal=employee)
    actions = set(
        session.scalars(
            select(RegistroAuditoria.accion).where(
                RegistroAuditoria.referencia_objeto == order.codigo_pedido
            )
        )
    )
    assert "CAMBIAR_ESTADO_PEDIDO" in actions


def test_213_operation_endpoint_is_scoped(api_client_factory, customer, guest):
    customer_client = api_client_factory(customer)
    order = customer_client.post(
        "/api/v1/pedidos",
        json={"lines": [{"variant_id": 1, "quantity": 1}]},
    )
    order_id = order.json()["id_pedido"]
    assert customer_client.get(f"/api/v1/pedidos/{order_id}/operacion").status_code == 200
    assert api_client_factory(guest).get(f"/api/v1/pedidos/{order_id}/operacion").status_code == 403


def test_219_production_role_can_read_operational_summary_without_payment_details(
    session, api_client_factory, customer
):
    production = add_employee(session, "PRODUCCION")
    order = create_order(session, customer)
    session.commit()
    response = api_client_factory(production).get(f"/api/v1/pedidos/{order.id_pedido}/operacion")
    assert response.status_code == 200
    assert response.json()["pago"]["anticipo_verificado"] == "0.00"
    assert api_client_factory(production).get("/api/v1/pagos").status_code == 403
