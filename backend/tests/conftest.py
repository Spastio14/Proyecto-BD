import os
from collections.abc import Callable, Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.security import Principal, UnconfiguredAuthenticationProvider
from app.main import create_app

ADMIN_URL = os.environ["TEST_ADMIN_DATABASE_URL"]
TEMPLATE_DATABASE = os.getenv("TEST_TEMPLATE_DATABASE", "s2r_backend_template")


class FixedAuthenticationProvider:
    def __init__(self, principal: Principal):
        self.principal = principal

    def authenticate(self, request, session):
        return self.principal


@pytest.fixture
def database_url() -> Generator[str, None, None]:
    name = f"s2r_test_{uuid4().hex}"
    admin_url = make_url(ADMIN_URL)
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as connection:
        connection.execute(text(f'create database "{name}" template "{TEMPLATE_DATABASE}"'))
    test_url = admin_url.set(database=name)
    try:
        yield test_url.render_as_string(hide_password=False)
    finally:
        with admin_engine.connect() as connection:
            connection.execute(
                text(
                    "select pg_terminate_backend(pid) from pg_stat_activity where datname = :name"
                ),
                {"name": name},
            )
            connection.execute(text(f'drop database if exists "{name}"'))
        admin_engine.dispose()


@pytest.fixture
def engine(database_url: str) -> Generator[Engine, None, None]:
    database_engine = create_engine(database_url, pool_pre_ping=True)
    yield database_engine
    database_engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Generator[Session, None, None]:
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        yield db
        db.rollback()


@pytest.fixture
def guest() -> Principal:
    return Principal(persona_id=1, origin="CLIENTE")


@pytest.fixture
def customer() -> Principal:
    return Principal(persona_id=2, origin="CLIENTE")


@pytest.fixture
def employee() -> Principal:
    return Principal(persona_id=3, origin="EMPLEADO")


@pytest.fixture
def api_client_factory(engine: Engine) -> Callable[[Principal | None], TestClient]:
    clients: list[TestClient] = []

    def factory(principal: Principal | None) -> TestClient:
        provider = (
            FixedAuthenticationProvider(principal)
            if principal is not None
            else UnconfiguredAuthenticationProvider()
        )
        settings = Settings(database_url=str(engine.url), app_env="test")
        client = TestClient(create_app(settings, engine=engine, auth_provider=provider))
        client.__enter__()
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.__exit__(None, None, None)
