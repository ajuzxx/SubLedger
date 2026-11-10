from django.db import transaction

from billing.models import Subscription, Plan


class SubscriptionService:

    @staticmethod
    @transaction.atomic
    def create_subscription(customer, plan, start_date, end_date):

        if not plan.is_active:
            raise ValueError("Cannot subscribe to an inactive plan.")

        existing_subscription = Subscription.objects.filter(
            customer=customer,
            plan=plan,
            status="active"
        ).exists()

        if existing_subscription:
            raise ValueError(
                "Customer already has an active subscription to this plan."
            )

        return Subscription.objects.create(
            customer=customer,
            plan=plan,
            start_date=start_date,
            end_date=end_date,
            status="active"
        )