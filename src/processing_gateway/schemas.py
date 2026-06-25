from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from processing_gateway.domain import PaymentStatus


class HealthResponse(BaseModel):
    status: str


class InitiatePaymentRequest(BaseModel):
    merchant_id: str = Field(min_length=1, max_length=80)
    amount: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    idempotency_key: str = Field(min_length=1, max_length=120)


class ConfirmPaymentRequest(BaseModel):
    approved: bool = True
    provider_reference: str | None = Field(default=None, max_length=120)
    reason: str | None = Field(default=None, max_length=300)


class MoneyOperationRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    idempotency_key: str = Field(min_length=1, max_length=120)


class AuditEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    action: str
    details: dict[str, str]
    created_at: datetime


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    merchant_id: str
    amount: Decimal
    currency: str
    idempotency_key: str
    status: PaymentStatus
    captured_amount: Decimal
    refunded_amount: Decimal
    provider_reference: str | None
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime
    audit_log: list[AuditEntryResponse]
