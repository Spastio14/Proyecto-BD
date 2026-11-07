from decimal import Decimal
from threading import Thread

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.core.security import SupabaseAuthenticationProvider
from app.main import create_app
from app.models.entities import (
    Cliente,
    CuentaAcceso,
    DetallePedido,
    EscalaPrecio,
    MovimientoInventario,
    Persona,
    RegistroAuditoria,
)
from app.services.catalog_admin import CatalogAdminService
from app.services.customers import CustomerService
from app.services.deliveries import DeliveryService
from app.services.orders import OrderLineInput, OrderService
from tests.helpers import add_client
from tests.integration.test_phase4_2_roles_auth import add_employee
from tests.integration.test_supabase_phase3 import FakeVerifier


class EmailGateway:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def request_email_change(self, *, access_token: str, new_email: str) -> None:
        self.calls.append((access_token, new_email))


def test_delivery_defaults_use_customer_usual_address_and_remain_editable(
    session, employee, api_client_factory
):
    person = session.get(Persona, 2)
    person.direccion_habitual = "Barrio de prueba, Managua"
    person.telefono_contacto = "8888-4242"
    session.commit()
    response = api_client_factory(employee).get(
        "/api/v1/entregas/pedidos/1/datos-iniciales"
    )
    assert response.status_code == 200
    assert response.json() == {
        "id_pedido": 1,
        "id_cliente": 2,
        "nombre_receptor": "Cliente Registrado",
        "telefono_receptor": "8888-4242",
        "direccion_habitual": "Barrio de prueba, Managua",
    }


def test_delivery_keeps_edited_recipient_snapshot(session, employee):
    customer = add_client(session)
    person = session.get(Persona, customer.persona_id)
    person.direccion_habitual = "Dirección habitual"
    order = OrderService().create(
        session,
        principal=customer,
        lines=[OrderLineInput(variant_id=1, quantity=1, promotion_id=None)],
        delivery_mode="ENVIO",
    )
    delivery = DeliveryService().schedule(
        session,
        order_id=order.id_pedido,
        agency_id=None,
        address="Dirección especial para este pedido",
        recipient_name="Persona receptora distinta",
        recipient_phone="7777-0000",
        agreed_fee=Decimal("0.00"),
        scheduled_at=None,
        principal=employee,
    )
    assert delivery.direccion_entrega == "Dirección especial para este pedido"
    assert delivery.nombre_receptor == "Persona receptora distinta"
    assert person.direccion_habitual == "Dirección habitual"


def test_customer_directory_is_compact_and_detail_contains_history(
    session, employee, api_client_factory
):
    client = api_client_factory(employee)
    directory = client.get("/api/v1/clientes")
    assert directory.status_code == 200
    assert set(directory.json()[0]) == {"id_persona", "nombre"}
    changed = client.post(
        "/api/v1/clientes/2/condicion-mayorista",
        json={"enabled": False, "reason": "Revisión administrativa"},
    )
    assert changed.status_code == 200
    edited = client.patch(
        "/api/v1/clientes/2",
        json={
            "phone": "8888-2020",
            "usual_address": "Dirección administrativa",
        },
    )
    assert edited.status_code == 200
    detail = client.get("/api/v1/clientes/2")
    assert detail.status_code == 200
    assert detail.json()["telefono"] == "8888-2020"
    assert detail.json()["direccion_habitual"] == "Dirección administrativa"
    assert detail.json()["pedidos"]
    assert any(
        event["accion"] == "REVOCAR_MAYORISTA"
        for event in detail.json()["historial"]
    )


def test_only_administrator_can_edit_customer_data(session, api_client_factory):
    seller = add_employee(session, "VENDEDOR")
    session.commit()
    client = api_client_factory(seller)
    assert client.get("/api/v1/clientes/2").status_code == 200
    response = client.patch("/api/v1/clientes/2", json={"phone": "8888-0000"})
    assert response.status_code == 403


def test_wholesale_condition_rejects_guests_and_preserves_historical_prices(
    session, employee
):
    price = session.scalar(
        select(DetallePedido.precio_unitario_aplicado).where(
            DetallePedido.id_pedido == 1,
            DetallePedido.numero_linea == 1,
        )
    )
    CustomerService.set_wholesale(
        session,
        client_id=2,
        enabled=False,
        reason="Fin de autorización mayorista",
        principal=employee,
    )
    assert session.get(Cliente, 2).condicion_comercial == "DETALLE"
    assert session.scalar(
        select(DetallePedido.precio_unitario_aplicado).where(
            DetallePedido.id_pedido == 1,
            DetallePedido.numero_linea == 1,
        )
    ) == price
    CustomerService.set_wholesale(
        session,
        client_id=2,
        enabled=True,
        reason="Nueva autorización documentada",
        principal=employee,
    )
    assert session.get(Cliente, 2).condicion_comercial == "MAYORISTA"
    actions = set(
        session.scalars(
            select(RegistroAuditoria.accion).where(
                RegistroAuditoria.referencia_objeto == "2",
                RegistroAuditoria.accion.in_(
                    {"AUTORIZAR_MAYORISTA", "REVOCAR_MAYORISTA"}
                ),
            )
        )
    )
    assert actions == {"AUTORIZAR_MAYORISTA", "REVOCAR_MAYORISTA"}
    try:
        CustomerService.set_wholesale(
            session,
            client_id=1,
            enabled=True,
            reason="Intento inválido",
            principal=employee,
        )
    except Exception as exc:
        assert "invitado" in str(exc).lower()
    else:
        raise AssertionError("Un invitado no debe convertirse en mayorista")


def test_composition_overview_exposes_material_cost_stock_and_capacity(session, employee):
    rows = CatalogAdminService.composition_overview(
        session,
        variant_id=1,
        principal=employee,
    )
    assert rows[0]["material"] == "Taza blanca 11 oz"
    assert rows[0]["costo_estandar"] == Decimal("25.00")
    assert rows[0]["existencia_fisica"] >= rows[0]["disponible"]
    assert rows[0]["unidades_posibles"] >= 0
    requirements = CatalogAdminService.requirements(
        session,
        variant_id=1,
        quantity=3,
        principal=employee,
    )
    assert requirements["requerimientos"][0]["cantidad_requerida"] == Decimal("3.000")


def test_scale_number_is_generated_and_scale_can_be_edited_or_disabled(session, employee):
    service = CatalogAdminService()
    variant = service.create_variant(
        session,
        principal=employee,
        product_id=1,
        code="AUTO-SCALE-TEST",
        features=None,
        retail_price=Decimal("100.00"),
        requires_production=False,
    )
    first = service.create_scale(
        session,
        variant_id=variant.id_variante,
        principal=employee,
        minimum_quantity=10,
        maximum_quantity=20,
        wholesale_unit_price=Decimal("80.00"),
    )
    assert first.numero_rango == 1
    updated = service.update_scale(
        session,
        variant_id=variant.id_variante,
        number=first.numero_rango,
        principal=employee,
        changes={"state": "INACTIVA", "wholesale_unit_price": Decimal("79.00")},
    )
    assert updated.estado == "INACTIVA"
    assert updated.precio_unitario_mayorista == Decimal("79.00")


def test_concurrent_scale_creation_generates_distinct_numbers(engine, session, employee):
    service = CatalogAdminService()
    variant = service.create_variant(
        session,
        principal=employee,
        product_id=1,
        code="CONCURRENT-SCALE-TEST",
        features=None,
        retail_price=Decimal("100.00"),
        requires_production=False,
    )
    variant_id = variant.id_variante
    session.commit()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    outcomes: list[object] = []

    def worker(minimum: int, maximum: int):
        try:
            with factory() as db, db.begin():
                row = CatalogAdminService.create_scale(
                    db,
                    variant_id=variant_id,
                    principal=employee,
                    minimum_quantity=minimum,
                    maximum_quantity=maximum,
                    wholesale_unit_price=Decimal("70.00"),
                )
                outcomes.append(row.numero_rango)
        except Exception as exc:
            outcomes.append(exc)

    threads = [Thread(target=worker, args=(100, 199)), Thread(target=worker, args=(200, 299))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert sorted(outcomes) == [1, 2]
    with factory() as db:
        assert db.scalar(
            select(func.count())
            .select_from(EscalaPrecio)
            .where(EscalaPrecio.id_variante == variant_id)
        ) == 2


def test_loss_options_and_selected_context_are_audited(
    session, employee, api_client_factory
):
    client = api_client_factory(employee)
    options = client.get("/api/v1/perdidas/opciones")
    assert options.status_code == 200
    assert len(options.json()["momentos"]) == 4
    reported = client.post(
        "/api/v1/perdidas",
        json={
            "moment": "DURANTE_PRODUCCION",
            "incident_type": "IMPRESION_FALLIDA",
            "reason": "Prueba controlada",
            "order_id": 1,
            "stage_id": 3,
            "description": "Hoja dañada durante impresión",
        },
    )
    assert reported.status_code == 201
    confirmed = client.post(
        f"/api/v1/perdidas/{reported.json()['id_perdida']}/confirmar",
        json={
            "lines": [
                {
                    "article_id": 1,
                    "quantity": "1.000",
                    "damage_description": "Material inutilizable",
                }
            ]
        },
    )
    assert confirmed.status_code == 200
    movement = session.scalar(
        select(MovimientoInventario)
        .where(MovimientoInventario.tipo_movimiento == "SALIDA_PERDIDA")
        .order_by(MovimientoInventario.id_movimiento.desc())
    )
    assert movement.id_pedido == 1


def test_profile_updates_only_personal_fields_and_rejects_roles(
    customer, api_client_factory
):
    client = api_client_factory(customer)
    response = client.patch(
        "/api/v1/perfil",
        json={
            "phone": "8888-9090",
            "usual_address": "Dirección personal",
        },
    )
    assert response.status_code == 200
    forbidden = client.patch("/api/v1/perfil", json={"roles": ["ADMINISTRADOR"]})
    assert forbidden.status_code == 422
    profile = client.get("/api/v1/perfil")
    assert profile.json()["telefono"] == "8888-9090"
    assert profile.json()["direccion_habitual"] == "Dirección personal"


def test_email_changes_only_after_verified_supabase_identity(engine):
    subject = "11111111-1111-4111-8111-111111111111"
    verifier = FakeVerifier(
        {"sub": subject, "email": "cliente@example.test", "is_anonymous": False}
    )
    gateway = EmailGateway()
    settings = Settings(database_url=str(engine.url), app_env="test")
    application = create_app(
        settings,
        engine=engine,
        auth_provider=SupabaseAuthenticationProvider(verifier),
    )
    application.state.token_verifier = verifier
    application.state.auth_gateway = gateway
    headers = {"Authorization": "Bearer verified-session"}
    with TestClient(application) as client:
        requested = client.post(
            "/api/v1/perfil/correo/solicitar",
            headers=headers,
            json={"new_email": "nuevo-correo@example.test"},
        )
        assert requested.status_code == 200
        assert gateway.calls == [("verified-session", "nuevo-correo@example.test")]
        with sessionmaker(bind=engine)() as db:
            assert db.get(Persona, 2).correo_electronico == "cliente@example.test"

        verifier.claims["email"] = "nuevo-correo@example.test"
        synchronized = client.post(
            "/api/v1/perfil/correo/sincronizar",
            headers=headers,
        )
        assert synchronized.status_code == 200

    with sessionmaker(bind=engine)() as db:
        assert db.get(Persona, 2).correo_electronico == "nuevo-correo@example.test"
        account = db.scalar(select(CuentaAcceso).where(CuentaAcceso.id_persona == 2))
        assert account.identificador_autenticacion == subject
        assert db.scalar(
            select(func.count())
            .select_from(RegistroAuditoria)
            .where(RegistroAuditoria.accion == "SINCRONIZAR_CORREO_VERIFICADO")
        ) == 1
