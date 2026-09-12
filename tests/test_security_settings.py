import importlib.util
import os
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured

PATH = Path(__file__).resolve().parents[1] / 'DjangoWebProject1/DjangoWebProject1/security.py'


def load_settings(env):
    with patch.dict(os.environ, env, clear=True):
        spec = importlib.util.spec_from_file_location('isolated_security', PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


class SecuritySettingsTests(TestCase):
    key = 'test-only-key-with-enough-length-and-variety-0123456789-abcdef'

    def test_missing_key_prevents_startup(self):
        with self.assertRaises(ImproperlyConfigured):
            load_settings({})

    def test_short_key_prevents_startup(self):
        with self.assertRaises(ImproperlyConfigured):
            load_settings({'SECRET_KEY': 'weak'})

    def test_missing_or_wildcard_hosts_prevents_production_startup(self):
        for hosts in ('', '*'):
            with self.assertRaises(ImproperlyConfigured):
                load_settings({'SECRET_KEY': self.key, 'ALLOWED_HOSTS': hosts})

    def test_production_is_secure_by_default(self):
        settings = load_settings({'SECRET_KEY': self.key, 'ALLOWED_HOSTS': 'instrumentpsk.ru'})
        self.assertFalse(settings.DEBUG)
        self.assertTrue(settings.SECURE_SSL_REDIRECT)
        self.assertTrue(settings.SESSION_COOKIE_SECURE)
        self.assertTrue(settings.CSRF_COOKIE_SECURE)
        self.assertGreater(settings.SECURE_HSTS_SECONDS, 0)

    def test_local_development_still_supports_http(self):
        settings = load_settings({'SECRET_KEY': self.key, 'DEBUG': 'True'})
        self.assertFalse(settings.SECURE_SSL_REDIRECT)
        self.assertFalse(settings.SESSION_COOKIE_SECURE)
        self.assertIn('127.0.0.1', settings.ALLOWED_HOSTS)
