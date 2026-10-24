from django.urls import include, path
from django.contrib import admin

urlpatterns = [path("auth/", include("accounts.urls")), path("admin/", admin.site.urls)]
