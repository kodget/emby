"""Isolated app tests: never import production settings or load any dotenv file."""
import os

SECRET_KEY = "isolated-test-secret-not-used-outside-tests"
DEBUG = True
USE_TZ = True
TIME_ZONE = "Africa/Lagos"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
ALLOWED_HOSTS = ["testserver", "localhost"]
INSTALLED_APPS = [
    "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions",
    "django.contrib.messages", "accounts.admin_config.EmbyAdminConfig", "django.contrib.staticfiles",
    "rest_framework", "accounts", "curriculum", "learning", "credits", "pastquestions",
]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
if os.environ.get("EMBY_TEST_POSTGRES") == "1":
    # Only a loopback, dedicated test cluster. Production DB_* variables are ignored.
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql", "NAME": "emby_tests",
        "USER": "emby_test", "HOST": "127.0.0.1", "PORT": "55432",
        "PASSWORD": "", "TEST": {"NAME": "test_emby_tests"},
    }}
ROOT_URLCONF = "tests.integration_urls"
MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "APP_DIRS": True,
              "OPTIONS": {"context_processors": [
                  "django.contrib.auth.context_processors.auth",
                  "django.contrib.messages.context_processors.messages",
                  "django.template.context_processors.request",
              ]}}]
STATIC_URL = "/static/"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
DEFAULT_FROM_EMAIL = "test@example.test"
FRONTEND_URL = "https://emby.example.test"
REST_FRAMEWORK = {"DEFAULT_AUTHENTICATION_CLASSES": [
    "rest_framework_simplejwt.authentication.JWTAuthentication",
]}
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"
CELERY_TASK_ALWAYS_EAGER = True
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
GOOGLE_CLIENT_ID = "isolated-test"
LLM_API_KEY = ""
YOUTUBE_API_KEY = ""

# URL-signing tests use inert credentials; no provider requests are allowed by fixtures.
import cloudinary
cloudinary.config(cloud_name='isolated-tests', api_key='test-key', api_secret='test-secret', secure=True)
