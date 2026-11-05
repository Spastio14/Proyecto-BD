from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import Conflict, NotFound
from app.models.entities import Cliente, Persona


class CustomerService:
    VALID_TYPES = frozenset({"INVITADO", "REGISTRADO", "EMPRESA"})

    def create(
        self,
        session: Session,
        *,
        names: str,
        surnames: str | None,
        client_type: str,
        email: str | None = None,
        phone: str | None = None,
        origin: str = "BACKEND",
    ) -> Cliente:
        if client_type not in self.VALID_TYPES:
            raise Conflict("Tipo de cliente inválido")
        person = Persona(
            nombres=names.strip(),
            apellidos=surnames,
            telefono_contacto=phone,
            correo_electronico=email,
            documento_identificacion=None,
        )
        session.add(person)
        session.flush()
        client = Cliente(
            id_persona=person.id_persona,
            tipo_cliente=client_type,
            condicion_comercial="DETALLE",
            fecha_registro=datetime.now(UTC),
            origen_registro=origin,
            estado="ACTIVO",
        )
        session.add(client)
        session.flush()
        return client

    @staticmethod
    def get(session: Session, client_id: int) -> Cliente:
        client = session.scalar(select(Cliente).where(Cliente.id_persona == client_id))
        if client is None:
            raise NotFound("Cliente no encontrado")
        return client
