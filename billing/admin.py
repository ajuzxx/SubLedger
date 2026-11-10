from django.contrib import admin

from .models import (
    Plan,
    Customer,
    Subscription,
    Invoice,
    PaymentAttempt,
    LedgerEntry,
)

admin.site.register(Plan)
admin.site.register(Customer)
admin.site.register(Subscription)
admin.site.register(Invoice)
admin.site.register(PaymentAttempt)
admin.site.register(LedgerEntry)
