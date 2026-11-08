from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.security import Principal, get_principal
from app.db.session import get_session
from app.schemas.api import CancelRequest, OrderCreate, OrderRead, OrderTransitionRequest
from app.services.operations import OrderOperationService
from app.services.orders import OrderLineInput, OrderService

router = APIRouter(prefix="/pedidos", tags=["pedidos"])

ACTIVE_OPERATIONAL_STATES = {
    "disenos": {"PAGADO_PARCIAL", "PAGADO", "EN_DISENO"},
    "produccion": {"EN_DISENO", "EN_PRODUCCION"},
    "entregas": {"LISTO"},
    "pagos": {"PENDIENTE_PAGO", "PAGADO_PARCIAL", "PAGADO"},
}


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
                customization=line.customization,
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


@router.get("/operativos")
def operational_orders(
    context: str = Query(pattern="^(disenos|produccion|entregas|pagos)$"),
    view: str = Query(default="activos", pattern="^(activos|historial|todos)$"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=100),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    from sqlalchemy import func, select

    from app.models.entities import Pedido
    from app.services.authorization import AuthorizationService

    AuthorizationService.require(session, principal, "PEDIDO_GESTIONAR")
    active_states = ACTIVE_OPERATIONAL_STATES[context]
    statement = select(Pedido)
    count_statement = select(func.count()).select_from(Pedido)
    if view == "activos":
        statement = statement.where(Pedido.estado.in_(active_states))
        count_statement = count_statement.where(Pedido.estado.in_(active_states))
    elif view == "historial":
        statement = statement.where(Pedido.estado.in_({"ENTREGADO", "CANCELADO", "EXPIRADO"}))
        count_statement = count_statement.where(
            Pedido.estado.in_({"ENTREGADO", "CANCELADO", "EXPIRADO"})
        )
    total = session.scalar(count_statement) or 0
    orders = list(
        session.scalars(
            statement.order_by(Pedido.fecha_creacion.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
    )
    return {
        "items": [
            OrderOperationService.summary(
                session, order_id=order.id_pedido, principal=principal
            )
            for order in orders
        ],
        "page": page,
        "limit": limit,
        "total": total,
    }


@router.get("/{order_id}", response_model=OrderRead)
def get_order(
    order_id: int,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    return OrderService.get_owned(session, order_id=order_id, principal=principal)


@router.get("/{order_id}/detalles")
def order_details(
    order_id: int,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> list[dict]:
    return [
        {
            "numero_linea": item.numero_linea,
            "id_variante": item.id_variante,
            "cantidad": item.cantidad,
            "precio_unitario": item.precio_unitario_aplicado,
            "descuento": item.descuento_aplicado,
            "importe": item.importe_pactado,
            "modo_precio": item.modo_precio,
            "personalizacion": item.descripcion_personalizacion,
        }
        for item in OrderService.details_owned(session, order_id=order_id, principal=principal)
    ]


@router.get("/{order_id}/historial")
def order_history(
    order_id: int,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> list[dict]:
    return [
        {
            "fecha_hora": item.fecha_hora,
            "estado_anterior": item.estado_anterior,
            "estado_nuevo": item.estado_nuevo,
            "motivo": item.motivo,
            "origen": item.origen_cambio,
        }
        for item in OrderService.history_owned(session, order_id=order_id, principal=principal)
    ]


@router.get("/{order_id}/operacion")
def order_operation(
    order_id: int,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    return OrderOperationService.summary(session, order_id=order_id, principal=principal)


@router.post("/{order_id}/estado", response_model=OrderRead)
def transition_order(
    order_id: int,
    payload: OrderTransitionRequest,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    return OrderService().transition_authorized(
        session,
        order_id=order_id,
        target=payload.target,
        principal=principal,
        reason=payload.reason,
    )


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
