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
                "puede_iniciar": order.estado == "EN_DISENO" and all_designs_approved,
                "puede_completar": order.estado == "EN_PRODUCCION" and reservations_consumed,
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
