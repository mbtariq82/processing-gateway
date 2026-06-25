from __future__ import annotations

import hmac
from hashlib import sha256

from processing_gateway.domain import PaymentStatus, SignatureError, WebhookEvent
from processing_gateway.payment_service import PaymentService
from processing_gateway.repository import PaymentRepository


class WebhookService:
    def __init__(
        self,
        repository: PaymentRepository,
        payment_service: PaymentService,
        signing_secret: str = "dev-secret",
    ) -> None:
        self.repository = repository
        self.payment_service = payment_service
        self.signing_secret = signing_secret

    def sign(self, event_id: str, payment_id: str, status: PaymentStatus) -> str:
        payload = f"{event_id}.{payment_id}.{status.value}".encode()
        return hmac.new(self.signing_secret.encode(), payload, sha256).hexdigest()

    def process(
        self,
        event_id: str,
        payment_id: str,
        event_type: str,
        status: PaymentStatus,
        signature: str,
        provider_reference: str | None = None,
    ) -> WebhookEvent:
        existing = self.repository.get_webhook_event(event_id)
        if existing:
            return existing

        expected_signature = self.sign(event_id, payment_id, status)
        if not hmac.compare_digest(expected_signature, signature):
            raise SignatureError("Webhook signature verification failed.")

        self.payment_service.apply_provider_status(payment_id, status, provider_reference)
        event = WebhookEvent(
            event_id=event_id,
            payment_id=payment_id,
            event_type=event_type,
            status=status,
        )
        return self.repository.add_webhook_event(event)
