from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.exceptions import Conflict, DomainError, NotFound
from app.core.security import Principal, VerifiedAuthIdentity
from app.integrations.supabase import AuthAdminIdentity, AuthGateway
from app.models.entities import (
    AsignacionRol,
    Cliente,
    CuentaAcceso,
    Empleado,
    Persona,
    RegistroAuditoria,
    Rol,
)
from app.services.audit import AuditService
from app.services.authorization import AuthorizationService

ALLOWED_EMPLOYEE_ROLES = frozenset({"ADMINISTRADOR", "CONTADOR", "VENDEDOR", "PRODUCCION"})
INVITATION_RESEND_COOLDOWN = timedelta(seconds=60)
INVITATION_EVENT_ACTIONS = frozenset(
    {
        "PREPARAR_INVITACION_EMPLEADO",
        "SOLICITAR_INVITACION_EMPLEADO",
        "INVITAR_EMPLEADO",
        "FALLAR_INVITACION_EMPLEADO",
        "SOLICITAR_REENVIO_INVITACION",
        "REENVIAR_INVITACION_EMPLEADO",
        "FALLAR_REENVIO_INVITACION",
        "ACTIVAR_EMPLEADO",
    }
)
INVITATION_REQUEST_ACTIONS = frozenset(
    {
        "SOLICITAR_INVITACION_EMPLEADO",
        "INVITAR_EMPLEADO",
        "FALLAR_INVITACION_EMPLEADO",
        "SOLICITAR_REENVIO_INVITACION",
        "REENVIAR_INVITACION_EMPLEADO",
        "FALLAR_REENVIO_INVITACION",
    }
)


@dataclass(frozen=True, slots=True)
class EmployeeInviteResult:
    persona_id: int
    employee_code: str
    status: str


class EmployeeService:
    @staticmethod
    def allowed_roles(session: Session, principal: Principal) -> list[Rol]:
        AuthorizationService.require(session, principal, "EMPLEADO_GESTIONAR")
        return list(
            session.scalars(
                select(Rol)
                .where(Rol.nombre.in_(ALLOWED_EMPLOYEE_ROLES), Rol.estado == "ACTIVO")
                .order_by(Rol.nombre)
            )
        )

    @staticmethod
    def list_all(session: Session, principal: Principal) -> list[dict[str, object]]:
        AuthorizationService.require(session, principal, "EMPLEADO_GESTIONAR")
        rows = session.execute(
            select(Empleado, Persona, CuentaAcceso)
            .join(Persona, Persona.id_persona == Empleado.id_persona)
            .outerjoin(CuentaAcceso, CuentaAcceso.id_persona == Empleado.id_persona)
            .order_by(Empleado.codigo_empleado)
        ).all()
        result: list[dict[str, object]] = []
        for employee, person, account in rows:
            roles = list(
                session.scalars(
                    select(Rol.nombre)
                    .join(AsignacionRol, AsignacionRol.id_rol == Rol.id_rol)
                    .where(
                        AsignacionRol.id_empleado == employee.id_persona,
                        AsignacionRol.estado == "ACTIVA",
                    )
                    .order_by(Rol.nombre)
                )
            )
            events = list(
                session.scalars(
                    select(RegistroAuditoria)
                    .where(
                        RegistroAuditoria.tipo_objeto_afectado == "EMPLEADO",
                        RegistroAuditoria.referencia_objeto == str(employee.id_persona),
                        RegistroAuditoria.accion.in_(INVITATION_EVENT_ACTIONS),
                    )
                    .order_by(RegistroAuditoria.fecha_hora.desc())
                )
            )
            latest = events[0] if events else None
            latest_request = next(
                (event for event in events if event.accion in INVITATION_REQUEST_ACTIONS),
                None,
            )
            invitation_date = events[-1].fecha_hora if events else None
            available_at = (
                latest_request.fecha_hora + INVITATION_RESEND_COOLDOWN
                if latest_request
                else None
            )
            can_resend = (
                employee.estado_laboral == "INACTIVO"
                and (account is None or account.estado_cuenta == "ACTIVA")
                and (available_at is None or available_at <= datetime.now(UTC))
            )
            activation_status = EmployeeService._activation_status(
                employee=employee,
                account=account,
                latest_action=latest.accion if latest else None,
            )
            result.append(
                {
                    "id_persona": employee.id_persona,
                    "codigo_empleado": employee.codigo_empleado,
                    "nombre": " ".join(
                        value for value in (person.nombres, person.apellidos) if value
                    ),
                    "correo": person.correo_electronico,
                    "estado_laboral": employee.estado_laboral,
                    "estado_cuenta": account.estado_cuenta if account else "PENDIENTE_VINCULO",
                    "estado_activacion": activation_status,
                    "fecha_invitacion": invitation_date,
                    "fecha_ultima_solicitud": (
                        latest_request.fecha_hora if latest_request else None
                    ),
                    "reenvio_disponible_desde": available_at,
                    "puede_reenviar": can_resend,
                    "acciones_permitidas": [
                        action
                        for action, allowed in (
                            ("REENVIAR_INVITACION", can_resend),
                            ("CAMBIAR_ROL", employee.estado_laboral != "SUSPENDIDO"),
                        )
                        if allowed
                    ],
                    "roles": roles,
                }
            )
        return result

    @staticmethod
    def detail(
        session: Session, *, employee_id: int, principal: Principal
    ) -> dict[str, object]:
        AuthorizationService.require(session, principal, "EMPLEADO_GESTIONAR")
        row = session.execute(
            select(Empleado, Persona)
            .join(Persona, Persona.id_persona == Empleado.id_persona)
            .where(Empleado.id_persona == employee_id)
        ).one_or_none()
        if row is None:
            raise NotFound("Empleado no encontrado")
        employee, person = row
        return {
            "id_persona": employee.id_persona,
            "codigo_empleado": employee.codigo_empleado,
            "nombres": person.nombres,
            "apellidos": person.apellidos,
            "correo": person.correo_electronico,
            "telefono": person.telefono_contacto,
            "documento": person.documento_identificacion,
            "estado_laboral": employee.estado_laboral,
        }

    @staticmethod
    def update_identity(
        session: Session,
        *,
        employee_id: int,
        changes: dict[str, object],
        principal: Principal,
    ) -> Persona:
        AuthorizationService.require(session, principal, "EMPLEADO_GESTIONAR")
        employee = session.get(Empleado, employee_id)
        person = session.scalar(
            select(Persona).where(Persona.id_persona == employee_id).with_for_update()
        )
        if employee is None or person is None:
            raise NotFound("Empleado no encontrado")
        before = {
            "nombres": person.nombres,
            "apellidos": person.apellidos,
            "telefono": person.telefono_contacto,
            "documento": person.documento_identificacion,
        }
        mapping = {
            "names": "nombres",
            "surnames": "apellidos",
            "phone": "telefono_contacto",
            "document": "documento_identificacion",
        }
        for source, target in mapping.items():
            if source in changes:
                value = changes[source]
                setattr(person, target, value.strip() if isinstance(value, str) else value)
        AuditService.record(
            session,
            principal=principal,
            action="ACTUALIZAR_IDENTIDAD_EMPLEADO",
            object_type="EMPLEADO",
            object_reference=str(employee_id),
            reason="Actualización administrativa autorizada",
            before=before,
            after={
                "nombres": person.nombres,
                "apellidos": person.apellidos,
                "telefono": person.telefono_contacto,
                "documento": person.documento_identificacion,
            },
        )
        return person

    @staticmethod
    def possible_duplicates(
        session: Session, principal: Principal
    ) -> list[dict[str, object]]:
        AuthorizationService.require(session, principal, "EMPLEADO_GESTIONAR")
        employees = EmployeeService.list_all(session, principal)
        groups: dict[str, list[dict[str, object]]] = {}
        for item in employees:
            email = str(item.get("correo") or "").strip().lower()
            name = " ".join(str(item.get("nombre") or "").lower().split())
            if email:
                groups.setdefault(f"correo:{email}", []).append(item)
            if name:
                groups.setdefault(f"nombre:{name}", []).append(item)
        return [
            {"coincidencia": key, "empleados": rows}
            for key, rows in groups.items()
            if len(rows) > 1
        ]

    @staticmethod
    def _activation_status(
        *, employee: Empleado, account: CuentaAcceso | None, latest_action: str | None
    ) -> str:
        if employee.estado_laboral == "SUSPENDIDO" or (
            account is not None and account.estado_cuenta in {"SUSPENDIDA", "BLOQUEADA"}
        ):
            return "SUSPENDIDA"
        if employee.estado_laboral == "ACTIVO":
            return "ACTIVA"
        if latest_action in {
            "FALLAR_INVITACION_EMPLEADO",
            "FALLAR_REENVIO_INVITACION",
        }:
            return "INVITACION_FALLIDA"
        if account is not None:
            return "PENDIENTE_ACTIVACION"
        return "PENDIENTE_ENVIO"

    @staticmethod
    def assign_role(
        session: Session,
        *,
        employee_id: int,
        role_id: int,
        principal: Principal,
    ) -> None:
        AuthorizationService.require(session, principal, "EMPLEADO_GESTIONAR")
        employee = session.scalar(
            select(Empleado).where(Empleado.id_persona == employee_id).with_for_update()
        )
        if employee is None:
            raise NotFound("Empleado no encontrado")
        role = session.get(Rol, role_id)
        if role is None or role.estado != "ACTIVO" or role.nombre not in ALLOWED_EMPLOYEE_ROLES:
            raise Conflict("El rol no está permitido para asignación administrativa")
        now = datetime.now(UTC)
        active = list(
            session.scalars(
                select(AsignacionRol)
                .where(
                    AsignacionRol.id_empleado == employee_id,
                    AsignacionRol.estado == "ACTIVA",
                )
                .with_for_update()
            )
        )
        if any(item.id_rol == role_id for item in active):
            return
        for item in active:
            item.estado = "FINALIZADA"
            item.fecha_finalizacion = now
        session.add(
            AsignacionRol(
                id_empleado=employee_id,
                id_rol=role_id,
                fecha_asignacion=now,
                fecha_finalizacion=None,
                estado="ACTIVA",
            )
        )
        AuditService.record(
            session,
            principal=principal,
            action="ASIGNAR_ROL_EMPLEADO",
            object_type="EMPLEADO",
            object_reference=str(employee_id),
            reason="Cambio de rol autorizado",
            before={"roles": [item.id_rol for item in active]},
            after={"id_rol": role_id},
        )


class EmployeeInvitationCoordinator:
    def __init__(
        self,
        factory: sessionmaker[Session],
        gateway: AuthGateway,
        *,
        redirect_to: str | None,
    ):
        self.factory = factory
        self.gateway = gateway
        self.redirect_to = redirect_to

    def invite(
        self,
        *,
        principal: Principal,
        names: str,
        surnames: str | None,
        email: str,
        phone: str | None,
        document: str | None,
        role_id: int,
        capacity: int,
    ) -> EmployeeInviteResult:
        normalized_email = email.strip().lower()
        employee_id, created = self._stage(
            principal=principal,
            names=names,
            surnames=surnames,
            email=normalized_email,
            phone=phone,
            document=document,
            role_id=role_id,
            capacity=capacity,
        )
        with self.factory() as verification:
            existing_account = verification.scalar(
                select(CuentaAcceso).where(CuentaAcceso.id_persona == employee_id)
            )
            employee = verification.get(Empleado, employee_id)
            if not created:
                return EmployeeInviteResult(
                    employee_id,
                    employee.codigo_empleado,
                    "PENDIENTE_ACTIVACION" if existing_account else "PENDIENTE_ENVIO",
                )

        self._record_event(
            principal=principal,
            employee_id=employee_id,
            action="SOLICITAR_INVITACION_EMPLEADO",
            reason="Solicitud inicial preparada para Supabase Auth",
            after={"canal": "INVITACION", "estado": "SOLICITUD_EN_CURSO"},
        )
        try:
            subject = self.gateway.invite_user(
                email=normalized_email,
                redirect_to=self.redirect_to,
            )
        except DomainError as exc:
            self._record_failure(
                principal=principal,
                employee_id=employee_id,
                action="FALLAR_INVITACION_EMPLEADO",
                exc=exc,
            )
            raise
        with self.factory() as session, session.begin():
            session.execute(
                text("select pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": f"employee-auth:{subject}"},
            )
            employee = session.get(Empleado, employee_id)
            if employee is None or employee.estado_laboral != "INACTIVO":
                raise Conflict("El perfil ya no admite una invitación")
            duplicate = session.scalar(
                select(CuentaAcceso).where(CuentaAcceso.identificador_autenticacion == subject)
            )
            if duplicate is not None and duplicate.id_persona != employee_id:
                raise Conflict("La identidad Auth ya está vinculada a otra persona")
            if duplicate is None:
                session.add(
                    CuentaAcceso(
                        id_persona=employee_id,
                        identificador_autenticacion=subject,
                        # El esquema aprobado exige una fecha. Se actualiza al completar
                        # la activación y nunca concede acceso mientras EMPLEADO sea INACTIVO.
                        fecha_activacion=datetime.now(UTC),
                        estado_cuenta="ACTIVA",
                        ultimo_acceso=None,
                    )
                )
            AuditService.record(
                session,
                principal=principal,
                action="INVITAR_EMPLEADO",
                object_type="EMPLEADO",
                object_reference=str(employee_id),
                reason="Supabase aceptó la solicitud de invitación; activación pendiente",
                after={
                    "canal": "INVITACION",
                    "estado": "PENDIENTE_ACTIVACION",
                    "estado_laboral": "INACTIVO",
                },
            )
            code = employee.codigo_empleado
        return EmployeeInviteResult(employee_id, code, "PENDIENTE_ACTIVACION")

    def resend(
        self,
        *,
        principal: Principal,
        employee_id: int,
    ) -> EmployeeInviteResult:
        """Solicita un enlace nuevo sin recrear perfiles, roles ni identidades."""
        with self.factory() as session, session.begin():
            AuthorizationService.require(session, principal, "EMPLEADO_GESTIONAR")
            self._lock_invitation(session, employee_id)
            employee, person, account = self._pending_employee(session, employee_id)
            self._enforce_resend_cooldown(session, employee_id)
            channel = "RECUPERACION" if account else "INVITACION"
            subject = account.identificador_autenticacion if account else None
            AuditService.record(
                session,
                principal=principal,
                action="SOLICITAR_REENVIO_INVITACION",
                object_type="EMPLEADO",
                object_reference=str(employee_id),
                reason="Administrador solicitó un enlace de activación nuevo",
                after={"canal": channel, "estado": "SOLICITUD_EN_CURSO"},
            )
            email = (person.correo_electronico or "").strip().lower()
            code = employee.codigo_empleado

        try:
            if subject:
                identity = self.gateway.get_user(subject=subject)
                if identity.subject != subject or identity.email != email:
                    raise Conflict("La identidad Auth no coincide con la invitación autorizada")
                self.gateway.send_password_recovery(
                    email=email,
                    redirect_to=self.redirect_to,
                )
            else:
                subject = self.gateway.invite_user(
                    email=email,
                    redirect_to=self.redirect_to,
                )
        except DomainError as exc:
            self._record_failure(
                principal=principal,
                employee_id=employee_id,
                action="FALLAR_REENVIO_INVITACION",
                exc=exc,
            )
            raise

        with self.factory() as session, session.begin():
            self._lock_invitation(session, employee_id)
            employee, person, account = self._pending_employee(session, employee_id)
            normalized_email = (person.correo_electronico or "").strip().lower()
            if normalized_email != email:
                raise Conflict("El correo del empleado cambió durante el reenvío")
            if account is None:
                duplicate = session.scalar(
                    select(CuentaAcceso).where(
                        CuentaAcceso.identificador_autenticacion == subject
                    )
                )
                if duplicate is not None and duplicate.id_persona != employee_id:
                    raise Conflict("La identidad Auth ya está vinculada a otra persona")
                if duplicate is None:
                    session.add(
                        CuentaAcceso(
                            id_persona=employee_id,
                            identificador_autenticacion=subject,
                            fecha_activacion=datetime.now(UTC),
                            estado_cuenta="ACTIVA",
                            ultimo_acceso=None,
                        )
                    )
            elif account.identificador_autenticacion != subject:
                raise Conflict("La identidad Auth cambió durante el reenvío")
            AuditService.record(
                session,
                principal=principal,
                action="REENVIAR_INVITACION_EMPLEADO",
                object_type="EMPLEADO",
                object_reference=str(employee_id),
                reason="Supabase aceptó la solicitud; la entrega del correo queda pendiente",
                after={"canal": channel, "estado": "PENDIENTE_ACTIVACION"},
            )
        return EmployeeInviteResult(employee_id, code, "PENDIENTE_ACTIVACION")

    def _stage(
        self,
        *,
        principal: Principal,
        names: str,
        surnames: str | None,
        email: str,
        phone: str | None,
        document: str | None,
        role_id: int,
        capacity: int,
    ) -> tuple[int, bool]:
        with self.factory() as session, session.begin():
            AuthorizationService.require(session, principal, "EMPLEADO_GESTIONAR")
            session.execute(
                text("select pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": f"employee-email:{email}"},
            )
            role = session.get(Rol, role_id)
            if role is None or role.estado != "ACTIVO" or role.nombre not in ALLOWED_EMPLOYEE_ROLES:
                raise Conflict("El rol seleccionado no está permitido")
            people = list(
                session.scalars(
                    select(Persona).where(func.lower(Persona.correo_electronico) == email)
                )
            )
            if len(people) > 1:
                raise Conflict("El correo requiere revisión administrativa")
            if people:
                person = people[0]
                if session.get(Cliente, person.id_persona) is not None:
                    raise Conflict("Una cuenta de cliente no puede convertirse en empleado")
                employee = session.get(Empleado, person.id_persona)
                if employee is None:
                    raise Conflict("El correo pertenece a otro perfil")
                if employee.estado_laboral != "INACTIVO":
                    raise Conflict("El empleado ya existe o no admite invitación")
                assignment = session.scalar(
                    select(AsignacionRol).where(
                        AsignacionRol.id_empleado == employee.id_persona,
                        AsignacionRol.estado == "ACTIVA",
                    )
                )
                if assignment is None or assignment.id_rol != role_id:
                    raise Conflict(
                        "La invitación pendiente tiene otro rol; resuélvela antes de reintentar"
                    )
                return employee.id_persona, False
            person = Persona(
                nombres=names.strip(),
                apellidos=surnames.strip() if surnames else None,
                telefono_contacto=phone,
                correo_electronico=email,
                documento_identificacion=document,
            )
            session.add(person)
            session.flush()
            employee = Empleado(
                id_persona=person.id_persona,
                codigo_empleado=f"EMP-{person.id_persona:06d}",
                fecha_ingreso=datetime.now(UTC),
                estado_laboral="INACTIVO",
                capacidad_maxima_asignaciones=capacity,
            )
            session.add(employee)
            session.flush()
            session.add(
                AsignacionRol(
                    id_empleado=person.id_persona,
                    id_rol=role_id,
                    fecha_asignacion=datetime.now(UTC),
                    fecha_finalizacion=None,
                    estado="ACTIVA",
                )
            )
            AuditService.record(
                session,
                principal=principal,
                action="PREPARAR_INVITACION_EMPLEADO",
                object_type="EMPLEADO",
                object_reference=str(person.id_persona),
                reason="Perfil inactivo creado antes de invitar Auth",
                after={"id_rol": role_id, "estado_laboral": "INACTIVO"},
            )
            return person.id_persona, True

    @staticmethod
    def _lock_invitation(session: Session, employee_id: int) -> None:
        session.execute(
            text("select pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"employee-invitation:{employee_id}"},
        )

    @staticmethod
    def _pending_employee(
        session: Session, employee_id: int
    ) -> tuple[Empleado, Persona, CuentaAcceso | None]:
        employee = session.scalar(
            select(Empleado).where(Empleado.id_persona == employee_id).with_for_update()
        )
        if employee is None:
            raise NotFound("Empleado no encontrado")
        if employee.estado_laboral == "ACTIVO":
            raise Conflict("Un empleado activo no admite reenvío de invitación")
        if employee.estado_laboral != "INACTIVO":
            raise Conflict("El empleado está suspendido y no admite reenvío")
        person = session.scalar(
            select(Persona).where(Persona.id_persona == employee_id).with_for_update()
        )
        if person is None or not person.correo_electronico:
            raise Conflict("El empleado no tiene un correo verificable")
        if session.get(Cliente, employee_id) is not None:
            raise Conflict("Una cuenta de cliente no puede activarse como empleado")
        assignment = session.scalar(
            select(AsignacionRol).where(
                AsignacionRol.id_empleado == employee_id,
                AsignacionRol.estado == "ACTIVA",
            )
        )
        if assignment is None:
            raise Conflict("La invitación no tiene un rol administrativo activo")
        account = session.scalar(
            select(CuentaAcceso)
            .where(CuentaAcceso.id_persona == employee_id)
            .with_for_update()
        )
        if account is not None and account.estado_cuenta != "ACTIVA":
            raise Conflict("La cuenta está suspendida o bloqueada")
        return employee, person, account

    @staticmethod
    def _enforce_resend_cooldown(session: Session, employee_id: int) -> None:
        latest = session.scalar(
            select(RegistroAuditoria)
            .where(
                RegistroAuditoria.tipo_objeto_afectado == "EMPLEADO",
                RegistroAuditoria.referencia_objeto == str(employee_id),
                RegistroAuditoria.accion.in_(INVITATION_REQUEST_ACTIONS),
            )
            .order_by(RegistroAuditoria.fecha_hora.desc())
            .limit(1)
        )
        if latest is None:
            return
        available_at = latest.fecha_hora + INVITATION_RESEND_COOLDOWN
        if available_at > datetime.now(UTC):
            seconds = max(1, int((available_at - datetime.now(UTC)).total_seconds()) + 1)
            raise Conflict(f"Espera {seconds} segundos antes de solicitar otro enlace")

    def _record_event(
        self,
        *,
        principal: Principal,
        employee_id: int,
        action: str,
        reason: str,
        after: dict[str, str],
    ) -> None:
        with self.factory() as session, session.begin():
            self._lock_invitation(session, employee_id)
            AuditService.record(
                session,
                principal=principal,
                action=action,
                object_type="EMPLEADO",
                object_reference=str(employee_id),
                reason=reason,
                after=after,
            )

    def _record_failure(
        self,
        *,
        principal: Principal,
        employee_id: int,
        action: str,
        exc: DomainError,
    ) -> None:
        self._record_event(
            principal=principal,
            employee_id=employee_id,
            action=action,
            reason="Supabase rechazó o no pudo completar la solicitud",
            after={"estado": "FALLIDA", "codigo_error": exc.code},
        )

    def activate(self, identity: VerifiedAuthIdentity) -> EmployeeInviteResult:
        with self.factory() as session, session.begin():
            for key in sorted((f"auth:{identity.subject}", f"email:{identity.email}")):
                session.execute(
                    text("select pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                    {"key": key},
                )
            account = session.scalar(
                select(CuentaAcceso).where(
                    CuentaAcceso.identificador_autenticacion == identity.subject
                )
            )
            if account is not None:
                if account.estado_cuenta != "ACTIVA":
                    raise Conflict("La cuenta de acceso está suspendida o bloqueada")
                person = session.get(Persona, account.id_persona)
                if person is None or (person.correo_electronico or "").lower() != identity.email:
                    raise Conflict("La identidad no coincide con la invitación")
            else:
                candidates = list(
                    session.scalars(
                        select(Persona)
                        .join(Empleado, Empleado.id_persona == Persona.id_persona)
                        .where(
                            func.lower(Persona.correo_electronico) == identity.email,
                            Empleado.estado_laboral == "INACTIVO",
                        )
                        .with_for_update()
                    )
                )
                if len(candidates) != 1:
                    raise Conflict("No existe una invitación administrativa verificable")
                person = candidates[0]
                if session.get(Cliente, person.id_persona) is not None:
                    raise Conflict("Una cuenta de cliente no puede activarse como empleado")
                account = CuentaAcceso(
                    id_persona=person.id_persona,
                    identificador_autenticacion=identity.subject,
                    fecha_activacion=datetime.now(UTC),
                    estado_cuenta="ACTIVA",
                    ultimo_acceso=None,
                )
                session.add(account)
            employee = session.get(Empleado, person.id_persona)
            if employee is None or employee.estado_laboral == "SUSPENDIDO":
                raise Conflict("El perfil no admite activación")
            if session.get(Cliente, person.id_persona) is not None:
                raise Conflict("Una cuenta de cliente no puede activarse como empleado")
            assignment = session.scalar(
                select(AsignacionRol).where(
                    AsignacionRol.id_empleado == person.id_persona,
                    AsignacionRol.estado == "ACTIVA",
                )
            )
            if assignment is None:
                raise Conflict("La invitación no tiene un rol administrativo activo")
            employee.estado_laboral = "ACTIVO"
            account.estado_cuenta = "ACTIVA"
            account.fecha_activacion = datetime.now(UTC)
            AuditService.record(
                session,
                principal=Principal(person.id_persona, "EMPLEADO"),
                action="ACTIVAR_EMPLEADO",
                object_type="EMPLEADO",
                object_reference=str(person.id_persona),
                reason="Identidad Supabase verificada tras invitación administrativa",
                after={"estado_laboral": "ACTIVO"},
            )
            return EmployeeInviteResult(person.id_persona, employee.codigo_empleado, "ACTIVO")

    def validate_pending(self, identity: VerifiedAuthIdentity) -> EmployeeInviteResult:
        """Confirma que el JWT corresponde a una invitación administrativa pendiente."""
        with self.factory() as session:
            account = session.scalar(
                select(CuentaAcceso).where(
                    CuentaAcceso.identificador_autenticacion == identity.subject
                )
            )
            if account is not None:
                if account.estado_cuenta != "ACTIVA":
                    raise Conflict("La cuenta de acceso está suspendida o bloqueada")
                person = session.get(Persona, account.id_persona)
                if person is None or (person.correo_electronico or "").lower() != identity.email:
                    raise Conflict("La identidad no coincide con la invitación")
            else:
                candidates = list(
                    session.scalars(
                        select(Persona)
                        .join(Empleado, Empleado.id_persona == Persona.id_persona)
                        .where(
                            func.lower(Persona.correo_electronico) == identity.email,
                            Empleado.estado_laboral == "INACTIVO",
                        )
                    )
                )
                if len(candidates) != 1:
                    raise Conflict("No existe una invitación administrativa verificable")
                person = candidates[0]
            if session.get(Cliente, person.id_persona) is not None:
                raise Conflict("Una cuenta de cliente no puede activarse como empleado")
            employee = session.get(Empleado, person.id_persona)
            if employee is None or employee.estado_laboral != "INACTIVO":
                raise Conflict("La invitación ya fue utilizada o no admite activación")
            assignment = session.scalar(
                select(AsignacionRol).where(
                    AsignacionRol.id_empleado == person.id_persona,
                    AsignacionRol.estado == "ACTIVA",
                )
            )
            if assignment is None:
                raise Conflict("La invitación no tiene un rol administrativo activo")
            return EmployeeInviteResult(
                person.id_persona, employee.codigo_empleado, "INVITACION_VERIFICADA"
            )

    def bootstrap_admin(
        self,
        *,
        identity: AuthAdminIdentity,
        names: str,
        surnames: str | None,
        phone: str | None,
        document: str | None,
        employee_code: str,
    ) -> EmployeeInviteResult:
        with self.factory() as session, session.begin():
            for key in sorted((f"auth:{identity.subject}", f"email:{identity.email}")):
                session.execute(
                    text("select pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                    {"key": key},
                )
            admin_role = session.scalar(
                select(Rol).where(Rol.nombre == "ADMINISTRADOR", Rol.estado == "ACTIVO")
            )
            if admin_role is None:
                raise Conflict("El rol ADMINISTRADOR no está instalado")
            account = session.scalar(
                select(CuentaAcceso).where(
                    CuentaAcceso.identificador_autenticacion == identity.subject
                )
            )
            if account is not None:
                if session.get(Cliente, account.id_persona) is not None:
                    raise Conflict(
                        "La cuenta elegida es cliente y no se convertirá automáticamente"
                    )
                employee = session.get(Empleado, account.id_persona)
                if employee is None:
                    raise Conflict("La cuenta pertenece a otro tipo de perfil")
                self._ensure_admin_assignment(session, employee.id_persona, admin_role.id_rol)
                employee.estado_laboral = "ACTIVO"
                return EmployeeInviteResult(employee.id_persona, employee.codigo_empleado, "ACTIVO")
            if (
                session.scalar(
                    select(Persona.id_persona).where(
                        func.lower(Persona.correo_electronico) == identity.email
                    )
                )
                is not None
            ):
                raise Conflict("El correo ya pertenece a un perfil; requiere revisión manual")
            person = Persona(
                nombres=names.strip(),
                apellidos=surnames.strip() if surnames else None,
                telefono_contacto=phone,
                correo_electronico=identity.email,
                documento_identificacion=document,
            )
            session.add(person)
            session.flush()
            employee = Empleado(
                id_persona=person.id_persona,
                codigo_empleado=employee_code,
                fecha_ingreso=datetime.now(UTC),
                estado_laboral="ACTIVO",
                capacidad_maxima_asignaciones=20,
            )
            session.add(employee)
            session.flush()
            session.add(
                CuentaAcceso(
                    id_persona=person.id_persona,
                    identificador_autenticacion=identity.subject,
                    fecha_activacion=datetime.now(UTC),
                    estado_cuenta="ACTIVA",
                    ultimo_acceso=None,
                )
            )
            self._ensure_admin_assignment(session, person.id_persona, admin_role.id_rol)
            AuditService.record(
                session,
                principal=None,
                action="INICIALIZAR_ADMINISTRADOR",
                object_type="EMPLEADO",
                object_reference=str(person.id_persona),
                reason="Inicialización manual con identidad Auth verificada por API administrativa",
                after={"rol": "ADMINISTRADOR"},
            )
            return EmployeeInviteResult(person.id_persona, employee_code, "ACTIVO")

    @staticmethod
    def _ensure_admin_assignment(session: Session, employee_id: int, role_id: int) -> None:
        existing = session.scalar(
            select(AsignacionRol.id_asignacion_rol).where(
                AsignacionRol.id_empleado == employee_id,
                AsignacionRol.id_rol == role_id,
                AsignacionRol.estado == "ACTIVA",
            )
        )
        if existing is None:
            session.add(
                AsignacionRol(
                    id_empleado=employee_id,
                    id_rol=role_id,
                    fecha_asignacion=datetime.now(UTC),
                    fecha_finalizacion=None,
                    estado="ACTIVA",
                )
            )
