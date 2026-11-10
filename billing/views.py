from rest_framework.viewsets import ModelViewSet

from .models import Plan
from .serializers import PlanSerializer


class PlanViewSet(ModelViewSet):
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer