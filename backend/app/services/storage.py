from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.exceptions import Conflict, NotFound, PermissionDenied
from app.core.security import Principal
from app.integrations.supabase import StorageGateway
from app.models.entities import DetallePedido, Pedido, Transaccion, VersionDiseno
from app.services.authorization import AuthorizationService
from app.services.designs import DesignService

ALLOWED_MIME = frozenset({"image/png", "image/jpeg", "application/pdf"})


class StorageCoordinator:
    def __init__(
        self,
        factory: sessionmaker[Session],
        gateway: StorageGateway,
        *,
        design_max_bytes: int,
        receipt_max_bytes: int,
        signed_url_ttl: int,
    ):
        self.factory = factory
        self.gateway = gateway
        self.design_max_bytes = design_max_bytes
        self.receipt_max_bytes = receipt_max_bytes
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
        self._validate(content, content_type, self.design_max_bytes)
        suffix = self._suffix(file_name, content_type)
        with self.factory() as precheck:
            self._authorize_order(precheck, order_id, principal, "DISENO_APROBAR")
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
