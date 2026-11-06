from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr


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


class OrderCreate(StrictInput):
    lines: list[OrderLineCreate] = Field(min_length=1)
    delivery_mode: Literal["RETIRO", "ENVIO"] = "RETIRO"


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
    milestone_number: int = Field(gt=0)
    idempotency_key: UUID
    method: Literal["EFECTIVO", "TRANSFERENCIA", "TARJETA", "OTRO"]
    bank: str | None = None
    reference: str | None = None


class PaymentRead(ORMModel):
    id_transaccion: int
    id_pedido: int
    numero_hito: int | None
    monto_con_signo: Decimal
    estado_verificacion: str
    clave_idem: UUID


class PaymentReject(StrictInput):
    reason: str = Field(min_length=1, max_length=500)


class CancelRequest(StrictInput):
    reason: str = Field(min_length=1, max_length=500)


class OrderTransitionRequest(StrictInput):
    target: Literal["EN_DISENO", "LISTO"]
    reason: str = Field(min_length=1, max_length=500)


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
    medium: str = "PORTAL"


class LossCreate(StrictInput):
    moment: str
    incident_type: str
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
