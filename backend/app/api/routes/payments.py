from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.security import Principal, get_principal
from app.db.session import get_session
from app.schemas.api import PaymentRead, PaymentReport
from app.services.payments import PaymentService

router = APIRouter(prefix="/pagos", tags=["pagos"])


@router.post(
    "/pedidos/{order_id}/reportar", response_model=PaymentRead, status_code=status.HTTP_201_CREATED
)
def report_payment(
    order_id: int,
    payload: PaymentReport,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    return PaymentService().report(
        session,
        order_id=order_id,
        milestone_number=payload.milestone_number,
        idempotency_key=payload.idempotency_key,
        method=payload.method,
        bank=payload.bank,
        reference=payload.reference,
        principal=principal,
    )


@router.post("/{payment_id}/confirmar", response_model=PaymentRead)
def confirm_payment(
    payment_id: int,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    return PaymentService().confirm(session, payment_id=payment_id, principal=principal)
