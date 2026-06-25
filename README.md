# Processing Gateway

Training implementation of a payment processing gateway. It supports payment
initiation, confirmation, capture, refund, void, provider webhooks, and
statement reconciliation.

## Features

- Idempotency keys for initiation, capture, and refund operations.
- Payment state machine with audit log entries for every state-changing action.
- Provider webhook handling with HMAC signatures and duplicate-delivery safety.
- Reconciliation reports for missing records, amount mismatches, status
  mismatches, and safe auto-resolution of authorized payments captured by the
  provider.

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e ".[dev]"
uvicorn processing_gateway.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the interactive API docs.

## Test

```bash
pytest
```

## Key endpoints

- `POST /payments`
- `POST /payments/{payment_id}/confirm`
- `POST /payments/{payment_id}/capture`
- `POST /payments/{payment_id}/refund`
- `POST /payments/{payment_id}/void`
- `POST /webhooks/provider`
- `POST /reconciliation`
