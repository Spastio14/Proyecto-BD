from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import Barrier

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import Conflict, NotFound
from app.models.entities import (
    DetallePedido,
    EscalaPrecio,
    Pedido,
    Promocion,
    PromocionVariante,
    VarianteProducto,
)
from app.services.orders import OrderLineInput, OrderService
from app.services.pricing import PricingService
from tests.helpers import add_client, create_order

pytestmark = pytest.mark.integration


def test_01_guest_five_units_allowed(session, guest):
    order = create_order(session, guest, quantity=5)
    assert order.total_pedido == Decimal("450.00")


def test_02_guest_six_units_rejected(session, guest):
    with pytest.raises(Conflict, match="máximo 5"):
        create_order(session, guest, quantity=6)


def test_03_guest_never_receives_wholesale_price(session):
    result = PricingService().price_line(session, client_type="INVITADO", variant_id=1, quantity=12)
    assert result.mode == "DETALLE"
    assert result.unit_price == Decimal("90.00")


def test_04_guest_cannot_have_two_active_orders(session, guest):
    create_order(session, guest)
    with pytest.raises(Conflict, match="pedido activo"):
        create_order(session, guest)


def test_05_registered_cannot_create_third_pending_order(session, customer):
    create_order(session, customer)
    create_order(session, customer)
    with pytest.raises(Conflict, match="dos pedidos"):
        create_order(session, customer)


def test_06_paid_registered_orders_do_not_count_toward_limit(session, customer):
    first = create_order(session, customer)
    second = create_order(session, customer)
    first.estado = "PAGADO"
    second.estado = "EN_PRODUCCION"
    session.flush()
    third = create_order(session, customer)
    assert third.estado == "PENDIENTE_PAGO"


@pytest.mark.concurrency
def test_07_concurrent_guest_requests_do_not_evade_limit(engine, session):
    principal = add_client(session, client_type="INVITADO")
    session.commit()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    barrier = Barrier(2)

    def attempt() -> str:
        with factory() as worker:
            barrier.wait()
            try:
                create_order(worker, principal)
                worker.commit()
                return "created"
            except Conflict:
                worker.rollback()
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    assert sorted(results) == ["conflict", "created"]


def test_08_invalid_order_rolls_back(session, guest):
    before = session.scalar(select(func.count()).select_from(Pedido))
    with pytest.raises(NotFound):
        OrderService().create(
            session,
            principal=guest,
            lines=[OrderLineInput(variant_id=99999, quantity=1)],
        )
    session.rollback()
    after = session.scalar(select(func.count()).select_from(Pedido))
    assert after == before


def test_09_detail_price_comes_from_database(session):
    result = PricingService().price_line(
        session, client_type="REGISTRADO", variant_id=1, quantity=1
    )
    assert result.unit_price == Decimal("90.00")
    assert result.mode == "DETALLE"


def test_10_wholesale_price_only_when_scale_matches(session):
    service = PricingService()
    retail = service.price_line(session, client_type="REGISTRADO", variant_id=1, quantity=11)
    wholesale = service.price_line(
        session,
        client_type="REGISTRADO",
        commercial_condition="MAYORISTA",
        variant_id=1,
        quantity=12,
    )
    assert retail.mode == "DETALLE"
    assert wholesale.mode == "MAYORISTA"
    assert wholesale.unit_price == Decimal("80.00")


def test_11_overlapping_active_scales_are_rejected_by_postgresql(session):
    session.add(
        EscalaPrecio(
            id_variante=1,
            numero_rango=99,
            cantidad_minima=20,
            cantidad_maxima=40,
            precio_unitario_mayorista=Decimal("70.00"),
            estado="ACTIVA",
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_12_active_promotion_is_applied(session):
    result = PricingService().price_line(
        session, client_type="REGISTRADO", variant_id=1, quantity=2, promotion_id=1
    )
    assert result.mode == "PROMOCION"
    assert result.total == Decimal("170.00")


def test_13_expired_promotion_is_rejected(session):
    promotion = Promocion(
        nombre="Vencida",
        tipo="PORCENTAJE",
        cantidad_requerida=1,
        beneficio="10 %",
        fecha_inicio=datetime.now(UTC) - timedelta(days=2),
        fecha_fin=datetime.now(UTC) - timedelta(days=1),
        condiciones=None,
        permite_combinacion_mayorista=False,
        valor_beneficio=Decimal("10.00"),
        estado="ACTIVA",
    )
    session.add(promotion)
    session.flush()
    session.add(PromocionVariante(id_promocion=promotion.id_promocion, id_variante=1))
    session.flush()
    with pytest.raises(Conflict, match="no está vigente"):
        PricingService().price_line(
            session,
            client_type="REGISTRADO",
            variant_id=1,
            quantity=1,
            promotion_id=promotion.id_promocion,
        )


def test_14_discount_cannot_exceed_gross(session):
    promotion = Promocion(
        nombre="Excesiva",
        tipo="DESCUENTO_FIJO",
        cantidad_requerida=1,
        beneficio="Descuento inválido",
        fecha_inicio=datetime.now(UTC) - timedelta(days=1),
        fecha_fin=datetime.now(UTC) + timedelta(days=1),
        condiciones=None,
        permite_combinacion_mayorista=False,
        valor_beneficio=Decimal("1000.00"),
        estado="ACTIVA",
    )
    session.add(promotion)
    session.flush()
    session.add(PromocionVariante(id_promocion=promotion.id_promocion, id_variante=1))
    session.flush()
    with pytest.raises(Conflict, match="supera"):
        PricingService().price_line(
            session,
            client_type="REGISTRADO",
            variant_id=1,
            quantity=1,
            promotion_id=promotion.id_promocion,
        )


def test_15_price_change_does_not_modify_historical_order(session, customer):
    order = create_order(session, customer)
    detail = session.get(DetallePedido, (order.id_pedido, 1))
    historical = detail.precio_unitario_aplicado
    session.get(VarianteProducto, 1).precio_detalle = Decimal("150.00")
    session.flush()
    session.refresh(detail)
    assert detail.precio_unitario_aplicado == historical == Decimal("90.00")


def test_16_two_cups_for_170_uses_configured_promotion(session, customer):
    order = create_order(session, customer, quantity=2, promotion_id=1)
    detail = session.get(DetallePedido, (order.id_pedido, 1))
    assert order.total_pedido == Decimal("170.00")
    assert detail.descuento_aplicado == Decimal("10.00")
    assert detail.id_promocion == 1
