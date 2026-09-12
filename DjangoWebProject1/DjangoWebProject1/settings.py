"""
Django settings for DjangoWebProject1 project.

Based on 'django-admin startproject' using Django 2.1.2.

For more information on this file, see
https://docs.djangoproject.com/en/2.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.1/ref/settings/
"""

import os
import posixpath
from dotenv import load_dotenv

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Загрузка переменных окружения из файла .env
load_dotenv(os.path.join(BASE_DIR, '.env'))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.1/howto/deployment/checklist/

from .security import *  # noqa: F403

# Application references
# https://docs.djangoproject.com/en/2.1/ref/settings/#std:setting-INSTALLED_APPS
INSTALLED_APPS = [
    'jazzmin', # Must be before django.contrib.admin
    'app',
    # Add your apps here to enable them
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize', # Added for humanize template tags
    'django.contrib.sitemaps',
    'django.contrib.sites',
]

SITE_ID = 1

JAZZMIN_SETTINGS = {
    # title of the window
    "site_title": "InstrumentPSK Админка",

    # Title on the login screen (19 chars max)
    "site_header": "InstrumentPSK",

    # Title on the brand (19 chars max)
    "site_brand": "InstrumentPSK",

    # Logo for the site, must be present in static files
    "site_logo": "app/content/favicon.png",

    # Welcome text on the login screen
    "welcome_sign": "Добро пожаловать в админку InstrumentPSK!",

    # Copyright on the footer
    "copyright": "InstrumentPSK",

    # List of model admins to search from the search bar
    "search_model": ["auth.User", "app.Product"],

    # Links to put along the top menu
    "topmenu_links": [
        {"name": "Сайт", "url": "/", "new_window": True},
        {"model": "auth.User"},
    ],

    # Custom CSS for the admin
    "custom_css": "app/css/admin_custom_v4.css",

    #############
    # Side Menu #
    #############
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_models": ["app.Profile", "app.ProductCharacteristic"],
    "order_with_respect_to": [
        "auth",
        "app.Product",
        "app.Category",
        "app.Characteristic",
        "app.Review",
        "app.Order",
        "app.OrderItem",
        "app.Feedback",
    ],

    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "app.Product": "fas fa-box-open",
        "app.Category": "fas fa-tags",
        "app.Brand": "fas fa-copyright",
        "app.RepairRequest": "fas fa-wrench",
        "app.Characteristic": "fas fa-cogs",
        "app.Review": "fas fa-star-half-alt",
        "app.Order": "fas fa-shopping-cart",
        "app.OrderItem": "fas fa-shopping-basket",
        "app.Feedback": "fas fa-comment-dots",
        "app.Favorite": "fas fa-heart",
        "app.Profile": "fas fa-id-card",
        "app.PromoCode": "fas fa-ticket-alt",
        "app.News": "fas fa-newspaper",
        "app.Promotion": "fas fa-bullhorn",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",

    #############
    # UI Tweaks #
    #############
    "show_ui_builder": False,
    "changeform_format": "horizontal_tabs",
    "theme": "darkly",
    "related_modal_active": True,
    "ui_tweaks": {
        "navbar_small_text": False,
        "footer_small_text": False,
        "body_small_text": True,
        "brand_small_text": False,
        "brand_colour": "navbar-dark",
        "accent": "accent-warning",
        "navbar": "navbar-light",
        "no_navbar_border": False,
        "navbar_fixed": True,
        "layout_boxed": False,
        "footer_fixed": False,
        "sidebar_fixed": True,
        "sidebar": "sidebar-dark-info",
        "sidebar_nav_small_text": False,
        "sidebar_disable_expand": False,
        "sidebar_nav_child_indent": False,
        "sidebar_nav_compact_style": False,
        "sidebar_nav_legacy_style": False,
        "sidebar_nav_flat_style": True,
        "theme": "darkly",
        "dark_mode_theme": "darkly",
        "button_classes": {
            "primary": "btn-primary",
            "secondary": "btn-secondary",
            "info": "btn-info",
            "warning": "btn-warning",
            "danger": "btn-danger",
            "success": "btn-success"
        }
    }
}

# Middleware framework
# https://docs.djangoproject.com/en/2.1/topics/http/middleware/
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'DjangoWebProject1.urls'

# Template configuration
# https://docs.djangoproject.com/en/2.1/topics/templates/
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
                'app.context_processors.categories_processor',
                'app.context_processors.cart_item_count',
            ],
        },
    },
]

WSGI_APPLICATION = 'DjangoWebProject1.wsgi.application'
import dj_database_url

# Database
# https://docs.djangoproject.com/en/2.1/ref/settings/#databases
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

# If DATABASE_URL is set in the environment, it will override the default sqlite3 settings
db_from_env = dj_database_url.config(conn_max_age=600, ssl_require=False)
if db_from_env:
    DATABASES['default'].update(db_from_env)

# Password validation
# https://docs.djangoproject.com/en/2.1/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/2.1/topics/i18n/
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.1/howto/static-files/
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'app', 'static'),
]

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

MEDIA_URL = '/media/'  # URL-префикс для медиафайлов
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')  # Путь к папке с медиафайлами

DEFAULT_CHARSET = 'utf-8'
FILE_CHARSET = 'utf-8'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_REDIRECT_URL = '/'
LOGIN_URL = 'login'

EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend'
    if DEBUG else 'django.core.mail.backends.smtp.EmailBackend',
)
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_TIMEOUT = 10
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '').replace(' ', '')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
WHITENOISE_MANIFEST_STRICT = False
