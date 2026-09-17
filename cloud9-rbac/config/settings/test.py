import os

from .base import *  # noqa: F403

SECRET_KEY = "test-only-not-a-deployment-secret-key-1234567890"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
if os.environ.get("TEST_SQLITE") == "1":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
            "ATOMIC_REQUESTS": True,
        }
    }
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
