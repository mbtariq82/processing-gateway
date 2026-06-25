from __future__ import annotations

from fastapi.testclient import TestClient

from processing_gateway.main import create_app


def test_provider_webhook_signature_and_duplicate_delivery() -> None:
    client = TestClient(create_app())
    payment = client.post(
        "/payments",
        json={
            "merchant_id": "merchant-1",
            "amount": "125.00",
            "currency": "gbp",
            "idempotency_key": "init-key",
        },
    ).json()

    signature = client.post(
        "/webhooks/signature",
        json={
            "event_id": "evt-1",
            "payment_id": payment["id"],
            "status": "authorized",
        },
    ).json()["signature"]

    payload = {
        "event_id": "evt-1",
        "payment_id": payment["id"],
        "event_type": "payment.authorized",
        "status": "authorized",
        "signature": signature,
        "provider_reference": "provider-evt-1",
    }
    first = client.post("/webhooks/provider", json=payload)
    second = client.post("/webhooks/provider", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["event_id"] == second.json()["event_id"]
    assert client.get(f"/payments/{payment['id']}").json()["status"] == "authorized"


def test_provider_webhook_rejects_bad_signature() -> None:
    client = TestClient(create_app())
    payment = client.post(
        "/payments",
        json={
            "merchant_id": "merchant-1",
            "amount": "125.00",
            "currency": "gbp",
            "idempotency_key": "init-key",
        },
    ).json()

    response = client.post(
        "/webhooks/provider",
        json={
            "event_id": "evt-1",
            "payment_id": payment["id"],
            "event_type": "payment.authorized",
            "status": "authorized",
            "signature": "bad-signature",
        },
    )

    assert response.status_code == 401
