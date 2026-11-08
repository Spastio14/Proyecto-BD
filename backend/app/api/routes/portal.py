from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.security import Principal, get_principal
from app.db.session import get_session
from app.schemas.api import DesignDecision, OrderCreate, PaymentReport, QuoteCreate, QuoteDecision
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
from app.services.designs import DesignService
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
                customization=line.customization,
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


@router.get("/pedidos/{code}/disenos")
def order_designs(
    code: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> list[dict[str, object]]:
    order = PortalService._order_by_code(session, code=code, principal=principal)
    return DesignService.order_lines(
        session, order_id=order.id_pedido, principal=principal
    )


@router.get(
    "/pedidos/{code}/disenos/{line_number}/versiones/{version_number}/archivo"
)
def order_design_file(
    code: str,
    line_number: int,
    version_number: int,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    order = PortalService._order_by_code(session, code=code, principal=principal)
    coordinator = getattr(request.app.state, "storage_coordinator", None)
    if coordinator is None:
        from app.api.routes.designs import StorageRouteUnavailable

        raise StorageRouteUnavailable("Supabase Storage no está configurado")
    url = coordinator.design_url(
        session,
        order_id=order.id_pedido,
        line_number=line_number,
        version_number=version_number,
        principal=principal,
    )
    return {"signed_url": url, "expires_in": request.app.state.settings.storage_signed_url_ttl}


@router.post(
    "/pedidos/{code}/disenos/{line_number}/versiones/{version_number}/decision"
)
def decide_order_design(
    code: str,
    line_number: int,
    version_number: int,
    payload: DesignDecision,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    order = PortalService._order_by_code(session, code=code, principal=principal)
    decision = DesignService().decide(
        session,
        order_id=order.id_pedido,
        line_number=line_number,
        version_number=version_number,
        approved=payload.approved,
        medium="PORTAL",
        observations=payload.observations,
        principal=principal,
    )
    return {"estado": decision.tipo_decision}


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
def catalog(
    request: Request,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    return PortalService.catalog(
        session,
        principal,
        public_storage_url=request.app.state.settings.supabase_url,
    )


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
