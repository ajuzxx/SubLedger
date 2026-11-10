from rest_framework.viewsets import ModelViewSet
from rest_framework.exceptions import ValidationError
from .models import Plan, Customer, Subscription, Invoice, PaymentAttempt
from .permissions import BillingRolePermission
from .serializers import (
    PlanSerializer,
    CustomerSerializer,
    SubscriptionSerializer,
    InvoiceSerializer,
    PaymentAttemptSerializer,
)

from .services.invoice_service import InvoiceService
from .services.subscription_service import SubscriptionService
from .services.payment_service import PaymentService

from .models import Plan, Customer,  Subscription, Invoice
from .serializers import (
    PlanSerializer,
    CustomerSerializer,
    SubscriptionSerializer,
    InvoiceSerializer,
)

class PlanViewSet(ModelViewSet):
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer
    permission_classes = [BillingRolePermission]
class CustomerViewSet(ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [BillingRolePermission]


class SubscriptionViewSet(ModelViewSet):
    queryset = Subscription.objects.select_related(
        "customer",
        "plan"
    )
    serializer_class = SubscriptionSerializer
    permission_classes = [BillingRolePermission]

    def perform_create(self, serializer):
        try:
            SubscriptionService.create_subscription(
                customer=serializer.validated_data["customer"],
                plan=serializer.validated_data["plan"],
                start_date=serializer.validated_data["start_date"],
                end_date=serializer.validated_data["end_date"],
            )

        except ValueError as error:
            raise ValidationError({"detail": str(error)})

class InvoiceViewSet(ModelViewSet):
    queryset = Invoice.objects.select_related(
        "subscription",
        "subscription__customer",
        "subscription__plan",
    )
    serializer_class = InvoiceSerializer
    permission_classes = [BillingRolePermission]


    def perform_create(self, serializer):
        try:
            invoice = InvoiceService.generate_invoice(
                subscription=serializer.validated_data["subscription"],
                billing_period_start=serializer.validated_data[
                    "billing_period_start"
                ],
                billing_period_end=serializer.validated_data[
                    "billing_period_end"
                ],
                due_date=serializer.validated_data["due_date"],
            )

            serializer.instance = invoice

        except ValueError as error:
            raise ValidationError({"detail": str(error)})

class PaymentViewSet(ModelViewSet):
    queryset = PaymentAttempt.objects.select_related(
        "invoice",
        "invoice__subscription",
        "invoice__subscription__customer",
    )
    serializer_class = PaymentAttemptSerializer
    permission_classes = [BillingRolePermission]

    def perform_create(self, serializer):
        try:
            payment_attempt, updated_invoice = (
                PaymentService.process_payment(
                    invoice=serializer.validated_data["invoice"],
                    amount=serializer.validated_data["amount"],
                    currency=serializer.validated_data["currency"],
                    status=serializer.validated_data["status"],
                    provider_reference=serializer.validated_data[
                        "provider_reference"
                    ],
                )
            )

            serializer.instance = payment_attempt

        except ValueError as error:
            raise ValidationError({"detail": str(error)})