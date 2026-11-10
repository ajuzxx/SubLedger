from rest_framework.routers import DefaultRouter
from .views import (
    PlanViewSet,
    CustomerViewSet,
    SubscriptionViewSet,
    InvoiceViewSet,
)
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
router.register(r"invoices", InvoiceViewSet, basename="invoice")
urlpatterns = router.urls