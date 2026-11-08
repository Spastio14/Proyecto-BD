from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegistrationRequest(StrictInput):
    names: str = Field(min_length=1, max_length=120)
    surnames: str | None = Field(default=None, max_length=120)
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: str | None = Field(default=None, max_length=30)
    password: SecretStr = Field(min_length=8, max_length=128)


class LoginRequest(StrictInput):
    email: str = Field(min_length=3, max_length=254)
    password: SecretStr = Field(min_length=1, max_length=128)


class InvitationExchangeRequest(StrictInput):
    token_hash: str | None = Field(default=None, min_length=16, max_length=2048)
    type: Literal["invite", "recovery"] = "invite"
    code: str | None = Field(default=None, min_length=8, max_length=2048)
    code_verifier: str | None = Field(default=None, min_length=32, max_length=256)

    @model_validator(mode="after")
    def validate_exchange_mode(self):
        token_mode = self.token_hash is not None
        code_mode = self.code is not None or self.code_verifier is not None
        if token_mode == code_mode:
            raise ValueError("Envía token_hash o el par code/code_verifier")
        if code_mode and (self.code is None or self.code_verifier is None):
            raise ValueError("code y code_verifier son obligatorios juntos")
        return self


class EmployeeActivationRequest(StrictInput):
    password: SecretStr = Field(min_length=8, max_length=128)


class RegistrationRecoveryRequest(StrictInput):
    names: str = Field(min_length=1, max_length=120)
    surnames: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=30)


class EmployeeInviteRequest(StrictInput):
    names: str = Field(min_length=1, max_length=120)
    surnames: str | None = Field(default=None, max_length=120)
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: str | None = Field(default=None, max_length=30)
    document: str | None = Field(default=None, max_length=120)
    role_id: int = Field(gt=0)
    capacity: int = Field(default=10, ge=0, le=1000)


class EmployeeRoleAssignment(StrictInput):
    role_id: int = Field(gt=0)


class GuestCreate(StrictInput):
    names: str = Field(min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=30)


class OrderLineCreate(StrictInput):
    variant_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    promotion_id: int | None = Field(default=None, gt=0)
    customization: str | None = Field(default=None, max_length=1000)


class OrderCreate(StrictInput):
    lines: list[OrderLineCreate] = Field(min_length=1)
    delivery_mode: Literal["RETIRO", "ENVIO"] = "RETIRO"


class PointOfSaleCustomerCreate(StrictInput):
    names: str = Field(min_length=1, max_length=120)
    surnames: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(
        default=None,
        max_length=254,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )


class PointOfSaleOrderCreate(OrderCreate):
    client_id: int = Field(gt=0)


class OrderRead(ORMModel):
    id_pedido: int
    codigo_pedido: str
    id_cliente: int
    estado: str
    total_pedido: Decimal
    fecha_creacion: datetime
    vencimiento_pago: datetime


class QuoteLineCreate(StrictInput):
    variant_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    customization: str | None = Field(default=None, max_length=1000)


class QuoteCreate(StrictInput):
    lines: list[QuoteLineCreate] = Field(min_length=1)
    observations: str | None = None


class PointOfSaleQuoteCreate(QuoteCreate):
    client_id: int = Field(gt=0)


class QuoteRead(ORMModel):
    id_cotizacion: int
    id_cliente: int
    estado: str
    total_ofrecido: Decimal
    fecha_emision: datetime
    fecha_vencimiento: datetime


class QuoteDecision(StrictInput):
    decision: Literal["ACEPTADA", "RECHAZADA"]
    reason: str = Field(min_length=1, max_length=500)


class PaymentReport(StrictInput):
    milestone_number: int | None = Field(default=None, gt=0)
    idempotency_key: UUID
    amount: Decimal | None = Field(default=None, gt=0)
    payment_scope: Literal["ANTICIPO", "SALDO", "TOTAL"] | None = None
    method: Literal["TRANSFERENCIA"]
    bank: str | None = None
    bank_origin: str | None = Field(default=None, max_length=120)
    bank_receiver: str | None = Field(default=None, max_length=120)
    reference: str | None = None


class PaymentRead(ORMModel):
    id_transaccion: int
    id_pedido: int
    numero_hito: int | None
    monto_con_signo: Decimal
    metodo_pago: str
    banco_origen: str | None
    banco_receptor: str | None
    referencia_bancaria: str | None
    estado_verificacion: str
    id_empleado_verificador: int | None
    fecha_hora: datetime
    fecha_verificacion: datetime | None
    clave_idem: UUID


class PaymentListRead(PaymentRead):
    codigo_pedido: str
    tipo_abono: str
    folio_caja: str | None = None


class PaymentReject(StrictInput):
    reason: str = Field(min_length=1, max_length=500)


class CashRegisterOpen(StrictInput):
    opening_amount: Decimal = Field(ge=0)


class CashRegisterClose(StrictInput):
    closing_amount: Decimal = Field(ge=0)


class CashPaymentCreate(StrictInput):
    cash_register_id: int = Field(gt=0)
    amount: Decimal = Field(gt=0)
    payment_scope: Literal["ANTICIPO", "SALDO", "TOTAL"]
    idempotency_key: UUID


class CancelRequest(StrictInput):
    reason: str = Field(min_length=1, max_length=500)


class OrderTransitionRequest(StrictInput):
    target: Literal["EN_DISENO"]
    reason: str = Field(min_length=1, max_length=500)


class CategoryCreate(StrictInput):
    name: str = Field(min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=500)


class CategoryUpdate(StrictInput):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=500)
    state: Literal["ACTIVA", "INACTIVA"] | None = None


class ProductCreate(StrictInput):
    category_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=500)
    commercial_information: str = Field(min_length=1, max_length=5000)
    publication_state: Literal["BORRADOR", "PUBLICADO", "INACTIVO"] = "BORRADOR"


class ProductUpdate(StrictInput):
    category_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=500)
    commercial_information: str | None = Field(default=None, min_length=1, max_length=5000)
    publication_state: Literal["BORRADOR", "PUBLICADO", "INACTIVO"] | None = None


class VariantCreate(StrictInput):
    product_id: int = Field(gt=0)
    code: str = Field(min_length=1, max_length=64)
    features: str | None = Field(default=None, max_length=500)
    retail_price: Decimal = Field(ge=0)
    requires_production: bool = True


class VariantUpdate(StrictInput):
    product_id: int | None = Field(default=None, gt=0)
    code: str | None = Field(default=None, min_length=1, max_length=64)
    features: str | None = Field(default=None, max_length=500)
    retail_price: Decimal | None = Field(default=None, ge=0)
    requires_production: bool | None = None
    state: Literal["ACTIVA", "INACTIVA"] | None = None


class PriceScaleUpsert(StrictInput):
    range_number: int = Field(gt=0)
    minimum_quantity: int = Field(gt=0)
    maximum_quantity: int | None = Field(default=None, gt=0)
    wholesale_unit_price: Decimal = Field(ge=0)
    state: Literal["ACTIVA", "INACTIVA"] = "ACTIVA"

    @model_validator(mode="after")
    def validate_range(self):
        if self.maximum_quantity is not None and self.maximum_quantity < self.minimum_quantity:
            raise ValueError("maximum_quantity debe ser mayor o igual que minimum_quantity")
        return self


class PriceScaleCreate(StrictInput):
    minimum_quantity: int = Field(gt=0)
    maximum_quantity: int | None = Field(default=None, gt=0)
    wholesale_unit_price: Decimal = Field(ge=0)

    @model_validator(mode="after")
    def validate_range(self):
        if self.maximum_quantity is not None and self.maximum_quantity < self.minimum_quantity:
            raise ValueError("maximum_quantity debe ser mayor o igual que minimum_quantity")
        return self


class PriceScaleUpdate(StrictInput):
    minimum_quantity: int | None = Field(default=None, gt=0)
    maximum_quantity: int | None = Field(default=None, gt=0)
    wholesale_unit_price: Decimal | None = Field(default=None, ge=0)
    state: Literal["ACTIVA", "INACTIVA"] | None = None


class InventoryArticleCreate(StrictInput):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=180)
    article_type: str = Field(min_length=1, max_length=80)
    unit: Literal["UNIDAD", "ML", "L", "G", "KG", "M", "M2", "HOJA"]
    minimum_stock: Decimal = Field(ge=0)
    reference_cost: Decimal = Field(ge=0)


class InventoryArticleUpdate(StrictInput):
    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=180)
    article_type: str | None = Field(default=None, min_length=1, max_length=80)
    unit: Literal["UNIDAD", "ML", "L", "G", "KG", "M", "M2", "HOJA"] | None = None
    minimum_stock: Decimal | None = Field(default=None, ge=0)
    reference_cost: Decimal | None = Field(default=None, ge=0)
    state: Literal["ACTIVO", "INACTIVO"] | None = None


class InventoryAdjustment(StrictInput):
    direction: Literal["ENTRADA", "SALIDA"]
    quantity: Decimal = Field(gt=0)
    reason: str = Field(min_length=3, max_length=500)
    observations: str | None = Field(default=None, max_length=2000)


class CompositionUpsert(StrictInput):
    standard_quantity: Decimal = Field(gt=0)
    observations: str = Field(default="", max_length=2000)


class ProviderCreate(StrictInput):
    name: str = Field(min_length=1, max_length=180)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=254)
    address: str | None = Field(default=None, max_length=500)


class PurchaseLineCreate(StrictInput):
    article_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(ge=0)


class PurchaseCreate(StrictInput):
    provider_id: int = Field(gt=0)
    document_number: str | None = Field(default=None, max_length=120)
    lines: list[PurchaseLineCreate] = Field(min_length=1)


class PurchaseLineAdd(StrictInput):
    article_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(ge=0)


class DeliverySchedule(StrictInput):
    agency_id: int | None = Field(default=None, gt=0)
    address: str = Field(min_length=1, max_length=500)
    recipient_name: str = Field(min_length=1, max_length=120)
    recipient_phone: str | None = Field(default=None, max_length=30)
    agreed_fee: Decimal = Field(default=Decimal("0.00"), ge=0)
    scheduled_at: datetime | None = None


class DeliveryComplete(StrictInput):
    reason: str = Field(min_length=1, max_length=500)


class DesignVersionCreate(StrictInput):
    line_number: int = Field(gt=0)
    file_name: str = Field(min_length=1, max_length=180)
    private_path: str = Field(min_length=1, max_length=1000)
    observations: str | None = None


class DesignDecision(StrictInput):
    approved: bool
    medium: Literal["PORTAL", "PRESENCIAL", "WHATSAPP"] = "PORTAL"
    observations: str | None = Field(default=None, max_length=500)
    reference: str | None = Field(default=None, max_length=180)
    evidence: str | None = Field(default=None, max_length=180)

    @model_validator(mode="after")
    def validate_external_evidence(self):
        if self.medium != "PORTAL" and (not self.reference or not self.evidence):
            raise ValueError("Una aprobación externa requiere referencia y evidencia")
        return self


class LossCreate(StrictInput):
    moment: Literal[
        "ANTES_PRODUCCION",
        "DURANTE_PRODUCCION",
        "DESPUES_PRODUCCION",
        "FUERA_PRODUCCION",
    ]
    incident_type: Literal[
        "ROTURA_ARTICULO",
        "IMPRESION_FALLIDA",
        "SUBLIMACION_DEFECTUOSA",
        "DESPERDICIO_INSUMO",
        "DANO_ALMACENAMIENTO",
        "OTRO",
    ]
    reason: str = Field(min_length=1, max_length=500)
    order_id: int | None = Field(default=None, gt=0)
    stage_id: int | None = Field(default=None, gt=0)
    description: str | None = Field(default=None, max_length=500)


class LossLine(StrictInput):
    article_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    damage_description: str | None = Field(default=None, max_length=500)


class LossConfirm(StrictInput):
    lines: list[LossLine] = Field(min_length=1)


class CustomerAdminUpdate(StrictInput):
    names: str | None = Field(default=None, min_length=1, max_length=120)
    surnames: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    document: str | None = Field(default=None, max_length=120)
    usual_address: str | None = Field(default=None, max_length=500)


class EmployeeIdentityUpdate(StrictInput):
    names: str | None = Field(default=None, min_length=1, max_length=120)
    surnames: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    document: str | None = Field(default=None, max_length=120)


class WholesaleConditionUpdate(StrictInput):
    enabled: bool
    reason: str = Field(min_length=3, max_length=500)


class ProfileUpdate(StrictInput):
    names: str | None = Field(default=None, min_length=1, max_length=120)
    surnames: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    document: str | None = Field(default=None, max_length=120)
    usual_address: str | None = Field(default=None, max_length=500)


class EmailChangeRequest(StrictInput):
    new_email: str = Field(
        min_length=3,
        max_length=254,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
