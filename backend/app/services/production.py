from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import Conflict
from app.core.security import Principal
from app.models.entities import (
    ComposicionProducto,
    DetallePedido,
    HitoPago,
    ReservaInventario,
    VarianteProducto,
    VersionDiseno,
)
from app.repositories.locks import lock_order
from app.services.authorization import AuthorizationService
from app.services.orders import OrderService


class ProductionService:
    def start(self, session: Session, *, order_id: int, principal: Principal):
        AuthorizationService.require(session, principal, "PRODUCCION_INICIAR")
        order = lock_order(session, order_id)
        if order.estado != "EN_DISENO":
            raise Conflict("Sólo un pedido en diseño puede iniciar producción")
        advance = session.get(HitoPago, (order_id, 1))
        if advance is None or advance.estado != "PAGADO":
            raise Conflict("Se requiere un anticipo confirmado")
        required_lines = session.execute(
            select(DetallePedido.numero_linea, DetallePedido.id_variante)
            .join(VarianteProducto, VarianteProducto.id_variante == DetallePedido.id_variante)
            .where(
                DetallePedido.id_pedido == order_id,
                VarianteProducto.requiere_produccion.is_(True),
            )
        ).all()
        for line_number, variant_id in required_lines:
            component_count = session.scalar(
                select(func.count())
                .select_from(ComposicionProducto)
                .where(ComposicionProducto.id_variante == variant_id)
            )
            if not component_count:
                raise Conflict(f"La línea {line_number} tiene una composición incompleta")
            latest = session.scalar(
                select(func.max(VersionDiseno.numero_version)).where(
                    VersionDiseno.id_pedido == order_id,
                    VersionDiseno.numero_linea == line_number,
                )
            )
            if latest is None:
                raise Conflict(f"La línea {line_number} no tiene diseño")
            current_version = session.get(VersionDiseno, (order_id, line_number, latest))
            if current_version is None or not current_version.es_aprobado:
                raise Conflict(f"La versión vigente de la línea {line_number} no está aprobada")
        if required_lines:
            reservation_count = session.scalar(
                select(func.count())
                .select_from(ReservaInventario)
                .where(
                    ReservaInventario.id_pedido == order_id,
                    ReservaInventario.estado == "ACTIVA",
                )
            )
            if not reservation_count:
                raise Conflict("El pedido no conserva una reserva activa de materiales")
        return OrderService().transition(
            session,
            order_id=order_id,
            target="EN_PRODUCCION",
            principal=principal,
            reason="Anticipo y diseños vigentes verificados",
        )

    def complete(self, session: Session, *, order_id: int, principal: Principal):
        AuthorizationService.require(session, principal, "PRODUCCION_INICIAR")
        order = lock_order(session, order_id)
        if order.estado == "LISTO":
            return order
        if order.estado != "EN_PRODUCCION":
            raise Conflict("Sólo un pedido en producción puede marcarse listo")
        reservations = list(
            session.scalars(
                select(ReservaInventario)
                .where(ReservaInventario.id_pedido == order_id)
                .with_for_update()
            )
        )
        if any(item.estado != "AGOTADA" or item.cantidad_pendiente > 0 for item in reservations):
            raise Conflict("Deben consumirse todas las reservas antes de completar producción")
        return OrderService().transition(
            session,
            order_id=order_id,
            target="LISTO",
            principal=principal,
            reason="Producción terminada y materiales consumidos",
        )
