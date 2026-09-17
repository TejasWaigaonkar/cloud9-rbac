import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

if len(SECRET_KEY) < 50 or not os.environ.get("POSTGRES_PASSWORD"):  # noqa: F405
    raise ImproperlyConfigured(
        "Set a random DJANGO_SECRET_KEY (50+ characters) and POSTGRES_PASSWORD."
    )
if not os.environ.get("DJANGO_ALLOWED_HOSTS") or "*" in ALLOWED_HOSTS:  # noqa: F405
    raise ImproperlyConfigured("Set explicit DJANGO_ALLOWED_HOSTS.")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
CSRF_TRUSTED_ORIGINS = os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")
if os.environ.get("TRUST_PROXY_PROTO") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_REDIRECT_EXEMPT = [r"^health/$", r"^ready/$"]
