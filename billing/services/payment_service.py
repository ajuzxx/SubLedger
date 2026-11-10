from decimal import Decimal

from django.db import transaction

from billing.models import (
    Invoice,
    PaymentAttempt,
    LedgerEntry,
)


class PaymentService:

    @staticmethod
    @transaction.atomic
    def process_payment(
        invoice,
        amount,
        currency,
        status,
        provider_reference,
    ):

        # Lock the invoice to prevent concurrent payment updates.
        invoice = Invoice.objects.select_for_update().get(
            id=invoice.id
        )

        # 1. Validate payment amount.
        if amount <= Decimal("0.00"):
            raise ValueError("Payment amount must be greater than zero.")

        # 2. Validate currency.
        if currency != invoice.currency:
            raise ValueError("Payment currency does not match invoice currency.")

        # 3. Validate payment status.
        if status not in ["successful", "failed"]:
            raise ValueError("Payment status must be successful or failed.")


        if not provider_reference:
            raise ValueError("Provider reference is required.")

        existing_attempt = PaymentAttempt.objects.filter(
            provider_reference=provider_reference
        ).exists()

        if existing_attempt:
            raise ValueError("This payment reference has already been used.")
        





        # 4. Prevent payment against a fully paid invoice.
        if invoice.status == "paid":
            raise ValueError("This invoice is already fully paid.")

        # 5. Create payment attempt.
        payment_attempt = PaymentAttempt.objects.create(
            invoice=invoice,
            amount=amount,
            currency=currency,
            status=status,
            provider_reference=provider_reference,
        )

        # 6. Handle failed payment.
        if status == "failed":

            LedgerEntry.objects.create(
                customer=invoice.subscription.customer,
                invoice=invoice,
                entry_type="payment_failure",
                amount=amount,
                currency=currency,
                reference_id=provider_reference,
                description="Payment failed.",
            )

            return payment_attempt, invoice

        # 7. Validate remaining invoice balance.
        remaining_amount = invoice.amount_due - invoice.amount_paid

        if amount > remaining_amount:
            raise ValueError(
                "Payment amount exceeds the remaining invoice balance."
            )

        # 8. Update invoice amount paid.
        invoice.amount_paid += amount

        # 9. Update invoice status.
        if invoice.amount_paid == invoice.amount_due:
            invoice.status = "paid"
        else:
            invoice.status = "partially_paid"

        invoice.save(
            update_fields=["amount_paid", "status", "updated_at"]
        )

        # 10. Create successful payment ledger entry.
        LedgerEntry.objects.create(
            customer=invoice.subscription.customer,
            invoice=invoice,
            entry_type="payment_success",
            amount=amount,
            currency=currency,
            reference_id=provider_reference,
            description="Payment completed successfully.",
        )

        return payment_attempt, invoice