from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.security import Principal, get_principal
from app.db.session import get_session
from app.schemas.api import ProviderCreate, PurchaseCreate, PurchaseLineAdd
from app.services.purchases import PurchaseService

router = APIRouter(prefix="/compras", tags=["compras"])


@router.get("/proveedores")
def list_providers(
    principal: Principal = Depends(get_principal), session: Session = Depends(get_session)
) -> list[dict]:
    return [
        {
            "id_proveedor": item.id_proveedor,
            "nombre": item.nombre,
            "telefono": item.telefono,
            "correo": item.correo,
            "direccion": item.direccion,
            "estado": item.estado,
        }
        for item in PurchaseService.list_providers(session, principal)
    ]


@router.post("/proveedores", status_code=status.HTTP_201_CREATED)
def create_provider(
    payload: ProviderCreate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    item = PurchaseService.create_provider(
        session,
        principal=principal,
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        address=payload.address,
    )
    return {"id_proveedor": item.id_proveedor, "nombre": item.nombre, "estado": item.estado}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_purchase(
    payload: PurchaseCreate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    item = PurchaseService().create(
        session,
        principal=principal,
        provider_id=payload.provider_id,
        document_number=payload.document_number,
        lines=[(line.article_id, line.quantity, line.unit_cost) for line in payload.lines],
    )
    return {
        "id_compra": item.id_compra,
        "id_proveedor": item.id_proveedor,
        "estado": item.estado,
        "total_compra": item.total_compra,
    }


@router.post("/{purchase_id}/detalles", status_code=status.HTTP_201_CREATED)
def add_purchase_line(
    purchase_id: int,
    payload: PurchaseLineAdd,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    detail = PurchaseService().add_line(
        session,
        purchase_id=purchase_id,
        article_id=payload.article_id,
        quantity=payload.quantity,
        unit_cost=payload.unit_cost,
        principal=principal,
    )
    return {
        "id_compra": detail.id_compra,
        "numero_linea": detail.numero_linea,
        "importe": detail.importe,
    }


@router.post("/{purchase_id}/confirmar")
def confirm_purchase(
    purchase_id: int,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    item = PurchaseService().confirm(session, purchase_id=purchase_id, principal=principal)
    return {"id_compra": item.id_compra, "estado": item.estado, "total_compra": item.total_compra}


@router.get("")
def list_purchases(
    provider_id: int | None = None,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> list[dict]:
    return [
        {
            "id_compra": item.id_compra,
            "id_proveedor": item.id_proveedor,
            "fecha_compra": item.fecha_compra,
            "numero_documento": item.numero_documento,
            "estado": item.estado,
            "total_compra": item.total_compra,
        }
        for item in PurchaseService.list_purchases(
            session, principal=principal, provider_id=provider_id
        )
    ]


@router.get("/{purchase_id}/detalles")
def purchase_details(
    purchase_id: int,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> list[dict]:
    return [
        {
            "numero_linea": item.numero_linea,
            "id_articulo": item.id_articulo,
            "cantidad_comprada": item.cantidad_comprada,
            "costo_unitario_compra": item.costo_unitario_compra,
            "importe": item.importe,
        }
        for item in PurchaseService.details(
            session, purchase_id=purchase_id, principal=principal
        )
    ]
