from django.urls import path
from . import views

urlpatterns = [
    path('balance/', views.get_balance, name='get_balance'),
    path('packages/', views.get_packages, name='get_packages'),
    path('history/', views.get_history, name='get_history'),
    path('purchase/', views.init_purchase, name='init_purchase'),
    path('verify-purchase/', views.verify_purchase, name='verify_purchase'),
]
