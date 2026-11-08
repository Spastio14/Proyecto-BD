from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import Conflict, NotFound, PermissionDenied
from app.core.security import Principal
from app.models.entities import (
    AprobacionDiseno,
    DetallePedido,
    Pedido,
    Producto,
    VarianteProducto,
    VersionDiseno,
)
from app.repositories.locks import lock_order
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
        order = lock_order(session, order_id)
        detail = session.get(DetallePedido, (order_id, line_number))
        if detail is None:
            raise NotFound("Pedido o línea no encontrada")
        if not principal.is_employee:
            raise PermissionDenied("Sólo el personal autorizado puede cargar diseños")
        AuthorizationService.require(session, principal, "DISENO_APROBAR")
        if order.estado != "EN_DISENO":
            raise Conflict("El pedido no está en una etapa que admita nuevos diseños")
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
        observations: str | None = None,
        reference: str | None = None,
        evidence: str | None = None,
    ) -> AprobacionDiseno:
        order = lock_order(session, order_id)
        version = session.get(VersionDiseno, (order_id, line_number, version_number))
        if version is None:
            raise NotFound("Versión de diseño no encontrada")
        latest = session.scalar(
            select(func.max(VersionDiseno.numero_version)).where(
                VersionDiseno.id_pedido == order_id,
                VersionDiseno.numero_linea == line_number,
            )
        )
        if latest != version_number:
            raise Conflict("La decisión sólo puede aplicarse a la versión vigente")
        if order.estado != "EN_DISENO":
            raise Conflict("El pedido no está esperando una decisión de diseño")
        if principal.is_employee:
            AuthorizationService.require(session, principal, "EMPLEADO_GESTIONAR")
            if medium == "PORTAL":
                raise Conflict("Un empleado debe registrar el medio de aprobación externa")
            if not reference or not evidence:
                raise Conflict("La aprobación externa requiere referencia y evidencia")
        else:
            if order.id_cliente != principal.persona_id:
                raise PermissionDenied("El diseño pertenece a otro cliente")
            if medium != "PORTAL":
                raise PermissionDenied("El cliente sólo puede decidir desde su sesión verificada")
        for item in session.scalars(
            select(VersionDiseno).where(
                VersionDiseno.id_pedido == order_id,
                VersionDiseno.numero_linea == line_number,
            )
        ):
            item.es_aprobado = False
        version.es_aprobado = approved
        note_parts = [observations.strip() if observations else None]
        if principal.is_employee:
            note_parts.extend(
                [
                    f"Referencia: {reference.strip()}",
                    f"Evidencia: {evidence.strip()}",
                ]
            )
        combined_note = " · ".join(part for part in note_parts if part) or None
        if combined_note and len(combined_note) > 500:
            raise Conflict("Las observaciones y evidencias no pueden superar 500 caracteres")
        decision = AprobacionDiseno(
            id_pedido=order_id,
            numero_linea=line_number,
            numero_version=version_number,
            id_empleado_registro=principal.persona_id if principal.is_employee else None,
            fecha_aprobacion=datetime.now(UTC),
            medio_confirmacion=medium,
            observacion=combined_note,
            tipo_decision="APROBADO" if approved else "RECHAZADO",
        )
        session.add(decision)
        AuditService.record(
            session,
            principal=principal,
            action="DECIDIR_DISENO",
            object_type="VERSION_DISENO",
            object_reference=f"{order_id}:{line_number}:{version_number}",
            reason=(
                "Decisión del cliente"
                if not principal.is_employee
                else "Aprobación externa autorizada"
            ),
            after={
                "tipo_decision": decision.tipo_decision,
                "medio": medium,
                "version": version_number,
            },
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

    @classmethod
    def order_lines(
        cls, session: Session, *, order_id: int, principal: Principal
    ) -> list[dict[str, object]]:
        order = session.get(Pedido, order_id)
        if order is None:
            raise NotFound("Pedido no encontrado")
        if principal.is_employee:
            AuthorizationService.require(session, principal, "DISENO_APROBAR")
        elif order.id_cliente != principal.persona_id:
            raise PermissionDenied("El pedido pertenece a otro cliente")
        details = session.execute(
            select(DetallePedido, VarianteProducto, Producto)
            .join(
                VarianteProducto,
                VarianteProducto.id_variante == DetallePedido.id_variante,
            )
            .join(Producto, Producto.id_producto == VarianteProducto.id_producto)
            .where(DetallePedido.id_pedido == order_id)
            .order_by(DetallePedido.numero_linea)
        ).all()
        result = []
        for detail, variant, product in details:
            versions = cls.list_versions(
                session,
                order_id=order_id,
                line_number=detail.numero_linea,
                principal=principal,
            )
            serialized = []
            for version in versions:
                decision = session.scalar(
                    select(AprobacionDiseno)
                    .where(
                        AprobacionDiseno.id_pedido == order_id,
                        AprobacionDiseno.numero_linea == detail.numero_linea,
                        AprobacionDiseno.numero_version == version.numero_version,
                    )
                    .order_by(AprobacionDiseno.fecha_aprobacion.desc())
                    .limit(1)
                )
                serialized.append(
                    {
                        "numero_version": version.numero_version,
                        "nombre_archivo": version.nombre_archivo,
                        "fecha_creacion": version.fecha_creacion,
                        "observaciones": version.observaciones,
                        "estado": (
                            decision.tipo_decision
                            if decision is not None
                            else ("APROBADO" if version.es_aprobado else "PENDIENTE")
                        ),
                        "es_vigente": version == versions[-1],
                    }
                )
            result.append(
                {
                    "numero_linea": detail.numero_linea,
                    "producto": product.nombre,
                    "variante": variant.caracteristicas or variant.codigo_variante,
                    "requiere_produccion": variant.requiere_produccion,
                    "estado": serialized[-1]["estado"] if serialized else "SIN_DISENO",
                    "versiones": serialized,
                }
            )
        return result
