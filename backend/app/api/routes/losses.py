from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.security import Principal, get_principal
from app.db.session import get_session
from app.schemas.api import LossConfirm, LossCreate
from app.services.losses import LossLineInput, LossService

router = APIRouter(prefix="/perdidas", tags=["perdidas"])


@router.post("", status_code=status.HTTP_201_CREATED)
def report_loss(
    payload: LossCreate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    loss = LossService().report(
        session,
        principal=principal,
        moment=payload.moment,
        incident_type=payload.incident_type,
        reason=payload.reason,
        order_id=payload.order_id,
        stage_id=payload.stage_id,
        description=payload.description,
    )
    return {"id_perdida": loss.id_perdida, "estado": loss.estado_registro}


@router.post("/{loss_id}/confirmar")
def confirm_loss(
    loss_id: int,
    payload: LossConfirm,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    loss = LossService().confirm(
        session,
        loss_id=loss_id,
        principal=principal,
        lines=[
            LossLineInput(
                article_id=line.article_id,
                quantity=line.quantity,
                damage_description=line.damage_description,
            )
            for line in payload.lines
        ],
    )
    return {"id_perdida": loss.id_perdida, "estado": loss.estado_registro}
