from django.contrib import admin, messages
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm
from django import forms

from .models import (
    Profile,
    School,
    ClassGroup,
    Announcement,
    ExamCountdown,
    PaymentTransaction,
    OnboardingQuestion,
    OnboardingResponse,
)


# =====================================
# INLINE PROFILE INSIDE USER ADMIN
# =====================================

class ProfileInline(admin.StackedInline):
    model = Profile
    fk_name = 'user'
    can_delete = False
    readonly_fields = (
        'class_head_verified', 'class_head_verification_requested',
        'class_head_rejection_reason', 'class_head_request_version',
        'class_head_reviewed_at', 'class_head_reviewed_by',
        'class_role', 'class_group', 'school', 'set_name',
    )


class ApprovalAwareUserChangeForm(UserChangeForm):
    def clean_is_active(self):
        from .class_heads import validate_reactivation
        from rest_framework.exceptions import ValidationError
        active = self.cleaned_data.get('is_active', False)
        try:
            validate_reactivation(self.instance.pk, active)
        except ValidationError as exc:
            raise forms.ValidationError(exc.detail) from None
        return active


class CustomUserAdmin(UserAdmin):
    form = ApprovalAwareUserChangeForm
    inlines = [ProfileInline]


# unregister default User admin
admin.site.unregister(User)

# register custom one
admin.site.register(User, CustomUserAdmin)


# =====================================
# PROFILE ADMIN
# =====================================

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):

    list_display = (
        'user',
        'class_role',
        'school',
        'class_group',
        'class_head_verified',
        'class_head_verification_requested',
        'subscription_tier',
        'email_verified',
    )

    list_filter = (
        'class_role',
        'subscription_tier',
        'class_head_verified',
        'email_verified',
    )

    search_fields = (
        'user__username',
        'user__email',
        'school__name',
    )

    readonly_fields = ProfileInline.readonly_fields + ('user',)

    actions = ['approve_class_heads']

    def approve_class_heads(self, request, queryset):
        from .class_heads import review_class_head
        from rest_framework.exceptions import APIException
        for profile in queryset:
            try:
                review_class_head(actor=request.user, user_id=profile.user_id, approved=True)
                self.message_user(request, f'Approved {profile.user}.', messages.SUCCESS)
            except APIException as exc:
                self.message_user(request, f'{profile.user}: {exc.detail}', messages.ERROR)

    approve_class_heads.short_description = "Approve selected class heads"


# =====================================
# CLASS GROUP ADMIN
# =====================================

@admin.register(ClassGroup)
class ClassGroupAdmin(admin.ModelAdmin):

    list_display = (
        'code',
        'school',
        'set_name',
        'is_active',
    )

    readonly_fields = ('class_heads',)


# =====================================
# OTHER MODELS
# =====================================

admin.site.register(School)
admin.site.register(Announcement)
admin.site.register(ExamCountdown)
admin.site.register(PaymentTransaction)
admin.site.register(OnboardingQuestion)
admin.site.register(OnboardingResponse)
