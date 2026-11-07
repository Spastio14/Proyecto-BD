from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import Principal, get_principal
from app.db.session import get_session
from app.schemas.api import OrderRead
from app.services.production import ProductionService

router = APIRouter(prefix="/produccion", tags=["produccion"])


@router.post("/pedidos/{order_id}/iniciar", response_model=OrderRead)
def start_production(
    order_id: int,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    return ProductionService().start(session, order_id=order_id, principal=principal)


@router.post("/pedidos/{order_id}/completar", response_model=OrderRead)
def complete_production(
    order_id: int,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    return ProductionService().complete(session, order_id=order_id, principal=principal)
