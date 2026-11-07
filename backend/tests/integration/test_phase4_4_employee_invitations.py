from datetime import UTC, datetime, timedelta
from threading import Event, Thread
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.core.exceptions import AccountInactive, Conflict
from app.core.security import Principal, SupabaseAuthenticationProvider, VerifiedAuthIdentity
from app.integrations.supabase import AuthAdminIdentity, AuthRateLimited
from app.main import create_app
from app.models.entities import (
    AsignacionRol,
    CuentaAcceso,
    Empleado,
    Persona,
    RegistroAuditoria,
)
from app.services.employees import EmployeeInvitationCoordinator, EmployeeService
from tests.integration.test_phase4_2_roles_auth import role_id
from tests.integration.test_supabase_phase3 import FakeVerifier, request

pytestmark = pytest.mark.integration


class InvitationGateway:
    def __init__(self, *, subject: str | None = None):
        self.subject = subject or str(uuid4())
        self.identity_email: str | None = None
        self.invite_failure: Exception | None = None
        self.recovery_failure: Exception | None = None
        self.invite_calls: list[tuple[str, str | None]] = []
        self.recovery_calls: list[tuple[str, str | None]] = []
        self.get_user_calls: list[str] = []

    def invite_user(self, *, email: str, redirect_to: str | None = None) -> str:
        self.invite_calls.append((email, redirect_to))
        if self.invite_failure:
            raise self.invite_failure
        self.identity_email = self.identity_email or email
        return self.subject

    def get_user(self, *, subject: str) -> AuthAdminIdentity:
        self.get_user_calls.append(subject)
        return AuthAdminIdentity(
            subject=subject,
            email=self.identity_email or "missing@example.test",
        )

    def send_password_recovery(
        self, *, email: str, redirect_to: str | None = None
    ) -> None:
        self.recovery_calls.append((email, redirect_to))
        if self.recovery_failure:
            raise self.recovery_failure

    def update_password(self, *, access_token: str, password: str) -> None:
        pass


class FixedProvider:
    def __init__(self, principal: Principal):
        self.principal = principal

    def authenticate(self, request, session):
        return self.principal


def coordinator(engine, gateway):
    return EmployeeInvitationCoordinator(
        sessionmaker(bind=engine, expire_on_commit=False),
        gateway,
        redirect_to="http://127.0.0.1:8000/app/activar-empleado/",
    )


def invite(service, session, admin, gateway, *, email=None):
    email = email or f"{uuid4().hex}@example.test"
    result = service.invite(
        principal=admin,
        names="Empleado",
        surnames="Pendiente",
        email=email,
        phone=None,
        document=None,
        role_id=role_id(session, "VENDEDOR"),
        capacity=10,
    )
    gateway.identity_email = email
    return result, email


def age_invitation_events(factory, employee_id):
    with factory() as db, db.begin():
        db.execute(
            update(RegistroAuditoria)
            .where(
                RegistroAuditoria.tipo_objeto_afectado == "EMPLEADO",
                RegistroAuditoria.referencia_objeto == str(employee_id),
            )
            .values(fecha_hora=datetime.now(UTC) - timedelta(minutes=2))
        )


def counts(factory, employee_id):
    with factory() as db:
        return (
            db.scalar(
                select(func.count()).select_from(Persona).where(Persona.id_persona == employee_id)
            ),
            db.scalar(
                select(func.count())
                .select_from(Empleado)
                .where(Empleado.id_persona == employee_id)
            ),
            db.scalar(
                select(func.count())
                .select_from(CuentaAcceso)
                .where(CuentaAcceso.id_persona == employee_id)
            ),
            db.scalar(
                select(func.count())
                .select_from(AsignacionRol)
                .where(
                    AsignacionRol.id_empleado == employee_id,
                    AsignacionRol.estado == "ACTIVA",
                )
            ),
        )


def test_initial_invitation_is_pending_and_never_claims_email_delivery(
    engine, session, employee
):
    gateway = InvitationGateway()
    service = coordinator(engine, gateway)
    result, _ = invite(service, session, employee, gateway)
    assert result.status == "PENDIENTE_ACTIVACION"
    with service.factory() as db:
        target = db.get(Empleado, result.persona_id)
        event = db.scalar(
            select(RegistroAuditoria)
            .where(RegistroAuditoria.accion == "INVITAR_EMPLEADO")
            .order_by(RegistroAuditoria.id_auditoria.desc())
        )
        assert target.estado_laboral == "INACTIVO"
        assert "aceptó la solicitud" in event.motivo
        assert "entregado" not in event.motivo.lower()


def test_pending_employee_cannot_authenticate_protected_requests(engine, session, employee):
    gateway = InvitationGateway()
    service = coordinator(engine, gateway)
    result, _ = invite(service, session, employee, gateway)
    provider = SupabaseAuthenticationProvider(FakeVerifier({"sub": gateway.subject}))
    with service.factory() as db, pytest.raises(AccountInactive):
        provider.authenticate(request(bearer="verified"), db)
    assert counts(service.factory, result.persona_id) == (1, 1, 1, 1)


def test_activation_requires_verified_identity_and_link_cannot_be_reused(
    engine, session, employee
):
    gateway = InvitationGateway()
    service = coordinator(engine, gateway)
    result, email = invite(service, session, employee, gateway)
    identity = VerifiedAuthIdentity(subject=gateway.subject, email=email)
    service.validate_pending(identity)
    assert service.activate(identity).status == "ACTIVO"
    with pytest.raises(Conflict, match="utilizada|no admite"):
        service.validate_pending(identity)
    with service.factory() as db:
        target = db.get(Empleado, result.persona_id)
        account = db.scalar(
            select(CuentaAcceso).where(CuentaAcceso.id_persona == result.persona_id)
        )
        assert target.estado_laboral == "ACTIVO"
        assert account.estado_cuenta == "ACTIVA"


def test_resend_for_existing_identity_uses_recovery_without_duplicates(
    engine, session, employee
):
    gateway = InvitationGateway()
    service = coordinator(engine, gateway)
    result, email = invite(service, session, employee, gateway)
    age_invitation_events(service.factory, result.persona_id)
    before = counts(service.factory, result.persona_id)
    resent = service.resend(principal=employee, employee_id=result.persona_id)
    assert resent.status == "PENDIENTE_ACTIVACION"
    assert gateway.get_user_calls == [gateway.subject]
    assert gateway.recovery_calls == [(email, service.redirect_to)]
    assert counts(service.factory, result.persona_id) == before == (1, 1, 1, 1)


def test_failed_initial_request_can_be_retried_without_duplicate_profile(
    engine, session, employee
):
    gateway = InvitationGateway()
    gateway.invite_failure = AuthRateLimited("Límite de Supabase")
    service = coordinator(engine, gateway)
    email = f"{uuid4().hex}@example.test"
    with pytest.raises(AuthRateLimited):
        invite(service, session, employee, gateway, email=email)
    with service.factory() as db:
        employee_id = db.scalar(
            select(Persona.id_persona).where(Persona.correo_electronico == email)
        )
    age_invitation_events(service.factory, employee_id)
    gateway.invite_failure = None
    gateway.identity_email = email
    service.resend(principal=employee, employee_id=employee_id)
    assert counts(service.factory, employee_id) == (1, 1, 1, 1)
    assert len(gateway.invite_calls) == 2


def test_failed_resend_is_audited_and_exposed_as_failed_state(engine, session, employee):
    gateway = InvitationGateway()
    service = coordinator(engine, gateway)
    result, _ = invite(service, session, employee, gateway)
    age_invitation_events(service.factory, result.persona_id)
    gateway.recovery_failure = AuthRateLimited("Límite de Supabase")
    with pytest.raises(AuthRateLimited):
        service.resend(principal=employee, employee_id=result.persona_id)
    with service.factory() as db:
        row = next(
            item
            for item in EmployeeService.list_all(db, employee)
            if item["id_persona"] == result.persona_id
        )
        action = db.scalar(
            select(RegistroAuditoria.accion)
            .where(RegistroAuditoria.referencia_objeto == str(result.persona_id))
            .order_by(RegistroAuditoria.id_auditoria.desc())
        )
    assert row["estado_activacion"] == "INVITACION_FALLIDA"
    assert action == "FALLAR_REENVIO_INVITACION"


def test_resend_rate_limit_blocks_repeated_request_before_supabase(
    engine, session, employee
):
    gateway = InvitationGateway()
    service = coordinator(engine, gateway)
    result, _ = invite(service, session, employee, gateway)
    with pytest.raises(Conflict, match="Espera"):
        service.resend(principal=employee, employee_id=result.persona_id)
    assert gateway.recovery_calls == []


def test_resend_rejects_auth_identity_with_different_email(engine, session, employee):
    gateway = InvitationGateway()
    service = coordinator(engine, gateway)
    result, _ = invite(service, session, employee, gateway)
    age_invitation_events(service.factory, result.persona_id)
    gateway.identity_email = "otra-identidad@example.test"
    with pytest.raises(Conflict, match="no coincide"):
        service.resend(principal=employee, employee_id=result.persona_id)
    assert gateway.recovery_calls == []


@pytest.mark.parametrize("state", ["ACTIVO", "SUSPENDIDO"])
def test_resend_is_blocked_for_active_or_suspended_employee(
    engine, session, employee, state
):
    gateway = InvitationGateway()
    service = coordinator(engine, gateway)
    result, _ = invite(service, session, employee, gateway)
    age_invitation_events(service.factory, result.persona_id)
    with service.factory() as db, db.begin():
        db.get(Empleado, result.persona_id).estado_laboral = state
    with pytest.raises(Conflict, match="activo|suspendido"):
        service.resend(principal=employee, employee_id=result.persona_id)
    assert gateway.recovery_calls == []


def test_resend_endpoint_requires_employee_management_permission(
    engine, session, employee, customer
):
    gateway = InvitationGateway()
    service = coordinator(engine, gateway)
    result, _ = invite(service, session, employee, gateway)
    settings = Settings(database_url=str(engine.url), app_env="test")
    application = create_app(settings, engine=engine, auth_provider=FixedProvider(customer))
    application.state.employee_invitation_coordinator = service
    with TestClient(application) as client:
        response = client.post(
            f"/api/v1/empleados/{result.persona_id}/reenviar-invitacion"
        )
    assert response.status_code == 403
    assert gateway.recovery_calls == []


def test_resend_endpoint_returns_pending_state_after_supabase_accepts(
    engine, session, employee
):
    gateway = InvitationGateway()
    service = coordinator(engine, gateway)
    result, _ = invite(service, session, employee, gateway)
    age_invitation_events(service.factory, result.persona_id)
    settings = Settings(database_url=str(engine.url), app_env="test")
    application = create_app(settings, engine=engine, auth_provider=FixedProvider(employee))
    application.state.employee_invitation_coordinator = service
    with TestClient(application) as client:
        response = client.post(
            f"/api/v1/empleados/{result.persona_id}/reenviar-invitacion"
        )
    assert response.status_code == 200
    assert response.json()["estado"] == "PENDIENTE_ACTIVACION"


def test_concurrent_resend_allows_only_one_external_request(engine, session, employee):
    class BlockingGateway(InvitationGateway):
        def __init__(self):
            super().__init__()
            self.entered = Event()
            self.release = Event()

        def send_password_recovery(self, *, email: str, redirect_to: str | None = None):
            self.recovery_calls.append((email, redirect_to))
            self.entered.set()
            assert self.release.wait(timeout=5)

    gateway = BlockingGateway()
    service = coordinator(engine, gateway)
    result, _ = invite(service, session, employee, gateway)
    age_invitation_events(service.factory, result.persona_id)
    outcomes = []

    def worker():
        try:
            outcome = service.resend(principal=employee, employee_id=result.persona_id)
            outcomes.append(outcome.status)
        except Exception as exc:  # La aserción posterior valida el tipo esperado.
            outcomes.append(exc)

    first = Thread(target=worker)
    first.start()
    assert gateway.entered.wait(timeout=5)
    second = Thread(target=worker)
    second.start()
    second.join(timeout=5)
    gateway.release.set()
    first.join(timeout=5)
    assert len(gateway.recovery_calls) == 1
    assert "PENDIENTE_ACTIVACION" in outcomes
    assert any(isinstance(item, Conflict) for item in outcomes)
