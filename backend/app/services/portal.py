from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFound, PermissionDenied
from app.core.security import Principal
from app.domain.orders import ALLOWED_TRANSITIONS
from app.domain.money import money
from app.models.entities import (
    Categoria,
    Cliente,
    ComposicionProducto,
    Cotizacion,
    DetalleCotizacion,
    DetallePedido,
    Envio,
    Pedido,
    Producto,
    HitoPago,
    Transaccion,
    VarianteProducto,
)
from app.schemas.portal import (
    PortalCatalogItem,
    PortalHistoryItem,
    PortalOrder,
    PortalOrderDetail,
    PortalPayment,
    PortalPaymentMilestone,
    PortalPricePreview,
    PortalProductLine,
    PortalQuote,
    PortalSummary,
)
from app.services.orders import OrderService
from app.services.inventory import InventoryService
from app.services.payments import PaymentService
from app.services.pricing import PricingService
from app.services.quotations import QuotationService

ACTIVE_ORDER_STATES = {
    "PENDIENTE_PAGO",
    "PAGADO_PARCIAL",
    "PAGADO",
    "EN_DISENO",
    "EN_PRODUCCION",
    "LISTO",
}


class PortalService:
    @staticmethod
    def _require_client(principal: Principal) -> None:
        if principal.is_employee:
            raise PermissionDenied("Este recurso pertenece al portal del cliente")

    @classmethod
    def _order_by_code(cls, session: Session, *, code: str, principal: Principal) -> Pedido:
        cls._require_client(principal)
        order = session.scalar(select(Pedido).where(Pedido.codigo_pedido == code))
        if order is None:
            raise NotFound("Pedido no encontrado")
        return OrderService.get_owned(session, order_id=order.id_pedido, principal=principal)

    @staticmethod
    def _order_lines(session: Session, order_id: int) -> list[PortalProductLine]:
        rows = session.execute(
            select(DetallePedido, VarianteProducto, Producto)
            .join(
                VarianteProducto,
                VarianteProducto.id_variante == DetallePedido.id_variante,
            )
            .join(Producto, Producto.id_producto == VarianteProducto.id_producto)
            .where(DetallePedido.id_pedido == order_id)
            .order_by(DetallePedido.numero_linea)
        ).all()
        return [
            PortalProductLine(
                producto=product.nombre,
                variante=variant.caracteristicas or variant.codigo_variante,
                cantidad=detail.cantidad,
                precio_unitario=detail.precio_unitario_aplicado,
                importe=detail.importe_pactado,
                personalizacion=detail.descripcion_personalizacion,
            )
            for detail, variant, product in rows
        ]

    @staticmethod
    def _requires_production(session: Session, order_id: int) -> bool:
        return bool(
            session.scalar(
                select(func.bool_or(VarianteProducto.requiere_produccion))
                .join(
                    DetallePedido,
                    DetallePedido.id_variante == VarianteProducto.id_variante,
                )
                .where(DetallePedido.id_pedido == order_id)
            )
        )

    @staticmethod
    def _next_action(
        order: Pedido,
        *,
        balance: Decimal,
        delivery: Envio | None,
        requires_production: bool,
    ) -> str:
        if order.estado == "PENDIENTE_PAGO":
            return "REPORTAR_PAGO"
        if order.estado == "PAGADO_PARCIAL":
            return (
                "ESPERAR_DISENO" if requires_production and balance > 0 else "ESPERAR_ACTUALIZACION"
            )
        if order.estado == "PAGADO":
            return "ESPERAR_DISENO" if requires_production else "ESPERAR_ACTUALIZACION"
        if order.estado == "EN_DISENO":
            return "REVISAR_DISENO"
        if order.estado == "EN_PRODUCCION":
            return "ESPERAR_PRODUCCION"
        if order.estado == "LISTO":
            if order.modalidad_entrega == "ENVIO":
                return "ESPERAR_ENVIO" if delivery is not None else "COORDINAR_ENVIO"
            return "RETIRAR_PEDIDO"
        if order.estado == "ENTREGADO":
            return "COMPLETADO"
        return "SIN_ACCION"

    @classmethod
    def _serialize_order(
        cls, session: Session, *, order: Pedido, principal: Principal
    ) -> PortalOrder:
        payment = PaymentService.summary(session, order_id=order.id_pedido, principal=principal)
        delivery = session.scalar(select(Envio).where(Envio.id_pedido == order.id_pedido))
        balance = money(payment["saldo_pendiente"])
        requires_production = cls._requires_production(session, order.id_pedido)
        # Solo considerar actividad de pago real: transacciones PENDIENTES o
        # VERIFICADAS. Las transacciones RECHAZADAS no bloquean la cancelación
        # porque no representan dinero en tránsito ni verificado.
        has_payment_activity = session.scalar(
            select(Transaccion.id_transaccion)
            .where(
                Transaccion.id_pedido == order.id_pedido,
                Transaccion.estado_verificacion.in_(("PENDIENTE", "VERIFICADO")),
            )
            .limit(1)
        ) is not None or session.scalar(
            select(HitoPago.numero_hito).where(
                HitoPago.id_pedido == order.id_pedido,
                HitoPago.estado == "PAGADO",
            ).limit(1)
        ) is not None
        if order.estado in {"EN_PRODUCCION", "LISTO", "ENTREGADO"}:
            cancel_reason = "La producción ya comenzó; solicita revisión administrativa"
        elif has_payment_activity:
            cancel_reason = "Hay pagos reportados o verificados; solicita revisión administrativa"
        elif order.estado == "CANCELADO":
            cancel_reason = "El pedido ya está cancelado"
        elif "CANCELADO" not in ALLOWED_TRANSITIONS.get(order.estado, frozenset()):
            cancel_reason = "El estado actual no admite cancelación"
        else:
            cancel_reason = None
        return PortalOrder(
            codigo=order.codigo_pedido,
            fecha=order.fecha_creacion,
            fecha_entrega_prevista=order.fecha_entrega_prevista,
            estado=order.estado,
            total=order.total_pedido,
            pagado=money(payment["total_verificado"]),
            saldo_pendiente=balance,
            modalidad_entrega=order.modalidad_entrega,
            estado_entrega=delivery.estado if delivery else None,
            proxima_accion=cls._next_action(
                order,
                balance=balance,
                delivery=delivery,
                requires_production=requires_production,
            ),
            requiere_produccion=requires_production,
            productos=cls._order_lines(session, order.id_pedido),
            puede_cancelar=cancel_reason is None,
            motivo_bloqueo_cancelacion=cancel_reason,
        )

    @classmethod
    def list_orders(cls, session: Session, principal: Principal) -> list[PortalOrder]:
        cls._require_client(principal)
        return [
            cls._serialize_order(session, order=order, principal=principal)
            for order in OrderService.list_owned(session, principal)
        ]

    @classmethod
    def order_detail(
        cls, session: Session, *, code: str, principal: Principal
    ) -> PortalOrderDetail:
        order = cls._order_by_code(session, code=code, principal=principal)
        base = cls._serialize_order(session, order=order, principal=principal)
        history = OrderService.history_owned(session, order_id=order.id_pedido, principal=principal)
        payment = PaymentService.summary(session, order_id=order.id_pedido, principal=principal)
        return PortalOrderDetail(
            **base.model_dump(),
            historial=[
                PortalHistoryItem(
                    fecha=item.fecha_hora,
                    estado=item.estado_nuevo,
                    detalle=item.motivo,
                )
                for item in history
            ],
            hitos_pago=[
                PortalPaymentMilestone(
                    numero=item["numero_hito"],
                    tipo=item["tipo_hito"],
                    monto=item["monto_exigido"],
                    pagado=item["monto_verificado"],
                    pendiente_verificacion=item["monto_pendiente_verificacion"],
                    saldo=item["monto_restante"],
                    disponible_reportar=item["monto_disponible_reportar"],
                    estado=item["estado"],
                    puede_reportar=item["puede_reportar"],
                )
                for item in payment["hitos"]
            ],
        )

    @staticmethod
    def _quote_reference(quote_id: int) -> str:
        return f"COT-{quote_id:06d}"

    @classmethod
    def quote_by_reference(
        cls, session: Session, *, reference: str, principal: Principal
    ) -> Cotizacion:
        cls._require_client(principal)
        try:
            quote_id = int(reference.removeprefix("COT-"))
        except ValueError as exc:
            raise NotFound("Cotización no encontrada") from exc
        quote = session.get(Cotizacion, quote_id)
        if quote is None:
            raise NotFound("Cotización no encontrada")
        if quote.id_cliente != principal.persona_id:
            raise PermissionDenied("La cotización pertenece a otro cliente")
        return quote

    @classmethod
    def _serialize_quote(cls, session: Session, quote: Cotizacion) -> PortalQuote:
        rows = session.execute(
            select(DetalleCotizacion, VarianteProducto, Producto)
            .join(
                VarianteProducto,
                VarianteProducto.id_variante == DetalleCotizacion.id_variante,
            )
            .join(Producto, Producto.id_producto == VarianteProducto.id_producto)
            .where(DetalleCotizacion.id_cotizacion == quote.id_cotizacion)
            .order_by(DetalleCotizacion.numero_linea)
        ).all()
        return PortalQuote(
            referencia=cls._quote_reference(quote.id_cotizacion),
            fecha=quote.fecha_emision,
            vencimiento=quote.fecha_vencimiento,
            estado=quote.estado,
            total=quote.total_ofrecido,
            productos=[
                PortalProductLine(
                    producto=product.nombre,
                    variante=variant.caracteristicas or variant.codigo_variante,
                    cantidad=detail.cantidad,
                    precio_unitario=detail.precio_ofrecido,
                    importe=money(
                        detail.precio_ofrecido * detail.cantidad - detail.descuento_ofrecido
                    ),
                    personalizacion=detail.descripcion_personalizacion,
                )
                for detail, variant, product in rows
            ],
        )

    @classmethod
    def list_quotes(cls, session: Session, principal: Principal) -> list[PortalQuote]:
        cls._require_client(principal)
        return [
            cls._serialize_quote(session, quote)
            for quote in QuotationService.list_owned(session, principal)
        ]

    @classmethod
    def list_payments(cls, session: Session, principal: Principal) -> list[PortalPayment]:
        cls._require_client(principal)
        orders = OrderService.list_owned(session, principal)
        result: list[PortalPayment] = []
        for order in orders:
            payments = PaymentService.list_for_order(
                session, order_id=order.id_pedido, principal=principal
            )
            result.extend(
                PortalPayment(
                    id_transaccion=payment.id_transaccion,
                    pedido=order.codigo_pedido,
                    fecha=payment.fecha_hora,
                    monto=payment.monto_con_signo,
                    estado=payment.estado_verificacion,
                    metodo=payment.metodo_pago,
                    banco_origen=payment.banco_origen,
                    referencia=payment.referencia_bancaria,
                )
                for payment in payments
                if payment.tipo_transaccion == "PAGO"
            )
        return sorted(result, key=lambda item: item.fecha, reverse=True)

    @classmethod
    def summary(cls, session: Session, principal: Principal) -> PortalSummary:
        orders = cls.list_orders(session, principal)
        quotes = cls.list_quotes(session, principal)
        payments = cls.list_payments(session, principal)
        active = [order for order in orders if order.estado in ACTIVE_ORDER_STATES]
        client = session.get(Cliente, principal.persona_id)
        active_limit = 1 if client and client.tipo_cliente == "INVITADO" else 2
        return PortalSummary(
            pedidos_activos=len(active),
            cotizaciones_pendientes=sum(quote.estado == "EMITIDA" for quote in quotes),
            pagos_pendientes=sum(payment.estado == "PENDIENTE" for payment in payments),
            pedidos_listos=sum(order.estado == "LISTO" for order in orders),
            saldo_total=money(sum((order.saldo_pendiente for order in active), Decimal(0))),
            limite_pedidos_activos=active_limit,
            puede_crear_pedido=len(active) < active_limit,
            motivo_bloqueo_pedido=(
                f"Alcanzaste el límite de {active_limit} pedido(s) activo(s). "
                "Finaliza o cancela uno antes de crear otro."
                if len(active) >= active_limit
                else None
            ),
            pedido_destacado=active[0] if active else None,
        )

    @classmethod
    def catalog(
        cls,
        session: Session,
        principal: Principal,
        *,
        public_storage_url: str | None = None,
    ) -> list[PortalCatalogItem]:
        cls._require_client(principal)
        rows = session.execute(
            select(VarianteProducto, Producto, Categoria)
            .join(Producto, Producto.id_producto == VarianteProducto.id_producto)
            .join(Categoria, Categoria.id_categoria == Producto.id_categoria)
            .where(
                VarianteProducto.estado == "ACTIVA",
                Producto.estado_publicacion == "PUBLICADO",
                Categoria.estado == "ACTIVA",
            )
            .order_by(Categoria.nombre, Producto.nombre, VarianteProducto.codigo_variante)
        ).all()
        result = []
        for variant, product, category in rows:
            composition = list(session.scalars(select(ComposicionProducto).where(ComposicionProducto.id_variante == variant.id_variante)))
            missing_recipe = variant.requiere_produccion and not composition
            insufficient = variant.requiere_produccion and any(
                InventoryService.availability(session, line.id_articulo) < line.cantidad_estandar
                for line in composition
            )
            cause = "RECETA_INCOMPLETA" if missing_recipe else "SIN_EXISTENCIAS" if insufficient else None
            result.append(PortalCatalogItem(
                id_producto=product.id_producto,
                id_variante=variant.id_variante,
                codigo=variant.codigo_variante,
                producto=product.nombre,
                categoria=category.nombre,
                descripcion=(
                    product.descripcion or product.informacion_comercial or "Personalizable"
                ),
                variante=variant.caracteristicas or variant.codigo_variante,
                precio_referencia=variant.precio_detalle,
                disponibilidad=("AGOTADO" if insufficient else "BAJO_PEDIDO" if variant.requiere_produccion else "DISPONIBLE"),
                causa_disponibilidad=cause,
                requiere_produccion=variant.requiere_produccion,
                imagen_url=(
                    f"{public_storage_url.rstrip('/')}/storage/v1/object/public/catalogo-productos/"
                    f"{product.ruta_imagen_principal}"
                    if public_storage_url and product.ruta_imagen_principal
                    else None
                ),
            ))
        return result

    @classmethod
    def price_preview(
        cls,
        session: Session,
        *,
        variant_id: int,
        quantity: int,
        principal: Principal,
    ) -> PortalPricePreview:
        cls._require_client(principal)
        client = session.get(Cliente, principal.persona_id)
        if client is None:
            raise NotFound("Cliente no encontrado")
        price = PricingService().price_line(
            session,
            client_type=client.tipo_cliente,
            commercial_condition=client.condicion_comercial,
            variant_id=variant_id,
            quantity=quantity,
        )
        return PortalPricePreview(
            precio_unitario=price.unit_price,
            descuento=price.discount,
            total=price.total,
            modo_precio=price.mode,
        )
