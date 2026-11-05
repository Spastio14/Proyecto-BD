from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import PermissionDenied
from app.core.security import Principal
from app.models.entities import AsignacionRol, Empleado, Permiso, Rol, RolPermiso


class AuthorizationService:
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
                Empleado.estado_laboral == "ACTIVO",
                AsignacionRol.estado == "ACTIVA",
                AsignacionRol.fecha_asignacion <= now,
                or_(
                    AsignacionRol.fecha_finalizacion.is_(None),
                    AsignacionRol.fecha_finalizacion >= now,
                ),
                Rol.estado == "ACTIVO",
                Permiso.codigo_permiso == permission,
            )
        )
        return authorized is not None

    @classmethod
    def require(cls, session: Session, principal: Principal, permission: str) -> None:
        if not cls.has_permission(session, principal, permission):
            raise PermissionDenied(f"Falta el permiso {permission}")
