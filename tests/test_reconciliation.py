from __future__ import annotations

from fastapi.testclient import TestClient

from processing_gateway.main import create_app


def test_reconciliation_auto_resolves_provider_capture() -> None:
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
    client.post(
        f"/payments/{payment['id']}/confirm",
        json={"approved": True, "provider_reference": "provider-123"},
    )

    report = client.post(
        "/reconciliation",
        json={
            "auto_resolve": True,
            "records": [
                {
                    "payment_id": payment["id"],
                    "amount": "125.00",
                    "status": "captured",
                    "provider_reference": "provider-123",
                },
                {
                    "payment_id": "missing-payment",
                    "amount": "10.00",
                    "status": "captured",
                },
            ],
        },
    )

    assert report.status_code == 200
    statuses = {item["status"] for item in report.json()["items"]}
    assert "auto-resolved" in statuses
    assert "missing-internal" in statuses
    assert client.get(f"/payments/{payment['id']}").json()["status"] == "captured"
