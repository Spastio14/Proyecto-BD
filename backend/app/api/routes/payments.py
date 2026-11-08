from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.routes.designs import StorageRouteUnavailable
from app.core.security import Principal, get_principal
from app.db.session import get_session
from app.models.entities import (
    AplicacionTransaccionHito,
    Caja,
    HitoPago,
    MovimientoCaja,
    Pedido,
)
from app.schemas.api import (
    CashPaymentCreate,
    CashRegisterClose,
    CashRegisterOpen,
    PaymentListRead,
    PaymentRead,
    PaymentReject,
    PaymentReport,
)
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
        amount=payload.amount,
        payment_scope=payload.payment_scope,
        method=payload.method,
        bank=payload.bank,
        bank_origin=payload.bank_origin,
        bank_receiver=payload.bank_receiver,
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
    payment_ids = {item.id_transaccion for item in payments}
    allocation_rows = (
        session.query(
            AplicacionTransaccionHito.id_transaccion,
            HitoPago.tipo_hito,
        )
        .join(
            HitoPago,
            (HitoPago.id_pedido == AplicacionTransaccionHito.id_pedido)
            & (HitoPago.numero_hito == AplicacionTransaccionHito.numero_hito),
        )
        .filter(AplicacionTransaccionHito.id_transaccion.in_(payment_ids))
        .all()
        if payment_ids
        else []
    )
    allocation_types: dict[int, list[str]] = {}
    for payment_id, milestone_type in allocation_rows:
        allocation_types.setdefault(payment_id, []).append(milestone_type)
    receipt_folios = (
        dict(
            session.query(MovimientoCaja.id_transaccion, MovimientoCaja.folio_recibo)
            .filter(MovimientoCaja.id_transaccion.in_(payment_ids))
            .all()
        )
        if payment_ids
        else {}
    )
    return [
        PaymentListRead(
            **PaymentRead.model_validate(item).model_dump(),
            codigo_pedido=order_codes[item.id_pedido],
            tipo_abono=(
                " + ".join(allocation_types.get(item.id_transaccion, []))
                or "SIN_DISTRIBUCION"
            ),
            folio_caja=receipt_folios.get(item.id_transaccion),
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


@router.post("/cajas/abrir", status_code=status.HTTP_201_CREATED)
def open_cash_register(
    payload: CashRegisterOpen,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    register = PaymentService().open_cash_register(
        session, opening_amount=payload.opening_amount, principal=principal
    )
    return {
        "id_caja": register.id_caja,
        "estado": register.estado,
        "saldo_inicial": register.saldo_inicial,
        "fecha_apertura": register.fecha_apertura,
    }


@router.get("/cajas/abierta")
def current_cash_register(
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict[str, object] | None:
    from app.services.authorization import AuthorizationService

    AuthorizationService.require(session, principal, "PAGO_VERIFICAR")
    register = session.query(Caja).filter(Caja.estado == "ABIERTA").one_or_none()
    if register is None:
        return None
    return {
        "id_caja": register.id_caja,
        "estado": register.estado,
        "saldo_inicial": register.saldo_inicial,
        "fecha_apertura": register.fecha_apertura,
    }


@router.post("/cajas/{cash_register_id}/cerrar")
def close_cash_register(
    cash_register_id: int,
    payload: CashRegisterClose,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    register = PaymentService().close_cash_register(
        session,
        cash_register_id=cash_register_id,
        closing_amount=payload.closing_amount,
        principal=principal,
    )
    return {"id_caja": register.id_caja, "estado": register.estado}


@router.post("/pedidos/{order_id}/efectivo", status_code=status.HTTP_201_CREATED)
def register_cash_payment(
    order_id: int,
    payload: CashPaymentCreate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    movement = PaymentService().register_cash_payment(
        session,
        order_id=order_id,
        cash_register_id=payload.cash_register_id,
        amount=payload.amount,
        payment_scope=payload.payment_scope,
        idempotency_key=payload.idempotency_key,
        principal=principal,
    )
    return {
        "id_movimiento_caja": movement.id_movimiento_caja,
        "id_transaccion": movement.id_transaccion,
        "folio_recibo": movement.folio_recibo,
        "monto": movement.monto,
    }


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
