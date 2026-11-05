from app.core.config import get_settings
from app.db.session import build_engine, build_session_factory
from app.services.expiration import OrderExpirationService


def main() -> None:
    engine = build_engine(get_settings())
    factory = build_session_factory(engine)
    try:
        with factory.begin() as session:
            expired = OrderExpirationService().expire_due(session)
        print(f"Pedidos expirados: {expired}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
