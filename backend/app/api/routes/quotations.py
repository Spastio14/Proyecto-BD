from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.security import Principal, get_principal
from app.db.session import get_session
from app.schemas.api import OrderRead, QuoteCreate, QuoteDecision, QuoteRead
from app.services.quotations import QuotationService, QuoteLineInput

router = APIRouter(prefix="/cotizaciones", tags=["cotizaciones"])


@router.post("", response_model=QuoteRead, status_code=status.HTTP_201_CREATED)
def create_quote(
    payload: QuoteCreate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    return QuotationService().create(
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


@router.get("", response_model=list[QuoteRead])
def list_quotes(
    principal: Principal = Depends(get_principal), session: Session = Depends(get_session)
):
    return QuotationService.list_owned(session, principal)


@router.post("/{quote_id}/decision", response_model=QuoteRead)
def decide_quote(
    quote_id: int,
    payload: QuoteDecision,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    return QuotationService.decide(
        session,
        quote_id=quote_id,
        decision=payload.decision,
        principal=principal,
        reason=payload.reason,
    )


@router.post("/{quote_id}/convertir", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
def convert_quote(
    quote_id: int,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    return QuotationService().convert(session, quote_id=quote_id, principal=principal)
