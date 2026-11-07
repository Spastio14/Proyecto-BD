from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.routes.designs import StorageRouteUnavailable
from app.core.security import Principal, get_principal
from app.db.session import get_session
from app.models.entities import Pedido
from app.schemas.api import PaymentListRead, PaymentRead, PaymentReject, PaymentReport
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


@router.post("/{payment_id}/rechazar", response_model=PaymentRead)
def reject_payment(
    payment_id: int,
    payload: PaymentReject,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    return PaymentService().reject(
        session,
        payment_id=payment_id,
        principal=principal,
        reason=payload.reason,
    )


@router.get("", response_model=list[PaymentListRead])
def list_payments(
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    payments = PaymentService.list_all(session, principal)
    order_codes = (
        dict(
            session.query(Pedido.id_pedido, Pedido.codigo_pedido)
            .filter(Pedido.id_pedido.in_({item.id_pedido for item in payments}))
            .all()
        )
        if payments
        else {}
    )
    return [
        PaymentListRead(
            **PaymentRead.model_validate(item).model_dump(),
            codigo_pedido=order_codes[item.id_pedido],
        )
        for item in payments
    ]


@router.get("/pedidos/{order_id}", response_model=list[PaymentRead])
def list_order_payments(
    order_id: int,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    return PaymentService.list_for_order(session, order_id=order_id, principal=principal)


@router.get("/pedidos/{order_id}/resumen")
def order_payment_summary(
    order_id: int,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    return PaymentService.summary(session, order_id=order_id, principal=principal)


@router.get("/{payment_id}", response_model=PaymentRead)
def get_payment(
    payment_id: int,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    return PaymentService.get_owned(session, payment_id=payment_id, principal=principal)


@router.post("/{payment_id}/comprobante", status_code=status.HTTP_201_CREATED)
async def upload_receipt(
    payment_id: int,
    request: Request,
    file: UploadFile = File(),
    principal: Principal = Depends(get_principal),
) -> dict:
    coordinator = getattr(request.app.state, "storage_coordinator", None)
    if coordinator is None:
        raise StorageRouteUnavailable("Supabase Storage no está configurado")
    maximum = request.app.state.settings.storage_receipt_max_bytes
    content = await file.read(maximum + 1)
    coordinator.upload_receipt(
        payment_id=payment_id,
        file_name=file.filename or "archivo",
        content_type=file.content_type or "application/octet-stream",
        content=content,
        principal=principal,
    )
    return {"id_transaccion": payment_id, "comprobante": "ALMACENADO"}


@router.get("/{payment_id}/comprobante")
def signed_receipt_url(
    payment_id: int,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    coordinator = getattr(request.app.state, "storage_coordinator", None)
    if coordinator is None:
        raise StorageRouteUnavailable("Supabase Storage no está configurado")
    url = coordinator.receipt_url(session, payment_id=payment_id, principal=principal)
    return {"signed_url": url, "expires_in": request.app.state.settings.storage_signed_url_ttl}
