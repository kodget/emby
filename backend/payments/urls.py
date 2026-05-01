from django.urls import path
from . import views

urlpatterns = [
    path('checkout/', views.checkout, name='checkout'),
    path('verify/', views.verify, name='verify'),
    path('webhook/', views.webhook, name='webhook'),
]
