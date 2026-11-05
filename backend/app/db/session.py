from collections.abc import Generator

from fastapi import Request
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings


def build_engine(settings: Settings) -> Engine:
    connect_args: dict[str, object] = {
        "connect_timeout": settings.db_connect_timeout,
        "sslmode": settings.database_sslmode,
    }
    if settings.database_connection_mode == "transaction_pooler":
        # PgBouncer en modo transaction no conserva prepared statements entre clientes.
        connect_args["prepare_threshold"] = None
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=settings.db_pool_recycle,
        connect_args=connect_args,
    )


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


def verify_connection(engine: Engine) -> None:
    with engine.connect() as connection:
        connection.execute(text("select 1"))


def get_session(request: Request) -> Generator[Session, None, None]:
    factory: sessionmaker[Session] = request.app.state.session_factory
    with factory() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
