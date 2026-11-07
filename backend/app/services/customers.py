from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import Conflict, NotFound
from app.core.security import Principal
from app.models.entities import Cliente, Pedido, Persona, RegistroAuditoria
from app.services.audit import AuditService
from app.services.authorization import AuthorizationService


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

    @staticmethod
    def list_for_employee(
        session: Session, principal: Principal
    ) -> list[dict[str, object]]:
        AuthorizationService.require(session, principal, "CLIENTE_CONSULTAR")
        rows = session.execute(
            select(Cliente, Persona)
            .join(Persona, Persona.id_persona == Cliente.id_persona)
            .order_by(Persona.nombres, Persona.apellidos)
        ).all()
        return [
            {
                "id_persona": customer.id_persona,
                "nombre": " ".join(
                    value for value in (person.nombres, person.apellidos) if value
                ),
            }
            for customer, person in rows
        ]

    @staticmethod
    def detail(session: Session, *, client_id: int, principal: Principal) -> dict[str, object]:
        AuthorizationService.require(session, principal, "CLIENTE_CONSULTAR")
        row = session.execute(
            select(Cliente, Persona)
            .join(Persona, Persona.id_persona == Cliente.id_persona)
            .where(Cliente.id_persona == client_id)
        ).one_or_none()
        if row is None:
            raise NotFound("Cliente no encontrado")
        customer, person = row
        orders = session.execute(
            select(Pedido.id_pedido, Pedido.codigo_pedido, Pedido.fecha_creacion, Pedido.estado,
                   Pedido.total_pedido)
            .where(Pedido.id_cliente == client_id)
            .order_by(Pedido.fecha_creacion.desc())
        ).all()
        events = list(
            session.scalars(
                select(RegistroAuditoria)
                .where(
                    RegistroAuditoria.referencia_objeto == str(client_id),
                    RegistroAuditoria.tipo_objeto_afectado.in_({"CLIENTE", "PERSONA"}),
                )
                .order_by(RegistroAuditoria.fecha_hora.desc())
            )
        )
        return {
            "id_persona": client_id,
            "nombres": person.nombres,
            "apellidos": person.apellidos,
            "nombre": " ".join(
                value for value in (person.nombres, person.apellidos) if value
            ),
            "correo": person.correo_electronico,
            "telefono": person.telefono_contacto,
            "documento": person.documento_identificacion,
            "direccion_habitual": person.direccion_habitual,
            "tipo_cliente": customer.tipo_cliente,
            "condicion_comercial": customer.condicion_comercial,
            "fecha_registro": customer.fecha_registro,
            "origen_registro": customer.origen_registro,
            "estado": customer.estado,
            "cantidad_pedidos": session.scalar(
                select(func.count()).select_from(Pedido).where(Pedido.id_cliente == client_id)
            ) or 0,
            "pedidos": [
                {
                    "id_pedido": item.id_pedido,
                    "codigo": item.codigo_pedido,
                    "fecha": item.fecha_creacion,
                    "estado": item.estado,
                    "total": item.total_pedido,
                }
                for item in orders
            ],
            "historial": [
                {
                    "fecha": event.fecha_hora,
                    "accion": event.accion,
                    "motivo": event.motivo,
                    "valor_anterior": event.valor_anterior,
                    "valor_nuevo": event.valor_nuevo,
                }
                for event in events
            ],
        }

    @staticmethod
    def update_admin(
        session: Session,
        *,
        client_id: int,
        changes: dict[str, object],
        principal: Principal,
    ) -> Persona:
        AuthorizationService.require(session, principal, "EMPLEADO_GESTIONAR")
        customer = session.scalar(
            select(Cliente).where(Cliente.id_persona == client_id).with_for_update()
        )
        if customer is None:
            raise NotFound("Cliente no encontrado")
        person = session.scalar(
            select(Persona).where(Persona.id_persona == client_id).with_for_update()
        )
        before = CustomerService._person_snapshot(person)
        CustomerService._apply_person_changes(person, changes)
        AuditService.record(
            session,
            principal=principal,
            action="ACTUALIZAR_CLIENTE",
            object_type="PERSONA",
            object_reference=str(client_id),
            reason="Actualización administrativa de datos autorizados",
            before=before,
            after=CustomerService._person_snapshot(person),
        )
        return person

    @staticmethod
    def set_wholesale(
        session: Session,
        *,
        client_id: int,
        enabled: bool,
        reason: str,
        principal: Principal,
    ) -> Cliente:
        AuthorizationService.require(session, principal, "EMPLEADO_GESTIONAR")
        customer = session.scalar(
            select(Cliente).where(Cliente.id_persona == client_id).with_for_update()
        )
        if customer is None:
            raise NotFound("Cliente no encontrado")
        if customer.tipo_cliente == "INVITADO":
            raise Conflict("Un cliente invitado no puede recibir condición mayorista")
        if customer.tipo_cliente not in {"REGISTRADO", "EMPRESA"}:
            raise Conflict("El tipo de cliente no admite condición mayorista")
        target = "MAYORISTA" if enabled else "DETALLE"
        if customer.condicion_comercial == target:
            return customer
        before = customer.condicion_comercial
        customer.condicion_comercial = target
        AuditService.record(
            session,
            principal=principal,
            action="AUTORIZAR_MAYORISTA" if enabled else "REVOCAR_MAYORISTA",
            object_type="CLIENTE",
            object_reference=str(client_id),
            reason=reason.strip(),
            before={"condicion_comercial": before},
            after={"condicion_comercial": target},
        )
        return customer

    @staticmethod
    def _apply_person_changes(person: Persona, changes: dict[str, object]) -> None:
        mapping = {
            "names": "nombres",
            "surnames": "apellidos",
            "phone": "telefono_contacto",
            "document": "documento_identificacion",
            "usual_address": "direccion_habitual",
        }
        for source, target in mapping.items():
            if source in changes:
                value = changes[source]
                setattr(person, target, value.strip() if isinstance(value, str) else value)

    @staticmethod
    def _person_snapshot(person: Persona) -> dict[str, object]:
        return {
            "nombres": person.nombres,
            "apellidos": person.apellidos,
            "telefono": person.telefono_contacto,
            "documento": person.documento_identificacion,
            "direccion_habitual": person.direccion_habitual,
        }
