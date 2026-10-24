from rest_framework.permissions import BasePermission
from .models import PlatformRole, ClassRole

# -----------------------------------
# CORE AUTHORIZATION FUNCTIONS
# -----------------------------------

def has_platform_admin_access(user):
    """Staff status alone does not grant access to every class or account."""
    return bool(user and user.is_authenticated and user.is_active and (
        user.is_superuser or getattr(getattr(user, 'profile', None), 'platform_role', None) == PlatformRole.ADMIN
    ))

def is_platform_admin(profile):
    """Check if the user has platform-wide administration privileges."""
    return profile.platform_role == PlatformRole.ADMIN

def can_manage_class(profile):
    """Check if the user has class-level management privileges."""
    if is_platform_admin(profile):
        return True
    return profile.is_class_head

def can_upload_slides(profile):
    """Check if the user can upload and manage slides for their class."""
    if can_manage_class(profile):
        return True
    if profile.class_role == ClassRole.CLASS_HEAD:
        return False
    if profile.class_role == ClassRole.MATERIAL_UPLOADER:
        return True
    if 'SLIDE_UPLOADER' in profile.class_capabilities:
        return True
    return False


def can_access_premium_features(profile):
    """Check if the user has access to premium features (entitlement wrapper)."""
    return profile.is_premium


# -----------------------------------
# DRF PERMISSION CLASSES
# -----------------------------------

class IsAuthenticated(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

class IsStudent(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and hasattr(request.user, "profile")

class IsClassHead(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated or not hasattr(request.user, "profile"):
            return False
        return can_manage_class(request.user.profile)

class IsSlideUploader(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated or not hasattr(request.user, "profile"):
            return False
        return can_upload_slides(request.user.profile)


class IsPlatformAdmin(BasePermission):
    message = 'Platform administrator access required.'

    def has_permission(self, request, view):
        return has_platform_admin_access(request.user)

class IsClassHeadOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        from rest_framework.permissions import SAFE_METHODS
        if request.method in SAFE_METHODS:
            return True
        if not request.user.is_authenticated or not hasattr(request.user, "profile"):
            return False
        return can_manage_class(request.user.profile)
