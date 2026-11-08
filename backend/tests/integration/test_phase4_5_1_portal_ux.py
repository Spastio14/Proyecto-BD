from pathlib import Path

import pytest

from tests.helpers import add_client

pytestmark = pytest.mark.integration


FORBIDDEN_CLIENT_KEYS = {
    "id_cliente",
    "id_persona",
    "id_pedido",
    "id_cotizacion",
    "id_articulo",
    "clave_idem",
    "costo_unitario",
    "costo_total",
    "uuid_auth",
    "permisos",
}


def _all_keys(value):
    if isinstance(value, dict):
        yield from value.keys()
        for child in value.values():
            yield from _all_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _all_keys(child)


def test_260_portal_order_contract_minimizes_customer_data(api_client_factory, customer):
    client = api_client_factory(customer)
    created = client.post(
        "/api/v1/portal/pedidos",
        json={"lines": [{"variant_id": 1, "quantity": 2}], "delivery_mode": "RETIRO"},
    )
    assert created.status_code == 201
    order = created.json()
    assert order["codigo"].startswith("PED-")
    assert order["productos"][0]["producto"]
    assert order["estado"] == "PENDIENTE_PAGO"
    assert order["requiere_produccion"] is True
    assert FORBIDDEN_CLIENT_KEYS.isdisjoint(_all_keys(order))

    detail = client.get(f"/api/v1/portal/pedidos/{order['codigo']}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["historial"][0]["estado"] == "PENDIENTE_PAGO"
    assert payload["proxima_accion"] == "REPORTAR_PAGO"
    assert FORBIDDEN_CLIENT_KEYS.isdisjoint(_all_keys(payload))


def test_261_portal_blocks_cross_customer_order_and_quote_access(
    session, api_client_factory, customer
):
    owner = api_client_factory(customer)
    order = owner.post(
        "/api/v1/portal/pedidos",
        json={"lines": [{"variant_id": 1, "quantity": 1}], "delivery_mode": "RETIRO"},
    ).json()
    quote = owner.post(
        "/api/v1/portal/cotizaciones",
        json={"lines": [{"variant_id": 1, "quantity": 1, "customization": "Logo"}]},
    ).json()

    other = add_client(session)
    session.commit()
    intruder = api_client_factory(other)
    assert intruder.get(f"/api/v1/portal/pedidos/{order['codigo']}").status_code in {403, 404}
    assert intruder.post(
        f"/api/v1/portal/cotizaciones/{quote['referencia']}/decision",
        json={"decision": "ACEPTADA", "reason": "Intento ajeno"},
    ).status_code in {403, 404}


def test_262_portal_is_exclusive_to_customers(api_client_factory, employee):
    client = api_client_factory(employee)
    for path in ("/api/v1/portal/resumen", "/api/v1/portal/pedidos", "/api/v1/portal/pagos"):
        response = client.get(path)
        assert response.status_code == 403
        assert response.json()["error"] == "permission_denied"


def test_263_catalog_price_preview_uses_backend_pricing(api_client_factory, customer):
    client = api_client_factory(customer)
    catalog = client.get("/api/v1/portal/catalogo")
    assert catalog.status_code == 200
    item = catalog.json()[0]
    preview = client.get(f"/api/v1/portal/catalogo/{item['id_variante']}/precio?cantidad=3")
    assert preview.status_code == 200
    price = preview.json()
    assert set(price) == {"precio_unitario", "descuento", "total", "modo_precio"}
    assert float(price["total"]) >= 0
    assert float(price["total"]) == pytest.approx(
        float(price["precio_unitario"]) * 3 - float(price["descuento"])
    )


def test_264_portal_summary_and_payments_hide_internal_references(api_client_factory, customer):
    client = api_client_factory(customer)
    summary = client.get("/api/v1/portal/resumen")
    payments = client.get("/api/v1/portal/pagos")
    assert summary.status_code == payments.status_code == 200
    assert FORBIDDEN_CLIENT_KEYS.isdisjoint(_all_keys(summary.json()))
    assert FORBIDDEN_CLIENT_KEYS.isdisjoint(_all_keys(payments.json()))


def test_265_frontend_has_explicit_tables_and_customer_portal_contracts():
    root = Path(__file__).resolve().parents[3]
    source = (root / "frontend" / "dashboard.js").read_text(encoding="utf-8")
    assert "Object.keys" not in source
    assert 'api("/portal/resumen")' in source
    assert 'api("/portal/catalogo")' in source
    assert "La tabla requiere columnas explícitas" in source
    assert "America/Managua" in (root / "frontend" / "presentation.js").read_text(encoding="utf-8")
