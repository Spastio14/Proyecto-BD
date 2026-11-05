from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.exceptions import Conflict, DomainError
from app.integrations.supabase import AuthGateway
from app.models.entities import Cliente, CuentaAcceso, Persona
from app.services.customers import CustomerService


class IdentityNotConfigured(DomainError):
    status_code = 503
    code = "identity_not_configured"


class RegistrationCoordinator:
    """Único dueño del commit local y de la compensación del usuario externo."""

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
                .where(Persona.correo_electronico == normalized_email)
            )
            if duplicate is not None:
                raise Conflict("El correo ya tiene un perfil comercial")

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
        except Exception as database_error:
            try:
                self.gateway.delete_user(auth_user_id)
            except Exception as compensation_error:
                raise IdentityNotConfigured(
                    "Falló el vínculo local y también la compensación del usuario externo"
                ) from compensation_error
            if isinstance(database_error, SQLAlchemyError):
                raise Conflict("No se pudo crear el vínculo local de la cuenta") from database_error
            raise


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
