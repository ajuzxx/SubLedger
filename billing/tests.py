from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User, Group

from rest_framework.test import APITestCase, APIClient
from rest_framework import status

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


# =====================================================================
# HELPER MIXIN — Creates users with roles for every test class
# =====================================================================

class RoleSetupMixin:
    """
    Creates three users, one per role (Admin, Billing Manager, Viewer),
    and provides helper methods to quickly switch between them.
    """

    def set_up_roles_and_users(self):
        # Create the three role groups
        self.admin_group = Group.objects.create(name="Admin")
        self.manager_group = Group.objects.create(name="Billing Manager")
        self.viewer_group = Group.objects.create(name="Viewer")

        # Admin user — full access
        self.admin_user = User.objects.create_user(
            username="admin_user",
            password="admin_pass_123",
        )
        self.admin_user.groups.add(self.admin_group)

        # Billing Manager user — read, create, update (no delete)
        self.manager_user = User.objects.create_user(
            username="manager_user",
            password="manager_pass_123",
        )
        self.manager_user.groups.add(self.manager_group)

        # Viewer user — read-only
        self.viewer_user = User.objects.create_user(
            username="viewer_user",
            password="viewer_pass_123",
        )
        self.viewer_user.groups.add(self.viewer_group)

        # Unauthenticated client (no login)
        self.anon_client = APIClient()

    def login_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)

    def login_as_manager(self):
        self.client.force_authenticate(user=self.manager_user)

    def login_as_viewer(self):
        self.client.force_authenticate(user=self.viewer_user)

    def login_as_anon(self):
        self.client.force_authenticate(user=None)


# =====================================================================
# 1. SERVICE-LAYER UNIT TESTS (no HTTP, no permissions)
# =====================================================================

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
            "Cannot subscribe to an inactive plan.",
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
            "Customer already has an active subscription to this plan.",
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

        # Change the plan price after invoice creation
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
            "An invoice already exists for this subscription and billing period.",
        ):
            InvoiceService.generate_invoice(
                subscription=self.subscription,
                billing_period_start=date(2026, 11, 10),
                billing_period_end=date(2026, 12, 9),
                due_date=date(2026, 11, 17),
            )

    def test_cannot_invoice_inactive_subscription(self):
        self.subscription.status = "cancelled"
        self.subscription.save()

        with self.assertRaisesMessage(
            ValueError,
            "Cannot generate invoice for an inactive subscription.",
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

    def test_successful_partial_payment(self):
        payment, updated_invoice = PaymentService.process_payment(
            invoice=self.invoice,
            amount=Decimal("400.00"),
            currency="INR",
            status="successful",
            provider_reference="PAY-PARTIAL-001",
        )
        self.assertEqual(payment.status, "successful")
        self.assertEqual(updated_invoice.amount_paid, Decimal("400.00"))
        self.assertEqual(updated_invoice.status, "partially_paid")

    def test_successful_full_payment(self):
        payment, updated_invoice = PaymentService.process_payment(
            invoice=self.invoice,
            amount=Decimal("999.00"),
            currency="INR",
            status="successful",
            provider_reference="PAY-FULL-001",
        )
        self.assertEqual(updated_invoice.amount_paid, Decimal("999.00"))
        self.assertEqual(updated_invoice.status, "paid")

    def test_failed_payment_does_not_change_balance(self):
        payment, updated_invoice = PaymentService.process_payment(
            invoice=self.invoice,
            amount=Decimal("999.00"),
            currency="INR",
            status="failed",
            provider_reference="PAY-FAIL-001",
        )
        self.assertEqual(payment.status, "failed")
        self.assertEqual(updated_invoice.amount_paid, Decimal("0.00"))
        self.assertEqual(updated_invoice.status, "pending")

    def test_overpayment_rejected(self):
        with self.assertRaisesMessage(
            ValueError,
            "Payment amount exceeds the remaining invoice balance.",
        ):
            PaymentService.process_payment(
                invoice=self.invoice,
                amount=Decimal("1500.00"),
                currency="INR",
                status="successful",
                provider_reference="PAY-OVER-001",
            )

    def test_payment_on_paid_invoice_rejected(self):
        PaymentService.process_payment(
            invoice=self.invoice,
            amount=Decimal("999.00"),
            currency="INR",
            status="successful",
            provider_reference="PAY-PAID-001",
        )

        with self.assertRaisesMessage(
            ValueError,
            "This invoice is already fully paid.",
        ):
            PaymentService.process_payment(
                invoice=self.invoice,
                amount=Decimal("100.00"),
                currency="INR",
                status="successful",
                provider_reference="PAY-PAID-002",
            )

    def test_duplicate_provider_reference_rejected(self):
        PaymentService.process_payment(
            invoice=self.invoice,
            amount=Decimal("400.00"),
            currency="INR",
            status="successful",
            provider_reference="PAY-DUP-001",
        )

        with self.assertRaisesMessage(
            ValueError,
            "This payment reference has already been used.",
        ):
            PaymentService.process_payment(
                invoice=self.invoice,
                amount=Decimal("100.00"),
                currency="INR",
                status="successful",
                provider_reference="PAY-DUP-001",
            )

    def test_ledger_entries_created_for_success(self):
        PaymentService.process_payment(
            invoice=self.invoice,
            amount=Decimal("999.00"),
            currency="INR",
            status="successful",
            provider_reference="PAY-LEDGER-001",
        )
        self.assertTrue(
            LedgerEntry.objects.filter(
                invoice=self.invoice,
                entry_type="payment_success",
            ).exists()
        )

    def test_ledger_entries_created_for_failure(self):
        PaymentService.process_payment(
            invoice=self.invoice,
            amount=Decimal("999.00"),
            currency="INR",
            status="failed",
            provider_reference="PAY-LEDGER-002",
        )
        self.assertTrue(
            LedgerEntry.objects.filter(
                invoice=self.invoice,
                entry_type="payment_failure",
            ).exists()
        )


# =====================================================================
# 2. ROLE-BASED ACCESS CONTROL (RBAC) PERMISSION TESTS
# =====================================================================

class PlanPermissionTests(RoleSetupMixin, APITestCase):

    def setUp(self):
        self.set_up_roles_and_users()
        self.plan_data = {
            "name": "Starter",
            "description": "Starter plan",
            "price": "499.00",
            "currency": "INR",
            "billing_cycle": "monthly",
        }
        self.plan = Plan.objects.create(
            name="Existing Plan",
            description="Already exists",
            price=Decimal("299.00"),
            currency="INR",
            billing_cycle="monthly",
        )

    # --- Admin: full access ---
    def test_admin_can_list_plans(self):
        self.login_as_admin()
        response = self.client.get(reverse("plan-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_can_create_plan(self):
        self.login_as_admin()
        response = self.client.post(
            reverse("plan-list"), self.plan_data, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_admin_can_delete_plan(self):
        self.login_as_admin()
        response = self.client.delete(
            reverse("plan-detail", args=[self.plan.id]),
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    # --- Billing Manager: read, create, update (no delete) ---
    def test_manager_can_list_plans(self):
        self.login_as_manager()
        response = self.client.get(reverse("plan-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_manager_can_create_plan(self):
        self.login_as_manager()
        response = self.client.post(
            reverse("plan-list"), self.plan_data, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_manager_cannot_delete_plan(self):
        self.login_as_manager()
        response = self.client.delete(
            reverse("plan-detail", args=[self.plan.id]),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # --- Viewer: read-only ---
    def test_viewer_can_list_plans(self):
        self.login_as_viewer()
        response = self.client.get(reverse("plan-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_viewer_cannot_create_plan(self):
        self.login_as_viewer()
        response = self.client.post(
            reverse("plan-list"), self.plan_data, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_viewer_cannot_delete_plan(self):
        self.login_as_viewer()
        response = self.client.delete(
            reverse("plan-detail", args=[self.plan.id]),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # --- Unauthenticated: no access ---
    def test_anon_cannot_list_plans(self):
        self.login_as_anon()
        response = self.client.get(reverse("plan-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_anon_cannot_create_plan(self):
        self.login_as_anon()
        response = self.client.post(
            reverse("plan-list"), self.plan_data, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class CustomerPermissionTests(RoleSetupMixin, APITestCase):

    def setUp(self):
        self.set_up_roles_and_users()
        self.customer_data = {
            "name": "Jane Doe",
            "email": "jane@example.com",
        }
        self.customer = Customer.objects.create(
            name="Existing Customer",
            email="existing@example.com",
        )

    def test_admin_can_create_customer(self):
        self.login_as_admin()
        response = self.client.post(
            reverse("customer-list"), self.customer_data, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_manager_can_create_customer(self):
        self.login_as_manager()
        response = self.client.post(
            reverse("customer-list"), self.customer_data, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_viewer_can_list_customers(self):
        self.login_as_viewer()
        response = self.client.get(reverse("customer-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_viewer_cannot_create_customer(self):
        self.login_as_viewer()
        response = self.client.post(
            reverse("customer-list"), self.customer_data, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anon_cannot_list_customers(self):
        self.login_as_anon()
        response = self.client.get(reverse("customer-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# =====================================================================
# 3. API INTEGRATION TESTS (Authenticated as Admin)
# =====================================================================

class PlanAPITests(RoleSetupMixin, APITestCase):

    def setUp(self):
        self.set_up_roles_and_users()
        self.login_as_admin()

    def test_create_plan(self):
        response = self.client.post(
            reverse("plan-list"),
            {
                "name": "Enterprise",
                "description": "Enterprise plan",
                "price": "4999.00",
                "currency": "INR",
                "billing_cycle": "yearly",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Enterprise")

    def test_list_plans(self):
        Plan.objects.create(
            name="Basic",
            description="Basic plan",
            price=Decimal("199.00"),
            currency="INR",
            billing_cycle="monthly",
        )
        response = self.client.get(reverse("plan-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_update_plan(self):
        plan = Plan.objects.create(
            name="Old Name",
            description="Old description",
            price=Decimal("100.00"),
            currency="INR",
            billing_cycle="monthly",
        )
        response = self.client.patch(
            reverse("plan-detail", args=[plan.id]),
            {"name": "New Name"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "New Name")


class SubscriptionAPITests(RoleSetupMixin, APITestCase):

    def setUp(self):
        self.set_up_roles_and_users()
        self.login_as_admin()

        self.customer = Customer.objects.create(
            name="API Customer",
            email="api@example.com",
        )
        self.plan = Plan.objects.create(
            name="Pro",
            description="Pro plan",
            price=Decimal("999.00"),
            currency="INR",
            billing_cycle="monthly",
            is_active=True,
        )

    def test_create_subscription(self):
        response = self.client.post(
            reverse("subscription-list"),
            {
                "customer": self.customer.id,
                "plan": self.plan.id,
                "start_date": "2026-11-10",
                "end_date": "2026-12-10",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_prevent_duplicate_subscription_via_api(self):
        self.client.post(
            reverse("subscription-list"),
            {
                "customer": self.customer.id,
                "plan": self.plan.id,
                "start_date": "2026-11-10",
                "end_date": "2026-12-10",
            },
            format="json",
        )
        response = self.client.post(
            reverse("subscription-list"),
            {
                "customer": self.customer.id,
                "plan": self.plan.id,
                "start_date": "2026-12-10",
                "end_date": "2027-01-10",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class InvoiceAPITests(RoleSetupMixin, APITestCase):

    def setUp(self):
        self.set_up_roles_and_users()
        self.login_as_admin()

        self.customer = Customer.objects.create(
            name="Invoice Customer",
            email="inv-api@example.com",
        )
        self.plan = Plan.objects.create(
            name="Pro",
            description="Pro plan",
            price=Decimal("999.00"),
            currency="INR",
            billing_cycle="monthly",
            is_active=True,
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
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
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
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PaymentAPITests(RoleSetupMixin, APITestCase):

    def setUp(self):
        self.set_up_roles_and_users()
        self.login_as_admin()

        self.customer = Customer.objects.create(
            name="Payment Customer",
            email="pay-api@example.com",
        )
        self.plan = Plan.objects.create(
            name="Pro",
            description="Pro plan",
            price=Decimal("999.00"),
            currency="INR",
            billing_cycle="monthly",
            is_active=True,
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

    def test_successful_payment_through_api(self):
        response = self.client.post(
            reverse("payment-list"),
            {
                "invoice": self.invoice.id,
                "amount": "400.00",
                "currency": "INR",
                "status": "successful",
                "provider_reference": "API-PAY-001",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.amount_paid, Decimal("400.00"))
        self.assertEqual(self.invoice.status, "partially_paid")

    def test_failed_payment_through_api(self):
        response = self.client.post(
            reverse("payment-list"),
            {
                "invoice": self.invoice.id,
                "amount": "999.00",
                "currency": "INR",
                "status": "failed",
                "provider_reference": "API-PAY-002",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.amount_paid, Decimal("0.00"))
        self.assertEqual(self.invoice.status, "pending")

    def test_overpayment_rejected_through_api(self):
        response = self.client.post(
            reverse("payment-list"),
            {
                "invoice": self.invoice.id,
                "amount": "1500.00",
                "currency": "INR",
                "status": "successful",
                "provider_reference": "API-PAY-003",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.amount_paid, Decimal("0.00"))

    def test_full_payment_marks_invoice_paid(self):
        response = self.client.post(
            reverse("payment-list"),
            {
                "invoice": self.invoice.id,
                "amount": "999.00",
                "currency": "INR",
                "status": "successful",
                "provider_reference": "API-PAY-004",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "paid")
