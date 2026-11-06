from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import PermissionDenied
from app.core.security import Principal
from app.models.entities import (
    AsignacionRol,
    Cliente,
    CuentaAcceso,
    Empleado,
    Permiso,
    Persona,
    Rol,
    RolPermiso,
)


class AuthorizationService:
    @staticmethod
    def _active_assignment_conditions(now: datetime):
        return (
            Empleado.estado_laboral == "ACTIVO",
            AsignacionRol.estado == "ACTIVA",
            AsignacionRol.fecha_asignacion <= now,
            or_(
                AsignacionRol.fecha_finalizacion.is_(None),
                AsignacionRol.fecha_finalizacion >= now,
            ),
            Rol.estado == "ACTIVO",
        )

    @staticmethod
    def has_permission(session: Session, principal: Principal, permission: str) -> bool:
        if not principal.is_employee:
            return False
        now = datetime.now(UTC)
        authorized = session.scalar(
            select(Permiso.id_permiso)
            .join(RolPermiso, RolPermiso.id_permiso == Permiso.id_permiso)
            .join(Rol, Rol.id_rol == RolPermiso.id_rol)
            .join(AsignacionRol, AsignacionRol.id_rol == Rol.id_rol)
            .join(Empleado, Empleado.id_persona == AsignacionRol.id_empleado)
            .where(
                Empleado.id_persona == principal.persona_id,
                *AuthorizationService._active_assignment_conditions(now),
                Permiso.codigo_permiso == permission,
            )
        )
        return authorized is not None

    @classmethod
    def require(cls, session: Session, principal: Principal, permission: str) -> None:
        if not cls.has_permission(session, principal, permission):
            raise PermissionDenied(f"Falta el permiso {permission}")

    @staticmethod
    def roles(session: Session, principal: Principal) -> list[str]:
        if not principal.is_employee:
            return []
        now = datetime.now(UTC)
        return list(
            session.scalars(
                select(Rol.nombre)
                .join(AsignacionRol, AsignacionRol.id_rol == Rol.id_rol)
                .join(Empleado, Empleado.id_persona == AsignacionRol.id_empleado)
                .where(
                    Empleado.id_persona == principal.persona_id,
                    *AuthorizationService._active_assignment_conditions(now),
                )
                .distinct()
                .order_by(Rol.nombre)
            )
        )

    @staticmethod
    def permissions(session: Session, principal: Principal) -> list[str]:
        if not principal.is_employee:
            return []
        now = datetime.now(UTC)
        return list(
            session.scalars(
                select(Permiso.codigo_permiso)
                .join(RolPermiso, RolPermiso.id_permiso == Permiso.id_permiso)
                .join(Rol, Rol.id_rol == RolPermiso.id_rol)
                .join(AsignacionRol, AsignacionRol.id_rol == Rol.id_rol)
                .join(Empleado, Empleado.id_persona == AsignacionRol.id_empleado)
                .where(
                    Empleado.id_persona == principal.persona_id,
                    *AuthorizationService._active_assignment_conditions(now),
                )
                .distinct()
                .order_by(Permiso.codigo_permiso)
            )
        )

    @classmethod
    def identity(cls, session: Session, principal: Principal) -> dict[str, object]:
        person = session.get(Persona, principal.persona_id)
        if person is None:
            raise PermissionDenied("La identidad no tiene una persona asociada")
        account = session.scalar(
            select(CuentaAcceso).where(CuentaAcceso.id_persona == principal.persona_id)
        )
        roles = cls.roles(session, principal)
        permissions = cls.permissions(session, principal)
        if principal.is_employee:
            profile = "EMPLEADO"
            normalized = {role.upper() for role in roles}
            if normalized & {"ADMINISTRADOR", "ADMINISTRACION", "DUEÑO", "DUENO"}:
                dashboard = "/app/admin/"
            elif "CONTADOR" in normalized:
                dashboard = "/app/contabilidad/"
            elif "VENDEDOR" in normalized:
                dashboard = "/app/ventas/"
            else:
                dashboard = "/app/produccion/"
        else:
            customer = session.get(Cliente, principal.persona_id)
            profile = customer.tipo_cliente if customer is not None else "CLIENTE"
            dashboard = "/app/cliente/"
        return {
            "id_persona": person.id_persona,
            "nombre": " ".join(
                value for value in (person.nombres, person.apellidos) if value
            ),
            "tipo_perfil": profile,
            "roles": roles,
            "permisos": permissions,
            "estado_cuenta": account.estado_cuenta if account is not None else "SIN_CUENTA",
            "dashboard_inicial": dashboard,
        }
