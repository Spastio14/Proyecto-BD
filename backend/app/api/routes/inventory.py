from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import Principal, get_principal
from app.db.session import get_session
from app.services.authorization import AuthorizationService
from app.services.inventory import InventoryService

router = APIRouter(prefix="/inventario", tags=["inventario"])


@router.get("/articulos/{article_id}/disponibilidad")
def availability(
    article_id: int,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    AuthorizationService.require(session, principal, "INVENTARIO_GESTIONAR")
    return {
        "id_articulo": article_id,
        "disponible": InventoryService.availability(session, article_id),
    }


@router.post("/pedidos/{order_id}/consumir")
def consume(
    order_id: int,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    AuthorizationService.require(session, principal, "INVENTARIO_GESTIONAR")
    movements = InventoryService().consume_order(session, order_id=order_id, principal=principal)
    return {"movimientos": [movement.id_movimiento for movement in movements]}
