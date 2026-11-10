from rest_framework.viewsets import ModelViewSet

from .models import Plan, Customer
from .serializers import PlanSerializer, CustomerSerializer


class PlanViewSet(ModelViewSet):
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer

class CustomerViewSet(ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer