from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.security import Principal, get_principal
from app.db.session import get_session
from app.schemas.api import DesignDecision, DesignVersionCreate
from app.services.designs import DesignService

router = APIRouter(prefix="/disenos", tags=["disenos"])


@router.post("/pedidos/{order_id}/versiones", status_code=status.HTTP_201_CREATED)
def add_version(
    order_id: int,
    payload: DesignVersionCreate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    version = DesignService().add_version(
        session,
        order_id=order_id,
        line_number=payload.line_number,
        file_name=payload.file_name,
        private_path=payload.private_path,
        observations=payload.observations,
        principal=principal,
    )
    return {
        "id_pedido": order_id,
        "numero_linea": payload.line_number,
        "numero_version": version.numero_version,
    }


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
