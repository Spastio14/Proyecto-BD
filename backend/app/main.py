from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.engine import Engine

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.exceptions import install_exception_handlers
from app.core.security import AuthenticationProvider, UnconfiguredAuthenticationProvider
from app.db.session import build_engine, build_session_factory, verify_connection


def create_app(
    settings: Settings | None = None,
    *,
    engine: Engine | None = None,
    auth_provider: AuthenticationProvider | None = None,
) -> FastAPI:
    configured = settings or get_settings()
    database_engine = engine or build_engine(configured)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        verify_connection(database_engine)
        yield
        database_engine.dispose()

    application = FastAPI(
        title="Sublimación Doble R API",
        version="2.0.0",
        lifespan=lifespan,
    )
    application.state.engine = database_engine
    application.state.session_factory = build_session_factory(database_engine)
    application.state.auth_provider = auth_provider or UnconfiguredAuthenticationProvider()
    application.include_router(api_router)
    install_exception_handlers(application)
    return application


app = create_app()
