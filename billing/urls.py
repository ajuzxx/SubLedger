from rest_framework.routers import DefaultRouter
from .views import PlanViewSet, CustomerViewSet, SubscriptionViewSet

router = DefaultRouter()

router.register(
    r"plans",
    PlanViewSet,
    basename="plan"
)

router.register(
    r"customers",
    CustomerViewSet,
    basename="customer"

)

router.register(
    r"subscriptions",
    SubscriptionViewSet,
    basename="subscription"
)

urlpatterns = router.urls