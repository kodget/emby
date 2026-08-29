from django.urls import path

from . import views

urlpatterns = [
    # The price catalogue: the frontend reads this instead of hardcoding amounts.
    path("plans/", views.plans, name="payment-plans"),
    path("checkout/", views.checkout, name="checkout"),
    path("verify/", views.verify, name="verify"),
    path("webhook/", views.webhook, name="webhook"),
]
