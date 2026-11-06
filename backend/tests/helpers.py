from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.security import Principal
from app.models.entities import Cliente, Pedido, Persona
from app.services.orders import OrderLineInput, OrderService


def add_client(
    session: Session,
    *,
    client_type: str = "REGISTRADO",
    commercial_condition: str = "DETALLE",
) -> Principal:
    person = Persona(
        nombres="Cliente",
        apellidos="Prueba",
        telefono_contacto=None,
        correo_electronico=f"{uuid4().hex}@example.test",
        documento_identificacion=None,
    )
    session.add(person)
    session.flush()
    session.add(
        Cliente(
            id_persona=person.id_persona,
            tipo_cliente=client_type,
            condicion_comercial=commercial_condition,
            fecha_registro=datetime.now(UTC),
            origen_registro="TEST",
            estado="ACTIVO",
        )
    )
    session.flush()
    return Principal(persona_id=person.id_persona, origin="CLIENTE")


def create_order(
    session: Session,
    principal: Principal,
    *,
    quantity: int = 1,
    promotion_id: int | None = None,
) -> Pedido:
    return OrderService().create(
        session,
        principal=principal,
        lines=[OrderLineInput(variant_id=1, quantity=quantity, promotion_id=promotion_id)],
    )
