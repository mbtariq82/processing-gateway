from __future__ import annotations

from threading import RLock

from processing_gateway.domain import NotFoundError, Payment, WebhookEvent


class PaymentRepository:
    def __init__(self) -> None:
        self._payments: dict[str, Payment] = {}
        self._operation_keys: dict[str, str] = {}
        self._webhook_events: dict[str, WebhookEvent] = {}
        self._lock = RLock()

    def add_payment(self, payment: Payment) -> Payment:
        with self._lock:
            self._payments[payment.id] = payment
            self._operation_keys[f"initiate:{payment.idempotency_key}"] = payment.id
            return payment

    def get_payment(self, payment_id: str) -> Payment:
        with self._lock:
            try:
                return self._payments[payment_id]
            except KeyError as exc:
                raise NotFoundError(f"Payment {payment_id!r} was not found.") from exc

    def list_payments(self) -> list[Payment]:
        with self._lock:
            return list(self._payments.values())

    def find_operation_result(self, operation: str, idempotency_key: str) -> str | None:
        with self._lock:
            return self._operation_keys.get(f"{operation}:{idempotency_key}")

    def remember_operation_result(
        self, operation: str, idempotency_key: str, payment_id: str
    ) -> None:
        with self._lock:
            self._operation_keys[f"{operation}:{idempotency_key}"] = payment_id

    def get_webhook_event(self, event_id: str) -> WebhookEvent | None:
        with self._lock:
            return self._webhook_events.get(event_id)

    def add_webhook_event(self, event: WebhookEvent) -> WebhookEvent:
        with self._lock:
            self._webhook_events[event.event_id] = event
            return event
