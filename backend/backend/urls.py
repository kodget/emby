"""
Root URL configuration for the EMBY backend.

Route map (matches the frontend's API client in lib/api.ts):
  /auth/   -> accounts      (auth, onboarding, class, profile, payments-lite)
  /api/    -> curriculum    (slides, decks, quiz, ai, community, schedule, stats...)
  /api/pastquestions/ -> pastquestions
  /api/payments/      -> payments (Paystack checkout/verify/webhook)
  /admin/  -> Django admin
"""

from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse


def health(_request):
    """Lightweight liveness probe."""
    return JsonResponse({"status": "ok", "service": "emby-backend"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),

    path("auth/", include("accounts.urls")),
    path("api/", include("curriculum.urls")),
    path("api/learning/", include("learning.urls")),
    path("api/pastquestions/", include("pastquestions.urls")),
    path("api/payments/", include("payments.urls")),
    path("api/credits/", include("credits.urls")),
]

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
