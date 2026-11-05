from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import Principal, get_principal
from app.db.session import get_session
from app.services.customers import CustomerService

router = APIRouter(prefix="/clientes", tags=["clientes"])


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
