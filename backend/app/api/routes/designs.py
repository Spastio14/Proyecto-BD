from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.core.security import Principal, get_principal
from app.db.session import get_session
from app.schemas.api import DesignDecision
from app.services.designs import DesignService

router = APIRouter(prefix="/disenos", tags=["disenos"])


class StorageRouteUnavailable(DomainError):
    status_code = 503
    code = "storage_not_configured"


@router.get("/pedidos/{order_id}/lineas/{line_number}/versiones")
def list_versions(
    order_id: int,
    line_number: int,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> list[dict[str, object]]:
    return [
        {
            "numero_version": version.numero_version,
            "nombre_archivo": version.nombre_archivo,
            "fecha_creacion": version.fecha_creacion,
            "observaciones": version.observaciones,
            "es_aprobado": version.es_aprobado,
        }
        for version in DesignService.list_versions(
            session,
            order_id=order_id,
            line_number=line_number,
            principal=principal,
        )
    ]


@router.post(
    "/pedidos/{order_id}/lineas/{line_number}/versiones",
    status_code=status.HTTP_201_CREATED,
)
async def upload_version(
    order_id: int,
    line_number: int,
    request: Request,
    file: UploadFile = File(),
    observations: str | None = Form(default=None),
    principal: Principal = Depends(get_principal),
) -> dict:
    coordinator = getattr(request.app.state, "storage_coordinator", None)
    if coordinator is None:
        raise StorageRouteUnavailable("Supabase Storage no está configurado")
    maximum = request.app.state.settings.storage_design_max_bytes
    content = await file.read(maximum + 1)
    version = coordinator.upload_design(
        order_id=order_id,
        line_number=line_number,
        file_name=file.filename or "archivo",
        content_type=file.content_type or "application/octet-stream",
        content=content,
        observations=observations,
        principal=principal,
    )
    return {
        "id_pedido": order_id,
        "numero_linea": line_number,
        "numero_version": version.numero_version,
    }


@router.get("/pedidos/{order_id}/lineas/{line_number}/versiones/{version_number}/archivo")
def signed_design_url(
    order_id: int,
    line_number: int,
    version_number: int,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    coordinator = getattr(request.app.state, "storage_coordinator", None)
    if coordinator is None:
        raise StorageRouteUnavailable("Supabase Storage no está configurado")
    url = coordinator.design_url(
        session,
        order_id=order_id,
        line_number=line_number,
        version_number=version_number,
        principal=principal,
    )
    return {"signed_url": url, "expires_in": request.app.state.settings.storage_signed_url_ttl}


@router.post("/pedidos/{order_id}/lineas/{line_number}/versiones/{version_number}/decision")
def decide(
    order_id: int,
    line_number: int,
    version_number: int,
    payload: DesignDecision,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    decision = DesignService().decide(
        session,
        order_id=order_id,
        line_number=line_number,
        version_number=version_number,
        approved=payload.approved,
        medium=payload.medium,
        principal=principal,
    )
    return {"id_aprobacion": decision.id_aprobacion, "tipo_decision": decision.tipo_decision}
