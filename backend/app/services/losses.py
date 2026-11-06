from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import Conflict, InsufficientInventory, NotFound
from app.core.security import Principal
from app.models.entities import DetallePerdida, MovimientoInventario, Perdida
from app.repositories.locks import lock_articles
from app.services.audit import AuditService
from app.services.authorization import AuthorizationService


@dataclass(frozen=True, slots=True)
class LossLineInput:
    article_id: int
    quantity: Decimal
    damage_description: str | None = None


class LossService:
    TYPES = frozenset(
        {
            "ROTURA_ARTICULO",
            "IMPRESION_FALLIDA",
            "SUBLIMACION_DEFECTUOSA",
            "DESPERDICIO_INSUMO",
            "DANO_ALMACENAMIENTO",
            "OTRO",
        }
    )
    MOMENTS = frozenset(
        {"ANTES_PRODUCCION", "DURANTE_PRODUCCION", "DESPUES_PRODUCCION", "FUERA_PRODUCCION"}
    )

    def report(
        self,
        session: Session,
        *,
        principal: Principal,
        moment: str,
        incident_type: str,
        reason: str,
        order_id: int | None = None,
        stage_id: int | None = None,
        description: str | None = None,
    ) -> Perdida:
        AuthorizationService.require(session, principal, "PERDIDA_REGISTRAR")
        if moment not in self.MOMENTS or incident_type not in self.TYPES:
            raise Conflict("Momento o tipo de pérdida inválido")
        if not reason.strip():
            raise Conflict("La pérdida requiere un motivo")
        if moment == "FUERA_PRODUCCION" and stage_id is not None:
            raise Conflict("Una pérdida fuera de producción no lleva etapa")
        loss = Perdida(
            id_pedido=order_id,
            id_empleado_reporta=principal.persona_id,
            id_etapa=stage_id,
            fecha_hora=datetime.now(UTC),
            momento_ocurrencia=moment,
            tipo_incidente=incident_type,
            motivo=reason,
            descripcion=description,
            estado_registro="REPORTADA",
        )
        session.add(loss)
        session.flush()
        return loss

    def confirm(
        self,
        session: Session,
        *,
        loss_id: int,
        lines: list[LossLineInput],
        principal: Principal,
    ) -> Perdida:
        AuthorizationService.require(session, principal, "PERDIDA_REGISTRAR")
        loss = session.scalar(
            select(Perdida).where(Perdida.id_perdida == loss_id).with_for_update()
        )
        if loss is None:
            raise NotFound("Pérdida no encontrada")
        if loss.estado_registro == "CONFIRMADA":
            return loss
        if loss.estado_registro != "REPORTADA" or not lines:
            raise Conflict("La pérdida no admite confirmación")
        if any(line.quantity <= 0 for line in lines):
            raise Conflict("Las cantidades perdidas deben ser positivas")
        articles = {
            article.id_articulo: article
            for article in lock_articles(session, {line.article_id for line in lines})
        }
        now = datetime.now(UTC)
        for number, line in enumerate(lines, start=1):
            article = articles[line.article_id]
            if article.existencia_actual < line.quantity:
                raise InsufficientInventory("La pérdida supera la existencia física")
            article.existencia_actual -= line.quantity
            movement = MovimientoInventario(
                id_articulo=article.id_articulo,
                id_pedido=loss.id_pedido,
                id_reserva=None,
                id_compra=None,
                numero_linea_compra=None,
                id_empleado=principal.persona_id,
                fecha_hora=now,
                tipo_movimiento="SALIDA_PERDIDA",
                cantidad=line.quantity,
                costo_unitario_aplicado=article.costo_referencia,
                motivo=loss.motivo,
                observaciones=loss.descripcion,
            )
            session.add(movement)
            session.flush()
            session.add(
                DetallePerdida(
                    id_perdida=loss.id_perdida,
                    numero_linea=number,
                    id_articulo=article.id_articulo,
                    id_movimiento=movement.id_movimiento,
                    cantidad_perdida=line.quantity,
                    costo_unitario_historico=article.costo_referencia,
                    descripcion_dano=line.damage_description,
                )
            )
        loss.estado_registro = "CONFIRMADA"
        AuditService.record(
            session,
            principal=principal,
            action="CONFIRMAR_PERDIDA",
            object_type="PERDIDA",
            object_reference=str(loss.id_perdida),
            reason=loss.motivo,
            after={"lineas": len(lines)},
        )
        session.flush()
        return loss

    @staticmethod
    def list_all(session: Session, principal: Principal) -> list[Perdida]:
        AuthorizationService.require(session, principal, "PERDIDA_CONSULTAR")
        return list(session.scalars(select(Perdida).order_by(Perdida.fecha_hora.desc())))
