from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.core.security import Principal, get_principal
from app.db.session import get_session
from app.schemas.api import EmployeeIdentityUpdate, EmployeeInviteRequest, EmployeeRoleAssignment
from app.services.authorization import AuthorizationService
from app.services.employees import EmployeeService

router = APIRouter(prefix="/empleados", tags=["empleados"])


class EmployeeInvitationUnavailable(DomainError):
    status_code = 503
    code = "employee_invitation_unavailable"


@router.get("/roles")
def allowed_roles(
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> list[dict[str, object]]:
    return [
        {"id_rol": role.id_rol, "nombre": role.nombre, "descripcion": role.descripcion}
        for role in EmployeeService.allowed_roles(session, principal)
    ]


@router.get("")
def list_employees(
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> list[dict[str, object]]:
    return EmployeeService.list_all(session, principal)


@router.get("/duplicados-posibles")
def possible_duplicates(
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> list[dict[str, object]]:
    return EmployeeService.possible_duplicates(session, principal)


@router.get("/{employee_id}")
def employee_detail(
    employee_id: int,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    return EmployeeService.detail(
        session, employee_id=employee_id, principal=principal
    )


@router.patch("/{employee_id}")
def update_employee(
    employee_id: int,
    payload: EmployeeIdentityUpdate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    person = EmployeeService.update_identity(
        session,
        employee_id=employee_id,
        changes=payload.model_dump(exclude_unset=True),
        principal=principal,
    )
    return {"id_persona": person.id_persona, "actualizado": True}


@router.post("/invitaciones", status_code=status.HTTP_201_CREATED)
def invite_employee(
    payload: EmployeeInviteRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    AuthorizationService.require(session, principal, "EMPLEADO_GESTIONAR")
    coordinator = getattr(request.app.state, "employee_invitation_coordinator", None)
    if coordinator is None:
        raise EmployeeInvitationUnavailable(
            "La invitación requiere la credencial privada de Supabase en el servidor"
        )
    result = coordinator.invite(
        principal=principal,
        names=payload.names,
        surnames=payload.surnames,
        email=payload.email,
        phone=payload.phone,
        document=payload.document,
        role_id=payload.role_id,
        capacity=payload.capacity,
    )
    return {
        "id_persona": result.persona_id,
        "codigo_empleado": result.employee_code,
        "estado": result.status,
    }


@router.post("/{employee_id}/reenviar-invitacion")
def resend_employee_invitation(
    employee_id: int,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    AuthorizationService.require(session, principal, "EMPLEADO_GESTIONAR")
    coordinator = getattr(request.app.state, "employee_invitation_coordinator", None)
    if coordinator is None:
        raise EmployeeInvitationUnavailable(
            "El reenvío requiere la integración privada de Supabase en el servidor"
        )
    result = coordinator.resend(principal=principal, employee_id=employee_id)
    return {
        "id_persona": result.persona_id,
        "codigo_empleado": result.employee_code,
        "estado": result.status,
    }


@router.put("/{employee_id}/rol", status_code=status.HTTP_204_NO_CONTENT)
def assign_role(
    employee_id: int,
    payload: EmployeeRoleAssignment,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> None:
    EmployeeService.assign_role(
        session,
        employee_id=employee_id,
        role_id=payload.role_id,
        principal=principal,
    )
