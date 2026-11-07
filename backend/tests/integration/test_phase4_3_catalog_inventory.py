from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.exceptions import Conflict
from app.models.entities import ArticuloInventariable, ReservaInventario
from app.services.catalog_admin import CatalogAdminService
from app.services.inventory import InventoryService
from app.services.payments import PaymentService
from app.services.purchases import PurchaseService
from tests.helpers import create_order
from tests.integration.test_payments_inventory import report_payment

pytestmark = pytest.mark.integration


def test_201_admin_catalog_crud_and_duplicate_variant_code(session, employee, api_client_factory):
    client = api_client_factory(employee)
    category = client.post(
        "/api/v1/catalogo/admin/categorias",
        json={"name": "Nuevos textiles", "description": "Catálogo de prueba"},
    )
    assert category.status_code == 201
    category_id = category.json()["id_categoria"]
    product = client.post(
        "/api/v1/catalogo/admin/productos",
        json={
            "category_id": category_id,
            "name": "Camiseta deportiva",
            "description": "Prueba",
            "commercial_information": "Personalizable",
            "publication_state": "BORRADOR",
        },
    )
    assert product.status_code == 201
    variant_payload = {
        "product_id": product.json()["id_producto"],
        "code": "DEP-001",
        "features": "Azul",
        "retail_price": "180.00",
        "requires_production": True,
    }
    first = client.post("/api/v1/catalogo/admin/variantes", json=variant_payload)
    assert first.status_code == 201
    assert first.json()["codigo_variante"] == "DEP-001"
    duplicate = client.post("/api/v1/catalogo/admin/variantes", json=variant_payload)
    assert duplicate.status_code == 409
    updated = client.patch(
        f"/api/v1/catalogo/admin/productos/{product.json()['id_producto']}",
        json={"publication_state": "PUBLICADO"},
    )
    assert updated.json()["estado_publicacion"] == "PUBLICADO"


def test_202_catalog_management_requires_explicit_permission(api_client_factory, customer):
    client = api_client_factory(customer)
    assert client.get("/api/v1/catalogo/admin/categorias").status_code == 403
    assert (
        client.post(
            "/api/v1/inventario/articulos",
            json={
                "code": "NO-001",
                "name": "No permitido",
                "article_type": "INSUMO",
                "unit": "UNIDAD",
                "minimum_stock": "0",
                "reference_cost": "0",
            },
        ).status_code
        == 403
    )


def test_203_article_starts_at_zero_and_only_movements_change_stock(session, employee):
    article = InventoryService.create_article(
        session,
        principal=employee,
        code="VINILO-TEST",
        name="Vinilo de prueba",
        article_type="INSUMO",
        unit="M",
        minimum_stock=Decimal("5.000"),
        reference_cost=Decimal("20.0000"),
    )
    assert article.existencia_actual == Decimal("0.000")
    provider = PurchaseService.create_provider(
        session,
        principal=employee,
        name="Proveedor fase 4.3",
        phone=None,
        email=None,
        address=None,
    )
    purchase = PurchaseService().create(
        session,
        principal=employee,
        provider_id=provider.id_proveedor,
        document_number="COMPRA-50",
        lines=[(article.id_articulo, Decimal("50.000"), Decimal("19.5000"))],
    )
    assert article.existencia_actual == Decimal("0.000")
    PurchaseService().confirm(session, purchase_id=purchase.id_compra, principal=employee)
    assert article.existencia_actual == Decimal("50.000")
    movement = InventoryService.adjust(
        session,
        article_id=article.id_articulo,
        direction="SALIDA",
        quantity=Decimal("2.000"),
        reason="Conteo físico autorizado",
        observations="Acta ficticia",
        principal=employee,
    )
    assert movement.tipo_movimiento == "SALIDA_AJUSTE"
    assert article.existencia_actual == Decimal("48.000")
    InventoryService.update_article(
        session,
        article_id=article.id_articulo,
        principal=employee,
        changes={"name": "Vinilo actualizado", "minimum_stock": Decimal("10")},
    )
    assert article.existencia_actual == Decimal("48.000")


def test_204_wholesale_scales_reject_overlap(session, employee):
    service = CatalogAdminService()
    variant = service.create_variant(
        session,
        principal=employee,
        product_id=1,
        code="ESCALA-TEST",
        features=None,
        retail_price=Decimal("100.00"),
        requires_production=False,
    )
    service.upsert_scale(
        session,
        variant_id=variant.id_variante,
        principal=employee,
        range_number=90,
        minimum_quantity=100,
        maximum_quantity=199,
        wholesale_unit_price=Decimal("75.00"),
        state="ACTIVA",
    )
    with pytest.raises(Conflict, match="solapa"):
        service.upsert_scale(
            session,
            variant_id=variant.id_variante,
            principal=employee,
            range_number=91,
            minimum_quantity=150,
            maximum_quantity=250,
            wholesale_unit_price=Decimal("70.00"),
            state="ACTIVA",
        )


def test_205_recipe_change_preserves_reserved_order_snapshot(session, customer, employee):
    order = create_order(session, customer)
    service = CatalogAdminService()
    with pytest.raises(Conflict, match="reserva histórica"):
        service.upsert_composition(
            session,
            variant_id=1,
            article_id=1,
            standard_quantity=Decimal("2.000"),
            observations="Nueva receta",
            principal=employee,
        )
    payment = report_payment(session, order, customer)
    PaymentService().confirm(session, payment_id=payment.id_transaccion, principal=employee)
    reservation = session.scalar(
        select(ReservaInventario).where(
            ReservaInventario.id_pedido == order.id_pedido,
            ReservaInventario.id_articulo == 1,
        )
    )
    assert reservation.cantidad_reservada == Decimal("1.000")
    service.upsert_composition(
        session,
        variant_id=1,
        article_id=1,
        standard_quantity=Decimal("2.000"),
        observations="Nueva receta",
        principal=employee,
    )
    assert reservation.cantidad_reservada == Decimal("1.000")
    requirements = service.requirements(session, variant_id=1, quantity=3, principal=employee)
    assert requirements["requerimientos"][0]["cantidad_requerida"] == Decimal("6.000")


def test_206_production_variant_without_recipe_is_flagged_incomplete(session, employee):
    service = CatalogAdminService()
    variant = service.create_variant(
        session,
        principal=employee,
        product_id=1,
        code="SIN-RECETA",
        features=None,
        retail_price=Decimal("10.00"),
        requires_production=True,
    )
    result = service.requirements(
        session, variant_id=variant.id_variante, quantity=1, principal=employee
    )
    assert result["composicion_incompleta"] is True
    assert result["disponible_para_producir"] is False


def test_207_article_code_is_unique(session, employee):
    existing = session.get(ArticuloInventariable, 1)
    with pytest.raises(Conflict, match="ya existe"):
        InventoryService.create_article(
            session,
            principal=employee,
            code=existing.codigo,
            name="Duplicado",
            article_type="INSUMO",
            unit="UNIDAD",
            minimum_stock=Decimal("0"),
            reference_cost=Decimal("0"),
        )
