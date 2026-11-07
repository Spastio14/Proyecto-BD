from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.security import Principal, get_principal
from app.db.session import get_session
from app.schemas.api import OrderCreate, PaymentReport, QuoteCreate, QuoteDecision
from app.schemas.portal import (
    PortalCatalogItem,
    PortalOrder,
    PortalOrderDetail,
    PortalPayment,
    PortalPaymentReport,
    PortalPricePreview,
    PortalQuote,
    PortalSummary,
)
from app.services.orders import OrderLineInput, OrderService
from app.services.payments import PaymentService
from app.services.portal import PortalService
from app.services.quotations import QuotationService, QuoteLineInput

router = APIRouter(prefix="/portal", tags=["portal-cliente"])


@router.get("/resumen", response_model=PortalSummary)
def summary(principal: Principal = Depends(get_principal), session: Session = Depends(get_session)):
    return PortalService.summary(session, principal)


@router.get("/pedidos", response_model=list[PortalOrder])
def orders(principal: Principal = Depends(get_principal), session: Session = Depends(get_session)):
    return PortalService.list_orders(session, principal)


@router.post("/pedidos", response_model=PortalOrder, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderCreate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    PortalService._require_client(principal)
    order = OrderService().create(
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
    return PortalService._serialize_order(session, order=order, principal=principal)


@router.get("/pedidos/{code}", response_model=PortalOrderDetail)
def order_detail(
    code: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    return PortalService.order_detail(session, code=code, principal=principal)


@router.get("/cotizaciones", response_model=list[PortalQuote])
def quotes(principal: Principal = Depends(get_principal), session: Session = Depends(get_session)):
    return PortalService.list_quotes(session, principal)


@router.post("/cotizaciones", response_model=PortalQuote, status_code=status.HTTP_201_CREATED)
def create_quote(
    payload: QuoteCreate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    PortalService._require_client(principal)
    quote = QuotationService().create(
        session,
        principal=principal,
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
    return PortalService._serialize_quote(session, quote)


@router.post("/cotizaciones/{reference}/decision", response_model=PortalQuote)
def decide_quote(
    reference: str,
    payload: QuoteDecision,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    quote = PortalService.quote_by_reference(session, reference=reference, principal=principal)
    decided = QuotationService.decide(
        session,
        quote_id=quote.id_cotizacion,
        decision=payload.decision,
        principal=principal,
        reason=payload.reason,
    )
    return PortalService._serialize_quote(session, decided)


@router.post("/cotizaciones/{reference}/convertir", response_model=PortalOrder)
def convert_quote(
    reference: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    quote = PortalService.quote_by_reference(session, reference=reference, principal=principal)
    order = QuotationService().convert(session, quote_id=quote.id_cotizacion, principal=principal)
    return PortalService._serialize_order(session, order=order, principal=principal)


@router.get("/pagos", response_model=list[PortalPayment])
def payments(
    principal: Principal = Depends(get_principal), session: Session = Depends(get_session)
):
    return PortalService.list_payments(session, principal)


@router.post(
    "/pedidos/{code}/pagos",
    response_model=PortalPaymentReport,
    status_code=status.HTTP_201_CREATED,
)
def report_payment(
    code: str,
    payload: PaymentReport,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    order = PortalService._order_by_code(session, code=code, principal=principal)
    payment = PaymentService().report(
        session,
        order_id=order.id_pedido,
        milestone_number=payload.milestone_number,
        idempotency_key=payload.idempotency_key,
        method=payload.method,
        bank=payload.bank,
        reference=payload.reference,
        principal=principal,
    )
    return PortalPaymentReport(
        pedido=order.codigo_pedido,
        monto=payment.monto_con_signo,
        estado=payment.estado_verificacion,
    )


@router.get("/catalogo", response_model=list[PortalCatalogItem])
def catalog(principal: Principal = Depends(get_principal), session: Session = Depends(get_session)):
    return PortalService.catalog(session, principal)


@router.get("/catalogo/{variant_id}/precio", response_model=PortalPricePreview)
def price_preview(
    variant_id: int,
    cantidad: int = Query(ge=1, le=10000),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    return PortalService.price_preview(
        session,
        variant_id=variant_id,
        quantity=cantidad,
        principal=principal,
    )
