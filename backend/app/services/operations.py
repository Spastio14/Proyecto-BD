from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import Principal
from app.models.entities import (
    DetallePedido,
    Envio,
    ReservaInventario,
    VarianteProducto,
    VersionDiseno,
)
from app.services.authorization import AuthorizationService
from app.services.orders import OrderService
from app.services.payments import PaymentService


class OrderOperationService:
    @classmethod
    def summary(cls, session: Session, *, order_id: int, principal: Principal) -> dict[str, object]:
        order = OrderService.get_owned(session, order_id=order_id, principal=principal)
        payment = PaymentService.summary(session, order_id=order_id, principal=principal)
        production_lines = session.execute(
            select(DetallePedido.numero_linea, VarianteProducto.requiere_produccion)
            .join(
                VarianteProducto,
                VarianteProducto.id_variante == DetallePedido.id_variante,
            )
            .where(DetallePedido.id_pedido == order_id)
            .order_by(DetallePedido.numero_linea)
        ).all()
        designs = []
        for line_number, requires_production in production_lines:
            latest = session.scalar(
                select(func.max(VersionDiseno.numero_version)).where(
                    VersionDiseno.id_pedido == order_id,
                    VersionDiseno.numero_linea == line_number,
                )
            )
            version = (
                session.get(VersionDiseno, (order_id, line_number, latest))
                if latest is not None
                else None
            )
            designs.append(
                {
                    "numero_linea": line_number,
                    "requiere_produccion": requires_production,
                    "version_vigente": latest,
                    "aprobada": bool(version and version.es_aprobado),
                }
            )
        reservations = list(
            session.scalars(
                select(ReservaInventario)
                .where(ReservaInventario.id_pedido == order_id)
                .order_by(ReservaInventario.id_articulo)
            )
        )
        delivery = session.scalar(select(Envio).where(Envio.id_pedido == order_id))
        all_designs_approved = all(
            not row["requiere_produccion"] or row["aprobada"] for row in designs
        )
        requires_materials = any(row["requiere_produccion"] for row in designs)
        reservations_consumed = (not requires_materials) or (
            bool(reservations)
            and all(
                item.estado == "AGOTADA" and item.cantidad_pendiente == 0 for item in reservations
            )
        )
        active_reservations = any(
            item.estado == "ACTIVA" and item.cantidad_pendiente > 0 for item in reservations
        )
        production_actions, production_message = cls._production_actions(
            session,
            principal=principal,
            state=order.estado,
            designs_approved=all_designs_approved,
            active_reservations=active_reservations,
            reservations_consumed=reservations_consumed,
        )
        return {
            "pedido": {
                "id_pedido": order.id_pedido,
                "codigo_pedido": order.codigo_pedido,
                "estado": order.estado,
                "modalidad_entrega": order.modalidad_entrega,
                "fecha_entrega_prevista": order.fecha_entrega_prevista,
            },
            "pago": payment,
            "disenos": designs,
            "inventario": {
                "reservas": [
                    {
                        "id_articulo": item.id_articulo,
                        "cantidad_reservada": item.cantidad_reservada,
                        "cantidad_pendiente": item.cantidad_pendiente,
                        "estado": item.estado,
                    }
                    for item in reservations
                ],
                "consumido": reservations_consumed,
            },
            "produccion": {
                "puede_iniciar": "INICIAR_PRODUCCION" in production_actions,
                "puede_consumir": "CONSUMIR_RESERVAS" in production_actions,
                "puede_completar": "COMPLETAR_PRODUCCION" in production_actions,
                "acciones_permitidas": production_actions,
                "mensaje": production_message,
            },
            "entrega": {
                "id_envio": delivery.id_envio if delivery else None,
                "estado": delivery.estado if delivery else None,
                "puede_completar": order.estado == "LISTO" and payment["completamente_pagado"],
            },
            "siguiente_accion": cls._next_action(
                order.estado,
                payment["completamente_pagado"],
                all_designs_approved,
                reservations_consumed,
            ),
        }

    @staticmethod
    def _production_actions(
        session: Session,
        *,
        principal: Principal,
        state: str,
        designs_approved: bool,
        active_reservations: bool,
        reservations_consumed: bool,
    ) -> tuple[list[str], str]:
        if state == "EN_DISENO":
            if not designs_approved:
                return [], "Faltan diseños vigentes aprobados"
            if not AuthorizationService.has_permission(session, principal, "PRODUCCION_INICIAR"):
                return [], "No tiene permiso para iniciar producción"
            return ["INICIAR_PRODUCCION"], "El pedido está listo para iniciar producción"
        if state == "EN_PRODUCCION" and active_reservations:
            if not AuthorizationService.has_permission(
                session, principal, "INVENTARIO_CONSUMIR_RESERVAS"
            ):
                return [], "No tiene permiso para consumir reservas de producción"
            return ["CONSUMIR_RESERVAS"], "Las reservas activas están listas para consumirse"
        if state == "EN_PRODUCCION" and reservations_consumed:
            if not AuthorizationService.has_permission(session, principal, "PRODUCCION_INICIAR"):
                return [], "No tiene permiso para completar producción"
            return ["COMPLETAR_PRODUCCION"], "Los materiales fueron consumidos; puede completar"
        if state == "EN_PRODUCCION":
            return [], "No existen reservas activas válidas para continuar"
        if state == "LISTO":
            return [], "La producción ya fue completada"
        if state in {"CANCELADO", "EXPIRADO", "ENTREGADO"}:
            return [], "El estado final del pedido no admite operaciones de producción"
        return [], "El pedido todavía no está en una etapa operativa de producción"

    @staticmethod
    def _next_action(
        state: str,
        fully_paid: bool,
        designs_approved: bool,
        reservations_consumed: bool,
    ) -> str:
        if state == "PENDIENTE_PAGO":
            return "REPORTAR_ANTICIPO"
        if state == "PAGADO_PARCIAL":
            return "INICIAR_DISENO"
        if state == "PAGADO":
            return "INICIAR_DISENO"
        if state == "EN_DISENO":
            return "INICIAR_PRODUCCION" if designs_approved else "APROBAR_DISENOS"
        if state == "EN_PRODUCCION":
            return "COMPLETAR_PRODUCCION" if reservations_consumed else "CONSUMIR_RESERVAS"
        if state == "LISTO":
            return "COMPLETAR_ENTREGA" if fully_paid else "REPORTAR_SALDO"
        return "SIN_ACCION"
