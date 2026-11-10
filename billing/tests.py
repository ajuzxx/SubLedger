from datetime import date
from decimal import Decimal
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from django.test import TestCase

from billing.models import (
    Plan,
    Customer,
    Subscription,
    Invoice,
    PaymentAttempt,
    LedgerEntry,
)

from billing.services.subscription_service import SubscriptionService
from billing.services.invoice_service import InvoiceService
from billing.services.payment_service import PaymentService


class SubscriptionServiceTests(TestCase):

    def setUp(self):
        self.customer = Customer.objects.create(
            name="Test Customer",
            email="test@example.com",
        )

        self.plan = Plan.objects.create(
            name="Pro",
            description="Pro subscription",
            price=Decimal("999.00"),
            currency="INR",
            billing_cycle="monthly",
            is_active=True,
        )

    def test_create_subscription_successfully(self):
        subscription = SubscriptionService.create_subscription(
            customer=self.customer,
            plan=self.plan,
            start_date=date(2026, 11, 10),
            end_date=date(2026, 12, 10),
        )

        self.assertEqual(subscription.status, "active")
        self.assertEqual(subscription.customer, self.customer)
        self.assertEqual(subscription.plan, self.plan)

    def test_cannot_subscribe_to_inactive_plan(self):
        self.plan.is_active = False
        self.plan.save()

        with self.assertRaisesMessage(
            ValueError,
            "Cannot subscribe to an inactive plan."
        ):
            SubscriptionService.create_subscription(
                customer=self.customer,
                plan=self.plan,
                start_date=date(2026, 11, 10),
                end_date=date(2026, 12, 10),
            )

    def test_prevent_duplicate_active_subscription(self):
        SubscriptionService.create_subscription(
            customer=self.customer,
            plan=self.plan,
            start_date=date(2026, 11, 10),
            end_date=date(2026, 12, 10),
        )

        with self.assertRaisesMessage(
            ValueError,
            "Customer already has an active subscription to this plan."
        ):
            SubscriptionService.create_subscription(
                customer=self.customer,
                plan=self.plan,
                start_date=date(2026, 12, 10),
                end_date=date(2027, 1, 10),
            )


class InvoiceServiceTests(TestCase):

    def setUp(self):
        self.customer = Customer.objects.create(
            name="Test Customer",
            email="invoice@example.com",
        )

        self.plan = Plan.objects.create(
            name="Pro",
            description="Pro subscription",
            price=Decimal("999.00"),
            currency="INR",
            billing_cycle="monthly",
        )

        self.subscription = SubscriptionService.create_subscription(
            customer=self.customer,
            plan=self.plan,
            start_date=date(2026, 11, 10),
            end_date=date(2026, 12, 10),
        )

    def test_generate_invoice_successfully(self):
        invoice = InvoiceService.generate_invoice(
            subscription=self.subscription,
            billing_period_start=date(2026, 11, 10),
            billing_period_end=date(2026, 12, 9),
            due_date=date(2026, 11, 17),
        )

        self.assertEqual(invoice.amount_due, Decimal("999.00"))
        self.assertEqual(invoice.amount_paid, Decimal("0.00"))
        self.assertEqual(invoice.status, "pending")

        self.assertTrue(
            LedgerEntry.objects.filter(
                invoice=invoice,
                entry_type="invoice_created",
            ).exists()
        )

    def test_invoice_preserves_original_plan_price(self):
        invoice = InvoiceService.generate_invoice(
            subscription=self.subscription,
            billing_period_start=date(2026, 11, 10),
            billing_period_end=date(2026, 12, 9),
            due_date=date(2026, 11, 17),
        )

        self.plan.price = Decimal("1499.00")
        self.plan.save()

        invoice.refresh_from_db()

        self.assertEqual(invoice.amount_due, Decimal("999.00"))

    def test_prevent_duplicate_invoice(self):
        InvoiceService.generate_invoice(
            subscription=self.subscription,
            billing_period_start=date(2026, 11, 10),
            billing_period_end=date(2026, 12, 9),
            due_date=date(2026, 11, 17),
        )

        with self.assertRaisesMessage(
            ValueError,
            "An invoice already exists for this subscription and billing period."
        ):
            InvoiceService.generate_invoice(
                subscription=self.subscription,
                billing_period_start=date(2026, 11, 10),
                billing_period_end=date(2026, 12, 9),
                due_date=date(2026, 11, 17),
            )


class PaymentServiceTests(TestCase):

    def setUp(self):
        self.customer = Customer.objects.create(
            name="Test Customer",
            email="payment@example.com",
        )

        self.plan = Plan.objects.create(
            name="Pro",
            description="Pro subscription",
            price=Decimal("999.00"),
            currency="INR",
            billing_cycle="monthly",
        )

        self.subscription = SubscriptionService.create_subscription(
            customer=self.customer,
            plan=self.plan,
            start_date=date(2026, 11, 10),
            end_date=date(2026, 12, 10),
        )

        self.invoice = InvoiceService.generate_invoice(
            subscription=self.subscription,
            billing_period_start=date(2026, 11, 10),
            billing_period_end=date(2026, 12, 9),
            due_date=date(2026, 11, 17),
        )

    def test_partial_payment(self):
        attempt, invoice = PaymentService.process_payment(
            invoice=self.invoice,
            amount=Decimal("400.00"),
            currency="INR",
            status="successful",
            provider_reference="TEST-TXN-001",
        )

        invoice.refresh_from_db()

        self.assertEqual(attempt.status, "successful")
        self.assertEqual(invoice.amount_paid, Decimal("400.00"))
        self.assertEqual(invoice.status, "partially_paid")

    def test_full_payment(self):
        PaymentService.process_payment(
            invoice=self.invoice,
            amount=Decimal("999.00"),
            currency="INR",
            status="successful",
            provider_reference="TEST-TXN-002",
        )

        self.invoice.refresh_from_db()

        self.assertEqual(self.invoice.amount_paid, Decimal("999.00"))
        self.assertEqual(self.invoice.status, "paid")

    def test_failed_payment_does_not_update_invoice(self):
        attempt, invoice = PaymentService.process_payment(
            invoice=self.invoice,
            amount=Decimal("999.00"),
            currency="INR",
            status="failed",
            provider_reference="TEST-TXN-003",
        )

        invoice.refresh_from_db()

        self.assertEqual(attempt.status, "failed")
        self.assertEqual(invoice.amount_paid, Decimal("0.00"))
        self.assertEqual(invoice.status, "pending")

        self.assertTrue(
            LedgerEntry.objects.filter(
                invoice=invoice,
                entry_type="payment_failure",
            ).exists()
        )

    def test_prevent_overpayment(self):
        attempts_before = PaymentAttempt.objects.count()

        with self.assertRaisesMessage(
            ValueError,
            "Payment amount exceeds the remaining invoice balance."
        ):
            PaymentService.process_payment(
                invoice=self.invoice,
                amount=Decimal("1500.00"),
                currency="INR",
                status="successful",
                provider_reference="TEST-TXN-004",
            )

        self.assertEqual(
            PaymentAttempt.objects.count(),
            attempts_before,
        )

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.amount_paid, Decimal("0.00"))

    def test_prevent_duplicate_provider_reference(self):
        PaymentService.process_payment(
            invoice=self.invoice,
            amount=Decimal("100.00"),
            currency="INR",
            status="successful",
            provider_reference="TEST-TXN-005",
        )

        with self.assertRaisesMessage(
            ValueError,
            "This payment reference has already been used."
        ):
            PaymentService.process_payment(
                invoice=self.invoice,
                amount=Decimal("100.00"),
                currency="INR",
                status="successful",
                provider_reference="TEST-TXN-005",
            )

    def test_reject_missing_provider_reference(self):
        with self.assertRaisesMessage(
            ValueError,
            "Provider reference is required."
        ):
            PaymentService.process_payment(
                invoice=self.invoice,
                amount=Decimal("100.00"),
                currency="INR",
                status="successful",
                provider_reference="",
            )
class BillingAPITests(APITestCase):

    def setUp(self):
        # Create a customer
        self.customer = Customer.objects.create(
            name="API Test Customer",
            email="api-test@example.com",
        )

        # Create a plan
        self.plan = Plan.objects.create(
            name="API Pro",
            description="API testing plan",
            price=Decimal("999.00"),
            currency="INR",
            billing_cycle="monthly",
        )

        # Create a subscription
        self.subscription = SubscriptionService.create_subscription(
            customer=self.customer,
            plan=self.plan,
            start_date=date(2026, 11, 10),
            end_date=date(2027, 11, 9),
        )

        # Create an invoice for payment tests
        self.invoice = InvoiceService.generate_invoice(
            subscription=self.subscription,
            billing_period_start=date(2026, 11, 10),
            billing_period_end=date(2026, 12, 9),
            due_date=date(2026, 11, 17),
        )

    def test_get_plans(self):
        response = self.client.get(reverse("plan-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_get_customers(self):
        response = self.client.get(reverse("customer-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_create_subscription_with_existing_active_subscription(self):
        response = self.client.post(
            reverse("subscription-list"),
            {
                "customer": self.customer.id,
                "plan": self.plan.id,
                "start_date": "2026-12-10",
                "end_date": "2027-01-09",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_create_subscription_successfully(self):
        another_customer = Customer.objects.create(
            name="Another Customer",
            email="another-api-test@example.com",
        )

        response = self.client.post(
            reverse("subscription-list"),
            {
                "customer": another_customer.id,
                "plan": self.plan.id,
                "start_date": "2026-11-10",
                "end_date": "2027-11-09",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

    def test_create_invoice_successfully(self):
        response = self.client.post(
            reverse("invoice-list"),
            {
                "subscription": self.subscription.id,
                "billing_period_start": "2026-12-10",
                "billing_period_end": "2027-01-09",
                "due_date": "2026-12-17",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            Decimal(response.data["amount_due"]),
            Decimal("999.00"),
        )

    def test_prevent_duplicate_invoice_through_api(self):
        response = self.client.post(
            reverse("invoice-list"),
            {
                "subscription": self.subscription.id,
                "billing_period_start": "2026-11-10",
                "billing_period_end": "2026-12-09",
                "due_date": "2026-11-17",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_successful_payment_through_api(self):
        response = self.client.post(
            reverse("payment-list"),
            {
                "invoice": self.invoice.id,
                "amount": "400.00",
                "currency": "INR",
                "status": "successful",
                "provider_reference": "API-TEST-PAYMENT-001",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.invoice.refresh_from_db()

        self.assertEqual(
            self.invoice.amount_paid,
            Decimal("400.00"),
        )

        self.assertEqual(
            self.invoice.status,
            "partially_paid",
        )

    def test_failed_payment_through_api(self):
        response = self.client.post(
            reverse("payment-list"),
            {
                "invoice": self.invoice.id,
                "amount": "999.00",
                "currency": "INR",
                "status": "failed",
                "provider_reference": "API-TEST-PAYMENT-002",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.invoice.refresh_from_db()

        self.assertEqual(
            self.invoice.amount_paid,
            Decimal("0.00"),
        )

        self.assertEqual(self.invoice.status, "pending")

    def test_overpayment_rejected_through_api(self):
        response = self.client.post(
            reverse("payment-list"),
            {
                "invoice": self.invoice.id,
                "amount": "1500.00",
                "currency": "INR",
                "status": "successful",
                "provider_reference": "API-TEST-PAYMENT-003",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.invoice.refresh_from_db()

        self.assertEqual(
            self.invoice.amount_paid,
            Decimal("0.00"),
        )