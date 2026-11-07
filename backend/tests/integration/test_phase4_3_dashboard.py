from pathlib import Path

import pytest

from app.models.base import Base
from app.services.reports import ReportService

pytestmark = pytest.mark.integration


def test_214_dashboard_has_operational_kpis_and_audit(session, employee):
    report = ReportService.dashboard(session, employee, days=30)
    assert report["periodo_dias"] == 30
    assert {
        "pedidos_por_estado",
        "indicadores_pedidos",
        "pagos_pendientes",
        "compras_confirmadas",
        "stock_bajo",
        "actividad_reciente",
    } <= report.keys()
    assert {"cantidad", "monto"} <= report["pagos_pendientes"].keys()
    assert {"cantidad", "total"} <= report["compras_confirmadas"].keys()
    assert {
        "nuevos",
        "pendientes_pago",
        "en_diseno",
        "en_produccion",
        "listos",
    } == report["indicadores_pedidos"].keys()


def test_215_report_period_is_validated_by_api(api_client_factory, employee):
    client = api_client_factory(employee)
    assert client.get("/api/v1/reportes/resumen?days=1").status_code == 200
    assert client.get("/api/v1/reportes/resumen?days=0").status_code == 422
    assert client.get("/api/v1/reportes/resumen?days=3651").status_code == 422


def test_216_phase_4_3_keeps_exactly_41_tables():
    assert len(Base.metadata.tables) == 41


def test_217_frontend_uses_guarded_operational_endpoints():
    source = (Path(__file__).resolve().parents[3] / "frontend" / "dashboard.js").read_text(
        encoding="utf-8"
    )
    assert "/produccion/pedidos/${id}/completar" in source
    assert "/pedidos/${x.id}/operacion" in source
    assert "CATALOGO_GESTIONAR" in source
    assert "<option>LISTO</option>" not in source


def test_218_catalog_and_inventory_openapi_routes_are_present(api_client_factory):
    schema = api_client_factory(None).get("/api/v1/openapi.json")
    if schema.status_code == 404:
        schema = api_client_factory(None).get("/openapi.json")
    paths = schema.json()["paths"]
    assert "/api/v1/catalogo/admin/categorias" in paths
    assert "/api/v1/inventario/articulos/{article_id}/ajustes" in paths
    assert "/api/v1/produccion/pedidos/{order_id}/completar" in paths
