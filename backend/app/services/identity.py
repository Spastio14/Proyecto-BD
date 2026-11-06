from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.exceptions import Conflict
from app.integrations.supabase import AuthGateway
from app.models.entities import Cliente, CuentaAcceso, Persona
from app.services.customers import CustomerService


@dataclass(frozen=True, slots=True)
class RegistrationLinkResult:
    persona_id: int
    created: bool


class RegistrationCoordinator:
    """Coordina Auth y el vínculo local sin borrar identidades existentes."""

    def __init__(self, factory: sessionmaker[Session], gateway: AuthGateway):
        self.factory = factory
        self.gateway = gateway

    def register(
        self,
        *,
        names: str,
        surnames: str | None,
        email: str,
        phone: str | None,
        password: str,
    ) -> int:
        normalized_email = email.strip().lower()
        with self.factory() as precheck:
            duplicate = precheck.scalar(
                select(Persona.id_persona)
                .join(Cliente, Cliente.id_persona == Persona.id_persona)
                .where(func.lower(Persona.correo_electronico) == normalized_email)
            )
            if duplicate is not None:
                raise Conflict(
                    "No fue posible crear la cuenta. Si ya te registraste, "
                    "inicia sesión o completa el vínculo"
                )

        auth_user_id = self.gateway.sign_up(email=normalized_email, password=password)
        try:
            with self.factory() as session, session.begin():
                customer = CustomerService().create(
                    session,
                    names=names,
                    surnames=surnames,
                    client_type="REGISTRADO",
                    email=normalized_email,
                    phone=phone,
                    origin="SUPABASE_AUTH",
                )
                session.add(
                    CuentaAcceso(
                        id_persona=customer.id_persona,
                        identificador_autenticacion=auth_user_id,
                        fecha_activacion=datetime.now(UTC),
                        estado_cuenta="ACTIVA",
                        ultimo_acceso=None,
                    )
                )
                session.flush()
                persona_id = customer.id_persona
            return persona_id
        except SQLAlchemyError as exc:
            # El endpoint Signup no permite saber con certeza si una identidad
            # pendiente ya existía. Nunca se elimina automáticamente; el usuario
            # puede completar el vínculo tras confirmar correo e iniciar sesión.
            raise Conflict(
                "La identidad Auth existe, pero no se pudo crear el vínculo comercial; "
                "confirma el correo e inicia sesión para completarlo"
            ) from exc

    def complete_verified_identity(
        self,
        *,
        subject: str,
        email: str,
        names: str,
        surnames: str | None,
        phone: str | None,
    ) -> RegistrationLinkResult:
        normalized_email = email.strip().lower()
        with self.factory() as session, session.begin():
            # Serializa reintentos del mismo Auth UID y carreras por correo sin
            # introducir otra tabla o una restricción no aprobada en PERSONA.
            for lock_key in sorted((f"auth:{subject}", f"email:{normalized_email}")):
                session.execute(
                    text("select pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                    {"key": lock_key},
                )

            existing_account = session.scalar(
                select(CuentaAcceso).where(CuentaAcceso.identificador_autenticacion == subject)
            )
            if existing_account is not None:
                return RegistrationLinkResult(
                    persona_id=existing_account.id_persona,
                    created=False,
                )

            # No se fusiona con una persona por coincidencia de correo. Si ya
            # existe un perfil comercial, requiere resolución administrativa.
            existing_person = session.scalar(
                select(Persona.id_persona).where(
                    func.lower(Persona.correo_electronico) == normalized_email
                )
            )
            if existing_person is not None:
                raise Conflict(
                    "El correo verificado ya pertenece a un perfil comercial; "
                    "se requiere revisión administrativa"
                )

            customer = CustomerService().create(
                session,
                names=names,
                surnames=surnames,
                client_type="REGISTRADO",
                email=normalized_email,
                phone=phone,
                origin="SUPABASE_AUTH_RECOVERY",
            )
            session.add(
                CuentaAcceso(
                    id_persona=customer.id_persona,
                    identificador_autenticacion=subject,
                    fecha_activacion=datetime.now(UTC),
                    estado_cuenta="ACTIVA",
                    ultimo_acceso=None,
                )
            )
            session.flush()
            return RegistrationLinkResult(persona_id=customer.id_persona, created=True)


class GuestCoordinator:
    def __init__(self, factory: sessionmaker[Session]):
        self.factory = factory

    def create(self, *, names: str, phone: str | None) -> int:
        with self.factory() as session, session.begin():
            guest = CustomerService().create(
                session,
                names=names,
                surnames=None,
                client_type="INVITADO",
                phone=phone,
                origin="PORTAL_INVITADO",
            )
            return guest.id_persona
