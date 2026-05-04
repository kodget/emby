from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.upload_past_questions, name='upload_past_questions'),
    path('status/<int:upload_id>/', views.get_upload_status, name='upload_status'),
]
