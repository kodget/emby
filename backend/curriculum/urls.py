from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SubjectViewSet, BlockViewSet, TopicViewSet, SectionViewSet, SlideViewSet, MaterialViewSet,
    UserProgressViewSet, ScheduleItemViewSet, UserStatsViewSet,
    CommunityPostViewSet, UpcomingTestViewSet, get_weekly_study_data, log_study_time, get_slide_content,
    generate_quiz, submit_quiz_answer, complete_quiz, get_quiz_history,
    ai_tutor, generate_questions_from_slide_view, ai_study_recommendations, suggest_videos,
    SlideDeckViewSet,
    reprocess_slide, reprocess_failed_slides, slide_processing_status, processing_overview,
)
from .upload_views import upload_file, delete_file
# New slide-aware AI views (replaces legacy textbook/video/mcq views)
from .ai_views import chat_with_slide, generate_resources, textbook_suggestions, video_suggestions, generate_mcqs, chat_history

router = DefaultRouter()
router.register(r'subjects', SubjectViewSet, basename='subject')
router.register(r'blocks', BlockViewSet, basename='block')
router.register(r'topics', TopicViewSet, basename='topic')
router.register(r'sections', SectionViewSet, basename='section')
router.register(r'slides', SlideViewSet, basename='slide')
router.register(r'materials', MaterialViewSet, basename='material')
router.register(r'progress', UserProgressViewSet, basename='progress')
router.register(r'schedule', ScheduleItemViewSet, basename='schedule')
router.register(r'stats', UserStatsViewSet, basename='stats')
router.register(r'community', CommunityPostViewSet, basename='community')
router.register(r'tests', UpcomingTestViewSet, basename='test')
router.register(r'decks', SlideDeckViewSet, basename='deck')

urlpatterns = [
    path('', include(router.urls)),
    path('upload/', upload_file, name='upload-file'),
    path('delete-file/', delete_file, name='delete-file'),
    path('slides/<str:slide_id>/content/', get_slide_content, name='slide-content'),
    path('quiz/generate/', generate_quiz, name='generate-quiz'),
    path('quiz/answer/', submit_quiz_answer, name='submit-quiz-answer'),
    path('quiz/<str:quiz_id>/complete/', complete_quiz, name='complete-quiz'),
    path('quiz/history/', get_quiz_history, name='quiz-history'),
    path('study-time/weekly/', get_weekly_study_data, name='weekly-study-data'),
    path('study-time/log/', log_study_time, name='log-study-time'),
    # AI endpoints — slide-aware (new implementation)
    path('ai/chat/', chat_with_slide, name='ai-chat'),
    path('ai/chat/history/', chat_history, name='ai-chat-history'),
    path('ai/resources/', generate_resources, name='ai-resources'),
    path('ai/textbook-suggestions/', textbook_suggestions, name='ai-textbook-suggestions'),
    path('ai/video-suggestions/', video_suggestions, name='ai-video-suggestions'),
    path('ai/generate-mcqs/', generate_mcqs, name='ai-generate-mcqs'),
    # Legacy AI endpoints (no path conflicts)
    path('ai/tutor/', ai_tutor, name='ai-tutor'),
    path('ai/recommendations/', ai_study_recommendations, name='ai-recommendations'),
    path('slides/<str:slide_id>/suggest-videos/', suggest_videos, name='suggest-videos'),
    path('slides/<str:slide_id>/generate-questions/', generate_questions_from_slide_view, name='generate-questions'),
    # Slide processing endpoints
    path('slides/<str:slide_id>/reprocess/', reprocess_slide, name='reprocess-slide'),
    path('slides/<str:slide_id>/status/', slide_processing_status, name='slide-processing-status'),
    path('processing/reprocess-failed/', reprocess_failed_slides, name='reprocess-failed-slides'),
    path('processing/overview/', processing_overview, name='processing-overview'),
]
