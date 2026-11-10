from rest_framework.viewsets import ModelViewSet
from rest_framework.exceptions import ValidationError

from .services.subscription_service import SubscriptionService
from .models import Plan, Customer,  Subscription
from .serializers import PlanSerializer, CustomerSerializer, SubscriptionSerializer


class PlanViewSet(ModelViewSet):
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer

class CustomerViewSet(ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer


class SubscriptionViewSet(ModelViewSet):
    queryset = Subscription.objects.select_related(
        "customer",
        "plan"
    )
    serializer_class = SubscriptionSerializer

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