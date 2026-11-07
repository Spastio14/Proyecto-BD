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
    @staticmethod
    def create_article(
        session: Session,
        *,
        principal: Principal,
        code: str,
        name: str,
        article_type: str,
        unit: str,
        minimum_stock: Decimal,
        reference_cost: Decimal,
    ) -> ArticuloInventariable:
        AuthorizationService.require(session, principal, "INVENTARIO_GESTIONAR")
        normalized_code = code.strip().upper()
        if (
            session.scalar(
                select(ArticuloInventariable.id_articulo).where(
                    ArticuloInventariable.codigo == normalized_code
                )
            )
            is not None
        ):
            raise Conflict("El código de artículo ya existe")
        article = ArticuloInventariable(
            codigo=normalized_code,
            nombre=name.strip(),
            tipo_articulo=article_type.strip().upper(),
            unidad_medida=unit,
            existencia_actual=Decimal("0.000"),
            existencia_minima=minimum_stock,
            costo_referencia=reference_cost,
            estado="ACTIVO",
        )
        session.add(article)
        session.flush()
        AuditService.record(
            session,
            principal=principal,
            action="CREAR_ARTICULO_INVENTARIO",
            object_type="ARTICULO_INVENTARIABLE",
            object_reference=str(article.id_articulo),
            reason="Alta administrativa con existencia inicial en cero",
            after={"codigo": article.codigo, "existencia_actual": article.existencia_actual},
        )
        return article

    @staticmethod
    def update_article(
        session: Session,
        *,
        article_id: int,
        principal: Principal,
        changes: dict,
    ) -> ArticuloInventariable:
        AuthorizationService.require(session, principal, "INVENTARIO_GESTIONAR")
        article = session.scalar(
            select(ArticuloInventariable)
            .where(ArticuloInventariable.id_articulo == article_id)
            .with_for_update()
        )
        if article is None:
            raise NotFound("Artículo no encontrado")
        if "code" in changes:
            code = changes["code"].strip().upper()
            duplicate = session.scalar(
                select(ArticuloInventariable.id_articulo).where(
                    ArticuloInventariable.codigo == code,
                    ArticuloInventariable.id_articulo != article_id,
                )
            )
            if duplicate is not None:
                raise Conflict("El código de artículo ya existe")
            changes["code"] = code
        mapping = {
            "code": "codigo",
            "name": "nombre",
            "article_type": "tipo_articulo",
            "unit": "unidad_medida",
            "minimum_stock": "existencia_minima",
            "reference_cost": "costo_referencia",
            "state": "estado",
        }
        before = {"codigo": article.codigo, "estado": article.estado}
        for source, value in changes.items():
            if source in mapping:
                setattr(
                    article, mapping[source], value.strip() if isinstance(value, str) else value
                )
        AuditService.record(
            session,
            principal=principal,
            action="ACTUALIZAR_ARTICULO_INVENTARIO",
            object_type="ARTICULO_INVENTARIABLE",
            object_reference=str(article_id),
            reason="Actualización administrativa sin alterar existencias",
            before=before,
            after={"codigo": article.codigo, "estado": article.estado},
        )
        return article

    @classmethod
    def adjust(
        cls,
        session: Session,
        *,
        article_id: int,
        direction: str,
        quantity: Decimal,
        reason: str,
        observations: str | None,
        principal: Principal,
    ) -> MovimientoInventario:
        AuthorizationService.require(session, principal, "INVENTARIO_GESTIONAR")
        articles = lock_articles(session, {article_id})
        if not articles:
            raise NotFound("Artículo no encontrado")
        article = articles[0]
        if article.estado != "ACTIVO":
            raise Conflict("No se puede ajustar un artículo inactivo")
        before = article.existencia_actual
        if direction == "SALIDA":
            if cls.availability(session, article_id) < quantity:
                raise InsufficientInventory("El ajuste de salida afectaría existencias reservadas")
            article.existencia_actual -= quantity
            movement_type = "SALIDA_AJUSTE"
        elif direction == "ENTRADA":
            article.existencia_actual += quantity
            movement_type = "ENTRADA_AJUSTE"
        else:
            raise Conflict("Dirección de ajuste inválida")
        movement = MovimientoInventario(
            id_articulo=article_id,
            id_pedido=None,
            id_reserva=None,
            id_compra=None,
            numero_linea_compra=None,
            id_empleado=principal.persona_id,
            fecha_hora=datetime.now(UTC),
            tipo_movimiento=movement_type,
            cantidad=quantity,
            costo_unitario_aplicado=article.costo_referencia,
            motivo=reason.strip(),
            observaciones=observations,
        )
        session.add(movement)
        session.flush()
        AuditService.record(
            session,
            principal=principal,
            action="AJUSTAR_INVENTARIO",
            object_type="ARTICULO_INVENTARIABLE",
            object_reference=str(article_id),
            reason=reason,
            before={"existencia_actual": before},
            after={
                "existencia_actual": article.existencia_actual,
                "movimiento": movement.id_movimiento,
                "tipo": movement_type,
            },
        )
        return movement

    @staticmethod
    def list_movements(
        session: Session, *, principal: Principal, article_id: int | None = None
    ) -> list[MovimientoInventario]:
        AuthorizationService.require(session, principal, "INVENTARIO_CONSULTAR")
        statement = select(MovimientoInventario).order_by(
            MovimientoInventario.fecha_hora.desc(), MovimientoInventario.id_movimiento.desc()
        )
        if article_id is not None:
            statement = statement.where(MovimientoInventario.id_articulo == article_id)
        return list(session.scalars(statement.limit(500)))

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

    @classmethod
    def list_with_availability(
        cls, session: Session, principal: Principal
    ) -> list[dict[str, object]]:
        AuthorizationService.require(session, principal, "INVENTARIO_CONSULTAR")
        articles = list(
            session.scalars(select(ArticuloInventariable).order_by(ArticuloInventariable.nombre))
        )
        return [
            {
                "id_articulo": article.id_articulo,
                "codigo": article.codigo,
                "nombre": article.nombre,
                "tipo_articulo": article.tipo_articulo,
                "unidad_medida": article.unidad_medida,
                "existencia_actual": article.existencia_actual,
                "existencia_minima": article.existencia_minima,
                "disponible": cls.availability(session, article.id_articulo),
                "reservado": article.existencia_actual
                - cls.availability(session, article.id_articulo),
                "costo_referencia": article.costo_referencia,
                "bajo_minimo": cls.availability(session, article.id_articulo)
                <= article.existencia_minima,
                "estado": article.estado,
            }
            for article in articles
        ]
