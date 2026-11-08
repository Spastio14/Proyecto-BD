from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import Conflict, PermissionDenied
from app.core.security import Principal, VerifiedAuthIdentity
from app.models.entities import Cliente, CuentaAcceso, Empleado, Persona
from app.services.audit import AuditService
from app.services.authorization import AuthorizationService
from app.services.customers import CustomerService


class ProfileService:
    @staticmethod
    def get(session: Session, principal: Principal) -> dict[str, object]:
        person = session.get(Persona, principal.persona_id)
        if person is None:
            raise PermissionDenied("La identidad no tiene una persona asociada")
        identity = AuthorizationService.identity(session, principal)
        customer = session.get(Cliente, principal.persona_id)
        employee = session.get(Empleado, principal.persona_id)
        return identity | {
            "nombres": person.nombres,
            "apellidos": person.apellidos,
            "correo": person.correo_electronico,
            "telefono": person.telefono_contacto,
            "documento": person.documento_identificacion,
            "direccion_habitual": person.direccion_habitual,
            "tipo_cliente": customer.tipo_cliente if customer else None,
            "condicion_comercial": customer.condicion_comercial if customer else None,
            "codigo_empleado": employee.codigo_empleado if employee else None,
        }

    @staticmethod
    def update(
        session: Session,
        *,
        principal: Principal,
        changes: dict[str, object],
    ) -> Persona:
        person = session.scalar(
            select(Persona)
            .where(Persona.id_persona == principal.persona_id)
            .with_for_update()
        )
        if person is None:
            raise PermissionDenied("La identidad no tiene una persona asociada")
        if principal.is_employee and {
            "names",
            "surnames",
            "document",
        }.intersection(changes):
            raise PermissionDenied(
                "Los datos de identidad del empleado sólo pueden modificarse por administración"
            )
        before = CustomerService._person_snapshot(person)
        CustomerService._apply_person_changes(person, changes)
        AuditService.record(
            session,
            principal=principal,
            action="ACTUALIZAR_PERFIL_PROPIO",
            object_type="PERSONA",
            object_reference=str(principal.persona_id),
            reason="Actualización de datos personales autorizados",
            before=before,
            after=CustomerService._person_snapshot(person),
        )
        return person

    @staticmethod
    def validate_auth_identity(
        session: Session,
        *,
        principal: Principal,
        identity: VerifiedAuthIdentity,
        require_current_email: bool,
    ) -> Persona:
        account = session.scalar(
            select(CuentaAcceso).where(
                CuentaAcceso.id_persona == principal.persona_id,
                CuentaAcceso.identificador_autenticacion == identity.subject,
                CuentaAcceso.estado_cuenta == "ACTIVA",
            )
        )
        if account is None:
            raise PermissionDenied("La sesión Auth no corresponde al perfil")
        person = session.get(Persona, principal.persona_id)
        if person is None:
            raise PermissionDenied("La identidad no tiene una persona asociada")
        current = (person.correo_electronico or "").strip().lower()
        if require_current_email and current != identity.email:
            raise Conflict("Primero sincroniza el correo ya verificado por Supabase")
        return person

    @classmethod
    def ensure_email_available(
        cls, session: Session, *, email: str, exclude_person_id: int
    ) -> None:
        existing = session.scalar(
            select(Persona.id_persona).where(
                func.lower(Persona.correo_electronico) == email,
                Persona.id_persona != exclude_person_id,
            )
        )
        if existing is not None:
            raise Conflict("El correo verificado ya pertenece a otro perfil")

    @classmethod
    def synchronize_email(
        cls,
        session: Session,
        *,
        principal: Principal,
        identity: VerifiedAuthIdentity,
    ) -> Persona:
        person = cls.validate_auth_identity(
            session,
            principal=principal,
            identity=identity,
            require_current_email=False,
        )
        cls.ensure_email_available(
            session,
            email=identity.email,
            exclude_person_id=principal.persona_id,
        )
        old_email = person.correo_electronico
        if (old_email or "").strip().lower() == identity.email:
            return person
        person.correo_electronico = identity.email
        AuditService.record(
            session,
            principal=principal,
            action="SINCRONIZAR_CORREO_VERIFICADO",
            object_type="PERSONA",
            object_reference=str(principal.persona_id),
            reason="Correo confirmado por Supabase Auth",
            before={"correo": old_email},
            after={"correo": identity.email},
        )
        return person
