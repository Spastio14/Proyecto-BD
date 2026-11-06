from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.core.security import (
    Principal,
    VerifiedAuthIdentity,
    get_principal,
    get_verified_auth_identity,
)
from app.db.session import get_session
from app.schemas.api import (
    GuestCreate,
    LoginRequest,
    RegistrationRecoveryRequest,
    RegistrationRequest,
)
from app.services.authorization import AuthorizationService

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthRouteUnavailable(DomainError):
    status_code = 503
    code = "auth_not_configured"


@router.post("/registro", status_code=status.HTTP_201_CREATED)
def register(payload: RegistrationRequest, request: Request) -> dict:
    coordinator = getattr(request.app.state, "registration_coordinator", None)
    if coordinator is None:
        raise AuthRouteUnavailable("El registro con Supabase no está configurado")
    persona_id = coordinator.register(
        names=payload.names,
        surnames=payload.surnames,
        email=payload.email,
        phone=payload.phone,
        password=payload.password.get_secret_value(),
    )
    return {
        "id_persona": persona_id,
        "email_verification_required": True,
    }


@router.post("/login")
def login(payload: LoginRequest, request: Request) -> dict:
    gateway = getattr(request.app.state, "auth_gateway", None)
    if gateway is None:
        raise AuthRouteUnavailable("El inicio de sesión con Supabase no está configurado")
    return gateway.sign_in(
        email=payload.email.strip().lower(), password=payload.password.get_secret_value()
    )


@router.get("/me")
def current_identity(
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    return AuthorizationService.identity(session, principal)


@router.post("/completar-registro")
def complete_registration(
    payload: RegistrationRecoveryRequest,
    request: Request,
    identity: VerifiedAuthIdentity = Depends(get_verified_auth_identity),
) -> dict:
    coordinator = getattr(request.app.state, "registration_coordinator", None)
    if coordinator is None:
        raise AuthRouteUnavailable("El vínculo con Supabase no está configurado")
    result = coordinator.complete_verified_identity(
        subject=identity.subject,
        email=identity.email,
        names=payload.names,
        surnames=payload.surnames,
        phone=payload.phone,
    )
    return {
        "id_persona": result.persona_id,
        "vinculo_creado": result.created,
    }


@router.post("/activar-empleado")
def activate_employee(
    request: Request,
    identity: VerifiedAuthIdentity = Depends(get_verified_auth_identity),
) -> dict:
    coordinator = getattr(request.app.state, "employee_invitation_coordinator", None)
    if coordinator is None:
        raise AuthRouteUnavailable("La activación de empleados no está configurada")
    result = coordinator.activate(identity)
    return {
        "id_persona": result.persona_id,
        "codigo_empleado": result.employee_code,
        "estado": result.status,
    }


@router.post("/invitado", status_code=status.HTTP_201_CREATED)
def create_guest(payload: GuestCreate, request: Request, response: Response) -> dict:
    coordinator = getattr(request.app.state, "guest_coordinator", None)
    signer = getattr(request.app.state, "guest_signer", None)
    if coordinator is None or signer is None:
        raise AuthRouteUnavailable("Las credenciales de invitado no están configuradas")
    persona_id = coordinator.create(names=payload.names, phone=payload.phone)
    settings = request.app.state.settings
    response.set_cookie(
        key=settings.guest_cookie_name,
        value=signer.issue(persona_id),
        max_age=settings.guest_cookie_max_age,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )
    return {"id_persona": persona_id, "tipo_cliente": "INVITADO"}
