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
]
if DEBUG and not TESTING:
    INSTALLED_APPS.append("debug_toolbar")

INSTALLED_APPS += getAppNames()

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

# Static files: Vite builds static/src into static/dist, which Django serves
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static" / "dist"]
STATIC_ROOT = BASE_DIR / "static" / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage" if DEBUG or TESTING
        else "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

BRAND_NAME = env("BRAND_NAME", default="Dakdot")
DEFAULT_CURRENCY = "UGX"

if not DEBUG and not TESTING:
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
    SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True
