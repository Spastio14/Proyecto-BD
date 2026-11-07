from decimal import Decimal

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.core.exceptions import Conflict, NotFound
from app.core.security import Principal
from app.domain.money import money
from app.models.entities import (
    ArticuloInventariable,
    Categoria,
    ComposicionProducto,
    DetallePedido,
    EscalaPrecio,
    Pedido,
    Producto,
    ReservaInventario,
    VarianteProducto,
)
from app.services.audit import AuditService
from app.services.authorization import AuthorizationService
from app.services.inventory import InventoryService


class CatalogAdminService:
    PERMISSION = "CATALOGO_GESTIONAR"

    @classmethod
    def _authorize(cls, session: Session, principal: Principal) -> None:
        AuthorizationService.require(session, principal, cls.PERMISSION)

    @classmethod
    def list_categories(cls, session: Session, principal: Principal) -> list[Categoria]:
        cls._authorize(session, principal)
        return list(session.scalars(select(Categoria).order_by(Categoria.nombre)))

    @classmethod
    def create_category(
        cls, session: Session, *, principal: Principal, name: str, description: str | None
    ) -> Categoria:
        cls._authorize(session, principal)
        category = Categoria(nombre=name.strip(), descripcion=description, estado="ACTIVA")
        session.add(category)
        session.flush()
        cls._audit(session, principal, "CREAR_CATEGORIA", "CATEGORIA", category.id_categoria)
        return category

    @classmethod
    def update_category(
        cls, session: Session, *, category_id: int, principal: Principal, changes: dict
    ) -> Categoria:
        cls._authorize(session, principal)
        category = session.get(Categoria, category_id)
        if category is None:
            raise NotFound("Categoría no encontrada")
        before = {"nombre": category.nombre, "estado": category.estado}
        mapping = {"name": "nombre", "description": "descripcion", "state": "estado"}
        cls._apply(category, changes, mapping)
        session.flush()
        cls._audit(
            session,
            principal,
            "ACTUALIZAR_CATEGORIA",
            "CATEGORIA",
            category_id,
            before,
            {"nombre": category.nombre, "estado": category.estado},
        )
        return category

    @classmethod
    def list_products(cls, session: Session, principal: Principal) -> list[Producto]:
        cls._authorize(session, principal)
        return list(session.scalars(select(Producto).order_by(Producto.nombre)))

    @classmethod
    def create_product(cls, session: Session, *, principal: Principal, **data) -> Producto:
        cls._authorize(session, principal)
        cls._active_category(session, data["category_id"])
        product = Producto(
            id_categoria=data["category_id"],
            nombre=data["name"].strip(),
            descripcion=data["description"],
            informacion_comercial=data["commercial_information"].strip(),
            estado_publicacion=data["publication_state"],
        )
        session.add(product)
        session.flush()
        cls._audit(session, principal, "CREAR_PRODUCTO", "PRODUCTO", product.id_producto)
        return product

    @classmethod
    def update_product(
        cls, session: Session, *, product_id: int, principal: Principal, changes: dict
    ) -> Producto:
        cls._authorize(session, principal)
        product = session.get(Producto, product_id)
        if product is None:
            raise NotFound("Producto no encontrado")
        if "category_id" in changes:
            cls._active_category(session, changes["category_id"])
        mapping = {
            "category_id": "id_categoria",
            "name": "nombre",
            "description": "descripcion",
            "commercial_information": "informacion_comercial",
            "publication_state": "estado_publicacion",
        }
        before = {"nombre": product.nombre, "estado": product.estado_publicacion}
        cls._apply(product, changes, mapping)
        session.flush()
        cls._audit(
            session,
            principal,
            "ACTUALIZAR_PRODUCTO",
            "PRODUCTO",
            product_id,
            before,
            {"nombre": product.nombre, "estado": product.estado_publicacion},
        )
        return product

    @classmethod
    def list_variants(cls, session: Session, principal: Principal) -> list[VarianteProducto]:
        cls._authorize(session, principal)
        return list(
            session.scalars(select(VarianteProducto).order_by(VarianteProducto.codigo_variante))
        )

    @classmethod
    def create_variant(cls, session: Session, *, principal: Principal, **data) -> VarianteProducto:
        cls._authorize(session, principal)
        cls._product(session, data["product_id"])
        code = data["code"].strip().upper()
        cls._unique_variant_code(session, code)
        variant = VarianteProducto(
            id_producto=data["product_id"],
            codigo_variante=code,
            caracteristicas=data["features"],
            precio_detalle=money(data["retail_price"]),
            requiere_produccion=data["requires_production"],
            estado="ACTIVA",
        )
        session.add(variant)
        session.flush()
        cls._audit(session, principal, "CREAR_VARIANTE", "VARIANTE_PRODUCTO", variant.id_variante)
        return variant

    @classmethod
    def update_variant(
        cls, session: Session, *, variant_id: int, principal: Principal, changes: dict
    ) -> VarianteProducto:
        cls._authorize(session, principal)
        variant = cls._variant(session, variant_id)
        if "product_id" in changes:
            cls._product(session, changes["product_id"])
        if "code" in changes:
            changes["code"] = changes["code"].strip().upper()
            cls._unique_variant_code(session, changes["code"], exclude=variant_id)
        if "retail_price" in changes:
            changes["retail_price"] = money(changes["retail_price"])
        mapping = {
            "product_id": "id_producto",
            "code": "codigo_variante",
            "features": "caracteristicas",
            "retail_price": "precio_detalle",
            "requires_production": "requiere_produccion",
            "state": "estado",
        }
        before = {"codigo": variant.codigo_variante, "estado": variant.estado}
        cls._apply(variant, changes, mapping)
        session.flush()
        cls._audit(
            session,
            principal,
            "ACTUALIZAR_VARIANTE",
            "VARIANTE_PRODUCTO",
            variant_id,
            before,
            {"codigo": variant.codigo_variante, "estado": variant.estado},
        )
        return variant

    @classmethod
    def list_scales(
        cls, session: Session, *, variant_id: int, principal: Principal
    ) -> list[EscalaPrecio]:
        cls._authorize(session, principal)
        cls._variant(session, variant_id)
        return list(
            session.scalars(
                select(EscalaPrecio)
                .where(EscalaPrecio.id_variante == variant_id)
                .order_by(EscalaPrecio.numero_rango)
            )
        )

    @classmethod
    def upsert_scale(
        cls, session: Session, *, variant_id: int, principal: Principal, **data
    ) -> EscalaPrecio:
        cls._authorize(session, principal)
        cls._variant(session, variant_id)
        number = data["range_number"]
        if data["state"] == "ACTIVA":
            cls._ensure_scale_does_not_overlap(
                session,
                variant_id=variant_id,
                number=number,
                minimum=data["minimum_quantity"],
                maximum=data["maximum_quantity"],
            )
        scale = session.get(EscalaPrecio, (variant_id, number))
        action = "ACTUALIZAR_ESCALA_PRECIO" if scale else "CREAR_ESCALA_PRECIO"
        if scale is None:
            scale = EscalaPrecio(id_variante=variant_id, numero_rango=number)
            session.add(scale)
        scale.cantidad_minima = data["minimum_quantity"]
        scale.cantidad_maxima = data["maximum_quantity"]
        scale.precio_unitario_mayorista = money(data["wholesale_unit_price"])
        scale.estado = data["state"]
        session.flush()
        cls._audit(session, principal, action, "ESCALA_PRECIO", f"{variant_id}:{number}")
        return scale

    @classmethod
    def list_composition(
        cls, session: Session, *, variant_id: int, principal: Principal
    ) -> list[ComposicionProducto]:
        cls._authorize(session, principal)
        cls._variant(session, variant_id)
        return list(
            session.scalars(
                select(ComposicionProducto)
                .where(ComposicionProducto.id_variante == variant_id)
                .order_by(ComposicionProducto.id_articulo)
            )
        )

    @classmethod
    def upsert_composition(
        cls,
        session: Session,
        *,
        variant_id: int,
        article_id: int,
        standard_quantity: Decimal,
        observations: str,
        principal: Principal,
    ) -> ComposicionProducto:
        cls._authorize(session, principal)
        cls._variant(session, variant_id)
        article = session.get(ArticuloInventariable, article_id)
        if article is None or article.estado != "ACTIVO":
            raise NotFound("Artículo inventariable activo no encontrado")
        cls._ensure_recipe_editable(session, variant_id)
        row = session.get(ComposicionProducto, (variant_id, article_id))
        action = "ACTUALIZAR_COMPOSICION" if row else "CREAR_COMPOSICION"
        if row is None:
            row = ComposicionProducto(id_variante=variant_id, id_articulo=article_id)
            session.add(row)
        row.cantidad_estandar = standard_quantity
        row.observaciones = observations
        session.flush()
        cls._audit(session, principal, action, "COMPOSICION_PRODUCTO", f"{variant_id}:{article_id}")
        return row

    @classmethod
    def delete_composition(
        cls,
        session: Session,
        *,
        variant_id: int,
        article_id: int,
        principal: Principal,
    ) -> None:
        cls._authorize(session, principal)
        cls._ensure_recipe_editable(session, variant_id)
        row = session.get(ComposicionProducto, (variant_id, article_id))
        if row is None:
            raise NotFound("Componente no encontrado")
        session.delete(row)
        cls._audit(
            session,
            principal,
            "ELIMINAR_COMPOSICION",
            "COMPOSICION_PRODUCTO",
            f"{variant_id}:{article_id}",
        )

    @classmethod
    def requirements(
        cls, session: Session, *, variant_id: int, quantity: int, principal: Principal
    ) -> dict[str, object]:
        cls._authorize(session, principal)
        variant = cls._variant(session, variant_id)
        if quantity <= 0:
            raise Conflict("La cantidad solicitada debe ser positiva")
        composition = cls.list_composition(session, variant_id=variant_id, principal=principal)
        rows = []
        total_cost = Decimal("0.0000")
        for item in composition:
            article = session.get(ArticuloInventariable, item.id_articulo)
            required = item.cantidad_estandar * quantity
            available = InventoryService.availability(session, item.id_articulo)
            cost = required * article.costo_referencia
            total_cost += cost
            rows.append(
                {
                    "id_articulo": article.id_articulo,
                    "codigo": article.codigo,
                    "nombre": article.nombre,
                    "unidad_medida": article.unidad_medida,
                    "cantidad_estandar": item.cantidad_estandar,
                    "cantidad_requerida": required,
                    "disponible": available,
                    "faltante": max(required - available, Decimal("0.000")),
                    "costo_estimado": money(cost),
                }
            )
        incomplete = variant.requiere_produccion and not rows
        return {
            "id_variante": variant_id,
            "cantidad": quantity,
            "composicion_incompleta": incomplete,
            "disponible_para_producir": bool(rows) and all(row["faltante"] == 0 for row in rows),
            "costo_estimado": money(total_cost),
            "requerimientos": rows,
        }

    @staticmethod
    def _apply(instance, changes: dict, mapping: dict[str, str]) -> None:
        for source, value in changes.items():
            if source in mapping:
                setattr(
                    instance, mapping[source], value.strip() if isinstance(value, str) else value
                )

    @staticmethod
    def _active_category(session: Session, category_id: int) -> Categoria:
        category = session.get(Categoria, category_id)
        if category is None or category.estado != "ACTIVA":
            raise NotFound("Categoría activa no encontrada")
        return category

    @staticmethod
    def _product(session: Session, product_id: int) -> Producto:
        product = session.get(Producto, product_id)
        if product is None:
            raise NotFound("Producto no encontrado")
        return product

    @staticmethod
    def _variant(session: Session, variant_id: int) -> VarianteProducto:
        variant = session.get(VarianteProducto, variant_id)
        if variant is None:
            raise NotFound("Variante no encontrada")
        return variant

    @staticmethod
    def _unique_variant_code(session: Session, code: str, exclude: int | None = None) -> None:
        statement = select(VarianteProducto.id_variante).where(
            VarianteProducto.codigo_variante == code
        )
        if exclude is not None:
            statement = statement.where(VarianteProducto.id_variante != exclude)
        if session.scalar(statement) is not None:
            raise Conflict("El código de variante ya existe")

    @staticmethod
    def _ensure_scale_does_not_overlap(
        session: Session,
        *,
        variant_id: int,
        number: int,
        minimum: int,
        maximum: int | None,
    ) -> None:
        upper = maximum if maximum is not None else 2_147_483_647
        scales = session.scalars(
            select(EscalaPrecio).where(
                EscalaPrecio.id_variante == variant_id,
                EscalaPrecio.numero_rango != number,
                EscalaPrecio.estado == "ACTIVA",
            )
        )
        for scale in scales:
            other_upper = scale.cantidad_maxima or 2_147_483_647
            if minimum <= other_upper and scale.cantidad_minima <= upper:
                raise Conflict("El rango mayorista se solapa con una escala activa")

    @staticmethod
    def _ensure_recipe_editable(session: Session, variant_id: int) -> None:
        unreserved_order = session.scalar(
            select(Pedido.id_pedido)
            .join(DetallePedido, DetallePedido.id_pedido == Pedido.id_pedido)
            .where(
                DetallePedido.id_variante == variant_id,
                Pedido.estado.not_in(("CANCELADO", "EXPIRADO", "ENTREGADO")),
                ~exists().where(ReservaInventario.id_pedido == Pedido.id_pedido),
            )
            .limit(1)
        )
        if unreserved_order is not None:
            raise Conflict(
                "La composición no puede cambiar mientras exista un pedido activo "
                "sin reserva histórica"
            )

    @staticmethod
    def _audit(
        session: Session,
        principal: Principal,
        action: str,
        object_type: str,
        reference,
        before=None,
        after=None,
    ) -> None:
        AuditService.record(
            session,
            principal=principal,
            action=action,
            object_type=object_type,
            object_reference=str(reference),
            reason="Gestión administrativa de catálogo",
            before=before,
            after=after,
        )
