import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Generate with: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
# SECRET_KEY - Must be set via environment variable
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if os.getenv("DJANGO_DEBUG", "True").lower() in ("true", "1", "yes"):
        # Development fallback
        SECRET_KEY = "django-insecure-dev-only-change-in-production"
    else:
        raise ValueError(
            "DJANGO_SECRET_KEY environment variable must be set in production!"
        )


# Convert string to boolean properly
DEBUG = os.getenv("DJANGO_DEBUG", "True").lower() in ("true", "1", "yes")

# Docker-aware ALLOWED_HOSTS configuration
if DEBUG:
    # Development: Allow Docker internal networking
    ALLOWED_HOSTS = os.getenv(
        "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0,[::1]"
    ).split(",")
else:
    # Production: Require explicit domain list
    allowed_hosts_str = os.getenv("DJANGO_ALLOWED_HOSTS", "")
    if not allowed_hosts_str:
        raise ValueError(
            "DJANGO_ALLOWED_HOSTS environment variable must be set in production! "
            "Example: DJANGO_ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com"
        )
    ALLOWED_HOSTS = [
        host.strip() for host in allowed_hosts_str.split(",") if host.strip()
    ]

AUTH_USER_MODEL = "core.User"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",  # GeoDjango
    "rest_framework",
    "core",
    "api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",  # <-- MUST come before AuthenticationMiddleware
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",  # <-- required for admin
    "django.contrib.messages.middleware.MessageMiddleware",  # <-- required for admin
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": os.getenv("POSTGRES_DB", "gonaj"),
        "USER": os.getenv("POSTGRES_USER", "gonajuser"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "gonajpass"),
        "HOST": os.getenv("DB_HOST", "db"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}


STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

ROOT_URLCONF = "backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "backend.wsgi.application"

GDAL_LIBRARY_PATH = os.getenv("GDAL_LIBRARY_PATH")

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
