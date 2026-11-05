from collections.abc import Generator

from fastapi import Request
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings


def build_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
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
