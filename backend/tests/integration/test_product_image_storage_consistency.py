import logging

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import Conflict, PermissionDenied
from app.models.entities import Producto
from app.services.audit import AuditService
from app.services.storage import CATALOG_BUCKET, StorageCoordinator

pytestmark = pytest.mark.integration

PNG = b"\x89PNG\r\n\x1a\ncontenido"
OLD_PATH = "productos/1/11111111111111111111111111111111.png"


class StatefulStorage:
    def __init__(self):
        self.objects: dict[tuple[str, str], bytes] = {}
        self.uploads: list[tuple[str, str]] = []
        self.delete_attempts: list[tuple[str, str]] = []
        self.fail_upload = False
        self.fail_delete_paths: set[str] = set()

    def upload(self, *, bucket, path, content, content_type):
        if self.fail_upload:
            raise RuntimeError("storage upload failed")
        self.uploads.append((bucket, path))
        self.objects[(bucket, path)] = content

    def delete(self, *, bucket, path):
        self.delete_attempts.append((bucket, path))
        if path in self.fail_delete_paths:
            raise RuntimeError("storage delete failed")
        self.objects.pop((bucket, path), None)

    def signed_url(self, *, bucket, path, expires_in):
        return f"https://storage.test/{bucket}/{path}?ttl={expires_in}"


def coordinator(engine, gateway):
    return StorageCoordinator(
        sessionmaker(bind=engine, expire_on_commit=False),
        gateway,
        design_max_bytes=1_000_000,
        receipt_max_bytes=1_000_000,
        product_max_bytes=1_000_000,
        signed_url_ttl=120,
    )


def set_product_image(session, path=OLD_PATH):
    product = session.get(Producto, 1)
    product.ruta_imagen_principal = path
    product.imagen_mime = "image/png"
    product.imagen_tamano_bytes = len(PNG)
    session.commit()


def upload(service, employee):
    return service.upload_product_image(
        product_id=1,
        file_name="catalogo.png",
        content_type="image/png",
        content=PNG,
        principal=employee,
    )


def test_first_product_image_is_uploaded_and_referenced(session, engine, employee):
    gateway = StatefulStorage()

    product = upload(coordinator(engine, gateway), employee)

    session.expire_all()
    stored_path = session.get(Producto, 1).ruta_imagen_principal
    assert stored_path == product.ruta_imagen_principal
    assert (CATALOG_BUCKET, stored_path) in gateway.objects
    assert gateway.delete_attempts == []


def test_existing_product_image_is_replaced_after_commit(session, engine, employee):
    set_product_image(session)
    gateway = StatefulStorage()
    gateway.objects[(CATALOG_BUCKET, OLD_PATH)] = PNG

    product = upload(coordinator(engine, gateway), employee)

    assert (CATALOG_BUCKET, OLD_PATH) not in gateway.objects
    assert (CATALOG_BUCKET, product.ruta_imagen_principal) in gateway.objects
    assert gateway.delete_attempts == [(CATALOG_BUCKET, OLD_PATH)]


def test_storage_upload_failure_preserves_database_reference(session, engine, employee):
    set_product_image(session)
    gateway = StatefulStorage()
    gateway.objects[(CATALOG_BUCKET, OLD_PATH)] = PNG
    gateway.fail_upload = True

    with pytest.raises(RuntimeError, match="upload failed"):
        upload(coordinator(engine, gateway), employee)

    session.expire_all()
    assert session.get(Producto, 1).ruta_imagen_principal == OLD_PATH
    assert gateway.delete_attempts == []
    assert (CATALOG_BUCKET, OLD_PATH) in gateway.objects


def test_database_failure_removes_new_upload_and_preserves_old_reference(
    session, engine, employee, monkeypatch
):
    set_product_image(session)
    gateway = StatefulStorage()
    gateway.objects[(CATALOG_BUCKET, OLD_PATH)] = PNG

    def fail_database_write(database_session, **kwargs):
        database_session.execute(text("select * from catalog_table_that_does_not_exist"))

    monkeypatch.setattr(AuditService, "record", fail_database_write)
    with pytest.raises(ProgrammingError):
        upload(coordinator(engine, gateway), employee)

    session.expire_all()
    assert session.get(Producto, 1).ruta_imagen_principal == OLD_PATH
    assert gateway.objects == {(CATALOG_BUCKET, OLD_PATH): PNG}
    assert len(gateway.delete_attempts) == 1
    assert gateway.delete_attempts[0][1] != OLD_PATH


def test_post_commit_cleanup_failure_keeps_new_image_and_reports_candidate(
    session, engine, employee, caplog
):
    set_product_image(session)
    gateway = StatefulStorage()
    gateway.objects[(CATALOG_BUCKET, OLD_PATH)] = PNG
    gateway.fail_delete_paths.add(OLD_PATH)

    with caplog.at_level(logging.WARNING, logger="app.services.storage"):
        product = upload(coordinator(engine, gateway), employee)

    session.expire_all()
    assert session.get(Producto, 1).ruta_imagen_principal == product.ruta_imagen_principal
    assert (CATALOG_BUCKET, product.ruta_imagen_principal) in gateway.objects
    assert (CATALOG_BUCKET, OLD_PATH) in gateway.objects
    assert (CATALOG_BUCKET, product.ruta_imagen_principal) not in gateway.delete_attempts
    assert "catalog_image_cleanup_pending" in caplog.text
    assert "phase=post_commit" in caplog.text
    assert f"path={OLD_PATH}" in caplog.text


def test_retry_and_later_orphan_cleanup_never_break_current_reference(
    session, engine, employee
):
    set_product_image(session)
    gateway = StatefulStorage()
    gateway.objects[(CATALOG_BUCKET, OLD_PATH)] = PNG
    gateway.fail_delete_paths.add(OLD_PATH)
    service = coordinator(engine, gateway)

    first = upload(service, employee)
    gateway.fail_delete_paths.clear()
    second = upload(service, employee)

    session.expire_all()
    assert session.get(Producto, 1).ruta_imagen_principal == second.ruta_imagen_principal
    assert (CATALOG_BUCKET, second.ruta_imagen_principal) in gateway.objects
    assert (CATALOG_BUCKET, first.ruta_imagen_principal) not in gateway.objects
    assert service.cleanup_orphan_product_image(path=OLD_PATH, principal=employee) is True
    assert (CATALOG_BUCKET, OLD_PATH) not in gateway.objects
    assert (CATALOG_BUCKET, second.ruta_imagen_principal) in gateway.objects


def test_permissions_and_references_prevent_unsafe_catalog_cleanup(
    session, engine, employee, customer
):
    protected_path = "productos/1/22222222222222222222222222222222.png"
    other = Producto(
        id_producto=2,
        id_categoria=1,
        nombre="Producto protegido",
        descripcion=None,
        informacion_comercial="Prueba de referencia compartida",
        estado_publicacion="BORRADOR",
        ruta_imagen_principal=protected_path,
        imagen_mime="image/png",
        imagen_tamano_bytes=len(PNG),
    )
    session.add(other)
    session.commit()
    gateway = StatefulStorage()
    gateway.objects[(CATALOG_BUCKET, protected_path)] = PNG
    service = coordinator(engine, gateway)

    with pytest.raises(PermissionDenied):
        upload(service, customer)
    with pytest.raises(PermissionDenied):
        service.cleanup_orphan_product_image(path=protected_path, principal=customer)
    assert service.cleanup_orphan_product_image(path=protected_path, principal=employee) is False
    with pytest.raises(Conflict, match="catálogo"):
        service.cleanup_orphan_product_image(
            path="pedidos/1/lineas/1/diseno.png", principal=employee
        )
    with pytest.raises(Conflict, match="catálogo"):
        service.cleanup_orphan_product_image(
            path="transacciones/1/comprobante.png", principal=employee
        )

    assert gateway.delete_attempts == []
    assert (CATALOG_BUCKET, protected_path) in gateway.objects
    assert gateway.uploads == []
