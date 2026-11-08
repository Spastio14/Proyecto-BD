from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import Conflict
from app.models.entities import (
    ArticuloInventariable,
    MovimientoInventario,
    RegistroAuditoria,
    ReservaInventario,
)
from app.services.authorization import AuthorizationService
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


def ready_for_production(session, customer, administrator, production):
    order = create_order(session, customer)
    advance = report_payment(session, order, customer)
    PaymentService().confirm(
        session,
        payment_id=advance.id_transaccion,
        principal=administrator,
    )
    OrderService().transition_authorized(
        session,
        order_id=order.id_pedido,
        target="EN_DISENO",
        principal=production,
        reason="Diseño iniciado por producción",
    )
    version = DesignService().add_version(
        session,
        order_id=order.id_pedido,
        line_number=1,
        file_name="permiso-produccion.png",
        private_path=f"pedidos/{order.id_pedido}/permiso-produccion.png",
        principal=production,
    )
    DesignService().decide(
        session,
        order_id=order.id_pedido,
        line_number=1,
        version_number=version.numero_version,
        approved=True,
        principal=customer,
    )
    return order


def in_production(session, customer, administrator, production):
    order = ready_for_production(session, customer, administrator, production)
    ProductionService().start(session, order_id=order.id_pedido, principal=production)
    return order


def test_production_can_start_consume_once_and_complete(
    session, customer, api_client_factory
):
    administrator = add_employee(session, "ADMINISTRADOR")
    production = add_employee(session, "PRODUCCION")
    order = ready_for_production(session, customer, administrator, production)
    session.commit()
    client = api_client_factory(production)

    started = client.post(f"/api/v1/produccion/pedidos/{order.id_pedido}/iniciar")
    assert started.status_code == 200
    assert started.json()["estado"] == "EN_PRODUCCION"

    session.expire_all()
    before = session.get(ArticuloInventariable, 1).existencia_actual
    assert before == Decimal("18.000")
    summary = client.get(f"/api/v1/pedidos/{order.id_pedido}/operacion").json()
    assert summary["produccion"]["acciones_permitidas"] == ["CONSUMIR_RESERVAS"]

    first = client.post(f"/api/v1/inventario/pedidos/{order.id_pedido}/consumir")
    second = client.post(f"/api/v1/inventario/pedidos/{order.id_pedido}/consumir")
    assert first.status_code == second.status_code == 200
    assert first.json()["movimientos"] == second.json()["movimientos"]

    session.expire_all()
    article = session.get(ArticuloInventariable, 1)
    reservation = session.scalar(
        select(ReservaInventario).where(ReservaInventario.id_pedido == order.id_pedido)
    )
    assert article.existencia_actual == Decimal("17.000")
    assert reservation.estado == "AGOTADA"
    assert reservation.cantidad_pendiente == Decimal("0.000")
    assert (
        session.scalar(
            select(func.count())
            .select_from(MovimientoInventario)
            .where(
                MovimientoInventario.id_pedido == order.id_pedido,
                MovimientoInventario.tipo_movimiento == "SALIDA_PRODUCCION",
            )
        )
        == 1
    )
    audit = session.scalar(
        select(RegistroAuditoria)
        .where(
            RegistroAuditoria.accion == "CONSUMIR_RESERVAS_PRODUCCION",
            RegistroAuditoria.referencia_objeto == str(order.id_pedido),
        )
        .order_by(RegistroAuditoria.id_auditoria.desc())
    )
    assert audit.id_persona_actor == production.persona_id

    after_consumption = client.get(f"/api/v1/pedidos/{order.id_pedido}/operacion").json()
    assert after_consumption["produccion"]["acciones_permitidas"] == [
        "COMPLETAR_PRODUCCION"
    ]
    completed = client.post(f"/api/v1/produccion/pedidos/{order.id_pedido}/completar")
    assert completed.status_code == 200
    assert completed.json()["estado"] == "LISTO"
    assert client.post(f"/api/v1/inventario/pedidos/{order.id_pedido}/consumir").status_code == 409
    assert client.post(f"/api/v1/produccion/pedidos/{order.id_pedido}/completar").status_code == 409


def test_production_cannot_administer_inventory(session, api_client_factory):
    production = add_employee(session, "PRODUCCION")
    session.commit()
    assert AuthorizationService.has_permission(
        session, production, "INVENTARIO_CONSUMIR_RESERVAS"
    )
    assert not AuthorizationService.has_permission(session, production, "INVENTARIO_GESTIONAR")
    client = api_client_factory(production)
    article = {
        "code": "PROD-NO",
        "name": "Artículo no autorizado",
        "article_type": "INSUMO",
        "unit": "UNIDAD",
        "minimum_stock": "0",
        "reference_cost": "999.0000",
    }
    assert client.post("/api/v1/inventario/articulos", json=article).status_code == 403
    assert (
        client.post(
            "/api/v1/inventario/articulos/1/ajustes",
            json={
                "direction": "ENTRADA",
                "quantity": "5.000",
                "reason": "Intento no autorizado",
                "observations": None,
            },
        ).status_code
        == 403
    )
    assert (
        client.patch(
            "/api/v1/inventario/articulos/1",
            json={"reference_cost": "999.0000"},
        ).status_code
        == 403
    )


@pytest.mark.parametrize(
    "state",
    ["PAGADO_PARCIAL", "EN_DISENO", "CANCELADO", "EXPIRADO", "LISTO", "ENTREGADO"],
)
def test_consumption_rejects_every_state_outside_production(
    session, customer, employee, state
):
    production = add_employee(session, "PRODUCCION")
    order = create_order(session, customer)
    advance = report_payment(session, order, customer)
    PaymentService().confirm(session, payment_id=advance.id_transaccion, principal=employee)
    order.estado = state
    session.flush()
    with pytest.raises(Conflict, match="pedidos en producción"):
        InventoryService().consume_order(
            session,
            order_id=order.id_pedido,
            principal=production,
        )


def test_only_administrator_and_production_receive_consumption_permission(session):
    administrator = add_employee(session, "ADMINISTRADOR")
    production = add_employee(session, "PRODUCCION")
    seller = add_employee(session, "VENDEDOR")
    accountant = add_employee(session, "CONTADOR")
    assert AuthorizationService.has_permission(
        session, administrator, "INVENTARIO_CONSUMIR_RESERVAS"
    )
    assert AuthorizationService.has_permission(
        session, production, "INVENTARIO_CONSUMIR_RESERVAS"
    )
    assert not AuthorizationService.has_permission(
        session, seller, "INVENTARIO_CONSUMIR_RESERVAS"
    )
    assert not AuthorizationService.has_permission(
        session, accountant, "INVENTARIO_CONSUMIR_RESERVAS"
    )


def test_seller_and_accountant_cannot_consume_production_reservations(
    session, customer, employee, api_client_factory
):
    production = add_employee(session, "PRODUCCION")
    seller = add_employee(session, "VENDEDOR")
    accountant = add_employee(session, "CONTADOR")
    order = in_production(session, customer, employee, production)
    session.commit()
    path = f"/api/v1/inventario/pedidos/{order.id_pedido}/consumir"
    assert api_client_factory(seller).post(path).status_code == 403
    assert api_client_factory(accountant).post(path).status_code == 403


@pytest.mark.concurrency
def test_concurrent_consumption_discount_is_exactly_once(
    engine, session, customer, employee
):
    production = add_employee(session, "PRODUCCION")
    order = in_production(session, customer, employee, production)
    order_id = order.id_pedido
    before = session.get(ArticuloInventariable, 1).existencia_actual
    session.commit()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    barrier = Barrier(2)

    def consume() -> list[int]:
        with factory() as worker, worker.begin():
            barrier.wait()
            return [
                item.id_movimiento
                for item in InventoryService().consume_order(
                    worker,
                    order_id=order_id,
                    principal=production,
                )
            ]

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: consume(), range(2)))
    assert results[0] == results[1]
    session.expire_all()
    assert session.get(ArticuloInventariable, 1).existencia_actual == before - Decimal("1.000")
    assert (
        session.scalar(
            select(func.count())
            .select_from(MovimientoInventario)
            .where(
                MovimientoInventario.id_pedido == order_id,
                MovimientoInventario.tipo_movimiento == "SALIDA_PRODUCCION",
            )
        )
        == 1
    )


def test_production_cannot_complete_when_required_reservations_are_missing(
    session, customer, employee
):
    production = add_employee(session, "PRODUCCION")
    order = in_production(session, customer, employee, production)
    reservations = list(
        session.scalars(
            select(ReservaInventario).where(ReservaInventario.id_pedido == order.id_pedido)
        )
    )
    for reservation in reservations:
        session.delete(reservation)
    session.flush()
    with pytest.raises(Conflict, match="reservas de producción verificables"):
        ProductionService().complete(
            session,
            order_id=order.id_pedido,
            principal=production,
        )


def test_operation_summary_explains_permission_and_state(session, customer, employee):
    production = add_employee(session, "PRODUCCION")
    order = in_production(session, customer, employee, production)
    allowed = OrderOperationService.summary(
        session,
        order_id=order.id_pedido,
        principal=production,
    )
    assert allowed["produccion"]["acciones_permitidas"] == ["CONSUMIR_RESERVAS"]
    assert "reservas activas" in allowed["produccion"]["mensaje"]
    denied = OrderOperationService.summary(
        session,
        order_id=order.id_pedido,
        principal=add_employee(session, "VENDEDOR"),
    )
    assert denied["produccion"]["acciones_permitidas"] == []
    assert "permiso" in denied["produccion"]["mensaje"]
