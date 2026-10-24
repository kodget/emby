from django.contrib.admin.apps import AdminConfig


class EmbyAdminConfig(AdminConfig):
    default_site = 'accounts.admin_site.EmbyAdminSite'
