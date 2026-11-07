from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import Principal, get_principal
from app.db.session import get_session
from app.schemas.api import CustomerAdminUpdate, WholesaleConditionUpdate
from app.services.customers import CustomerService

router = APIRouter(prefix="/clientes", tags=["clientes"])


@router.get("")
def list_customers(
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> list[dict[str, object]]:
    return CustomerService.list_for_employee(session, principal)


@router.get("/me")
def me(
    principal: Principal = Depends(get_principal), session: Session = Depends(get_session)
) -> dict:
    customer = CustomerService.get(session, principal.persona_id)
    return {
        "id_persona": customer.id_persona,
        "tipo_cliente": customer.tipo_cliente,
        "estado": customer.estado,
    }


@router.get("/{client_id}")
def customer_detail(
    client_id: int,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    return CustomerService.detail(session, client_id=client_id, principal=principal)


@router.patch("/{client_id}")
def update_customer(
    client_id: int,
    payload: CustomerAdminUpdate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    person = CustomerService.update_admin(
        session,
        client_id=client_id,
        changes=payload.model_dump(exclude_unset=True),
        principal=principal,
    )
    return {"id_persona": person.id_persona, "actualizado": True}


@router.post("/{client_id}/condicion-mayorista")
def update_wholesale_condition(
    client_id: int,
    payload: WholesaleConditionUpdate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    customer = CustomerService.set_wholesale(
        session,
        client_id=client_id,
        enabled=payload.enabled,
        reason=payload.reason,
        principal=principal,
    )
    return {
        "id_persona": customer.id_persona,
        "condicion_comercial": customer.condicion_comercial,
    }
