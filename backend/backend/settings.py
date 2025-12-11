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
    "django.contrib.sites",  # Required by allauth
    "rest_framework",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.headless",
    "core",
    "api",
    "accounts",
]

SITE_ID = 1

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",  # <-- MUST come before AuthenticationMiddleware
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",  # <-- required for admin
    "allauth.account.middleware.AccountMiddleware",  # <-- required by django-allauth
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

# ============================================================================
# REST FRAMEWORK CONFIGURATION
# ============================================================================

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        # "api.views.auth.JWTAuthentication",  # Causes circular import, use explicitly in views
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "EXCEPTION_HANDLER": "rest_framework.views.exception_handler",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
}

# ============================================================================
# JWT AUTHENTICATION CONFIGURATION
# ============================================================================

# JWT Secret - should be different from Django SECRET_KEY
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", SECRET_KEY)

# JWT Access Token lifetime (in seconds)
JWT_ACCESS_TOKEN_LIFETIME = int(
    os.getenv("JWT_ACCESS_TOKEN_LIFETIME", 900)
)  # 15 minutes

# Refresh Token lifetime (in days)
REFRESH_TOKEN_LIFETIME_DAYS = int(
    os.getenv("REFRESH_TOKEN_LIFETIME_DAYS", 30)
)  # 30 days

# ============================================================================
# DJANGO-ALLAUTH CONFIGURATION
# ============================================================================

# Authentication backends
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",  # Django default
    "allauth.account.auth_backends.AuthenticationBackend",  # allauth
]

# Allauth settings
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = True  # We use both email and username
ACCOUNT_EMAIL_VERIFICATION = "optional"  # Magic link handles verification
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USER_MODEL_USERNAME_FIELD = "username"
ACCOUNT_USER_MODEL_EMAIL_FIELD = "email"

# Headless mode settings
HEADLESS_FRONTEND_URLS = {
    "account_confirm_email": os.getenv(
        "FRONTEND_EMAIL_CONFIRM_URL", "http://localhost:3000/verify-email/{key}"
    ),
    "account_reset_password": os.getenv(
        "FRONTEND_PASSWORD_RESET_URL", "http://localhost:3000/reset-password/{key}"
    ),
}

# Use custom adapters
ACCOUNT_ADAPTER = "accounts.allauth_adapter.HeadlessAccountAdapter"
SOCIALACCOUNT_ADAPTER = "accounts.allauth_adapter.HeadlessSocialAccountAdapter"

# Social account providers
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
            "secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
            "key": "",
        },
        "SCOPE": [
            "profile",
            "email",
        ],
        "AUTH_PARAMS": {
            "access_type": "online",
        },
        "VERIFIED_EMAIL": True,
    }
}

# ============================================================================
# EMAIL CONFIGURATION
# ============================================================================

# Email backend
if DEBUG:
    # Development: Console backend (prints to terminal)
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    # Production: SMTP backend
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
    EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() in ("true", "1", "yes")
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")

# Email settings
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@gonaj.app")
SERVER_EMAIL = os.getenv("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

# Magic link token max age (in seconds)
MAGIC_LINK_TOKEN_MAX_AGE = int(os.getenv("MAGIC_LINK_TOKEN_MAX_AGE", 900))  # 15 minutes
