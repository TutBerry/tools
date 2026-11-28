"""Validated environment-based Django settings for TutBerry."""
import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

def required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ImproperlyConfigured(f"Missing required environment variable: {name}")
    return value

SECRET_KEY = required("DJANGO_SECRET_KEY")
DATABASE_URL = required("DATABASE_URL")
DATABASES = {"default": dj_database_url.parse(DATABASE_URL)}
if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
    raise ImproperlyConfigured("DATABASE_URL must be PostgreSQL")
DEBUG_VALUE = os.getenv("DJANGO_DEBUG", "false").lower()
if DEBUG_VALUE not in {"true", "false"}:
    raise ImproperlyConfigured("DJANGO_DEBUG must be true or false")
DEBUG = DEBUG_VALUE == "true"
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
LOG_LEVEL = os.getenv("LOG_LEVEL", "info").lower()
if LOG_LEVEL not in {"debug", "info", "warning", "error"}:
    raise ImproperlyConfigured("Invalid LOG_LEVEL")
APP_VERSION = os.getenv("APP_VERSION", "0.1.0")
ROOT_URLCONF = "tutberry.urls"
INSTALLED_APPS = ["django.contrib.auth", "django.contrib.contenttypes", "rest_framework", "tutberry"]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "tutberry.middleware.NoStoreMiddleware",
    "tutberry.middleware.RequestLoggingMiddleware",
]
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": [
            "django.template.context_processors.debug",
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
        ]},
    }
]
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "tutberry.api_errors.api_exception_handler",
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.BasicAuthentication",
    ],
}

# Optional asynchronous infrastructure; legacy CI can run without services.
BROKER_URL = os.getenv("BROKER_URL", "amqp://tutberry:tutberry@broker:5672/")
CACHE_URL = os.getenv("CACHE_URL", "redis://cache:6379/0")
SMTP_HOST = os.getenv("SMTP_HOST", "mailpit")

def bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ImproperlyConfigured(f"Invalid {name}") from exc
    if not minimum <= value <= maximum:
        raise ImproperlyConfigured(f"Invalid {name}")
    return value

SMTP_PORT = bounded_int("SMTP_PORT", 1025, 1, 65535)
NOTIFICATION_MAX_ATTEMPTS = bounded_int("NOTIFICATION_MAX_ATTEMPTS", 3, 1, 10)
LISTINGS_CACHE_TTL_SECONDS = bounded_int("LISTINGS_CACHE_TTL_SECONDS", 5, 0, 300)
PROCESSED_EVENTS_TTL_HOURS = bounded_int("PROCESSED_EVENTS_TTL_HOURS", 24, 1, 168)
PROCESSING_LEASE_SECONDS = bounded_int("PROCESSING_LEASE_SECONDS", 60, 10, 600)

DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
