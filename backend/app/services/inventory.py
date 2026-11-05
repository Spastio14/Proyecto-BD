from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import Conflict, InsufficientInventory, NotFound
from app.core.security import Principal
from app.domain.money import ZERO
from app.models.entities import (
    ArticuloInventariable,
    ComposicionProducto,
    DetallePedido,
    MovimientoInventario,
    ReservaInventario,
)
from app.repositories.locks import lock_articles, lock_order
from app.services.audit import AuditService
from app.services.authorization import AuthorizationService


class InventoryReservationService:
    RESERVABLE_STATES = frozenset({"PENDIENTE_PAGO", "PAGADO_PARCIAL", "PAGADO", "EN_DISENO"})

    def reserve_for_order(self, session: Session, *, order_id: int) -> list[ReservaInventario]:
        order = lock_order(session, order_id)
        if order.estado not in self.RESERVABLE_STATES:
            raise Conflict("El estado del pedido no permite reservar")
        existing = list(
            session.scalars(
                select(ReservaInventario).where(
                    ReservaInventario.id_pedido == order_id,
                    ReservaInventario.estado == "ACTIVA",
                )
            )
        )
        if existing:
            return existing

        requirement_rows = session.execute(
            select(
                ComposicionProducto.id_articulo,
                func.sum(ComposicionProducto.cantidad_estandar * DetallePedido.cantidad),
            )
            .join(DetallePedido, DetallePedido.id_variante == ComposicionProducto.id_variante)
            .where(DetallePedido.id_pedido == order_id)
            .group_by(ComposicionProducto.id_articulo)
        ).all()
        requirements = {article_id: Decimal(required) for article_id, required in requirement_rows}
        articles = lock_articles(session, set(requirements))
        now = datetime.now(UTC)
        reservations: list[ReservaInventario] = []
        for article in articles:
            reserved = session.scalar(
                select(func.coalesce(func.sum(ReservaInventario.cantidad_pendiente), 0)).where(
                    ReservaInventario.id_articulo == article.id_articulo,
                    ReservaInventario.estado == "ACTIVA",
                )
            )
            required = requirements[article.id_articulo]
            available = Decimal(article.existencia_actual) - Decimal(reserved or 0)
            if available < required:
                raise InsufficientInventory(
                    f"Inventario insuficiente para {article.codigo}: "
                    f"disponible {available}, requerido {required}"
                )
            reservation = ReservaInventario(
                id_pedido=order_id,
                id_articulo=article.id_articulo,
                cantidad_reservada=required,
                cantidad_pendiente=required,
                fecha_reserva=now,
                fecha_liberacion=None,
                estado="ACTIVA",
            )
            session.add(reservation)
            reservations.append(reservation)
        session.flush()
        return reservations


class InventoryService:
    def consume_order(
        self, session: Session, *, order_id: int, principal: Principal
    ) -> list[MovimientoInventario]:
        AuthorizationService.require(session, principal, "INVENTARIO_GESTIONAR")
        lock_order(session, order_id)
        reservations = list(
            session.scalars(
                select(ReservaInventario)
                .where(ReservaInventario.id_pedido == order_id)
                .order_by(ReservaInventario.id_articulo)
                .with_for_update()
            )
        )
        if not reservations:
            raise Conflict("El pedido no tiene reservas")
        articles = {
            item.id_articulo: item
            for item in lock_articles(session, {r.id_articulo for r in reservations})
        }
        movements: list[MovimientoInventario] = []
        now = datetime.now(UTC)
        for reservation in reservations:
            prior = session.scalar(
                select(MovimientoInventario).where(
                    MovimientoInventario.id_reserva == reservation.id_reserva,
                    MovimientoInventario.tipo_movimiento == "SALIDA_PRODUCCION",
                )
            )
            if prior is not None:
                movements.append(prior)
                continue
            if reservation.estado != "ACTIVA" or reservation.cantidad_pendiente <= ZERO:
                raise Conflict("La reserva ya fue consumida o liberada")
            article = articles[reservation.id_articulo]
            if article.existencia_actual < reservation.cantidad_pendiente:
                raise InsufficientInventory("La existencia física no cubre la reserva")
            amount = reservation.cantidad_pendiente
            article.existencia_actual -= amount
            reservation.cantidad_pendiente = Decimal("0.000")
            reservation.estado = "AGOTADA"
            reservation.fecha_liberacion = now
            movement = MovimientoInventario(
                id_articulo=article.id_articulo,
                id_pedido=order_id,
                id_reserva=reservation.id_reserva,
                id_compra=None,
                numero_linea_compra=None,
                id_empleado=principal.persona_id,
                fecha_hora=now,
                tipo_movimiento="SALIDA_PRODUCCION",
                cantidad=amount,
                costo_unitario_aplicado=article.costo_referencia,
                motivo="Consumo de reserva en producción",
                observaciones=None,
            )
            session.add(movement)
            movements.append(movement)
        AuditService.record(
            session,
            principal=principal,
            action="CONSUMIR_INVENTARIO",
            object_type="PEDIDO",
            object_reference=str(order_id),
            reason="Consumo de materiales reservados",
            after={"movimientos": len(movements)},
        )
        session.flush()
        return movements

    @staticmethod
    def availability(session: Session, article_id: int) -> Decimal:
        article = session.get(ArticuloInventariable, article_id)
        if article is None:
            raise NotFound("Artículo no encontrado")
        reserved = session.scalar(
            select(func.coalesce(func.sum(ReservaInventario.cantidad_pendiente), 0)).where(
                ReservaInventario.id_articulo == article_id,
                ReservaInventario.estado == "ACTIVA",
            )
        )
        return Decimal(article.existencia_actual) - Decimal(reserved or 0)
