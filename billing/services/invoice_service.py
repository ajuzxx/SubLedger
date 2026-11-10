import uuid

from django.db import transaction

from billing.models import (
    Subscription,
    Invoice,
    LedgerEntry,
)


class InvoiceService:

    @staticmethod
    @transaction.atomic
    def generate_invoice(
        subscription,
        billing_period_start,
        billing_period_end,
        due_date,
    ):

        # 1. Check subscription status
        if subscription.status != "active":
            raise ValueError(
                "Cannot generate invoice for an inactive subscription."
            )

        # 2. Validate billing period
        if billing_period_start > billing_period_end:
            raise ValueError(
                "Billing period start cannot be after billing period end."
            )

        # 3. Generate unique invoice number
        invoice_number = (
            f"INV-{uuid.uuid4().hex[:8].upper()}"
        )

        # 4. Create invoice
        invoice = Invoice.objects.create(
            subscription=subscription,
            invoice_number=invoice_number,
            amount_due=subscription.plan.price,
            amount_paid=0,
            currency=subscription.plan.currency,
            billing_period_start=billing_period_start,
            billing_period_end=billing_period_end,
            due_date=due_date,
            status="pending",
        )

        # 5. Create ledger entry
        LedgerEntry.objects.create(
            customer=subscription.customer,
            invoice=invoice,
            entry_type="invoice_created",
            amount=invoice.amount_due,
            currency=invoice.currency,
            reference_id=invoice.invoice_number,
            description="Invoice generated successfully.",
        )

        return invoice