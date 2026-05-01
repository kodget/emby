from django.contrib import admin
from django.core.mail import send_mail
from django.conf import settings
from .models import (
    Profile, School, ClassGroup, OnboardingQuestion,
    OnboardingResponse, Announcement, PaymentTransaction, ExamCountdown
)


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name']


@admin.register(ClassGroup)
class ClassGroupAdmin(admin.ModelAdmin):
    list_display = ['code', 'school', 'set_name', 'get_class_heads', 'is_active', 'created_at']
    list_filter = ['is_active', 'school']
    search_fields = ['code', 'set_name']
    readonly_fields = ['code']
    
    def get_class_heads(self, obj):
        """Display all class heads"""
        return ", ".join([head.get_full_name() or head.username for head in obj.class_heads.all()])
    get_class_heads.short_description = 'Class Heads'


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'school', 'subscription_tier', 'email_verified', 
                    'class_head_verified', 'class_head_verification_requested', 'onboarding_completed']
    list_filter = ['role', 'subscription_tier', 'email_verified', 'class_head_verified', 
                   'class_head_verification_requested', 'onboarding_completed']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at']
    actions = ['approve_class_heads', 'reject_class_heads']
    
    def approve_class_heads(self, request, queryset):
        """Bulk approve class heads"""
        count = 0
        for profile in queryset.filter(role='class_head', class_head_verification_requested=True):
            profile.class_head_verified = True
            profile.class_head_verification_requested = False
            profile.class_head_rejection_reason = ''

            if profile.class_group:
                profile.class_group.class_heads.add(profile.user)

            profile.save()

            # Send approval email with class code
            try:
                class_code = profile.class_group.code if profile.class_group else 'N/A'
                send_mail(
                    'Class Head Verified — Your Class Code',
                    f'Hi {profile.user.get_full_name() or profile.user.username},\n\n'
                    f'Your class head account has been verified!\n\n'
                    f'Your class code is: {class_code}\n\n'
                    f'Share this code with your classmates so they can join your class on Emby.\n\n'
                    f'You now have full access to all premium features.\n\n'
                    f'— The Emby Team',
                    settings.DEFAULT_FROM_EMAIL,
                    [profile.user.email],
                    fail_silently=True,
                )
            except Exception as e:
                self.message_user(request, f"Email failed for {profile.user.email}: {e}", level='warning')

            count += 1

        self.message_user(request, f"{count} class head(s) approved and notified.")
    approve_class_heads.short_description = "Approve selected class heads"
    
    def reject_class_heads(self, request, queryset):
        """Bulk reject class heads"""
        count = 0
        for profile in queryset.filter(role='class_head', class_head_verification_requested=True):
            profile.class_head_verified = False
            profile.class_head_verification_requested = False
            profile.class_head_rejection_reason = 'Rejected by admin'
            profile.save()
            count += 1
        
        self.message_user(request, f"{count} class head(s) rejected.")
    reject_class_heads.short_description = "Reject selected class heads"


@admin.register(OnboardingQuestion)
class OnboardingQuestionAdmin(admin.ModelAdmin):
    list_display = ['question_text', 'question_type', 'order', 'is_active']
    list_filter = ['question_type', 'is_active']
    ordering = ['order']


@admin.register(OnboardingResponse)
class OnboardingResponseAdmin(admin.ModelAdmin):
    list_display = ['user', 'question', 'answer', 'created_at']
    search_fields = ['user__username', 'answer']
    list_filter = ['question']


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'class_group', 'created_by', 'created_at']
    search_fields = ['title', 'content']
    list_filter = ['class_group', 'created_at']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ['reference', 'user', 'amount', 'status', 'subscription_months', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['reference', 'user__username', 'user__email']
    readonly_fields = ['created_at', 'verified_at']


@admin.register(ExamCountdown)
class ExamCountdownAdmin(admin.ModelAdmin):
    list_display = ['title', 'class_group', 'exam_date', 'days_remaining', 'created_by', 'created_at']
    search_fields = ['title', 'subject']
    list_filter = ['class_group', 'exam_date', 'subject']
    readonly_fields = ['created_at', 'updated_at', 'days_remaining']
    ordering = ['exam_date']
