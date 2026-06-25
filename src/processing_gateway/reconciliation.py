from __future__ import annotations

from processing_gateway.domain import (
    PaymentStatus,
    ProviderStatementRecord,
    ReconciliationItem,
    ReconciliationReport,
    ReconciliationStatus,
)
from processing_gateway.payment_service import PaymentService
from processing_gateway.repository import PaymentRepository


class ReconciliationService:
    def __init__(self, repository: PaymentRepository, payment_service: PaymentService) -> None:
        self.repository = repository
        self.payment_service = payment_service

    def reconcile(
        self,
        records: list[ProviderStatementRecord],
        auto_resolve: bool = True,
    ) -> ReconciliationReport:
        provider_by_payment = {record.payment_id: record for record in records}
        items: list[ReconciliationItem] = []

        for payment in self.repository.list_payments():
            record = provider_by_payment.get(payment.id)
            if record is None:
                items.append(
                    ReconciliationItem(
                        payment_id=payment.id,
                        status=ReconciliationStatus.MISSING_PROVIDER,
                        details={"internal_status": payment.status.value},
                    )
                )
                continue

            if record.amount != payment.amount:
                items.append(
                    ReconciliationItem(
                        payment_id=payment.id,
                        status=ReconciliationStatus.AMOUNT_MISMATCH,
                        details={
                            "internal_amount": str(payment.amount),
                            "provider_amount": str(record.amount),
                        },
                    )
                )
                continue

            if record.status != payment.status:
                if (
                    auto_resolve
                    and payment.status is PaymentStatus.AUTHORIZED
                    and record.status is PaymentStatus.CAPTURED
                ):
                    self.payment_service.apply_provider_status(
                        payment.id,
                        PaymentStatus.CAPTURED,
                        record.provider_reference,
                    )
                    items.append(
                        ReconciliationItem(
                            payment_id=payment.id,
                            status=ReconciliationStatus.AUTO_RESOLVED,
                            details={"resolution": "Applied provider captured status."},
                        )
                    )
                else:
                    items.append(
                        ReconciliationItem(
                            payment_id=payment.id,
                            status=ReconciliationStatus.STATUS_MISMATCH,
                            details={
                                "internal_status": payment.status.value,
                                "provider_status": record.status.value,
                            },
                        )
                    )
                continue

            items.append(
                ReconciliationItem(
                    payment_id=payment.id,
                    status=ReconciliationStatus.MATCHED,
                    details={"status": payment.status.value},
                )
            )

        internal_ids = {payment.id for payment in self.repository.list_payments()}
        for record in records:
            if record.payment_id not in internal_ids:
                items.append(
                    ReconciliationItem(
                        payment_id=record.payment_id,
                        status=ReconciliationStatus.MISSING_INTERNAL,
                        details={"provider_status": record.status.value},
                    )
                )

        return ReconciliationReport(items=items)
