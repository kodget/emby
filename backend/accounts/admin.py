from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin

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
    can_delete = False


class CustomUserAdmin(UserAdmin):
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
        'role',
        'school',
        'class_group',
        'class_head_verified',
        'class_head_verification_requested',
        'subscription_tier',
        'email_verified',
    )

    list_filter = (
        'role',
        'subscription_tier',
        'class_head_verified',
        'email_verified',
    )

    search_fields = (
        'user__username',
        'user__email',
        'school__name',
    )

    list_editable = (
        'role',
        'class_head_verified',
    )

    actions = ['approve_class_heads']

    def approve_class_heads(self, request, queryset):

        for profile in queryset:

            profile.class_head_verified = True
            profile.class_head_verification_requested = False
            profile.save()

            if profile.class_group:
                profile.class_group.class_heads.add(profile.user)

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

    filter_horizontal = ('class_heads',)


# =====================================
# OTHER MODELS
# =====================================

admin.site.register(School)
admin.site.register(Announcement)
admin.site.register(ExamCountdown)
admin.site.register(PaymentTransaction)
admin.site.register(OnboardingQuestion)
admin.site.register(OnboardingResponse)