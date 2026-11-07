from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.routes.auth import AuthRouteUnavailable
from app.core.security import (
    Principal,
    VerifiedAuthIdentity,
    bearer_token,
    get_principal,
    get_verified_auth_identity,
)
from app.db.session import get_session
from app.schemas.api import EmailChangeRequest, ProfileUpdate
from app.services.audit import AuditService
from app.services.profiles import ProfileService

router = APIRouter(prefix="/perfil", tags=["perfil"])


@router.get("")
def get_profile(
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    return ProfileService.get(session, principal)


@router.patch("")
def update_profile(
    payload: ProfileUpdate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    person = ProfileService.update(
        session,
        principal=principal,
        changes=payload.model_dump(exclude_unset=True),
    )
    return {"id_persona": person.id_persona, "actualizado": True}


@router.post("/correo/solicitar")
def request_email_change(
    payload: EmailChangeRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
    identity: VerifiedAuthIdentity = Depends(get_verified_auth_identity),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    gateway = getattr(request.app.state, "auth_gateway", None)
    if gateway is None:
        raise AuthRouteUnavailable("El cambio de correo con Supabase no está configurado")
    person = ProfileService.validate_auth_identity(
        session,
        principal=principal,
        identity=identity,
        require_current_email=True,
    )
    new_email = payload.new_email.strip().lower()
    ProfileService.ensure_email_available(
        session,
        email=new_email,
        exclude_person_id=principal.persona_id,
    )
    gateway.request_email_change(
        access_token=bearer_token(request),
        new_email=new_email,
    )
    AuditService.record(
        session,
        principal=principal,
        action="SOLICITAR_CAMBIO_CORREO",
        object_type="PERSONA",
        object_reference=str(person.id_persona),
        reason="Supabase aceptó la solicitud; confirmación pendiente",
        before={"correo": person.correo_electronico},
        after={"correo_solicitado": new_email, "estado": "PENDIENTE_CONFIRMACION"},
    )
    return {"confirmacion_requerida": True}


@router.post("/correo/sincronizar")
def synchronize_verified_email(
    principal: Principal = Depends(get_principal),
    identity: VerifiedAuthIdentity = Depends(get_verified_auth_identity),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    person = ProfileService.synchronize_email(
        session,
        principal=principal,
        identity=identity,
    )
    return {"id_persona": person.id_persona, "correo": person.correo_electronico}
