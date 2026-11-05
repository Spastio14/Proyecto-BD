from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.security import Principal, get_principal
from app.db.session import get_session
from app.schemas.api import CancelRequest, OrderCreate, OrderRead
from app.services.orders import OrderLineInput, OrderService

router = APIRouter(prefix="/pedidos", tags=["pedidos"])


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderCreate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    return OrderService().create(
        session,
        principal=principal,
        lines=[
            OrderLineInput(
                variant_id=line.variant_id,
                quantity=line.quantity,
                promotion_id=line.promotion_id,
            )
            for line in payload.lines
        ],
        delivery_mode=payload.delivery_mode,
    )


@router.get("", response_model=list[OrderRead])
def list_orders(
    principal: Principal = Depends(get_principal), session: Session = Depends(get_session)
):
    return OrderService.list_owned(session, principal)


@router.get("/{order_id}", response_model=OrderRead)
def get_order(
    order_id: int,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    return OrderService.get_owned(session, order_id=order_id, principal=principal)


@router.post("/{order_id}/cancelar", response_model=OrderRead)
def cancel_order(
    order_id: int,
    payload: CancelRequest,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    return OrderService().cancel(
        session, order_id=order_id, principal=principal, reason=payload.reason
    )
