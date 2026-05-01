from rest_framework.permissions import BasePermission


# -----------------------------------
# CHECK IF USER IS AUTHENTICATED
# -----------------------------------
class IsAuthenticated(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


# -----------------------------------
# STUDENT ONLY
# -----------------------------------
class IsStudent(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            hasattr(request.user, "profile") and
            request.user.profile.role == "student"
        )


# -----------------------------------
# CLASS REP ONLY
# -----------------------------------
class IsClassRep(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            hasattr(request.user, "profile") and
            request.user.profile.role == "class_rep"
        )


# -----------------------------------
# ORGANIZER ONLY
# -----------------------------------
class IsOrganizer(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            hasattr(request.user, "profile") and
            request.user.profile.role == "organizer"
        )


# -----------------------------------
# UPLOADER ONLY
# -----------------------------------
class IsUploader(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            hasattr(request.user, "profile") and
            request.user.profile.role == "uploader"
        )