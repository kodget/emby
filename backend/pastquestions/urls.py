from django.urls import path
from . import views

urlpatterns = [
    path('upload-pq/', views.upload_past_questions, name='upload_past_questions'),

    path(
        'questions/<str:block_id>/',
        views.get_questions,
        name='get_questions_by_block'
    ),

    path(
        'questions/<str:block_id>/<str:topic>/',
        views.get_questions,
        name='get_questions_by_block_and_topic'
    ),
]