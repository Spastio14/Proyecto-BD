import logging
import re
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.exceptions import Conflict, NotFound, PermissionDenied
from app.core.security import Principal
from app.integrations.supabase import StorageGateway
from app.models.entities import DetallePedido, Pedido, Producto, Transaccion, VersionDiseno
from app.services.audit import AuditService
from app.services.authorization import AuthorizationService
from app.services.designs import DesignService

ALLOWED_MIME = frozenset({"image/png", "image/jpeg", "application/pdf"})
CATALOG_BUCKET = "catalogo-productos"
CATALOG_IMAGE_PATH = re.compile(
    r"^productos/[1-9][0-9]*/[0-9a-f]{32}\.(?:png|jpg|webp)$"
)

logger = logging.getLogger(__name__)


class StorageCoordinator:
    def __init__(
        self,
        factory: sessionmaker[Session],
        gateway: StorageGateway,
        *,
        design_max_bytes: int,
        receipt_max_bytes: int,
        signed_url_ttl: int,
        product_max_bytes: int = 5 * 1024 * 1024,
    ):
        self.factory = factory
        self.gateway = gateway
        self.design_max_bytes = design_max_bytes
        self.receipt_max_bytes = receipt_max_bytes
        self.product_max_bytes = product_max_bytes
        self.signed_url_ttl = signed_url_ttl

    @staticmethod
    def _validate(content: bytes, content_type: str, maximum: int) -> None:
        if content_type not in ALLOWED_MIME:
            raise Conflict("Tipo de archivo no permitido")
        if not content or len(content) > maximum:
            raise Conflict("El tamaño del archivo no está permitido")
        signatures = {
            "image/png": (b"\x89PNG\r\n\x1a\n",),
            "image/jpeg": (b"\xff\xd8\xff",),
            "application/pdf": (b"%PDF-",),
        }
        if not content.startswith(signatures[content_type]):
            raise Conflict("El contenido no coincide con el MIME declarado")

    @staticmethod
    def _suffix(file_name: str, content_type: str) -> str:
        expected = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "application/pdf": ".pdf",
        }[content_type]
        supplied = Path(file_name).suffix.lower()
        if supplied == ".jpeg":
            supplied = ".jpg"
        if supplied != expected:
            raise Conflict("La extensión no coincide con el tipo del archivo")
        return expected

    def upload_design(
        self,
        *,
        order_id: int,
        line_number: int,
        file_name: str,
        content_type: str,
        content: bytes,
        observations: str | None,
        principal: Principal,
    ) -> VersionDiseno:
        if not principal.is_employee:
            raise PermissionDenied("Sólo el personal autorizado puede cargar diseños")
        self._validate(content, content_type, self.design_max_bytes)
        suffix = self._suffix(file_name, content_type)
        with self.factory() as precheck:
            order = self._authorize_order(precheck, order_id, principal, "DISENO_APROBAR")
            if order.estado != "EN_DISENO":
                raise Conflict("El pedido no está en una etapa que admita nuevos diseños")
            if precheck.get(DetallePedido, (order_id, line_number)) is None:
                raise NotFound("Línea de pedido no encontrada")
        path = f"pedidos/{order_id}/lineas/{line_number}/{uuid4().hex}{suffix}"
        self.gateway.upload(bucket="disenos", path=path, content=content, content_type=content_type)
        try:
            with self.factory() as session, session.begin():
                version = DesignService().add_version(
                    session,
                    order_id=order_id,
                    line_number=line_number,
                    file_name=Path(file_name).name,
                    private_path=path,
                    observations=observations,
                    principal=principal,
                )
                session.flush()
                session.expunge(version)
            return version
        except Exception:
            self.gateway.delete(bucket="disenos", path=path)
            raise

    def upload_product_image(
        self,
        *,
        product_id: int,
        file_name: str,
        content_type: str,
        content: bytes,
        principal: Principal,
    ) -> Producto:
        if content_type not in {"image/png", "image/jpeg", "image/webp"}:
            raise Conflict("La fotografía debe ser PNG, JPEG o WebP")
        if not content or len(content) > self.product_max_bytes:
            raise Conflict("La fotografía supera el tamaño permitido")
        signatures = {
            "image/png": b"\x89PNG\r\n\x1a\n",
            "image/jpeg": b"\xff\xd8\xff",
        }
        valid_signature = (
            len(content) >= 12
            and content.startswith(b"RIFF")
            and content[8:12] == b"WEBP"
            if content_type == "image/webp"
            else content.startswith(signatures[content_type])
        )
        if not valid_signature:
            raise Conflict("El contenido no coincide con el tipo de imagen")
        suffix = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}[
            content_type
        ]
        supplied = Path(file_name).suffix.lower().replace(".jpeg", ".jpg")
        if supplied != suffix:
            raise Conflict("La extensión no coincide con el tipo de imagen")
        with self.factory() as precheck:
            AuthorizationService.require(precheck, principal, "CATALOGO_GESTIONAR")
            product = precheck.get(Producto, product_id)
            if product is None:
                raise NotFound("Producto no encontrado")
        path = f"productos/{product_id}/{uuid4().hex}{suffix}"
        self.gateway.upload(
            bucket=CATALOG_BUCKET, path=path, content=content, content_type=content_type
        )
        old_path = None
        try:
            with self.factory() as session, session.begin():
                AuthorizationService.require(session, principal, "CATALOGO_GESTIONAR")
                product = session.scalar(
                    select(Producto)
                    .where(Producto.id_producto == product_id)
                    .with_for_update()
                )
                if product is None:
                    raise NotFound("Producto no encontrado")
                old_path = product.ruta_imagen_principal
                product.ruta_imagen_principal = path
                product.imagen_mime = content_type
                product.imagen_tamano_bytes = len(content)
                AuditService.record(
                    session,
                    principal=principal,
                    action="ACTUALIZAR_IMAGEN_PRODUCTO",
                    object_type="PRODUCTO",
                    object_reference=str(product_id),
                    reason="Fotografía comercial validada y almacenada",
                    before={"ruta": old_path},
                    after={"ruta": path, "mime": content_type, "tamano": len(content)},
                )
                session.flush()
                session.expunge(product)
        except Exception:
            self._try_cleanup_catalog_image(path, phase="database_rollback")
            raise

        # PostgreSQL ya confirmó la ruta nueva. La limpieza de la ruta anterior
        # es secundaria y nunca debe invalidar la referencia recién guardada.
        if old_path and old_path != path:
            self._try_cleanup_catalog_image(old_path, phase="post_commit")
        return product

    def cleanup_orphan_product_image(self, *, path: str, principal: Principal) -> bool:
        """Elimina una imagen de catálogo generada que ya no esté referenciada.

        Los candidatos se identifican en los logs ``catalog_image_cleanup_pending``.
        La comprobación de referencias se repite inmediatamente antes de borrar.
        """
        if not CATALOG_IMAGE_PATH.fullmatch(path):
            raise Conflict("La ruta no corresponde a una imagen administrada del catálogo")
        with self.factory() as session:
            AuthorizationService.require(session, principal, "CATALOGO_GESTIONAR")
        return self._delete_catalog_image_if_unreferenced(path)

    def _delete_catalog_image_if_unreferenced(self, path: str) -> bool:
        with self.factory() as session:
            referenced = session.scalar(
                select(Producto.id_producto)
                .where(Producto.ruta_imagen_principal == path)
                .limit(1)
            )
        if referenced is not None:
            return False
        self.gateway.delete(bucket=CATALOG_BUCKET, path=path)
        return True

    def _try_cleanup_catalog_image(self, path: str, *, phase: str) -> bool:
        try:
            return self._delete_catalog_image_if_unreferenced(path)
        except Exception as exc:
            logger.warning(
                "catalog_image_cleanup_pending phase=%s bucket=%s path=%s error_type=%s",
                phase,
                CATALOG_BUCKET,
                path,
                type(exc).__name__,
            )
            return False

    def upload_receipt(
        self,
        *,
        payment_id: int,
        file_name: str,
        content_type: str,
        content: bytes,
        principal: Principal,
    ) -> str:
        self._validate(content, content_type, self.receipt_max_bytes)
        suffix = self._suffix(file_name, content_type)
        with self.factory() as precheck:
            payment = precheck.get(Transaccion, payment_id)
            if payment is None or payment.tipo_transaccion != "PAGO":
                raise NotFound("Transacción de pago no encontrada")
            self._authorize_order(precheck, payment.id_pedido, principal, "PAGO_VERIFICAR")
            if payment.ruta_comprobante is not None:
                raise Conflict("La transacción ya tiene un comprobante")
        path = f"transacciones/{payment_id}/{uuid4().hex}{suffix}"
        self.gateway.upload(
            bucket="comprobantes", path=path, content=content, content_type=content_type
        )
        try:
            with self.factory() as session, session.begin():
                payment = session.scalar(
                    select(Transaccion)
                    .where(Transaccion.id_transaccion == payment_id)
                    .with_for_update()
                )
                if payment is None or payment.tipo_transaccion != "PAGO":
                    raise NotFound("Transacción de pago no encontrada")
                self._authorize_order(session, payment.id_pedido, principal, "PAGO_VERIFICAR")
                if payment.ruta_comprobante is not None:
                    raise Conflict("La transacción ya tiene un comprobante")
                payment.ruta_comprobante = path
                payment.comprobante_mime = content_type
                payment.comprobante_tamano_bytes = len(content)
            return path
        except Exception:
            self.gateway.delete(bucket="comprobantes", path=path)
            raise

    @staticmethod
    def _authorize_order(
        session: Session, order_id: int, principal: Principal, employee_permission: str
    ) -> Pedido:
        order = session.get(Pedido, order_id)
        if order is None:
            raise NotFound("Pedido no encontrado")
        if principal.is_employee:
            AuthorizationService.require(session, principal, employee_permission)
        elif order.id_cliente != principal.persona_id:
            raise PermissionDenied("El pedido pertenece a otro cliente")
        return order

    def design_url(
        self,
        session: Session,
        *,
        order_id: int,
        line_number: int,
        version_number: int,
        principal: Principal,
    ) -> str:
        self._authorize_order(session, order_id, principal, "DISENO_APROBAR")
        version = session.get(VersionDiseno, (order_id, line_number, version_number))
        if version is None:
            raise NotFound("Versión de diseño no encontrada")
        return self.gateway.signed_url(
            bucket="disenos", path=version.ruta_archivo, expires_in=self.signed_url_ttl
        )

    def receipt_url(self, session: Session, *, payment_id: int, principal: Principal) -> str:
        payment = session.get(Transaccion, payment_id)
        if payment is None or payment.ruta_comprobante is None:
            raise NotFound("Comprobante no encontrado")
        self._authorize_order(session, payment.id_pedido, principal, "PAGO_VERIFICAR")
        return self.gateway.signed_url(
            bucket="comprobantes",
            path=payment.ruta_comprobante,
            expires_in=self.signed_url_ttl,
        )
