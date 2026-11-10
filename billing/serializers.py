from rest_framework import serializers
from .models import Plan, Customer, Subscription

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