from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.engine import Engine

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.exceptions import install_exception_handlers
from app.core.security import (
    AuthenticationProvider,
    CompositeAuthenticationProvider,
    GuestAuthenticationProvider,
    GuestCredentialSigner,
    SupabaseAuthenticationProvider,
    SupabaseTokenVerifier,
    UnconfiguredAuthenticationProvider,
)
from app.db.session import build_engine, build_session_factory, verify_connection
from app.integrations.supabase import SupabaseHTTPClient
from app.services.identity import GuestCoordinator, RegistrationCoordinator
from app.services.storage import StorageCoordinator


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
    factory = build_session_factory(database_engine)
    application.state.session_factory = factory
    application.state.settings = configured
    application.state.auth_gateway = None
    application.state.registration_coordinator = None
    application.state.guest_coordinator = None
    application.state.guest_signer = None
    application.state.storage_coordinator = None

    providers: list[AuthenticationProvider] = []
    if (
        configured.supabase_url
        and configured.supabase_project_ref
        and configured.supabase_public_key
    ):
        public_key = configured.supabase_public_key.get_secret_value()
        secret_key = (
            configured.supabase_secret_key.get_secret_value()
            if configured.supabase_secret_key
            else None
        )
        gateway = SupabaseHTTPClient(configured.supabase_url, public_key, secret_key)
        application.state.auth_gateway = gateway
        if secret_key:
            application.state.registration_coordinator = RegistrationCoordinator(factory, gateway)
            application.state.storage_coordinator = StorageCoordinator(
                factory,
                gateway,
                design_max_bytes=configured.storage_design_max_bytes,
                receipt_max_bytes=configured.storage_receipt_max_bytes,
                signed_url_ttl=configured.storage_signed_url_ttl,
            )
        providers.append(
            SupabaseAuthenticationProvider(
                SupabaseTokenVerifier(
                    project_url=configured.supabase_url,
                    project_ref=configured.supabase_project_ref,
                    audience=configured.supabase_jwt_audience,
                )
            )
        )
    if configured.guest_cookie_secret:
        signer = GuestCredentialSigner(
            configured.guest_cookie_secret.get_secret_value(),
            max_age=configured.guest_cookie_max_age,
        )
        application.state.guest_signer = signer
        application.state.guest_coordinator = GuestCoordinator(factory)
        providers.append(GuestAuthenticationProvider(signer, configured.guest_cookie_name))

    application.state.auth_provider = auth_provider or (
        CompositeAuthenticationProvider(*providers)
        if providers
        else UnconfiguredAuthenticationProvider()
    )
    application.include_router(api_router)
    install_exception_handlers(application)
    return application


app = create_app()
