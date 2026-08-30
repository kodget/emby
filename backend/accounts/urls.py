from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

router = DefaultRouter()
router.register(r'announcements', views.AnnouncementViewSet, basename='announcement')
router.register(r'exam-countdowns', views.ExamCountdownViewSet, basename='exam-countdown')

urlpatterns = [
    # Authentication
    path('signup/', views.signup, name='signup'),
    path('login/', views.login, name='login'),
    path('google-login/', views.google_login, name='google-login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('verify-email/', views.verify_email, name='verify-email'),
    path('resend-verification/', views.resend_verification, name='resend-verification'),
    
    # Password Reset
    path('forgot-password/', views.forgot_password, name='forgot-password'),
    path('reset-password/', views.reset_password, name='reset-password'),
    path('change-password/', views.change_password, name='change-password'),
    
    # Onboarding
    path('onboarding/questions/', views.get_onboarding_questions, name='onboarding-questions'),
    path('onboarding/submit/', views.submit_onboarding, name='submit-onboarding'),
    path('onboarding/responses/update/', views.update_onboarding_responses, name='update-onboarding-responses'),
    
    # Class
    path('class/join/', views.join_class, name='join-class'),
    path('class/my-class/', views.get_my_class, name='my-class'),
    path('class/validate-code/', views.validate_class_code, name='validate-class-code'),
    
    # Class Head Verification
    path('class-head/request-verification/', views.request_class_head_verification, name='request-class-head-verification'),
    path('class-head/verify/', views.verify_class_head, name='verify-class-head'),
    path('class-head/pending/', views.pending_class_head_verifications, name='pending-class-head-verifications'),
    
    # Profile
    path('profile/', views.get_profile, name='profile'),
    path('profile/update/', views.update_profile, name='update-profile'),
    
    # Payment
    path('payment/initiate/', views.initiate_payment, name='initiate-payment'),
    path('payment/verify/', views.verify_payment, name='verify-payment'),
    
    # Admin
    path('admin/analytics/', __import__('accounts.admin_views').admin_views.get_analytics, name='admin-analytics'),
    path('admin/users/', __import__('accounts.admin_views').admin_views.get_users, name='admin-users'),
    path('admin/curriculum/', __import__('accounts.admin_views').admin_views.get_curriculum, name='admin-curriculum'),
    path('admin/payments/', __import__('accounts.admin_views').admin_views.get_payments, name='admin-payments'),
    
    # Universal Admin
    path('admin/schema/', __import__('accounts.universal_admin').universal_admin.admin_schema, name='admin-schema'),
    path('admin/data/<str:app_label>/<str:model_name>/', __import__('accounts.universal_admin').universal_admin.admin_data_list, name='admin-data-list'),
    path('admin/data/<str:app_label>/<str:model_name>/<str:pk>/', __import__('accounts.universal_admin').universal_admin.admin_data_detail, name='admin-data-detail'),
    
    # Router URLs
    path('', include(router.urls)),
]
