from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import Conflict, NotFound, PermissionDenied
from app.core.security import Principal
from app.models.entities import AprobacionDiseno, DetallePedido, Pedido, VersionDiseno
from app.services.audit import AuditService
from app.services.authorization import AuthorizationService


class DesignService:
    def add_version(
        self,
        session: Session,
        *,
        order_id: int,
        line_number: int,
        file_name: str,
        private_path: str,
        principal: Principal,
        observations: str | None = None,
    ) -> VersionDiseno:
        order = session.get(Pedido, order_id)
        detail = session.get(DetallePedido, (order_id, line_number))
        if order is None or detail is None:
            raise NotFound("Pedido o línea no encontrada")
        if principal.is_employee:
            AuthorizationService.require(session, principal, "DISENO_APROBAR")
        elif order.id_cliente != principal.persona_id:
            raise PermissionDenied("El pedido pertenece a otro cliente")
        if private_path.startswith(("http://", "https://")):
            raise Conflict("El diseño debe usar una ruta privada, no una URL pública")
        last = session.scalar(
            select(func.coalesce(func.max(VersionDiseno.numero_version), 0)).where(
                VersionDiseno.id_pedido == order_id,
                VersionDiseno.numero_linea == line_number,
            )
        )
        version = VersionDiseno(
            id_pedido=order_id,
            numero_linea=line_number,
            numero_version=int(last or 0) + 1,
            nombre_archivo=file_name,
            ruta_archivo=private_path,
            fecha_creacion=datetime.now(UTC),
            observaciones=observations,
            es_aprobado=False,
        )
        session.add(version)
        session.flush()
        return version

    def decide(
        self,
        session: Session,
        *,
        order_id: int,
        line_number: int,
        version_number: int,
        approved: bool,
        principal: Principal,
        medium: str = "PORTAL",
    ) -> AprobacionDiseno:
        AuthorizationService.require(session, principal, "DISENO_APROBAR")
        version = session.get(VersionDiseno, (order_id, line_number, version_number))
        if version is None:
            raise NotFound("Versión de diseño no encontrada")
        version.es_aprobado = approved
        decision = AprobacionDiseno(
            id_pedido=order_id,
            numero_linea=line_number,
            numero_version=version_number,
            id_empleado_registro=principal.persona_id,
            fecha_aprobacion=datetime.now(UTC),
            medio_confirmacion=medium,
            observacion=None,
            tipo_decision="APROBADO" if approved else "RECHAZADO",
        )
        session.add(decision)
        AuditService.record(
            session,
            principal=principal,
            action="DECIDIR_DISENO",
            object_type="VERSION_DISENO",
            object_reference=f"{order_id}:{line_number}:{version_number}",
            reason="Decisión registrada sobre versión exacta",
            after={"tipo_decision": decision.tipo_decision},
        )
        session.flush()
        return decision

    @staticmethod
    def list_versions(
        session: Session, *, order_id: int, line_number: int, principal: Principal
    ) -> list[VersionDiseno]:
        order = session.get(Pedido, order_id)
        if order is None:
            raise NotFound("Pedido no encontrado")
        if principal.is_employee:
            AuthorizationService.require(session, principal, "DISENO_APROBAR")
        elif order.id_cliente != principal.persona_id:
            raise PermissionDenied("El pedido pertenece a otro cliente")
        return list(
            session.scalars(
                select(VersionDiseno)
                .where(
                    VersionDiseno.id_pedido == order_id,
                    VersionDiseno.numero_linea == line_number,
                )
                .order_by(VersionDiseno.numero_version)
            )
        )
