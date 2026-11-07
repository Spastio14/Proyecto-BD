from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.security import Principal, get_principal
from app.db.session import get_session
from app.schemas.api import DeliveryComplete, DeliverySchedule, OrderRead
from app.services.deliveries import DeliveryService

router = APIRouter(prefix="/entregas", tags=["entregas"])


@router.get("/agencias")
def list_agencies(
    principal: Principal = Depends(get_principal), session: Session = Depends(get_session)
) -> list[dict]:
    return [
        {
            "id_agencia": item.id_agencia,
            "nombre": item.nombre,
            "tipo_agencia": item.tipo_agencia,
            "telefono": item.telefono,
        }
        for item in DeliveryService.list_agencies(session, principal)
    ]


@router.get("/pedidos/{order_id}/datos-iniciales")
def delivery_defaults(
    order_id: int,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    return DeliveryService.defaults(
        session,
        order_id=order_id,
        principal=principal,
    )


@router.post("/pedidos/{order_id}", status_code=status.HTTP_201_CREATED)
def schedule_delivery(
    order_id: int,
    payload: DeliverySchedule,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    item = DeliveryService().schedule(
        session,
        order_id=order_id,
        agency_id=payload.agency_id,
        address=payload.address,
        recipient_name=payload.recipient_name,
        recipient_phone=payload.recipient_phone,
        agreed_fee=payload.agreed_fee,
        scheduled_at=payload.scheduled_at,
        principal=principal,
    )
    return {"id_envio": item.id_envio, "id_pedido": item.id_pedido, "estado": item.estado}


@router.post("/pedidos/{order_id}/completar", response_model=OrderRead)
def complete_delivery(
    order_id: int,
    payload: DeliveryComplete,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    return DeliveryService().complete(
        session, order_id=order_id, principal=principal, reason=payload.reason
    )
