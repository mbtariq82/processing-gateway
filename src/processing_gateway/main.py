from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from processing_gateway.domain import (
    GatewayError,
    NotFoundError,
    SignatureError,
    StateTransitionError,
    ValidationError,
)
from processing_gateway.payment_service import PaymentService
from processing_gateway.repository import PaymentRepository
from processing_gateway.schemas import (
    ConfirmPaymentRequest,
    HealthResponse,
    InitiatePaymentRequest,
    MoneyOperationRequest,
    PaymentResponse,
    SignatureRequest,
    SignatureResponse,
    WebhookEventResponse,
    WebhookPayload,
)
from processing_gateway.webhook_service import WebhookService


def create_app(repository: PaymentRepository | None = None) -> FastAPI:
    repository = repository or PaymentRepository()
    payment_service = PaymentService(repository)
    webhook_service = WebhookService(repository, payment_service)

    app = FastAPI(
        title="Processing Gateway",
        version="0.1.0",
        summary="Payment API with idempotency, webhooks, and reconciliation.",
    )
    app.state.repository = repository
    app.state.payment_service = payment_service
    app.state.webhook_service = webhook_service

    @app.exception_handler(GatewayError)
    async def handle_gateway_error(_request: Request, exc: GatewayError) -> JSONResponse:
        status_code = status.HTTP_400_BAD_REQUEST
        if isinstance(exc, NotFoundError):
            status_code = status.HTTP_404_NOT_FOUND
        elif isinstance(exc, StateTransitionError):
            status_code = status.HTTP_409_CONFLICT
        elif isinstance(exc, ValidationError):
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        elif isinstance(exc, SignatureError):
            status_code = status.HTTP_401_UNAUTHORIZED
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.post("/payments", status_code=status.HTTP_201_CREATED, response_model=PaymentResponse)
    def initiate_payment(payload: InitiatePaymentRequest) -> PaymentResponse:
        payment = payment_service.initiate(
            payload.merchant_id,
            payload.amount,
            payload.currency,
            payload.idempotency_key,
        )
        return PaymentResponse.model_validate(payment)

    @app.get("/payments", response_model=list[PaymentResponse])
    def list_payments() -> list[PaymentResponse]:
        return [PaymentResponse.model_validate(payment) for payment in repository.list_payments()]

    @app.get("/payments/{payment_id}", response_model=PaymentResponse)
    def get_payment(payment_id: str) -> PaymentResponse:
        return PaymentResponse.model_validate(repository.get_payment(payment_id))

    @app.post("/payments/{payment_id}/confirm", response_model=PaymentResponse)
    def confirm_payment(payment_id: str, payload: ConfirmPaymentRequest) -> PaymentResponse:
        payment = payment_service.confirm(
            payment_id,
            payload.approved,
            payload.provider_reference,
            payload.reason,
        )
        return PaymentResponse.model_validate(payment)

    @app.post("/payments/{payment_id}/capture", response_model=PaymentResponse)
    def capture_payment(payment_id: str, payload: MoneyOperationRequest) -> PaymentResponse:
        payment = payment_service.capture(payment_id, payload.amount, payload.idempotency_key)
        return PaymentResponse.model_validate(payment)

    @app.post("/payments/{payment_id}/refund", response_model=PaymentResponse)
    def refund_payment(payment_id: str, payload: MoneyOperationRequest) -> PaymentResponse:
        payment = payment_service.refund(payment_id, payload.amount, payload.idempotency_key)
        return PaymentResponse.model_validate(payment)

    @app.post("/payments/{payment_id}/void", response_model=PaymentResponse)
    def void_payment(payment_id: str) -> PaymentResponse:
        return PaymentResponse.model_validate(payment_service.void(payment_id))

    @app.post("/webhooks/signature", response_model=SignatureResponse)
    def create_signature(payload: SignatureRequest) -> SignatureResponse:
        return SignatureResponse(
            signature=webhook_service.sign(payload.event_id, payload.payment_id, payload.status)
        )

    @app.post("/webhooks/provider", response_model=WebhookEventResponse)
    def provider_webhook(payload: WebhookPayload) -> WebhookEventResponse:
        event = webhook_service.process(
            payload.event_id,
            payload.payment_id,
            payload.event_type,
            payload.status,
            payload.signature,
            payload.provider_reference,
        )
        return WebhookEventResponse.model_validate(event)

    return app


app = create_app()
