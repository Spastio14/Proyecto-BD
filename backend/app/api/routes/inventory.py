from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.security import Principal, get_principal
from app.db.session import get_session
from app.schemas.api import InventoryAdjustment, InventoryArticleCreate, InventoryArticleUpdate
from app.services.authorization import AuthorizationService
from app.services.inventory import InventoryService

router = APIRouter(prefix="/inventario", tags=["inventario"])


def _article(row) -> dict:
    return {
        "id_articulo": row.id_articulo,
        "codigo": row.codigo,
        "nombre": row.nombre,
        "tipo_articulo": row.tipo_articulo,
        "unidad_medida": row.unidad_medida,
        "existencia_actual": row.existencia_actual,
        "existencia_minima": row.existencia_minima,
        "costo_referencia": row.costo_referencia,
        "estado": row.estado,
    }


@router.get("/articulos")
def list_inventory(
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> list[dict[str, object]]:
    return InventoryService.list_with_availability(session, principal)


@router.post("/articulos", status_code=status.HTTP_201_CREATED)
def create_article(
    payload: InventoryArticleCreate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    return _article(
        InventoryService.create_article(
            session,
            principal=principal,
            code=payload.code,
            name=payload.name,
            article_type=payload.article_type,
            unit=payload.unit,
            minimum_stock=payload.minimum_stock,
            reference_cost=payload.reference_cost,
        )
    )


@router.patch("/articulos/{article_id}")
def update_article(
    article_id: int,
    payload: InventoryArticleUpdate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    return _article(
        InventoryService.update_article(
            session,
            article_id=article_id,
            principal=principal,
            changes=payload.model_dump(exclude_unset=True),
        )
    )


@router.post("/articulos/{article_id}/ajustes", status_code=status.HTTP_201_CREATED)
def adjust_article(
    article_id: int,
    payload: InventoryAdjustment,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    movement = InventoryService.adjust(
        session,
        article_id=article_id,
        direction=payload.direction,
        quantity=payload.quantity,
        reason=payload.reason,
        observations=payload.observations,
        principal=principal,
    )
    return {"id_movimiento": movement.id_movimiento, "tipo": movement.tipo_movimiento}


@router.get("/movimientos")
def list_movements(
    article_id: int | None = None,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> list[dict]:
    return [
        {
            "id_movimiento": row.id_movimiento,
            "id_articulo": row.id_articulo,
            "id_pedido": row.id_pedido,
            "fecha_hora": row.fecha_hora,
            "tipo_movimiento": row.tipo_movimiento,
            "cantidad": row.cantidad,
            "costo_unitario_aplicado": row.costo_unitario_aplicado,
            "motivo": row.motivo,
        }
        for row in InventoryService.list_movements(
            session, principal=principal, article_id=article_id
        )
    ]


@router.get("/articulos/{article_id}/disponibilidad")
def availability(
    article_id: int,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    AuthorizationService.require(session, principal, "INVENTARIO_CONSULTAR")
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
    AuthorizationService.require(session, principal, "INVENTARIO_CONSUMIR_RESERVAS")
    movements = InventoryService().consume_order(session, order_id=order_id, principal=principal)
    return {"movimientos": [movement.id_movimiento for movement in movements]}
