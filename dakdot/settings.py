import base64
import hashlib
import sys
from pathlib import Path

import environ

from dakdot.appsConfig import getAppNames

BASE_DIR = Path(__file__).resolve().parent.parent

# Env vars come from dakdot/.env (copy dakdot/.envtemp). Always give defaults as env("X", default=...).
env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / "dakdot" / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
TESTING = "test" in sys.argv  # `manage.py test`: no HTTPS redirect, plain static files

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["127.0.0.1", "localhost"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=["http://localhost:8000", "http://127.0.0.1:8000"])
INTERNAL_IPS = env.list("INTERNAL_IPS", default=["127.0.0.1"])


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",  # needed by the allauth MFA templates
    "django.forms",
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "allauth.mfa",
    "django_htmx",
    "django_extensions",
    "django_cotton",
    "django_cotton_ui",
    "simple_history",
    "ninja",
]
if DEBUG and not TESTING:
    INSTALLED_APPS.append("debug_toolbar")

# apps.core goes before django_cotton_ui so the kit overrides in apps/core/templates/cotton/ui/ win: with APP_DIRS,
# the first app holding a template path is the one used.
INSTALLED_APPS.insert(INSTALLED_APPS.index("django_cotton_ui"), "apps.core")
INSTALLED_APPS += [name for name in getAppNames() if name != "apps.core"]

SITE_ID = 1

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
]
if "debug_toolbar" in INSTALLED_APPS:
    MIDDLEWARE.append("debug_toolbar.middleware.DebugToolbarMiddleware")

ROOT_URLCONF = "dakdot.urls"

# App templates live in each app (templates/<app>/). The root templates/ only overrides allauth's pages.
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.nav",
                "apps.core.context_processors.brand",
            ],
        },
    },
]

WSGI_APPLICATION = "dakdot.wsgi.application"
ASGI_APPLICATION = "dakdot.asgi.application"

DATABASES = {"default": env.db("DATABASE_URL", default="sqlite:///db.sqlite3")}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Kampala"
USE_I18N = True
USE_TZ = True

AUTH_USER_MODEL = "accounts.User"

# allauth: email-only sign-in, no public sign-up (staff are added by an admin)
ACCOUNT_USER_MODEL_USERNAME_FIELD = "username"
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_ADAPTER = "accounts.adapters.NoSignupAdapter"
MFA_SUPPORTED_TYPES = ["totp", "webauthn", "recovery_codes"]
MFA_PASSKEY_LOGIN_ENABLED = True
MFA_WEBAUTHN_ALLOW_INSECURE_ORIGIN = DEBUG
MFA_TOTP_ISSUER = "Dakdot"
MFA_WEBAUTHN_RP_ID = env("MFA_WEBAUTHN_RP_ID", default="localhost")

LOGIN_REDIRECT_URL = "/app/"
LOGOUT_REDIRECT_URL = "account_login"
SESSION_COOKIE_AGE = 24 * 60 * 60

EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Dakdot Creations <connect@dakdot.com>")
SERVER_EMAIL = env("SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)
# Who gets an email with the details when a page crashes (DEBUG=False only), e.g. ADMINS=elijah@dakdot.com
ADMINS = [(email.split("@")[0], email) for email in env.list("ADMINS", default=[])]

# Static files: Vite builds static/src into static/dist, and `collectstatic` gathers them into one place.
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static" / "dist"]
STATIC_ROOT = BASE_DIR / "static" / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Azure Blob Storage (production). Give either AZURE_CONNECTION_STRING, or AZURE_ACCOUNT_NAME with AZURE_ACCOUNT_KEY.
# - Uploads (expense receipts, the company logo), with AZURE_CONTAINER set: a private container, every link a
#   signed URL that expires after AZURE_URL_EXPIRATION_SECS. Unset: on disk in MEDIA_ROOT, served to signed-in
#   staff by apps.core.views.media_file.
# - Static files (CSS, JS, fonts), with AZURE_STATIC_CONTAINER set: a public container, filled by `collectstatic`
#   on every deploy (entrypoint.sh). Unset: served by the app itself (whitenoise).
AZURE = {
    "connection_string": env("AZURE_CONNECTION_STRING", default="") or None,
    "account_name": env("AZURE_ACCOUNT_NAME", default="") or None,
    "account_key": env("AZURE_ACCOUNT_KEY", default="") or None,
}
AZURE_MEDIA_CONTAINER = env("AZURE_MEDIA_CONTAINER", default="")
AZURE_STATIC_CONTAINER = env("AZURE_STATIC_CONTAINER", default="")

if AZURE_MEDIA_CONTAINER:
    MEDIA_STORAGE = {"BACKEND": "storages.backends.azure_storage.AzureStorage", "OPTIONS": {
        **AZURE, "azure_container": AZURE_MEDIA_CONTAINER, "overwrite_files": False,
        "expiration_secs": env.int("AZURE_URL_EXPIRATION_SECS", default=300),
    }}
else:
    MEDIA_STORAGE = {"BACKEND": "django.core.files.storage.FileSystemStorage"}

if AZURE_STATIC_CONTAINER:
    # Public links, no signature. AZURE_STATIC_DOMAIN puts a CDN or custom domain in front, e.g. static.dakdot.com.
    STATIC_STORAGE = {"BACKEND": "apps.core.storages.AzureStaticStorage", "OPTIONS": {
        **AZURE, "azure_container": AZURE_STATIC_CONTAINER, "expiration_secs": None, "overwrite_files": True,
        "custom_domain": env("AZURE_STATIC_DOMAIN", default="") or None,
        "cache_control": "public, max-age=31536000, immutable",  # names are hashed, so cache them for good
    }}
elif DEBUG or TESTING:
    STATIC_STORAGE = {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}
else:
    STATIC_STORAGE = {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}

STORAGES = {"default": MEDIA_STORAGE, "staticfiles": STATIC_STORAGE}

# API (apps/api, django-ninja) for Dakdot's products' apps
API_RATE_LIMIT = env("API_RATE_LIMIT", default="120/m")  # per key; "<number>/<s|m|h|d>"
API_DOCS_ENABLED = env.bool("API_DOCS_ENABLED", default=True)  # /api/v1/docs, admins only
NINJA_PAGINATION_CLASS = "ninja.pagination.LimitOffsetPagination"
NINJA_PAGINATION_PER_PAGE = 50
NINJA_PAGINATION_MAX_LIMIT = 200
NINJA_NUM_PROXIES = env.int("NINJA_NUM_PROXIES", default=0)  # proxies in front of the app (for client IPs)

# Cache: the API rate limit and sign-in lockouts are counted here, so every worker must share it. In production it
# is a table in the database (no Redis needed; entrypoint.sh creates it with `manage.py createcachetable`).
# Locally it is in memory. CACHE_URL overrides either, e.g. redis://localhost:6379/1 later on.
CACHES = {"default": env.cache("CACHE_URL", default="locmemcache://" if DEBUG or TESTING else "dbcache://django_cache")}

# Encrypts project secrets (apps.core.crypto). Required in production: `uv run manage.py secrets_key` makes one.
# Locally it falls back to a key made from SECRET_KEY, so secrets saved in development need no setup.
SECRETS_KEY = env("SECRETS_KEY", default="")
if not SECRETS_KEY and (DEBUG or TESTING):
    SECRETS_KEY = base64.urlsafe_b64encode(hashlib.sha256(SECRET_KEY.encode()).digest()).decode()

BRAND_NAME = env("BRAND_NAME", default="Dakdot")
DEFAULT_CURRENCY = "UGX"

if not DEBUG and not TESTING:
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
    SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True
