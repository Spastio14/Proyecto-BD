from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import Conflict, NotFound
from app.core.security import Principal
from app.domain.money import ZERO, money
from app.models.entities import (
    ArticuloInventariable,
    Compra,
    DetalleCompra,
    MovimientoInventario,
    Proveedor,
)
from app.repositories.locks import lock_articles
from app.services.audit import AuditService
from app.services.authorization import AuthorizationService


class PurchaseService:
    @staticmethod
    def list_providers(session: Session, principal: Principal) -> list[Proveedor]:
        AuthorizationService.require(session, principal, "INVENTARIO_GESTIONAR")
        return list(session.scalars(select(Proveedor).order_by(Proveedor.nombre)))

    @staticmethod
    def create_provider(
        session: Session,
        *,
        principal: Principal,
        name: str,
        phone: str | None,
        email: str | None,
        address: str | None,
    ) -> Proveedor:
        AuthorizationService.require(session, principal, "INVENTARIO_GESTIONAR")
        provider = Proveedor(
            nombre=name.strip(),
            telefono=phone,
            correo=email.strip().lower() if email else None,
            direccion=address,
            estado="ACTIVO",
        )
        session.add(provider)
        session.flush()
        AuditService.record(
            session,
            principal=principal,
            action="CREAR_PROVEEDOR",
            object_type="PROVEEDOR",
            object_reference=str(provider.id_proveedor),
            reason="Proveedor registrado desde la aplicación",
            after={"nombre": provider.nombre},
        )
        return provider

    def create(
        self,
        session: Session,
        *,
        principal: Principal,
        provider_id: int,
        document_number: str | None,
        lines: list[tuple[int, Decimal, Decimal]],
    ) -> Compra:
        AuthorizationService.require(session, principal, "INVENTARIO_GESTIONAR")
        provider = session.get(Proveedor, provider_id)
        if provider is None or provider.estado != "ACTIVO":
            raise NotFound("Proveedor activo no encontrado")
        if not lines:
            raise Conflict("La compra requiere al menos un detalle")
        purchase = Compra(
            id_proveedor=provider_id,
            fecha_compra=datetime.now(UTC),
            numero_documento=document_number,
            estado="BORRADOR",
            total_compra=ZERO,
        )
        session.add(purchase)
        session.flush()
        for article_id, quantity, unit_cost in lines:
            self._append_line(
                session,
                purchase=purchase,
                article_id=article_id,
                quantity=quantity,
                unit_cost=unit_cost,
            )
        self._recalculate_total(session, purchase)
        AuditService.record(
            session,
            principal=principal,
            action="CREAR_COMPRA",
            object_type="COMPRA",
            object_reference=str(purchase.id_compra),
            reason="Compra creada en borrador",
            after={"proveedor": provider_id, "total": purchase.total_compra},
        )
        session.flush()
        return purchase

    def add_line(
        self,
        session: Session,
        *,
        purchase_id: int,
        article_id: int,
        quantity: Decimal,
        unit_cost: Decimal,
        principal: Principal,
    ) -> DetalleCompra:
        AuthorizationService.require(session, principal, "INVENTARIO_GESTIONAR")
        purchase = self._lock_purchase(session, purchase_id)
        if purchase.estado != "BORRADOR":
            raise Conflict("Sólo una compra en borrador admite detalles")
        detail = self._append_line(
            session,
            purchase=purchase,
            article_id=article_id,
            quantity=quantity,
            unit_cost=unit_cost,
        )
        self._recalculate_total(session, purchase)
        session.flush()
        return detail

    def confirm(
        self, session: Session, *, purchase_id: int, principal: Principal
    ) -> Compra:
        AuthorizationService.require(session, principal, "INVENTARIO_GESTIONAR")
        purchase = self._lock_purchase(session, purchase_id)
        if purchase.estado == "CONFIRMADA":
            return purchase
        if purchase.estado != "BORRADOR":
            raise Conflict("La compra no admite confirmación")
        details = list(
            session.scalars(
                select(DetalleCompra)
                .where(DetalleCompra.id_compra == purchase_id)
                .order_by(DetalleCompra.numero_linea)
            )
        )
        if not details:
            raise Conflict("La compra no tiene detalles")
        articles = {
            article.id_articulo: article
            for article in lock_articles(session, {detail.id_articulo for detail in details})
        }
        now = datetime.now(UTC)
        for detail in details:
            prior = session.scalar(
                select(MovimientoInventario.id_movimiento).where(
                    MovimientoInventario.id_compra == purchase_id,
                    MovimientoInventario.numero_linea_compra == detail.numero_linea,
                    MovimientoInventario.tipo_movimiento == "ENTRADA_COMPRA",
                )
            )
            if prior is not None:
                raise Conflict("La compra ya tiene movimientos de entrada")
            article = articles[detail.id_articulo]
            article.existencia_actual += detail.cantidad_comprada
            session.add(
                MovimientoInventario(
                    id_articulo=detail.id_articulo,
                    id_pedido=None,
                    id_reserva=None,
                    id_compra=purchase_id,
                    numero_linea_compra=detail.numero_linea,
                    id_empleado=principal.persona_id,
                    fecha_hora=now,
                    tipo_movimiento="ENTRADA_COMPRA",
                    cantidad=detail.cantidad_comprada,
                    costo_unitario_aplicado=detail.costo_unitario_compra,
                    motivo="Confirmación de compra",
                    observaciones=purchase.numero_documento,
                )
            )
        purchase.estado = "CONFIRMADA"
        AuditService.record(
            session,
            principal=principal,
            action="CONFIRMAR_COMPRA",
            object_type="COMPRA",
            object_reference=str(purchase.id_compra),
            reason="Entrada de inventario confirmada de forma atómica",
            before={"estado": "BORRADOR"},
            after={"estado": "CONFIRMADA", "lineas": len(details)},
        )
        session.flush()
        return purchase

    @staticmethod
    def list_purchases(
        session: Session, *, principal: Principal, provider_id: int | None = None
    ) -> list[Compra]:
        AuthorizationService.require(session, principal, "INVENTARIO_GESTIONAR")
        statement = select(Compra).order_by(Compra.fecha_compra.desc())
        if provider_id is not None:
            statement = statement.where(Compra.id_proveedor == provider_id)
        return list(session.scalars(statement))

    @staticmethod
    def details(
        session: Session, *, purchase_id: int, principal: Principal
    ) -> list[DetalleCompra]:
        AuthorizationService.require(session, principal, "INVENTARIO_GESTIONAR")
        if session.get(Compra, purchase_id) is None:
            raise NotFound("Compra no encontrada")
        return list(
            session.scalars(
                select(DetalleCompra)
                .where(DetalleCompra.id_compra == purchase_id)
                .order_by(DetalleCompra.numero_linea)
            )
        )

    @staticmethod
    def _lock_purchase(session: Session, purchase_id: int) -> Compra:
        purchase = session.scalar(
            select(Compra).where(Compra.id_compra == purchase_id).with_for_update()
        )
        if purchase is None:
            raise NotFound("Compra no encontrada")
        return purchase

    @staticmethod
    def _append_line(
        session: Session,
        *,
        purchase: Compra,
        article_id: int,
        quantity: Decimal,
        unit_cost: Decimal,
    ) -> DetalleCompra:
        if quantity <= 0 or unit_cost < 0:
            raise Conflict("Cantidad o costo de compra inválido")
        if session.get(ArticuloInventariable, article_id) is None:
            raise NotFound("Artículo inventariable no encontrado")
        number = session.scalar(
            select(func.coalesce(func.max(DetalleCompra.numero_linea), 0)).where(
                DetalleCompra.id_compra == purchase.id_compra
            )
        )
        detail = DetalleCompra(
            id_compra=purchase.id_compra,
            numero_linea=int(number or 0) + 1,
            id_articulo=article_id,
            cantidad_comprada=quantity,
            costo_unitario_compra=unit_cost,
            importe=money(quantity * unit_cost),
        )
        session.add(detail)
        session.flush()
        return detail

    @staticmethod
    def _recalculate_total(session: Session, purchase: Compra) -> None:
        total = session.scalar(
            select(func.coalesce(func.sum(DetalleCompra.importe), 0)).where(
                DetalleCompra.id_compra == purchase.id_compra
            )
        )
        purchase.total_compra = money(total or ZERO)
