from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import Conflict, PermissionDenied
from app.models.entities import (
    AprobacionDiseno,
    Cliente,
    DetallePedido,
    Pedido,
    Producto,
    RegistroAuditoria,
    VersionDiseno,
)
from app.services.designs import DesignService
from app.services.employees import EmployeeService
from app.services.storage import StorageCoordinator
from tests.helpers import add_client
from tests.integration.test_phase4_2_roles_auth import add_employee

pytestmark = pytest.mark.integration


class FakeStorage:
    def __init__(self):
        self.uploads = []
        self.deletions = []

    def upload(self, **payload):
        self.uploads.append(payload)

    def delete(self, *, bucket, path):
        self.deletions.append((bucket, path))

    def signed_url(self, *, bucket, path, expires_in):
        return f"https://storage.test/signed/{bucket}/{path}?ttl={expires_in}"


def test_design_versions_are_discovered_and_only_current_version_can_be_decided(
    session, customer, employee
):
    session.query(AprobacionDiseno).filter(AprobacionDiseno.id_pedido == 1).delete()
    first = session.get(VersionDiseno, (1, 1, 1))
    first.es_aprobado = False
    service = DesignService()
    second = service.add_version(
        session,
        order_id=1,
        line_number=1,
        file_name="cliente-v2.png",
        private_path="pedidos/1/lineas/1/v2.png",
        observations="Segunda propuesta",
        principal=employee,
    )
    lines = service.order_lines(session, order_id=1, principal=customer)
    assert [item["numero_version"] for item in lines[0]["versiones"]] == [1, 2]
    assert lines[0]["estado"] == "PENDIENTE"
    assert lines[0]["versiones"][-1]["es_vigente"] is True
    with pytest.raises(Conflict, match="versión vigente"):
        service.decide(
            session,
            order_id=1,
            line_number=1,
            version_number=1,
            approved=True,
            principal=customer,
        )
    service.decide(
        session,
        order_id=1,
        line_number=1,
        version_number=second.numero_version,
        approved=True,
        principal=customer,
    )
    assert second.es_aprobado is True
    third = service.add_version(
        session,
        order_id=1,
        line_number=1,
        file_name="cliente-v3.png",
        private_path="pedidos/1/lineas/1/v3.png",
        principal=employee,
    )
    assert third.es_aprobado is False
    assert service.order_lines(session, order_id=1, principal=customer)[0]["estado"] == "PENDIENTE"


def test_design_access_rejects_other_customer_and_external_approval_needs_evidence(
    session, customer, employee
):
    intruder = add_client(session)
    with pytest.raises(PermissionDenied, match="otro cliente"):
        DesignService.order_lines(session, order_id=1, principal=intruder)
    with pytest.raises(Conflict, match="medio"):
        DesignService().decide(
            session,
            order_id=1,
            line_number=1,
            version_number=1,
            approved=True,
            principal=employee,
            medium="PORTAL",
        )
    with pytest.raises(Conflict, match="referencia y evidencia"):
        DesignService().decide(
            session,
            order_id=1,
            line_number=1,
            version_number=1,
            approved=True,
            principal=employee,
            medium="WHATSAPP",
        )
    production_employee = add_employee(session, "PRODUCCION")
    with pytest.raises(PermissionDenied):
        DesignService().decide(
            session,
            order_id=1,
            line_number=1,
            version_number=1,
            approved=True,
            principal=production_employee,
            medium="WHATSAPP",
            reference="Conversación 2026-11-08",
            evidence="Captura archivada",
        )
    decision = DesignService().decide(
        session,
        order_id=1,
        line_number=1,
        version_number=1,
        approved=True,
        principal=employee,
        medium="WHATSAPP",
        reference="Conversación 2026-11-08",
        evidence="Captura archivada",
    )
    assert decision.id_empleado_registro == employee.persona_id
    assert "Evidencia: Captura archivada" in decision.observacion


def test_private_design_url_is_signed_after_owner_authorization(
    session, engine, customer
):
    gateway = FakeStorage()
    coordinator = StorageCoordinator(
        sessionmaker(bind=engine, expire_on_commit=False),
        gateway,
        design_max_bytes=1_000_000,
        receipt_max_bytes=1_000_000,
        signed_url_ttl=120,
    )
    url = coordinator.design_url(
        session,
        order_id=1,
        line_number=1,
        version_number=1,
        principal=customer,
    )
    assert url.startswith("https://storage.test/signed/disenos/")
    intruder = add_client(session)
    with pytest.raises(PermissionDenied):
        coordinator.design_url(
            session,
            order_id=1,
            line_number=1,
            version_number=1,
            principal=intruder,
        )


def test_product_image_replacement_validates_content_and_deletes_previous_file(
    session, engine, employee
):
    session.get(Producto, 1).ruta_imagen_principal = "productos/1/anterior.png"
    session.get(Producto, 1).imagen_mime = "image/png"
    session.get(Producto, 1).imagen_tamano_bytes = 16
    session.commit()
    gateway = FakeStorage()
    coordinator = StorageCoordinator(
        sessionmaker(bind=engine, expire_on_commit=False),
        gateway,
        design_max_bytes=1_000_000,
        receipt_max_bytes=1_000_000,
        product_max_bytes=1_000_000,
        signed_url_ttl=120,
    )
    product = coordinator.upload_product_image(
        product_id=1,
        file_name="catalogo.png",
        content_type="image/png",
        content=b"\x89PNG\r\n\x1a\ncontenido",
        principal=employee,
    )
    assert product.ruta_imagen_principal.startswith("productos/1/")
    assert gateway.deletions == [("catalogo-productos", "productos/1/anterior.png")]
    with pytest.raises(Conflict, match="contenido"):
        coordinator.upload_product_image(
            product_id=1,
            file_name="falso.webp",
            content_type="image/webp",
            content=b"RIFFxxxxxxxxxxxx",
            principal=employee,
        )


def test_customer_cannot_upload_or_replace_product_images(session, engine, customer):
    gateway = FakeStorage()
    coordinator = StorageCoordinator(
        sessionmaker(bind=engine, expire_on_commit=False),
        gateway,
        design_max_bytes=1_000_000,
        receipt_max_bytes=1_000_000,
        product_max_bytes=1_000_000,
        signed_url_ttl=120,
    )
    with pytest.raises(PermissionDenied):
        coordinator.upload_product_image(
            product_id=1,
            file_name="intento.png",
            content_type="image/png",
            content=b"\x89PNG\r\n\x1a\ncontenido",
            principal=customer,
        )
    assert gateway.uploads == []


def test_seller_creates_traceable_customer_order_and_quote(api_client_factory, session):
    seller = add_employee(session, "VENDEDOR")
    session.commit()
    client = api_client_factory(seller)
    created_customer = client.post(
        "/api/v1/ventas/clientes",
        json={"names": "Mostrador", "surnames": "Individual", "phone": "88880000"},
    )
    assert created_customer.status_code == 201
    customer_id = created_customer.json()["id_persona"]
    customer = session.get(Cliente, customer_id)
    assert customer.tipo_cliente == "INVITADO"
    assert customer.condicion_comercial == "DETALLE"
    order = client.post(
        "/api/v1/ventas/pedidos",
        json={
            "client_id": customer_id,
            "delivery_mode": "RETIRO",
            "lines": [{"variant_id": 1, "quantity": 2, "customization": "Nombre Ana"}],
        },
    )
    assert order.status_code == 201
    stored_order = session.get(Pedido, order.json()["id_pedido"])
    assert stored_order.id_cliente == customer_id
    assert stored_order.id_empleado_registro == seller.persona_id
    assert stored_order.canal_origen == "PRESENCIAL"
    detail = session.get(DetallePedido, (stored_order.id_pedido, 1))
    assert detail.descripcion_personalizacion == "Nombre Ana"
    second_customer = client.post(
        "/api/v1/ventas/clientes", json={"names": "Cotización", "phone": "77770000"}
    ).json()
    quote = client.post(
        "/api/v1/ventas/cotizaciones",
        json={
            "client_id": second_customer["id_persona"],
            "lines": [{"variant_id": 1, "quantity": 2, "customization": "Logo"}],
        },
    )
    assert quote.status_code == 201
    assert quote.json()["id_cliente"] == second_customer["id_persona"]
    assert session.scalar(
        select(RegistroAuditoria.id_auditoria).where(
            RegistroAuditoria.accion == "CREAR_COTIZACION",
            RegistroAuditoria.id_persona_actor == seller.persona_id,
        )
    )


def test_point_of_sale_keeps_guest_limits_and_employee_profile_identity_rules(
    api_client_factory, session, customer
):
    seller = add_employee(session, "VENDEDOR")
    session.commit()
    seller_api = api_client_factory(seller)
    in_store = seller_api.post(
        "/api/v1/ventas/clientes", json={"names": "Sin excepción", "phone": "66660000"}
    ).json()
    too_many = seller_api.post(
        "/api/v1/ventas/pedidos",
        json={
            "client_id": in_store["id_persona"],
            "lines": [{"variant_id": 1, "quantity": 6}],
        },
    )
    assert too_many.status_code == 409
    assert "máximo 5" in too_many.json()["detail"]
    forbidden = seller_api.patch("/api/v1/perfil", json={"names": "Cambio indebido"})
    assert forbidden.status_code == 403
    assert seller_api.patch("/api/v1/perfil", json={"phone": "55550000"}).status_code == 200
    customer_api = api_client_factory(customer)
    customer_update = customer_api.patch(
        "/api/v1/perfil", json={"names": "Nombre permitido"}
    )
    assert customer_update.status_code == 200


def test_possible_employee_duplicates_are_reported_without_automatic_changes(
    session, employee
):
    first = add_employee(session, "VENDEDOR")
    second = add_employee(session, "VENDEDOR")
    rows = EmployeeService.possible_duplicates(session, employee)
    name_group = next(row for row in rows if row["coincidencia"] == "nombre:vendedor prueba")
    assert {item["id_persona"] for item in name_group["empleados"]} == {
        first.persona_id,
        second.persona_id,
    }


def test_active_operational_orders_exclude_delivered_and_schema_keeps_41_tables(
    api_client_factory, employee, session
):
    session.get(Pedido, 2).estado = "ENTREGADO"
    session.commit()
    active = api_client_factory(employee).get(
        "/api/v1/pedidos/operativos?context=disenos&view=activos&page=1&limit=50"
    )
    assert active.status_code == 200
    assert all(item["pedido"]["estado"] != "ENTREGADO" for item in active.json()["items"])
    with pytest.raises(Conflict, match="admita nuevos diseños"):
        DesignService().add_version(
            session,
            order_id=2,
            line_number=1,
            file_name="tardio.png",
            private_path="pedidos/2/tardio.png",
            principal=employee,
        )
    table_count = session.scalar(
        text(
            "select count(*) from information_schema.tables "
            "where table_schema='public' and table_type='BASE TABLE'"
        )
    )
    assert table_count == 41


def test_frontend_contract_contains_store_search_design_and_pos_flows():
    root = Path(__file__).resolve().parents[3]
    source = (root / "frontend" / "dashboard.js").read_text(encoding="utf-8")
    assert "[object Object]" not in source
    assert "data-searchable" in source
    assert "Ver producto" in source
    assert "/disenos/" in source and "signed_url" in source
    assert "/ventas/pedidos" in source and "/ventas/cotizaciones" in source
    assert "product-image" in source
