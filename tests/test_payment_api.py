from __future__ import annotations

from fastapi.testclient import TestClient

from processing_gateway.main import create_app


def build_client() -> TestClient:
    return TestClient(create_app())


def initiate_payment(client: TestClient, key: str = "init-key") -> dict:
    response = client.post(
        "/payments",
        json={
            "merchant_id": "merchant-1",
            "amount": "125.00",
            "currency": "gbp",
            "idempotency_key": key,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_payment_api_is_idempotent() -> None:
    client = build_client()

    first = initiate_payment(client, "same-key")
    second = initiate_payment(client, "same-key")

    assert second["id"] == first["id"]
    assert len(second["audit_log"]) == 1


def test_payment_api_authorize_capture_and_refund() -> None:
    client = build_client()
    payment = initiate_payment(client)

    confirmed = client.post(
        f"/payments/{payment['id']}/confirm",
        json={"approved": True, "provider_reference": "provider-123"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "authorized"

    captured = client.post(
        f"/payments/{payment['id']}/capture",
        json={"amount": "125.00", "idempotency_key": "capture-1"},
    )
    assert captured.status_code == 200
    assert captured.json()["status"] == "captured"

    refunded = client.post(
        f"/payments/{payment['id']}/refund",
        json={"amount": "125.00", "idempotency_key": "refund-1"},
    )
    assert refunded.status_code == 200
    assert refunded.json()["status"] == "refunded"


def test_payment_api_rejects_invalid_transition() -> None:
    client = build_client()
    payment = initiate_payment(client)

    response = client.post(
        f"/payments/{payment['id']}/capture",
        json={"amount": "125.00", "idempotency_key": "capture-too-early"},
    )

    assert response.status_code == 409
