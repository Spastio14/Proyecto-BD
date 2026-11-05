from fastapi import APIRouter, Request, Response, status

from app.core.exceptions import DomainError
from app.schemas.api import GuestCreate, LoginRequest, RegistrationRequest

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
