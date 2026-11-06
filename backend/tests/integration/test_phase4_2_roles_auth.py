from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.core.exceptions import Conflict
from app.core.security import Principal, SupabaseAuthenticationProvider, VerifiedAuthIdentity
from app.integrations.supabase import AuthAdminIdentity, AuthRateLimited
from app.main import create_app
from app.models.entities import (
    AsignacionRol,
    Cliente,
    CuentaAcceso,
    Empleado,
    Persona,
    Rol,
)
from app.services.authorization import AuthorizationService
from app.services.employees import EmployeeInvitationCoordinator, EmployeeService
from tests.integration.test_supabase_phase3 import FakeVerifier, request

pytestmark = pytest.mark.integration


class InviteGateway:
    def __init__(self, *, subject: str | None = None, failure: Exception | None = None):
        self.subject = subject or str(uuid4())
        self.failure = failure
        self.calls: list[tuple[str, str | None]] = []
        self.password_calls: list[tuple[str, str]] = []

    def invite_user(self, *, email: str, redirect_to: str | None = None) -> str:
        self.calls.append((email, redirect_to))
        if self.failure:
            raise self.failure
        return self.subject

    def update_password(self, *, access_token: str, password: str) -> None:
        self.password_calls.append((access_token, password))


def role_id(session, name: str) -> int:
    return session.scalar(select(Rol.id_rol).where(Rol.nombre == name))


def add_employee(session, role_name: str) -> Principal:
    person = Persona(
        nombres=role_name.title(),
        apellidos="Prueba",
        telefono_contacto=None,
        correo_electronico=f"{uuid4().hex}@example.test",
        documento_identificacion=None,
    )
    session.add(person)
    session.flush()
    session.add(
        Empleado(
            id_persona=person.id_persona,
            codigo_empleado=f"TEST-{person.id_persona}",
            fecha_ingreso=datetime.now(UTC),
            estado_laboral="ACTIVO",
            capacidad_maxima_asignaciones=10,
        )
    )
    session.add(
        CuentaAcceso(
            id_persona=person.id_persona,
            identificador_autenticacion=str(uuid4()),
            fecha_activacion=datetime.now(UTC),
            estado_cuenta="ACTIVA",
            ultimo_acceso=None,
        )
    )
    session.add(
        AsignacionRol(
            id_empleado=person.id_persona,
            id_rol=role_id(session, role_name),
            fecha_asignacion=datetime.now(UTC),
            fecha_finalizacion=None,
            estado="ACTIVA",
        )
    )
    session.flush()
    return Principal(person.id_persona, "EMPLEADO")


def test_121_auth_me_routes_client_to_its_dashboard(api_client_factory, customer):
    response = api_client_factory(customer).get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["tipo_perfil"] == "REGISTRADO"
    assert response.json()["roles"] == []
    assert response.json()["dashboard_inicial"] == "/app/cliente/"


def test_122_auth_me_uses_database_roles_and_permissions(api_client_factory, employee):
    response = api_client_factory(employee).get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["dashboard_inicial"] == "/app/admin/"
    assert "EMPLEADO_GESTIONAR" in response.json()["permisos"]
    assert "ADMINISTRACION" in response.json()["roles"]


def test_123_accountant_is_read_only_for_finance_and_purchases(session, api_client_factory):
    accountant = add_employee(session, "CONTADOR")
    session.commit()
    client = api_client_factory(accountant)
    assert client.get("/api/v1/reportes/resumen").status_code == 200
    assert client.get("/api/v1/compras").status_code == 200
    assert (
        client.post("/api/v1/compras/proveedores", json={"name": "No permitido"}).status_code == 403
    )
    assert client.get("/api/v1/empleados").status_code == 403


def test_124_seller_cannot_see_financial_reports_or_purchases(session, api_client_factory):
    seller = add_employee(session, "VENDEDOR")
    session.commit()
    client = api_client_factory(seller)
    assert client.get("/api/v1/pedidos").status_code == 200
    assert client.get("/api/v1/clientes").status_code == 200
    assert client.get("/api/v1/reportes/resumen").status_code == 403
    assert client.get("/api/v1/compras").status_code == 403


def test_125_admin_invites_and_employee_activates_verified_identity(engine, session, employee):
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    subject = str(uuid4())
    gateway = InviteGateway(subject=subject)
    coordinator = EmployeeInvitationCoordinator(
        factory,
        gateway,
        redirect_to="http://127.0.0.1:8000/app/activar-empleado/",
    )
    email = f"{uuid4().hex}@example.test"
    result = coordinator.invite(
        principal=employee,
        names="Vendedora",
        surnames="Invitada",
        email=email,
        phone=None,
        document=None,
        role_id=role_id(session, "VENDEDOR"),
        capacity=10,
    )
    with factory() as verification:
        invited = verification.get(Empleado, result.persona_id)
        assert invited.estado_laboral == "INACTIVO"
        assert (
            verification.scalar(
                select(CuentaAcceso.identificador_autenticacion).where(
                    CuentaAcceso.id_persona == result.persona_id
                )
            )
            == subject
        )
    activated = coordinator.activate(VerifiedAuthIdentity(subject=subject, email=email))
    assert activated.status == "ACTIVO"
    with factory() as verification:
        principal = SupabaseAuthenticationProvider(FakeVerifier({"sub": subject})).authenticate(
            request(bearer="verified"), verification
        )
        profile = AuthorizationService.identity(verification, principal)
        assert profile["dashboard_inicial"] == "/app/ventas/"
        assert "PEDIDO_GESTIONAR" in profile["permisos"]
        assert "REPORTE_FINANCIERO_CONSULTAR" not in profile["permisos"]


def test_126_failed_invitation_remains_recoverable_only_by_verified_identity(
    engine, session, employee
):
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    gateway = InviteGateway(failure=AuthRateLimited("Límite de correo"))
    coordinator = EmployeeInvitationCoordinator(factory, gateway, redirect_to=None)
    email = f"{uuid4().hex}@example.test"
    with pytest.raises(AuthRateLimited):
        coordinator.invite(
            principal=employee,
            names="Pendiente",
            surnames=None,
            email=email,
            phone=None,
            document=None,
            role_id=role_id(session, "PRODUCCION"),
            capacity=5,
        )
    with factory() as verification:
        person_id = verification.scalar(
            select(Persona.id_persona).where(Persona.correo_electronico == email)
        )
        assert verification.get(Empleado, person_id).estado_laboral == "INACTIVO"
        assert (
            verification.scalar(
                select(func.count())
                .select_from(CuentaAcceso)
                .where(CuentaAcceso.id_persona == person_id)
            )
            == 0
        )
    subject = str(uuid4())
    result = coordinator.activate(VerifiedAuthIdentity(subject=subject, email=email))
    assert result.status == "ACTIVO"


def test_127_client_email_cannot_be_converted_to_employee(engine, session, employee):
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    gateway = InviteGateway()
    coordinator = EmployeeInvitationCoordinator(factory, gateway, redirect_to=None)
    client_email = session.scalar(
        select(Persona.correo_electronico)
        .join(Cliente, Cliente.id_persona == Persona.id_persona)
        .where(Cliente.id_persona == 2)
    )
    with pytest.raises(Conflict, match="cliente"):
        coordinator.invite(
            principal=employee,
            names="No convertir",
            surnames=None,
            email=client_email,
            phone=None,
            document=None,
            role_id=role_id(session, "ADMINISTRADOR"),
            capacity=10,
        )
    assert gateway.calls == []


def test_128_role_change_replaces_effective_permissions(session, employee):
    target = add_employee(session, "VENDEDOR")
    EmployeeService.assign_role(
        session,
        employee_id=target.persona_id,
        role_id=role_id(session, "CONTADOR"),
        principal=employee,
    )
    session.flush()
    assert AuthorizationService.has_permission(session, target, "REPORTE_FINANCIERO_CONSULTAR")
    assert not AuthorizationService.has_permission(session, target, "PEDIDO_GESTIONAR")


def test_129_public_page_has_no_administrative_switch(api_client_factory):
    client = api_client_factory(None)
    page = client.get("/app/")
    assert page.status_code == 200
    assert 'data-view="empleado"' not in page.text
    for path in (
        "/app/cliente/",
        "/app/admin/",
        "/app/contabilidad/",
        "/app/ventas/",
        "/app/produccion/",
    ):
        assert client.get(path).status_code == 200
    assert client.get("/api/v1/empleados").status_code == 401


def test_130_public_registration_rejects_role_and_client_cannot_invite(
    api_client_factory, customer
):
    public = api_client_factory(None)
    invalid = public.post(
        "/api/v1/auth/registro",
        json={
            "names": "Cliente",
            "surnames": None,
            "email": "cliente-nuevo@example.test",
            "phone": None,
            "password": "password-seguro",
            "role": "ADMINISTRADOR",
        },
    )
    assert invalid.status_code == 422
    client = api_client_factory(customer)
    denied = client.post(
        "/api/v1/empleados/invitaciones",
        json={
            "names": "Empleado",
            "surnames": None,
            "email": "empleado-nuevo@example.test",
            "phone": None,
            "document": None,
            "role_id": 1,
            "capacity": 10,
        },
    )
    assert denied.status_code == 403


def test_131_bootstrap_admin_is_verified_and_idempotent(engine):
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    coordinator = EmployeeInvitationCoordinator(factory, InviteGateway(), redirect_to=None)
    identity = AuthAdminIdentity(subject=str(uuid4()), email=f"{uuid4().hex}@example.test")
    first = coordinator.bootstrap_admin(
        identity=identity,
        names="Propietaria",
        surnames="Verificada",
        phone=None,
        document=None,
        employee_code="EMP-BOOTSTRAP-TEST",
    )
    second = coordinator.bootstrap_admin(
        identity=identity,
        names="Ignorado",
        surnames=None,
        phone=None,
        document=None,
        employee_code="OTRO-CODIGO",
    )
    assert second.persona_id == first.persona_id
    with factory() as verification:
        principal = Principal(first.persona_id, "EMPLEADO")
        assert AuthorizationService.has_permission(verification, principal, "EMPLEADO_GESTIONAR")


def test_132_bootstrap_never_converts_existing_client(engine):
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    coordinator = EmployeeInvitationCoordinator(factory, InviteGateway(), redirect_to=None)
    identity = AuthAdminIdentity(
        subject="11111111-1111-4111-8111-111111111111",
        email="cliente@example.test",
    )
    with pytest.raises(Conflict, match="cliente"):
        coordinator.bootstrap_admin(
            identity=identity,
            names="No convertir",
            surnames=None,
            phone=None,
            document=None,
            employee_code="NO-CONVERTIR",
        )


@pytest.mark.parametrize(
    ("role_name", "dashboard"),
    [
        ("CONTADOR", "/app/contabilidad/"),
        ("VENDEDOR", "/app/ventas/"),
        ("PRODUCCION", "/app/produccion/"),
    ],
)
def test_133_each_employee_role_resolves_its_dashboard(session, role_name, dashboard):
    principal = add_employee(session, role_name)
    profile = AuthorizationService.identity(session, principal)
    assert profile["dashboard_inicial"] == dashboard


def test_134_design_dashboard_can_list_real_versions(api_client_factory, employee):
    response = api_client_factory(employee).get("/api/v1/disenos/pedidos/1/lineas/1/versiones")
    assert response.status_code == 200
    assert response.json()[0]["numero_version"] == 1


def test_135_production_cannot_list_customer_directory(session, api_client_factory):
    production = add_employee(session, "PRODUCCION")
    session.commit()
    assert api_client_factory(production).get("/api/v1/clientes").status_code == 403


def test_136_invitation_api_validates_sets_password_and_activates(engine, session, employee):
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    subject = str(uuid4())
    email = f"{uuid4().hex}@example.test"
    gateway = InviteGateway(subject=subject)
    coordinator = EmployeeInvitationCoordinator(factory, gateway, redirect_to=None)
    coordinator.invite(
        principal=employee,
        names="Empleado",
        surnames="Invitado",
        email=email,
        phone=None,
        document=None,
        role_id=role_id(session, "VENDEDOR"),
        capacity=10,
    )
    claims = {"sub": subject, "email": email, "is_anonymous": False}
    verifier = FakeVerifier(claims)
    settings = Settings(database_url=str(engine.url), app_env="test")
    application = create_app(
        settings,
        engine=engine,
        auth_provider=SupabaseAuthenticationProvider(verifier),
    )
    application.state.token_verifier = verifier
    application.state.auth_gateway = gateway
    application.state.employee_invitation_coordinator = coordinator
    headers = {"Authorization": "Bearer invitation-session-token"}

    with TestClient(application) as client:
        validation = client.get("/api/v1/auth/validar-invitacion", headers=headers)
        assert validation.status_code == 200
        assert validation.json()["estado"] == "INVITACION_VERIFICADA"

        activation = client.post(
            "/api/v1/auth/activar-empleado",
            headers=headers,
            json={"password": "secure-password-123"},
        )
        assert activation.status_code == 200
        assert activation.json()["estado"] == "ACTIVO"

        profile = client.get("/api/v1/auth/me", headers=headers)
        assert profile.status_code == 200
        assert profile.json()["dashboard_inicial"] == "/app/ventas/"

    assert gateway.password_calls == [("invitation-session-token", "secure-password-123")]
