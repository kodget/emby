from rest_framework.permissions import BasePermission, SAFE_METHODS

from accounts.permissions import can_upload_slides
from .class_access import content_admin, member_class


def can_reprocess_upload(user, obj):
    if content_admin(user):
        return True
    profile = getattr(user, 'profile', None)
    group = member_class(user)
    return bool(profile and group and can_upload_slides(profile) and obj.class_group_id == group.pk
                and (profile.is_class_head or obj.uploaded_by_id == user.pk))


class PlatformAdminWritesOnly(BasePermission):
    message = 'Only platform administrators may edit the shared question catalogue.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and (
            request.method in SAFE_METHODS or content_admin(user)
        ))


class CanWriteUploadedContent(BasePermission):
    """Uploaders manage their own files; approved heads manage their class's files."""
    message = 'Only authorized uploaders can create content or manage their own uploads.'

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated or not user.is_active:
            return False
        if request.method in SAFE_METHODS:
            return True
        profile = getattr(user, 'profile', None)
        if profile is None:
            return False
        if content_admin(user):
            return True
        return bool(member_class(user) and can_upload_slides(profile))

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if content_admin(request.user):
            return True
        group = member_class(request.user)
        return bool(group and obj.class_group_id == group.pk and (
            request.user.profile.is_class_head or obj.uploaded_by_id == request.user.pk
        ))
