"""Environment configuration. Production fails closed without a strong key."""
import os

from django.core.exceptions import ImproperlyConfigured


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in {"1", "true", "yes"}


DEBUG = env_bool("DEBUG")
SECRET_KEY = os.environ.get("SECRET_KEY", "")
if len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5:
    raise ImproperlyConfigured("Set SECRET_KEY to a random value of at least 50 characters.")

ALLOWED_HOSTS = [host.strip() for host in os.environ.get(
    "ALLOWED_HOSTS", "localhost,127.0.0.1" if DEBUG else ""
).split(",") if host.strip()]
if not DEBUG and (not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS):
    raise ImproperlyConfigured("Set explicit ALLOWED_HOSTS for production.")
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.environ.get(
    "CSRF_TRUSTED_ORIGINS", ""
).split(",") if origin.strip()]
# Only nginx is published; it overwrites this header before forwarding requests.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
# Start with one hour; increase after HTTPS monitoring, without committing all subdomains.
SECURE_HSTS_SECONDS = 0 if DEBUG else int(os.environ.get("SECURE_HSTS_SECONDS", "3600"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS")
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
