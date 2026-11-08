from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from time import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.core.exceptions import AuthenticationRequired, Conflict, PermissionDenied
from app.core.security import GuestCredentialSigner, SupabaseAuthenticationProvider
from app.main import create_app
from app.models.entities import (
    ArticuloInventariable,
    DetallePerdida,
    HistorialPedido,
    MovimientoInventario,
    ReservaInventario,
    Transaccion,
)
from app.services.designs import DesignService
from app.services.identity import RegistrationCoordinator
from app.services.inventory import InventoryService
from app.services.losses import LossLineInput, LossService
from app.services.orders import OrderService
from app.services.payments import PaymentService
from app.services.production import ProductionService
from app.services.quotations import QuotationService, QuoteLineInput
from app.services.storage import StorageCoordinator
from tests.helpers import add_client, create_order
from tests.integration.test_payments_inventory import report_payment
from tests.integration.test_supabase_phase3 import (
    FakeGateway,
    FakeVerifier,
    request,
    storage,
)

pytestmark = pytest.mark.integration


def test_96_guest_cookie_has_secure_attributes(engine):
    settings = Settings(
        database_url=str(engine.url),
        app_env="test",
        guest_cookie_secret="fase-4-cookie-secret-seguro-1234567890",
    )
    with TestClient(create_app(settings, engine=engine)) as client:
        response = client.post(
            "/api/v1/auth/invitado",
            json={"names": "Invitado Ficticio", "phone": None},
        )
    assert response.status_code == 201
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=strict" in cookie
    assert "max-age=" in cookie


def test_97_expired_guest_cookie_is_rejected(monkeypatch):
    signer = GuestCredentialSigner("fase-4-cookie-secret-seguro-1234567890", max_age=300)
    credential = signer.issue(1)
    current = time()
    monkeypatch.setattr("cryptography.fernet.time.time", lambda: current + 301)
    with pytest.raises(AuthenticationRequired, match="vencida"):
        signer.verify(credential)


def test_98_rejected_payment_never_reserves_inventory(session, customer, employee):
    order = create_order(session, customer)
    payment = report_payment(session, order, customer)
    PaymentService().reject(
        session,
        payment_id=payment.id_transaccion,
        principal=employee,
        reason="Comprobante inválido",
    )
    assert payment.estado_verificacion == "RECHAZADO"
    assert order.estado == "PENDIENTE_PAGO"
    assert (
        session.scalar(
            select(func.count())
            .select_from(ReservaInventario)
            .where(ReservaInventario.id_pedido == order.id_pedido)
        )
        == 0
    )


@pytest.mark.concurrency
def test_99_concurrent_confirmation_of_same_payment_is_idempotent(engine, session, employee):
    customer = add_client(session)
    order = create_order(session, customer)
    payment = report_payment(session, order, customer)
    payment_id = payment.id_transaccion
    order_id = order.id_pedido
    session.commit()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    barrier = Barrier(2)

    def confirm() -> str:
        with factory() as worker:
            barrier.wait()
            PaymentService().confirm(worker, payment_id=payment_id, principal=employee)
            worker.commit()
            return "ok"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(lambda _: confirm(), range(2))) == ["ok", "ok"]
    with factory() as verification:
        assert (
            verification.scalar(
                select(func.count())
                .select_from(ReservaInventario)
                .where(ReservaInventario.id_pedido == order_id)
            )
            == 1
        )


def test_100_availability_tracks_reservation_and_consumption(session, customer, employee):
    article = session.get(ArticuloInventariable, 1)
    initial_stock = article.existencia_actual
    initial_available = InventoryService.availability(session, 1)
    order = create_order(session, customer, quantity=2)
    payment = report_payment(session, order, customer)
    PaymentService().confirm(session, payment_id=payment.id_transaccion, principal=employee)
    assert InventoryService.availability(session, 1) == initial_available - Decimal("2.000")
    order.estado = "EN_PRODUCCION"
    InventoryService().consume_order(session, order_id=order.id_pedido, principal=employee)
    assert article.existencia_actual == initial_stock - Decimal("2.000")
    assert InventoryService.availability(session, 1) == initial_available - Decimal("2.000")


@pytest.mark.concurrency
def test_101_concurrent_loss_confirmation_affects_inventory_once(engine, session, employee):
    loss = LossService().report(
        session,
        principal=employee,
        moment="FUERA_PRODUCCION",
        incident_type="DANO_ALMACENAMIENTO",
        reason="Pérdida concurrente ficticia",
    )
    loss_id = loss.id_perdida
    initial = session.get(ArticuloInventariable, 1).existencia_actual
    session.commit()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    barrier = Barrier(2)

    def confirm() -> str:
        with factory() as worker:
            barrier.wait()
            LossService().confirm(
                worker,
                loss_id=loss_id,
                lines=[LossLineInput(article_id=1, quantity=Decimal("1.000"))],
                principal=employee,
            )
            worker.commit()
            return "ok"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(lambda _: confirm(), range(2))) == ["ok", "ok"]
    with factory() as verification:
        assert verification.get(ArticuloInventariable, 1).existencia_actual == initial - Decimal(
            "1.000"
        )
        assert (
            verification.scalar(
                select(func.count())
                .select_from(DetallePerdida)
                .where(DetallePerdida.id_perdida == loss_id)
            )
            == 1
        )


def test_102_loss_cost_is_reproducible_from_historical_lines(session, employee):
    loss = LossService().report(
        session,
        principal=employee,
        moment="FUERA_PRODUCCION",
        incident_type="ROTURA_ARTICULO",
        reason="Taza rota ficticia",
    )
    LossService().confirm(
        session,
        loss_id=loss.id_perdida,
        lines=[LossLineInput(article_id=1, quantity=Decimal("2.000"))],
        principal=employee,
    )
    cost = session.scalar(
        select(
            func.sum(DetallePerdida.cantidad_perdida * DetallePerdida.costo_unitario_historico)
        ).where(DetallePerdida.id_perdida == loss.id_perdida)
    )
    assert cost == Decimal("50.0000000")


@pytest.mark.parametrize(
    ("file_name", "content_type", "content"),
    [
        ("arte.png", "image/png", b"\x89PNG\r\n\x1a\ncontenido"),
        ("arte.jpg", "image/jpeg", b"\xff\xd8\xffcontenido"),
        ("arte.jpeg", "image/jpeg", b"\xff\xd8\xffcontenido"),
        ("arte.pdf", "application/pdf", b"%PDF-contenido"),
    ],
)
def test_103_storage_accepts_only_matching_supported_files(file_name, content_type, content):
    StorageCoordinator._validate(content, content_type, 1024)
    assert StorageCoordinator._suffix(file_name, content_type) in {".png", ".jpg", ".pdf"}


def test_104_storage_rejects_oversized_or_mismatched_content():
    with pytest.raises(Conflict, match="tamaño"):
        StorageCoordinator._validate(b"%PDF-" + b"x" * 20, "application/pdf", 10)
    with pytest.raises(Conflict, match="contenido"):
        StorageCoordinator._validate(b"contenido falso", "image/png", 1024)
    with pytest.raises(Conflict, match="extensión"):
        StorageCoordinator._suffix("arte.pdf", "image/png")


@pytest.mark.concurrency
def test_105_concurrent_receipt_upload_keeps_one_object_and_compensates_other(
    engine, session, customer
):
    order = create_order(session, customer)
    payment = report_payment(session, order, customer)
    payment_id = payment.id_transaccion
    session.commit()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    barrier = Barrier(2)

    class ConcurrentGateway(FakeGateway):
        def upload(self, *, bucket, path, content, content_type):
            super().upload(
                bucket=bucket,
                path=path,
                content=content,
                content_type=content_type,
            )
            barrier.wait()

    gateway = ConcurrentGateway()
    coordinator = storage(factory, gateway)

    def upload(number: int) -> str:
        try:
            coordinator.upload_receipt(
                payment_id=payment_id,
                file_name=f"comprobante-{number}.pdf",
                content_type="application/pdf",
                content=b"%PDF-ficticio",
                principal=customer,
            )
            return "stored"
        except Conflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(upload, [1, 2]))
    assert sorted(results) == ["conflict", "stored"]
    assert len(gateway.uploaded) == 2
    assert len(gateway.removed) == 1
    with factory() as verification:
        saved = verification.get(Transaccion, payment_id)
        assert saved.ruta_comprobante is not None
        assert gateway.removed[0][1] != saved.ruta_comprobante


def test_106_scenario_a_registered_customer_complete_business_flow(engine, employee):
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    gateway = FakeGateway()
    RegistrationCoordinator(factory, gateway).register(
        names="Cliente",
        surnames="Fase Cuatro",
        email="cliente-fase4@example.test",
        phone=None,
        password="password-ficticio",
    )
    with factory() as session, session.begin():
        customer = SupabaseAuthenticationProvider(
            FakeVerifier({"sub": gateway.auth_id})
        ).authenticate(request(bearer="jwt-verificado"), session)
        quote = QuotationService().create(
            session,
            principal=customer,
            lines=[QuoteLineInput(variant_id=1, quantity=2, customization="Logo ficticio")],
        )
        quote.estado = "ACEPTADA"
        order = QuotationService().convert(
            session, quote_id=quote.id_cotizacion, principal=customer
        )
        payment = report_payment(session, order, customer)
        PaymentService().confirm(session, payment_id=payment.id_transaccion, principal=employee)
        OrderService().transition(
            session,
            order_id=order.id_pedido,
            target="EN_DISENO",
            principal=employee,
            reason="Diseño solicitado",
        )
        version = DesignService().add_version(
            session,
            order_id=order.id_pedido,
            line_number=1,
            file_name="arte.png",
            private_path="pedidos/fase4/arte.png",
            principal=employee,
        )
        DesignService().decide(
            session,
            order_id=order.id_pedido,
            line_number=1,
            version_number=version.numero_version,
            approved=True,
            principal=customer,
        )
        ProductionService().start(session, order_id=order.id_pedido, principal=employee)
        assert order.estado == "EN_PRODUCCION"
        assert (
            session.scalar(
                select(func.count())
                .select_from(HistorialPedido)
                .where(HistorialPedido.id_pedido == order.id_pedido)
            )
            >= 3
        )


def test_107_scenario_b_guest_limits_are_enforced_end_to_end(engine):
    settings = Settings(
        database_url=str(engine.url),
        app_env="test",
        guest_cookie_secret="fase-4-cookie-secret-seguro-1234567890",
    )
    with TestClient(create_app(settings, engine=engine), base_url="https://testserver") as client:
        assert (
            client.post(
                "/api/v1/auth/invitado",
                json={"names": "Invitado Fase Cuatro", "phone": None},
            ).status_code
            == 201
        )
        assert client.get("/api/v1/catalogo").status_code == 200
        first = client.post(
            "/api/v1/pedidos",
            json={"lines": [{"variant_id": 1, "quantity": 5}]},
        )
        assert first.status_code == 201
        assert first.json()["total_pedido"] == "450.00"
        assert (
            client.post(
                "/api/v1/pedidos",
                json={"lines": [{"variant_id": 1, "quantity": 6}]},
            ).status_code
            == 409
        )
        assert (
            client.post(
                "/api/v1/pedidos",
                json={"lines": [{"variant_id": 1, "quantity": 1}]},
            ).status_code
            == 409
        )


def test_108_scenario_c_loss_during_production_creates_costed_movement(session, customer, employee):
    order = create_order(session, customer)
    payment = report_payment(session, order, customer)
    PaymentService().confirm(session, payment_id=payment.id_transaccion, principal=employee)
    OrderService().transition(
        session,
        order_id=order.id_pedido,
        target="EN_DISENO",
        principal=employee,
        reason="Diseño de prueba",
    )
    version = DesignService().add_version(
        session,
        order_id=order.id_pedido,
        line_number=1,
        file_name="perdida.png",
        private_path="pedidos/fase4/perdida.png",
        principal=employee,
    )
    DesignService().decide(
        session,
        order_id=order.id_pedido,
        line_number=1,
        version_number=version.numero_version,
        approved=True,
        principal=customer,
    )
    ProductionService().start(session, order_id=order.id_pedido, principal=employee)
    loss = LossService().report(
        session,
        principal=employee,
        moment="DURANTE_PRODUCCION",
        incident_type="SUBLIMACION_DEFECTUOSA",
        reason="Taza dañada durante prueba",
        order_id=order.id_pedido,
        stage_id=3,
    )
    LossService().confirm(
        session,
        loss_id=loss.id_perdida,
        lines=[LossLineInput(article_id=1, quantity=Decimal("1.000"))],
        principal=employee,
    )
    movement = session.scalar(
        select(MovimientoInventario).where(MovimientoInventario.id_pedido == order.id_pedido)
    )
    assert movement.tipo_movimiento == "SALIDA_PERDIDA"
    assert movement.costo_unitario_aplicado == Decimal("25.0000")


def test_109_scenario_e_cross_customer_private_resources_are_denied(engine, session):
    owner = add_client(session)
    attacker = add_client(session)
    order = create_order(session, owner)
    payment = report_payment(session, order, owner)
    payment.ruta_comprobante = "transacciones/fase4/privado.pdf"
    payment.comprobante_mime = "application/pdf"
    payment.comprobante_tamano_bytes = 100
    order_id = order.id_pedido
    payment_id = payment.id_transaccion
    session.commit()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    coordinator = storage(factory, FakeGateway())
    with factory() as verification:
        with pytest.raises(PermissionDenied):
            OrderService.get_owned(verification, order_id=order_id, principal=attacker)
        with pytest.raises(PermissionDenied):
            coordinator.receipt_url(verification, payment_id=payment_id, principal=attacker)
