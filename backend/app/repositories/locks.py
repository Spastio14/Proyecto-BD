from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFound
from app.models.entities import ArticuloInventariable, Cliente, Pedido, Transaccion


def lock_client(session: Session, client_id: int) -> Cliente:
    client = session.scalar(
        select(Cliente).where(Cliente.id_persona == client_id).with_for_update()
    )
    if client is None:
        raise NotFound("Cliente no encontrado")
    return client


def lock_order(session: Session, order_id: int) -> Pedido:
    order = session.scalar(select(Pedido).where(Pedido.id_pedido == order_id).with_for_update())
    if order is None:
        raise NotFound("Pedido no encontrado")
    return order


def lock_payment(session: Session, payment_id: int) -> Transaccion:
    payment = session.scalar(
        select(Transaccion)
        .where(Transaccion.id_transaccion == payment_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if payment is None:
        raise NotFound("Transacción no encontrada")
    return payment


def lock_articles(session: Session, article_ids: set[int]) -> list[ArticuloInventariable]:
    if not article_ids:
        return []
    statement: Select[tuple[ArticuloInventariable]] = (
        select(ArticuloInventariable)
        .where(ArticuloInventariable.id_articulo.in_(sorted(article_ids)))
        .order_by(ArticuloInventariable.id_articulo)
        .with_for_update()
    )
    articles = list(session.scalars(statement))
    if len(articles) != len(article_ids):
        raise NotFound("Artículo inventariable no encontrado")
    return articles
