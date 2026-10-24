from django.contrib.admin import AdminSite


class EmbyAdminSite(AdminSite):
    def has_permission(self, request):
        from .permissions import has_platform_admin_access
        # Django's staff/model permissions still apply in addition to the platform role.
        return super().has_permission(request) and has_platform_admin_access(request.user)
