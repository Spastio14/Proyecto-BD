from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import Principal
from app.models.entities import (
    ArticuloInventariable,
    AsignacionRol,
    Cliente,
    Compra,
    DetalleCompra,
    DetallePedido,
    DetallePerdida,
    Empleado,
    MovimientoInventario,
    Pedido,
    Persona,
    Producto,
    Proveedor,
    ReservaInventario,
    Rol,
    Transaccion,
    VarianteProducto,
)
from app.services.authorization import AuthorizationService


class ReportService:
    @staticmethod
    def dashboard(session: Session, principal: Principal) -> dict[str, object]:
        AuthorizationService.require(session, principal, "REPORTE_FINANCIERO_CONSULTAR")

        sold = session.execute(
            select(
                Producto.id_producto,
                Producto.nombre,
                func.coalesce(func.sum(DetallePedido.cantidad), 0).label("unidades"),
            )
            .join(VarianteProducto, VarianteProducto.id_producto == Producto.id_producto)
            .join(DetallePedido, DetallePedido.id_variante == VarianteProducto.id_variante)
            .join(Pedido, Pedido.id_pedido == DetallePedido.id_pedido)
            .where(Pedido.estado.not_in(("CANCELADO", "EXPIRADO")))
            .group_by(Producto.id_producto, Producto.nombre)
            .order_by(func.sum(DetallePedido.cantidad).desc(), Producto.nombre)
            .limit(3)
        ).mappings()

        orders_by_client = session.execute(
            select(
                Cliente.id_persona,
                func.concat(Persona.nombres, " ", func.coalesce(Persona.apellidos, "")).label(
                    "cliente"
                ),
                func.count(Pedido.id_pedido).label("pedidos"),
            )
            .join(Persona, Persona.id_persona == Cliente.id_persona)
            .outerjoin(Pedido, Pedido.id_cliente == Cliente.id_persona)
            .group_by(Cliente.id_persona, Persona.nombres, Persona.apellidos)
            .order_by(func.count(Pedido.id_pedido).desc(), Cliente.id_persona)
        ).mappings()

        verified_income = session.scalar(
            select(func.coalesce(func.sum(Transaccion.monto_con_signo), 0)).where(
                Transaccion.tipo_transaccion == "PAGO",
                Transaccion.estado_verificacion == "VERIFICADO",
            )
        )

        losses = session.execute(
            select(
                ArticuloInventariable.id_articulo,
                ArticuloInventariable.nombre,
                func.sum(DetallePerdida.cantidad_perdida).label("cantidad_perdida"),
                func.sum(
                    DetallePerdida.cantidad_perdida
                    * DetallePerdida.costo_unitario_historico
                ).label("costo_perdida"),
            )
            .join(
                DetallePerdida,
                DetallePerdida.id_articulo == ArticuloInventariable.id_articulo,
            )
            .group_by(ArticuloInventariable.id_articulo, ArticuloInventariable.nombre)
            .order_by(func.sum(DetallePerdida.cantidad_perdida).desc())
            .limit(3)
        ).mappings()

        supplier_quantities = (
            select(
                Compra.id_proveedor,
                func.coalesce(func.sum(DetalleCompra.cantidad_comprada), 0).label(
                    "articulos_comprados"
                ),
            )
            .join(DetalleCompra, DetalleCompra.id_compra == Compra.id_compra)
            .where(Compra.estado == "CONFIRMADA")
            .group_by(Compra.id_proveedor)
            .subquery()
        )
        supplier_totals = (
            select(
                Compra.id_proveedor,
                func.coalesce(func.sum(Compra.total_compra), 0).label("total_documentado"),
            )
            .where(Compra.estado == "CONFIRMADA")
            .group_by(Compra.id_proveedor)
            .subquery()
        )
        suppliers = session.execute(
            select(
                Proveedor.id_proveedor,
                Proveedor.nombre,
                func.coalesce(supplier_quantities.c.articulos_comprados, 0).label(
                    "articulos_comprados"
                ),
                func.coalesce(supplier_totals.c.total_documentado, 0).label(
                    "total_documentado"
                ),
            )
            .outerjoin(
                supplier_quantities,
                supplier_quantities.c.id_proveedor == Proveedor.id_proveedor,
            )
            .outerjoin(
                supplier_totals,
                supplier_totals.c.id_proveedor == Proveedor.id_proveedor,
            )
            .order_by(
                func.coalesce(supplier_quantities.c.articulos_comprados, 0).desc(),
                Proveedor.nombre,
            )
        ).mappings()

        roles = session.execute(
            select(
                Empleado.id_persona,
                Empleado.codigo_empleado,
                Persona.nombres,
                Persona.apellidos,
                Rol.nombre.label("rol"),
            )
            .join(Persona, Persona.id_persona == Empleado.id_persona)
            .outerjoin(AsignacionRol, AsignacionRol.id_empleado == Empleado.id_persona)
            .outerjoin(Rol, Rol.id_rol == AsignacionRol.id_rol)
            .order_by(Empleado.codigo_empleado, Rol.nombre)
        ).mappings()

        movements = session.execute(
            select(
                MovimientoInventario.id_movimiento,
                ArticuloInventariable.nombre.label("articulo"),
                MovimientoInventario.tipo_movimiento,
                MovimientoInventario.cantidad,
                MovimientoInventario.fecha_hora,
            )
            .join(
                ArticuloInventariable,
                ArticuloInventariable.id_articulo == MovimientoInventario.id_articulo,
            )
            .order_by(MovimientoInventario.fecha_hora.desc())
            .limit(50)
        ).mappings()

        reserved = (
            select(
                ReservaInventario.id_articulo,
                func.sum(ReservaInventario.cantidad_pendiente).label("reservado"),
            )
            .where(ReservaInventario.estado == "ACTIVA")
            .group_by(ReservaInventario.id_articulo)
            .subquery()
        )
        inventory = session.execute(
            select(
                ArticuloInventariable.id_articulo,
                ArticuloInventariable.codigo,
                ArticuloInventariable.nombre,
                ArticuloInventariable.existencia_actual,
                ArticuloInventariable.existencia_minima,
                (
                    ArticuloInventariable.existencia_actual
                    - func.coalesce(reserved.c.reservado, 0)
                ).label("disponible"),
            )
            .outerjoin(reserved, reserved.c.id_articulo == ArticuloInventariable.id_articulo)
            .order_by(ArticuloInventariable.nombre)
        ).mappings()

        return {
            "productos_mas_vendidos": [dict(row) for row in sold],
            "pedidos_por_cliente": [dict(row) for row in orders_by_client],
            "ingresos_verificados": verified_income,
            "perdidas_principales": [dict(row) for row in losses],
            "compras_por_proveedor": [dict(row) for row in suppliers],
            "empleados_roles": [dict(row) for row in roles],
            "movimientos_inventario": [dict(row) for row in movements],
            "inventario": [dict(row) for row in inventory],
        }
