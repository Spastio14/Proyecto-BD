from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import Principal, get_principal
from app.db.session import get_session
from app.models.entities import Categoria, Producto, VarianteProducto
from app.schemas.api import (
    CategoryCreate,
    CategoryUpdate,
    CompositionUpsert,
    PriceScaleCreate,
    PriceScaleUpdate,
    PriceScaleUpsert,
    ProductCreate,
    ProductUpdate,
    VariantCreate,
    VariantUpdate,
)
from app.services.catalog_admin import CatalogAdminService

router = APIRouter(prefix="/catalogo", tags=["catalogo"])


@router.get("")
def catalog(session: Session = Depends(get_session)) -> list[dict]:
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
    return [
        {
            "id_variante": variant.id_variante,
            "codigo": variant.codigo_variante,
            "producto": product.nombre,
            "categoria": category.nombre,
            "precio_detalle": variant.precio_detalle,
        }
        for variant, product, category in rows
    ]


def _category(row: Categoria) -> dict:
    return {
        "id_categoria": row.id_categoria,
        "nombre": row.nombre,
        "descripcion": row.descripcion,
        "estado": row.estado,
    }


def _product(row: Producto) -> dict:
    return {
        "id_producto": row.id_producto,
        "id_categoria": row.id_categoria,
        "nombre": row.nombre,
        "descripcion": row.descripcion,
        "informacion_comercial": row.informacion_comercial,
        "estado_publicacion": row.estado_publicacion,
    }


def _variant(row: VarianteProducto) -> dict:
    return {
        "id_variante": row.id_variante,
        "id_producto": row.id_producto,
        "codigo_variante": row.codigo_variante,
        "caracteristicas": row.caracteristicas,
        "precio_detalle": row.precio_detalle,
        "requiere_produccion": row.requiere_produccion,
        "estado": row.estado,
    }


@router.get("/admin/categorias")
def list_categories(
    principal: Principal = Depends(get_principal), session: Session = Depends(get_session)
) -> list[dict]:
    return [_category(row) for row in CatalogAdminService.list_categories(session, principal)]


@router.post("/admin/categorias", status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    return _category(
        CatalogAdminService.create_category(
            session,
            principal=principal,
            name=payload.name,
            description=payload.description,
        )
    )


@router.patch("/admin/categorias/{category_id}")
def update_category(
    category_id: int,
    payload: CategoryUpdate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    return _category(
        CatalogAdminService.update_category(
            session,
            category_id=category_id,
            principal=principal,
            changes=payload.model_dump(exclude_unset=True),
        )
    )


@router.get("/admin/productos")
def list_products(
    principal: Principal = Depends(get_principal), session: Session = Depends(get_session)
) -> list[dict]:
    return [_product(row) for row in CatalogAdminService.list_products(session, principal)]


@router.post("/admin/productos", status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    return _product(
        CatalogAdminService.create_product(session, principal=principal, **payload.model_dump())
    )


@router.patch("/admin/productos/{product_id}")
def update_product(
    product_id: int,
    payload: ProductUpdate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    return _product(
        CatalogAdminService.update_product(
            session,
            product_id=product_id,
            principal=principal,
            changes=payload.model_dump(exclude_unset=True),
        )
    )


@router.get("/admin/variantes")
def list_variants(
    principal: Principal = Depends(get_principal), session: Session = Depends(get_session)
) -> list[dict]:
    return [_variant(row) for row in CatalogAdminService.list_variants(session, principal)]


@router.post("/admin/variantes", status_code=status.HTTP_201_CREATED)
def create_variant(
    payload: VariantCreate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    return _variant(
        CatalogAdminService.create_variant(session, principal=principal, **payload.model_dump())
    )


@router.patch("/admin/variantes/{variant_id}")
def update_variant(
    variant_id: int,
    payload: VariantUpdate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    return _variant(
        CatalogAdminService.update_variant(
            session,
            variant_id=variant_id,
            principal=principal,
            changes=payload.model_dump(exclude_unset=True),
        )
    )


@router.get("/admin/variantes/{variant_id}/escalas")
def list_scales(
    variant_id: int,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> list[dict]:
    return [
        {
            "id_variante": row.id_variante,
            "numero_rango": row.numero_rango,
            "cantidad_minima": row.cantidad_minima,
            "cantidad_maxima": row.cantidad_maxima,
            "precio_unitario_mayorista": row.precio_unitario_mayorista,
            "estado": row.estado,
        }
        for row in CatalogAdminService.list_scales(
            session, variant_id=variant_id, principal=principal
        )
    ]


def _scale(row) -> dict:
    return {
        "id_variante": row.id_variante,
        "numero_rango": row.numero_rango,
        "cantidad_minima": row.cantidad_minima,
        "cantidad_maxima": row.cantidad_maxima,
        "precio_unitario_mayorista": row.precio_unitario_mayorista,
        "estado": row.estado,
    }


@router.post("/admin/variantes/{variant_id}/escalas", status_code=status.HTTP_201_CREATED)
def create_scale(
    variant_id: int,
    payload: PriceScaleCreate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    return _scale(
        CatalogAdminService.create_scale(
            session,
            variant_id=variant_id,
            principal=principal,
            **payload.model_dump(),
        )
    )


@router.patch("/admin/variantes/{variant_id}/escalas/{range_number}")
def update_scale(
    variant_id: int,
    range_number: int,
    payload: PriceScaleUpdate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    return _scale(
        CatalogAdminService.update_scale(
            session,
            variant_id=variant_id,
            number=range_number,
            principal=principal,
            changes=payload.model_dump(exclude_unset=True),
        )
    )


@router.put("/admin/variantes/{variant_id}/escalas/{range_number}")
def upsert_scale(
    variant_id: int,
    range_number: int,
    payload: PriceScaleUpsert,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    data = payload.model_dump()
    if data["range_number"] != range_number:
        data["range_number"] = range_number
    row = CatalogAdminService.upsert_scale(
        session, variant_id=variant_id, principal=principal, **data
    )
    return {
        "id_variante": row.id_variante,
        "numero_rango": row.numero_rango,
        "cantidad_minima": row.cantidad_minima,
        "cantidad_maxima": row.cantidad_maxima,
        "precio_unitario_mayorista": row.precio_unitario_mayorista,
        "estado": row.estado,
    }


@router.get("/admin/variantes/{variant_id}/composicion")
def list_composition(
    variant_id: int,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> list[dict]:
    return CatalogAdminService.composition_overview(
        session,
        variant_id=variant_id,
        principal=principal,
    )


@router.put("/admin/variantes/{variant_id}/composicion/{article_id}")
def upsert_composition(
    variant_id: int,
    article_id: int,
    payload: CompositionUpsert,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    row = CatalogAdminService.upsert_composition(
        session,
        variant_id=variant_id,
        article_id=article_id,
        standard_quantity=payload.standard_quantity,
        observations=payload.observations,
        principal=principal,
    )
    return {
        "id_variante": row.id_variante,
        "id_articulo": row.id_articulo,
        "cantidad_estandar": row.cantidad_estandar,
        "observaciones": row.observaciones,
    }


@router.delete(
    "/admin/variantes/{variant_id}/composicion/{article_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_composition(
    variant_id: int,
    article_id: int,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> Response:
    CatalogAdminService.delete_composition(
        session,
        variant_id=variant_id,
        article_id=article_id,
        principal=principal,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/admin/variantes/{variant_id}/requerimientos")
def composition_requirements(
    variant_id: int,
    cantidad: int = 1,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    return CatalogAdminService.requirements(
        session,
        variant_id=variant_id,
        quantity=cantidad,
        principal=principal,
    )
