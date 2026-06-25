from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import uuid4


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class GatewayError(Exception):
    pass


class NotFoundError(GatewayError):
    pass


class ValidationError(GatewayError):
    pass


class StateTransitionError(GatewayError):
    pass


class SignatureError(GatewayError):
    pass


class PaymentStatus(StrEnum):
    PENDING = "pending"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    REFUNDED = "refunded"
    VOIDED = "voided"
    FAILED = "failed"


class ReconciliationStatus(StrEnum):
    MATCHED = "matched"
    MISSING_INTERNAL = "missing-internal"
    MISSING_PROVIDER = "missing-provider"
    AMOUNT_MISMATCH = "amount-mismatch"
    STATUS_MISMATCH = "status-mismatch"
    AUTO_RESOLVED = "auto-resolved"


@dataclass
class AuditEntry:
    action: str
    details: dict[str, str]
    id: str = field(default_factory=lambda: new_id("audit"))
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class Payment:
    merchant_id: str
    amount: Decimal
    currency: str
    idempotency_key: str
    status: PaymentStatus = PaymentStatus.PENDING
    captured_amount: Decimal = Decimal("0.00")
    refunded_amount: Decimal = Decimal("0.00")
    provider_reference: str | None = None
    failure_reason: str | None = None
    id: str = field(default_factory=lambda: new_id("pay"))
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)
    audit_log: list[AuditEntry] = field(default_factory=list)


@dataclass
class WebhookEvent:
    event_id: str
    payment_id: str
    event_type: str
    status: PaymentStatus
    processed: bool = True
    received_at: datetime = field(default_factory=utcnow)


@dataclass
class ProviderStatementRecord:
    payment_id: str
    amount: Decimal
    status: PaymentStatus
    provider_reference: str | None = None


@dataclass
class ReconciliationItem:
    payment_id: str
    status: ReconciliationStatus
    details: dict[str, str]


@dataclass
class ReconciliationReport:
    items: list[ReconciliationItem]
    id: str = field(default_factory=lambda: new_id("recon"))
    created_at: datetime = field(default_factory=utcnow)
