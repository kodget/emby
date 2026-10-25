"""Validate Render runtime configuration without logging any secret values."""
from django.core.exceptions import ImproperlyConfigured


def validate_deployment(environ):
    if str(environ.get("RENDER", "")).lower() != "true":
        return
    enabled = lambda name: str(environ.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}
    problems = []
    if enabled("DEBUG"):
        problems.append("Set DEBUG=False on Render")
    secret = environ.get("SECRET_KEY", "")
    if len(secret.encode("utf-8")) < 32 or secret.startswith("django-insecure"):
        problems.append("Set a strong, stable SECRET_KEY shared by web, worker and scheduler")
    if not str(environ.get("REDIS_URL", "")).strip():
        problems.append("Set REDIS_URL to the shared Channels/Celery Redis service")
    if enabled("CELERY_TASK_ALWAYS_EAGER"):
        problems.append("Set CELERY_TASK_ALWAYS_EAGER=False and run the Celery worker")
    if problems:
        raise ImproperlyConfigured(". ".join(problems) + ".")
