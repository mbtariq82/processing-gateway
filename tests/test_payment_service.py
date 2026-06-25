from __future__ import annotations

from processing_gateway.domain import StateTransitionError
from processing_gateway.payment_service import PaymentService
from processing_gateway.repository import PaymentRepository


def build_service() -> PaymentService:
    return PaymentService(PaymentRepository())


def test_initiate_payment_is_idempotent() -> None:
    service = build_service()

    first = service.initiate("merchant-1", "125.00", "gbp", "same-key")
    second = service.initiate("merchant-1", "125.00", "gbp", "same-key")

    assert second.id == first.id
    assert first.status == "pending"
    assert len(first.audit_log) == 1


def test_authorize_capture_and_refund_payment() -> None:
    service = build_service()
    payment = service.initiate("merchant-1", "125.00", "gbp", "init-1")

    authorized = service.confirm(payment.id, approved=True, provider_reference="provider-123")
    assert authorized.status == "authorized"

    captured = service.capture(payment.id, "125.00", "capture-1")
    assert captured.status == "captured"
    assert captured.captured_amount == 125

    repeated_capture = service.capture(payment.id, "125.00", "capture-1")
    assert repeated_capture.id == payment.id

    refunded = service.refund(payment.id, "125.00", "refund-1")
    assert refunded.status == "refunded"
    assert refunded.refunded_amount == 125


def test_invalid_capture_transition_is_rejected() -> None:
    service = build_service()
    payment = service.initiate("merchant-1", "125.00", "gbp", "init-1")

    try:
        service.capture(payment.id, "125.00", "capture-too-early")
    except StateTransitionError:
        return

    raise AssertionError("Expected capture before authorization to fail.")
