from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import Conflict
from app.core.security import Principal
from app.models.entities import (
    DetallePedido,
    HitoPago,
    VarianteProducto,
    VersionDiseno,
)
from app.repositories.locks import lock_order
from app.services.authorization import AuthorizationService
from app.services.orders import OrderService


class ProductionService:
    def start(self, session: Session, *, order_id: int, principal: Principal):
        AuthorizationService.require(session, principal, "PRODUCCION_INICIAR")
        lock_order(session, order_id)
        advance = session.get(HitoPago, (order_id, 1))
        if advance is None or advance.estado != "PAGADO":
            raise Conflict("Se requiere un anticipo confirmado")
        required_lines = session.execute(
            select(DetallePedido.numero_linea)
            .join(VarianteProducto, VarianteProducto.id_variante == DetallePedido.id_variante)
            .where(
                DetallePedido.id_pedido == order_id,
                VarianteProducto.requiere_produccion.is_(True),
            )
        ).scalars()
        for line_number in required_lines:
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
        return OrderService().transition(
            session,
            order_id=order_id,
            target="EN_PRODUCCION",
            principal=principal,
            reason="Anticipo y diseños vigentes verificados",
        )
