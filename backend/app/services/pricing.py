from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import Conflict, NotFound
from app.domain.money import ZERO, money
from app.models.entities import (
    ArticuloInventariable,
    ComposicionProducto,
    EscalaPrecio,
    Promocion,
    PromocionVariante,
    VarianteProducto,
)


@dataclass(frozen=True, slots=True)
class PriceResult:
    unit_price: Decimal
    discount: Decimal
    total: Decimal
    mode: str
    promotion_id: int | None
    estimated_cost: Decimal


class PricingService:
    WHOLESALE_CLIENT_TYPES = frozenset({"REGISTRADO", "EMPRESA"})

    def price_line(
        self,
        session: Session,
        *,
        client_type: str,
        variant_id: int,
        quantity: int,
        promotion_id: int | None = None,
        now: datetime | None = None,
    ) -> PriceResult:
        if quantity <= 0:
            raise Conflict("La cantidad debe ser mayor que cero")
        variant = session.scalar(
            select(VarianteProducto).where(
                VarianteProducto.id_variante == variant_id,
                VarianteProducto.estado == "ACTIVA",
            )
        )
        if variant is None:
            raise NotFound("Variante activa no encontrada")

        unit_price = money(variant.precio_detalle)
        mode = "DETALLE"
        scale = None
        if client_type in self.WHOLESALE_CLIENT_TYPES:
            scale = session.scalar(
                select(EscalaPrecio).where(
                    EscalaPrecio.id_variante == variant_id,
                    EscalaPrecio.estado == "ACTIVA",
                    EscalaPrecio.cantidad_minima <= quantity,
                    or_(
                        EscalaPrecio.cantidad_maxima.is_(None),
                        EscalaPrecio.cantidad_maxima >= quantity,
                    ),
                )
            )
            if scale is not None:
                unit_price = money(scale.precio_unitario_mayorista)
                mode = "MAYORISTA"

        gross = money(unit_price * quantity)
        discount = ZERO
        selected_promotion = None
        if promotion_id is not None:
            current = now or datetime.now(UTC)
            promotion = session.scalar(
                select(Promocion)
                .join(PromocionVariante, PromocionVariante.id_promocion == Promocion.id_promocion)
                .where(
                    Promocion.id_promocion == promotion_id,
                    PromocionVariante.id_variante == variant_id,
                    Promocion.estado == "ACTIVA",
                    Promocion.fecha_inicio <= current,
                    Promocion.fecha_fin >= current,
                )
            )
            if promotion is None:
                raise Conflict("La promoción no está vigente o no aplica a la variante")
            if quantity < promotion.cantidad_requerida:
                raise Conflict("La cantidad no alcanza el mínimo de la promoción")
            if scale is not None and not promotion.permite_combinacion_mayorista:
                raise Conflict("La promoción no puede combinarse con precio mayorista")
            discount = self._promotion_discount(promotion, unit_price, quantity, gross)
            selected_promotion = promotion.id_promocion
            mode = "MAYORISTA_PROMO" if scale is not None else "PROMOCION"

        total = money(gross - discount)
        if discount < ZERO or total < ZERO:
            raise Conflict("El descuento produciría un importe inválido")
        return PriceResult(
            unit_price=unit_price,
            discount=money(discount),
            total=total,
            mode=mode,
            promotion_id=selected_promotion,
            estimated_cost=self._estimated_cost(session, variant_id, quantity),
        )

    @staticmethod
    def _promotion_discount(
        promotion: Promocion, unit_price: Decimal, quantity: int, gross: Decimal
    ) -> Decimal:
        value = money(promotion.valor_beneficio)
        if promotion.tipo == "PORCENTAJE":
            result = money(gross * value / Decimal("100"))
        elif promotion.tipo == "DESCUENTO_FIJO":
            result = value
        elif promotion.tipo == "PRECIO_PAQUETE":
            packages, remainder = divmod(quantity, promotion.cantidad_requerida)
            promotional_total = money(packages * value + remainder * unit_price)
            result = money(gross - promotional_total)
        else:
            raise Conflict("Tipo de promoción desconocido")
        if result > gross:
            raise Conflict("El descuento supera el importe aplicable")
        return result

    @staticmethod
    def _estimated_cost(session: Session, variant_id: int, quantity: int) -> Decimal:
        rows = session.execute(
            select(ComposicionProducto.cantidad_estandar, ArticuloInventariable.costo_referencia)
            .join(
                ArticuloInventariable,
                ArticuloInventariable.id_articulo == ComposicionProducto.id_articulo,
            )
            .where(ComposicionProducto.id_variante == variant_id)
        ).all()
        return money(sum((amount * cost * quantity for amount, cost in rows), ZERO))
