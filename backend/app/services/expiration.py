from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.entities import Pedido, Transaccion
from app.services.orders import OrderService


class OrderExpirationService:
    def expire_due(self, session: Session, *, now: datetime | None = None, limit: int = 100) -> int:
        current = now or datetime.now(UTC)
        candidates = list(
            session.scalars(
                select(Pedido)
                .where(
                    Pedido.estado == "PENDIENTE_PAGO",
                    or_(
                        and_(
                            Pedido.fecha_inicio_revision_pago.is_(None),
                            Pedido.vencimiento_pago < current,
                        ),
                        and_(
                            Pedido.fecha_inicio_revision_pago.is_not(None),
                            Pedido.fecha_inicio_revision_pago + timedelta(hours=24) < current,
                        ),
                    ),
                )
                .order_by(Pedido.vencimiento_pago)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )
        expired = 0
        for order in candidates:
            verified = session.scalar(
                select(Transaccion.id_transaccion).where(
                    Transaccion.id_pedido == order.id_pedido,
                    Transaccion.tipo_transaccion == "PAGO",
                    Transaccion.estado_verificacion == "VERIFICADO",
                )
            )
            if verified is not None:
                continue
            OrderService().transition(
                session,
                order_id=order.id_pedido,
                target="EXPIRADO",
                principal=None,
                reason="Ventana de pago agotada sin anticipo confirmado",
            )
            expired += 1
        return expired
