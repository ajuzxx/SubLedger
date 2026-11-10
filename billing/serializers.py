from rest_framework import serializers
from .models import (
    Plan,
    Customer,
    Subscription,
    Invoice,
    PaymentAttempt,
)
class PlanSerializer(serializers.ModelSerializer):

    class Meta:
        model = Plan
        fields = "__all__"




class CustomerSerializer(serializers.ModelSerializer):

    class Meta:
        model = Customer
        fields = "__all__"

class SubscriptionSerializer(serializers.ModelSerializer):

    class Meta:
        model = Subscription
        fields = "__all__"

class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = "__all__"
        read_only_fields = [
            "invoice_number",
            "amount_due",
            "amount_paid",
            "currency",
            "status",
            "created_at",
            "updated_at",
        ]
class PaymentAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentAttempt
        fields = "__all__"
        read_only_fields = ["created_at"]