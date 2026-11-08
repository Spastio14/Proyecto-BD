from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.security import Principal, get_principal
from app.db.session import get_session
from app.models.entities import Cliente
from app.schemas.api import (
    PointOfSaleCustomerCreate,
    PointOfSaleOrderCreate,
    PointOfSaleQuoteCreate,
)
from app.services.authorization import AuthorizationService
from app.services.customers import CustomerService
from app.services.orders import OrderLineInput, OrderService
from app.services.pricing import PricingService
from app.services.quotations import QuotationService, QuoteLineInput

router = APIRouter(prefix="/ventas", tags=["ventas-presenciales"])


@router.get("/clientes/buscar")
def search_customers(
    q: str = Query(min_length=1, max_length=120),
    limit: int = Query(default=20, ge=1, le=50),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> list[dict[str, object]]:
    return CustomerService.search(
        session, principal=principal, query=q, limit=limit
    )


@router.post("/clientes", status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: PointOfSaleCustomerCreate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    customer = CustomerService.create_point_of_sale(
        session, principal=principal, **payload.model_dump()
    )
    return {"id_persona": customer.id_persona, "tipo_cliente": customer.tipo_cliente}


@router.get("/precios/{variant_id}")
def preview_price(
    variant_id: int,
    client_id: int = Query(gt=0),
    quantity: int = Query(gt=0, le=10000),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    AuthorizationService.require(session, principal, "PEDIDO_GESTIONAR")
    client = session.get(Cliente, client_id)
    if client is None or client.estado != "ACTIVO":
        from app.core.exceptions import NotFound

        raise NotFound("Cliente activo no encontrado")
    price = PricingService().price_line(
        session,
        client_type=client.tipo_cliente,
        commercial_condition=client.condicion_comercial,
        variant_id=variant_id,
        quantity=quantity,
    )
    return {
        "precio_unitario": price.unit_price,
        "descuento": price.discount,
        "total": price.total,
        "modo_precio": price.mode,
    }


@router.post("/pedidos", status_code=status.HTTP_201_CREATED)
def create_point_of_sale_order(
    payload: PointOfSaleOrderCreate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    order = OrderService().create(
        session,
        principal=principal,
        client_id=payload.client_id,
        channel="PRESENCIAL",
        delivery_mode=payload.delivery_mode,
        lines=[
            OrderLineInput(
                variant_id=line.variant_id,
                quantity=line.quantity,
                promotion_id=line.promotion_id,
                customization=line.customization,
            )
            for line in payload.lines
        ],
    )
    return {
        "id_pedido": order.id_pedido,
        "codigo_pedido": order.codigo_pedido,
        "total_pedido": order.total_pedido,
        "estado": order.estado,
    }


@router.post("/cotizaciones", status_code=status.HTTP_201_CREATED)
def create_point_of_sale_quote(
    payload: PointOfSaleQuoteCreate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    quote = QuotationService().create(
        session,
        principal=principal,
        client_id=payload.client_id,
        lines=[
            QuoteLineInput(
                variant_id=line.variant_id,
                quantity=line.quantity,
                customization=line.customization,
            )
            for line in payload.lines
        ],
        observations=payload.observations,
    )
    return {
        "id_cotizacion": quote.id_cotizacion,
        "id_cliente": quote.id_cliente,
        "total_ofrecido": quote.total_ofrecido,
        "estado": quote.estado,
    }
