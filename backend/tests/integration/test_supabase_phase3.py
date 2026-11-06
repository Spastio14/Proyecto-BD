import os
import subprocess
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from app.core.config import Settings
from app.core.exceptions import AuthenticationRequired, Conflict, PermissionDenied
from app.core.security import (
    GuestAuthenticationProvider,
    GuestCredentialSigner,
    SupabaseAuthenticationProvider,
    SupabaseTokenVerifier,
)
from app.db.session import build_engine
from app.models.entities import CuentaAcceso, Persona, Transaccion, VersionDiseno
from app.services.authorization import AuthorizationService
from app.services.identity import RegistrationCoordinator
from app.services.payments import PaymentService
from app.services.storage import StorageCoordinator
from tests.helpers import create_order

pytestmark = pytest.mark.integration

PROJECT_REF = "iwvmbdfkxrssduoqobgy"
PROJECT_URL = f"https://{PROJECT_REF}.supabase.co"


class StaticJWKClient:
    def __init__(self, key):
        self.key = key

    def get_signing_key_from_jwt(self, token):
        return SimpleNamespace(key=self.key)


def token(
    private_key,
    *,
    issuer=PROJECT_URL + "/auth/v1",
    expires_delta=300,
    audience="authenticated",
):
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(uuid4()),
            "iss": issuer,
            "aud": audience,
            "iat": now,
            "exp": now + timedelta(seconds=expires_delta),
        },
        private_key,
        algorithm="ES256",
        headers={"kid": "test-key"},
    )


def verifier(public_key):
    instance = SupabaseTokenVerifier(
        project_url=PROJECT_URL, project_ref=PROJECT_REF, audience="authenticated"
    )
    instance.jwks = StaticJWKClient(public_key)
    return instance


def request(*, bearer=None, cookie=None):
    headers = []
    if bearer:
        headers.append((b"authorization", f"Bearer {bearer}".encode()))
    if cookie:
        headers.append((b"cookie", f"s2r_guest={cookie}".encode()))
    return Request({"type": "http", "headers": headers})


class FakeVerifier:
    def __init__(self, claims):
        self.claims = claims

    def verify(self, token):
        return self.claims


class FakeGateway:
    def __init__(self, auth_id=None):
        self.auth_id = auth_id or str(uuid4())
        self.uploaded = []
        self.removed = []

    def sign_up(self, *, email, password):
        return self.auth_id

    def sign_in(self, *, email, password):
        return {}

    def upload(self, *, bucket, path, content, content_type):
        self.uploaded.append((bucket, path, content_type, len(content)))

    def delete(self, *, bucket, path):
        self.removed.append((bucket, path))

    def signed_url(self, *, bucket, path, expires_in):
        return f"https://signed.example.test/{bucket}/{path}?ttl={expires_in}"


def storage(factory, gateway):
    return StorageCoordinator(
        factory,
        gateway,
        design_max_bytes=1024,
        receipt_max_bytes=1024,
        signed_url_ttl=300,
    )


def test_51_valid_project_jwt_is_cryptographically_verified():
    private_key = ec.generate_private_key(ec.SECP256R1())
    claims = verifier(private_key.public_key()).verify(token(private_key))
    assert claims["aud"] == "authenticated"


def test_52_jwt_with_invalid_signature_is_rejected():
    trusted = ec.generate_private_key(ec.SECP256R1())
    attacker = ec.generate_private_key(ec.SECP256R1())
    with pytest.raises(jwt.InvalidSignatureError):
        verifier(trusted.public_key()).verify(token(attacker))


def test_53_expired_jwt_is_rejected():
    private_key = ec.generate_private_key(ec.SECP256R1())
    with pytest.raises(jwt.ExpiredSignatureError):
        verifier(private_key.public_key()).verify(token(private_key, expires_delta=-1))


def test_54_token_from_another_project_is_rejected():
    private_key = ec.generate_private_key(ec.SECP256R1())
    with pytest.raises(jwt.InvalidIssuerError):
        verifier(private_key.public_key()).verify(
            token(private_key, issuer="https://otro-proyecto.supabase.co/auth/v1")
        )


def test_55_verified_subject_resolves_linked_active_customer(session):
    provider = SupabaseAuthenticationProvider(
        FakeVerifier({"sub": "11111111-1111-4111-8111-111111111111"})
    )
    principal = provider.authenticate(request(bearer="verified"), session)
    assert principal.persona_id == 2
    assert principal.origin == "CLIENTE"


def test_56_unlinked_subject_is_rejected(session):
    provider = SupabaseAuthenticationProvider(FakeVerifier({"sub": str(uuid4())}))
    with pytest.raises(AuthenticationRequired, match="no está activa o vinculada"):
        provider.authenticate(request(bearer="verified"), session)


def test_57_roles_in_jwt_do_not_grant_employee_identity(session):
    provider = SupabaseAuthenticationProvider(
        FakeVerifier({"sub": "11111111-1111-4111-8111-111111111111", "role": "administrador"})
    )
    assert provider.authenticate(request(bearer="verified"), session).origin == "CLIENTE"


def test_58_signed_guest_credential_resolves_only_guest_profile(session):
    signer = GuestCredentialSigner("test-secret-with-enough-entropy", max_age=300)
    provider = GuestAuthenticationProvider(signer, "s2r_guest")
    assert provider.authenticate(request(cookie=signer.issue(1)), session).persona_id == 1


def test_59_tampered_guest_credential_is_rejected(session):
    signer = GuestCredentialSigner("test-secret-with-enough-entropy", max_age=300)
    credential = signer.issue(1)
    provider = GuestAuthenticationProvider(signer, "s2r_guest")
    with pytest.raises(AuthenticationRequired):
        provider.authenticate(request(cookie=credential[:-1] + "A"), session)


def test_60_registration_links_auth_user_to_existing_model(engine):
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    gateway = FakeGateway()
    person_id = RegistrationCoordinator(factory, gateway).register(
        names="Registro",
        surnames="Fase Tres",
        email=f"{uuid4().hex}@example.test",
        phone=None,
        password="password-for-test",
    )
    with factory() as session:
        account = session.scalar(select(CuentaAcceso).where(CuentaAcceso.id_persona == person_id))
        assert account.identificador_autenticacion == gateway.auth_id


def test_61_registration_never_deletes_existing_auth_user_on_local_conflict(engine):
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    existing_auth_id = "11111111-1111-4111-8111-111111111111"
    gateway = FakeGateway(existing_auth_id)
    with pytest.raises(Conflict, match="vínculo comercial"):
        RegistrationCoordinator(factory, gateway).register(
            names="Conflicto",
            surnames=None,
            email=f"{uuid4().hex}@example.test",
            phone=None,
            password="password-for-test",
        )
    with factory() as session:
        account = session.scalar(
            select(CuentaAcceso).where(CuentaAcceso.identificador_autenticacion == existing_auth_id)
        )
        assert account.id_persona == 2


def test_62_remote_database_configuration_requires_tls():
    with pytest.raises(ValueError, match="exigir TLS"):
        Settings(
            database_url="postgresql+psycopg://example.invalid/db",
            database_connection_mode="session_pooler",
            database_sslmode="prefer",
        )


def test_63_transaction_pooler_disables_prepared_statements(monkeypatch):
    captured = {}

    def fake_create_engine(url, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("app.db.session.create_engine", fake_create_engine)
    settings = Settings(
        database_url="postgresql+psycopg://example.invalid/db",
        database_connection_mode="transaction_pooler",
        database_sslmode="require",
    )
    build_engine(settings)
    assert captured["connect_args"]["prepare_threshold"] is None
    assert captured["connect_args"]["sslmode"] == "require"


def test_64_design_upload_creates_private_version(engine, customer):
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session, session.begin():
        order = create_order(session, customer)
        order_id = order.id_pedido
    gateway = FakeGateway()
    version = storage(factory, gateway).upload_design(
        order_id=order_id,
        line_number=1,
        file_name="arte.png",
        content_type="image/png",
        content=b"\x89PNG\r\n\x1a\ntest",
        observations=None,
        principal=customer,
    )
    assert version.ruta_archivo.startswith(f"pedidos/{order_id}/lineas/1/")
    assert not version.ruta_archivo.startswith("http")
    assert gateway.uploaded[0][0] == "disenos"


def test_65_storage_rejects_mime_before_upload(engine, customer):
    gateway = FakeGateway()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with pytest.raises(Conflict, match="Tipo"):
        storage(factory, gateway).upload_design(
            order_id=1,
            line_number=1,
            file_name="script.svg",
            content_type="image/svg+xml",
            content=b"<svg/>",
            observations=None,
            principal=customer,
        )
    assert gateway.uploaded == []


def test_66_storage_deletes_object_when_database_link_fails(engine, customer, monkeypatch):
    gateway = FakeGateway()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session, session.begin():
        order = create_order(session, customer)
        order_id = order.id_pedido

    def fail_after_upload(*args, **kwargs):
        raise RuntimeError("fallo local simulado")

    monkeypatch.setattr("app.services.storage.DesignService.add_version", fail_after_upload)
    with pytest.raises(RuntimeError, match="simulado"):
        storage(factory, gateway).upload_design(
            order_id=order_id,
            line_number=1,
            file_name="arte.png",
            content_type="image/png",
            content=b"\x89PNG\r\n\x1a\ntest",
            observations=None,
            principal=customer,
        )
    assert gateway.removed and gateway.removed[0][0] == "disenos"


def test_67_receipt_upload_is_structurally_linked_to_transaction(engine, customer):
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session, session.begin():
        order = create_order(session, customer)
        payment = PaymentService().report(
            session,
            order_id=order.id_pedido,
            milestone_number=1,
            idempotency_key=uuid4(),
            method="TRANSFERENCIA",
            principal=customer,
        )
        payment_id = payment.id_transaccion
    gateway = FakeGateway()
    path = storage(factory, gateway).upload_receipt(
        payment_id=payment_id,
        file_name="comprobante.pdf",
        content_type="application/pdf",
        content=b"%PDF-test",
        principal=customer,
    )
    with factory() as session:
        saved = session.get(Transaccion, payment_id)
        assert saved.ruta_comprobante == path
        assert saved.comprobante_tamano_bytes == 9


def test_68_receipt_cannot_be_silently_replaced(engine, customer):
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session, session.begin():
        order = create_order(session, customer)
        payment = PaymentService().report(
            session,
            order_id=order.id_pedido,
            milestone_number=1,
            idempotency_key=uuid4(),
            method="TRANSFERENCIA",
            principal=customer,
        )
        payment.ruta_comprobante = "transacciones/existente.pdf"
        payment.comprobante_mime = "application/pdf"
        payment.comprobante_tamano_bytes = 10
        payment_id = payment.id_transaccion
    gateway = FakeGateway()
    with pytest.raises(Conflict, match="ya tiene"):
        storage(factory, gateway).upload_receipt(
            payment_id=payment_id,
            file_name="otro.pdf",
            content_type="application/pdf",
            content=b"%PDF-test",
            principal=customer,
        )
    assert gateway.uploaded == []
    assert gateway.removed == []


def test_69_signed_design_url_checks_order_ownership(engine, customer, guest):
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session, session.begin():
        order = create_order(session, customer)
        version = VersionDiseno(
            id_pedido=order.id_pedido,
            numero_linea=1,
            numero_version=1,
            nombre_archivo="arte.png",
            ruta_archivo="pedidos/privado/arte.png",
            fecha_creacion=datetime.now(UTC),
            observaciones=None,
            es_aprobado=False,
        )
        session.add(version)
        order_id = order.id_pedido
    gateway = FakeGateway()
    with factory() as session, pytest.raises(PermissionDenied):
        storage(factory, gateway).design_url(
            session,
            order_id=order_id,
            line_number=1,
            version_number=1,
            principal=guest,
        )


def test_70_private_tables_remain_closed_to_authenticated_role(engine):
    with engine.connect() as connection:
        connection.execute(text("set role authenticated"))
        with pytest.raises(DBAPIError):
            connection.execute(text("select count(*) from public.pedido"))


def test_71_suspended_local_account_is_rejected(session):
    account = session.scalar(
        select(CuentaAcceso).where(
            CuentaAcceso.identificador_autenticacion == "11111111-1111-4111-8111-111111111111"
        )
    )
    account.estado_cuenta = "SUSPENDIDA"
    session.flush()
    provider = SupabaseAuthenticationProvider(
        FakeVerifier({"sub": "11111111-1111-4111-8111-111111111111"})
    )
    with pytest.raises(AuthenticationRequired):
        provider.authenticate(request(bearer="verified"), session)


def test_72_employee_identity_still_requires_database_permission(session):
    provider = SupabaseAuthenticationProvider(
        FakeVerifier({"sub": "33333333-3333-4333-8333-333333333333"})
    )
    principal = provider.authenticate(request(bearer="verified"), session)
    assert principal.origin == "EMPLEADO"
    assert AuthorizationService.has_permission(session, principal, "PEDIDO_GESTIONAR")
    assert not AuthorizationService.has_permission(session, principal, "PERMISO_INVENTADO")


def test_73_unauthorized_design_upload_is_rejected_before_storage(engine, customer, guest):
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session, session.begin():
        order = create_order(session, customer)
        order_id = order.id_pedido
    gateway = FakeGateway()
    with pytest.raises(PermissionDenied):
        storage(factory, gateway).upload_design(
            order_id=order_id,
            line_number=1,
            file_name="arte.png",
            content_type="image/png",
            content=b"\x89PNG\r\n\x1a\ntest",
            observations=None,
            principal=guest,
        )
    assert gateway.uploaded == []


def test_74_receipt_url_is_private_to_order_owner(engine, customer, guest):
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session, session.begin():
        order = create_order(session, customer)
        payment = PaymentService().report(
            session,
            order_id=order.id_pedido,
            milestone_number=1,
            idempotency_key=uuid4(),
            method="TRANSFERENCIA",
            principal=customer,
        )
        payment.ruta_comprobante = "transacciones/privado/comprobante.pdf"
        payment.comprobante_mime = "application/pdf"
        payment.comprobante_tamano_bytes = 100
        payment_id = payment.id_transaccion
    with factory() as session, pytest.raises(PermissionDenied):
        storage(factory, FakeGateway()).receipt_url(session, payment_id=payment_id, principal=guest)


def test_75_signed_url_uses_bounded_expiration(engine, customer):
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session, session.begin():
        order = create_order(session, customer)
        session.add(
            VersionDiseno(
                id_pedido=order.id_pedido,
                numero_linea=1,
                numero_version=1,
                nombre_archivo="arte.png",
                ruta_archivo="pedidos/privado/arte.png",
                fecha_creacion=datetime.now(UTC),
                observaciones=None,
                es_aprobado=False,
            )
        )
        order_id = order.id_pedido
    with factory() as session:
        signed = storage(factory, FakeGateway()).design_url(
            session,
            order_id=order_id,
            line_number=1,
            version_number=1,
            principal=customer,
        )
    assert signed.endswith("ttl=300")


def test_76_verified_auth_identity_completes_missing_commercial_link(engine):
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    coordinator = RegistrationCoordinator(factory, FakeGateway())
    subject = str(uuid4())
    email = f"{uuid4().hex}@example.test"

    first = coordinator.complete_verified_identity(
        subject=subject,
        email=email,
        names="Cuenta",
        surnames="Recuperada",
        phone=None,
    )
    second = coordinator.complete_verified_identity(
        subject=subject,
        email=email,
        names="No debe duplicarse",
        surnames=None,
        phone=None,
    )

    assert first.created is True
    assert second.created is False
    assert second.persona_id == first.persona_id
    with factory() as session:
        accounts = session.scalars(
            select(CuentaAcceso).where(CuentaAcceso.identificador_autenticacion == subject)
        ).all()
        person = session.get(Persona, first.persona_id)
        assert len(accounts) == 1
        assert person.nombres == "Cuenta"


def test_77_recovery_does_not_link_identity_by_email_alone(engine):
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    coordinator = RegistrationCoordinator(factory, FakeGateway())
    subject = str(uuid4())
    with pytest.raises(Conflict, match="revisión administrativa"):
        coordinator.complete_verified_identity(
            subject=subject,
            email="cliente@example.test",
            names="Suplantación",
            surnames=None,
            phone=None,
        )
    with factory() as session:
        assert (
            session.scalar(
                select(CuentaAcceso).where(CuentaAcceso.identificador_autenticacion == subject)
            )
            is None
        )


def test_78_recovery_endpoint_uses_verified_token_subject(engine, api_client_factory):
    subject = str(uuid4())
    email = f"{uuid4().hex}@example.test"
    client = api_client_factory(None)
    client.app.state.token_verifier = FakeVerifier({"sub": subject, "email": email})
    client.app.state.registration_coordinator = RegistrationCoordinator(
        client.app.state.session_factory, FakeGateway()
    )
    response = client.post(
        "/api/v1/auth/completar-registro",
        headers={"Authorization": "Bearer verified-token"},
        json={"names": "Recuperación", "surnames": "Segura", "phone": None},
    )
    assert response.status_code == 200
    assert response.json()["vinculo_creado"] is True
    with sessionmaker(bind=engine)() as session:
        account = session.scalar(
            select(CuentaAcceso).where(CuentaAcceso.identificador_autenticacion == subject)
        )
        assert account is not None
        assert session.get(Persona, account.id_persona).correo_electronico == email


@pytest.mark.remote
def test_79_remote_project_is_postgresql_17_and_has_expected_schema():
    if os.getenv("RUN_SUPABASE_REMOTE_TESTS") != "1":
        pytest.skip("requiere opt-in y credenciales remotas privadas")
    url = os.environ["SUPABASE_TEST_DATABASE_URL"]
    remote = create_engine(url, connect_args={"sslmode": "require"})
    with remote.connect() as connection:
        assert connection.scalar(text("show server_version")).startswith("17.")
        assert (
            connection.scalar(
                text("select count(*) from information_schema.tables where table_schema='public'")
            )
            == 41
        )
    remote.dispose()


@pytest.mark.remote
def test_80_remote_migration_history_matches_local_files():
    if os.getenv("RUN_SUPABASE_REMOTE_TESTS") != "1":
        pytest.skip("requiere opt-in, Supabase CLI enlazado y token privado")
    result = subprocess.run(
        ["supabase", "migration", "list", "--linked"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "202611050002" in result.stdout
