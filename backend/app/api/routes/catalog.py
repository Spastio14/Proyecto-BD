from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.entities import Categoria, Producto, VarianteProducto

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
