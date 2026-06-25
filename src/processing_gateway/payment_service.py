from __future__ import annotations

from decimal import Decimal

from processing_gateway.domain import (
    AuditEntry,
    Payment,
    PaymentStatus,
    StateTransitionError,
    ValidationError,
    utcnow,
)
from processing_gateway.money import money
from processing_gateway.repository import PaymentRepository


class PaymentService:
    def __init__(self, repository: PaymentRepository) -> None:
        self.repository = repository

    def initiate(
        self,
        merchant_id: str,
        amount: Decimal,
        currency: str,
        idempotency_key: str,
    ) -> Payment:
        self._validate_common(merchant_id, amount, currency, idempotency_key)
        existing_id = self.repository.find_operation_result("initiate", idempotency_key)
        if existing_id:
            return self.repository.get_payment(existing_id)

        payment = Payment(
            merchant_id=merchant_id.strip(),
            amount=money(amount),
            currency=currency.upper().strip(),
            idempotency_key=idempotency_key.strip(),
        )
        self._audit(payment, "payment_initiated", {"status": PaymentStatus.PENDING.value})
        return self.repository.add_payment(payment)

    def confirm(
        self,
        payment_id: str,
        approved: bool,
        provider_reference: str | None = None,
        reason: str | None = None,
    ) -> Payment:
        payment = self.repository.get_payment(payment_id)
        self._require_status(payment, PaymentStatus.PENDING)
        if approved:
            payment.status = PaymentStatus.AUTHORIZED
            payment.provider_reference = provider_reference or payment.provider_reference
            self._audit(
                payment,
                "payment_authorized",
                {"provider_reference": payment.provider_reference or ""},
            )
        else:
            payment.status = PaymentStatus.FAILED
            payment.failure_reason = reason or "Provider declined the payment."
            self._audit(payment, "payment_failed", {"reason": payment.failure_reason})
        payment.updated_at = utcnow()
        return payment

    def capture(
        self,
        payment_id: str,
        amount: Decimal,
        idempotency_key: str,
    ) -> Payment:
        self._validate_idempotency_key(idempotency_key)
        existing_id = self.repository.find_operation_result("capture", idempotency_key)
        if existing_id:
            return self.repository.get_payment(existing_id)

        payment = self.repository.get_payment(payment_id)
        self._require_status(payment, PaymentStatus.AUTHORIZED)
        capture_amount = money(amount)
        if capture_amount <= 0 or capture_amount > payment.amount:
            raise ValidationError("Capture amount must be greater than zero and no more than the payment amount.")

        payment.captured_amount = capture_amount
        payment.status = PaymentStatus.CAPTURED
        payment.updated_at = utcnow()
        self._audit(payment, "payment_captured", {"amount": str(capture_amount)})
        self.repository.remember_operation_result("capture", idempotency_key, payment.id)
        return payment

    def refund(
        self,
        payment_id: str,
        amount: Decimal,
        idempotency_key: str,
    ) -> Payment:
        self._validate_idempotency_key(idempotency_key)
        existing_id = self.repository.find_operation_result("refund", idempotency_key)
        if existing_id:
            return self.repository.get_payment(existing_id)

        payment = self.repository.get_payment(payment_id)
        if payment.status not in {PaymentStatus.CAPTURED, PaymentStatus.REFUNDED}:
            raise StateTransitionError("Only captured payments can be refunded.")
        refund_amount = money(amount)
        refundable = money(payment.captured_amount - payment.refunded_amount)
        if refund_amount <= 0 or refund_amount > refundable:
            raise ValidationError(f"Refund amount must be between 0.01 and {refundable}.")

        payment.refunded_amount = money(payment.refunded_amount + refund_amount)
        if payment.refunded_amount == payment.captured_amount:
            payment.status = PaymentStatus.REFUNDED
        payment.updated_at = utcnow()
        self._audit(payment, "payment_refunded", {"amount": str(refund_amount)})
        self.repository.remember_operation_result("refund", idempotency_key, payment.id)
        return payment

    def void(self, payment_id: str) -> Payment:
        payment = self.repository.get_payment(payment_id)
        if payment.status not in {PaymentStatus.PENDING, PaymentStatus.AUTHORIZED}:
            raise StateTransitionError("Only pending or authorized payments can be voided.")
        payment.status = PaymentStatus.VOIDED
        payment.updated_at = utcnow()
        self._audit(payment, "payment_voided", {})
        return payment

    def apply_provider_status(
        self,
        payment_id: str,
        status: PaymentStatus,
        provider_reference: str | None = None,
    ) -> Payment:
        payment = self.repository.get_payment(payment_id)
        valid_targets = {
            PaymentStatus.AUTHORIZED,
            PaymentStatus.CAPTURED,
            PaymentStatus.REFUNDED,
            PaymentStatus.FAILED,
        }
        if status not in valid_targets:
            raise ValidationError("Provider callbacks can only authorize, capture, refund, or fail payments.")

        if status is PaymentStatus.AUTHORIZED and payment.status is PaymentStatus.PENDING:
            payment.status = status
        elif status is PaymentStatus.CAPTURED and payment.status in {PaymentStatus.AUTHORIZED, PaymentStatus.PENDING}:
            payment.status = status
            payment.captured_amount = payment.amount
        elif status is PaymentStatus.REFUNDED and payment.status is PaymentStatus.CAPTURED:
            payment.status = status
            payment.refunded_amount = payment.captured_amount
        elif status is PaymentStatus.FAILED and payment.status is PaymentStatus.PENDING:
            payment.status = status
        else:
            raise StateTransitionError(f"Cannot apply provider status {status.value} from {payment.status.value}.")

        payment.provider_reference = provider_reference or payment.provider_reference
        payment.updated_at = utcnow()
        self._audit(payment, "provider_status_applied", {"status": status.value})
        return payment

    @staticmethod
    def _validate_common(
        merchant_id: str,
        amount: Decimal,
        currency: str,
        idempotency_key: str,
    ) -> None:
        if not merchant_id.strip():
            raise ValidationError("merchant_id is required.")
        if money(amount) <= 0:
            raise ValidationError("amount must be greater than zero.")
        if len(currency.strip()) != 3:
            raise ValidationError("currency must be a three-letter ISO code.")
        PaymentService._validate_idempotency_key(idempotency_key)

    @staticmethod
    def _validate_idempotency_key(idempotency_key: str) -> None:
        if not idempotency_key.strip():
            raise ValidationError("idempotency_key is required.")

    @staticmethod
    def _require_status(payment: Payment, expected: PaymentStatus) -> None:
        if payment.status is not expected:
            raise StateTransitionError(
                f"Payment must be {expected.value}; current status is {payment.status.value}."
            )

    @staticmethod
    def _audit(payment: Payment, action: str, details: dict[str, str]) -> None:
        payment.audit_log.append(AuditEntry(action=action, details=details))
