from datetime import timedelta
from unittest.mock import patch

from django.apps import apps
from django.contrib import admin
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import path, reverse
from django.utils import timezone


def broken(request, token):
    raise ValueError('password=DO_NOT_STORE')


urlpatterns = [path('broken/<str:token>/', broken, name='broken'), path('admin/', admin.site.urls)]


@override_settings(ROOT_URLCONF=__name__, SECURE_SSL_REDIRECT=False)
class ErrorJournalTests(TestCase):
    def model(self):
        self.assertTrue(apps.get_app_config('app').models.get('errorevent'), 'Error journal model is missing')
        return apps.get_model('app', 'ErrorEvent')

    def fail_request(self):
        self.client.raise_request_exception = False
        return self.client.post('/broken/PRIVATE_TOKEN/?password=SECRET', {'password': 'FORM_SECRET'}, HTTP_COOKIE='secret=COOKIE_SECRET')

    def test_exception_is_recorded_without_request_secrets(self):
        model = self.model()
        self.assertEqual(self.fail_request().status_code, 500)
        event = model.objects.get()
        self.assertEqual(event.exception_type, 'ValueError')
        self.assertEqual(event.route, 'broken/<str:token>/')
        self.assertEqual(event.method, 'POST')
        self.assertIn('broken', event.stack)
        for secret in ['PRIVATE_TOKEN', 'SECRET', 'DO_NOT_STORE', 'HTTP_COOKIE']:
            self.assertNotIn(secret, str(event.__dict__))

    def test_repeats_aggregate_and_reopen(self):
        model = self.model()
        self.fail_request()
        model.objects.update(resolved=True)
        self.fail_request()
        event = model.objects.get()
        self.assertEqual(event.occurrences, 2)
        self.assertFalse(event.resolved)

    def test_staff_cannot_read_even_with_model_permissions(self):
        model = self.model()
        from django.contrib.auth.models import Permission
        user = User.objects.create_user('staff', is_staff=True)
        user.user_permissions.set(Permission.objects.filter(content_type__model='errorevent'))
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('admin:app_errorevent_changelist')).status_code, 403)

    def test_superuser_can_read_but_not_add(self):
        self.model()
        user = User.objects.create_superuser('owner', 'owner@example.test', 'test-password')
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('admin:app_errorevent_changelist')).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin:app_errorevent_add')).status_code, 403)

    def test_database_failure_does_not_replace_original_exception(self):
        model = self.model()
        with patch.object(model.objects, 'get_or_create', side_effect=RuntimeError('DB_SECRET')):
            with self.assertLogs('app.error_journal.fallback', level='ERROR') as logs:
                self.assertEqual(self.fail_request().status_code, 500)
        self.assertNotIn('DB_SECRET', str(logs.output))
        self.assertNotIn('DO_NOT_STORE', str(logs.output))

    def test_expired_entries_are_removed(self):
        model = self.model()
        old = model.objects.create(fingerprint='old', exception_type='Old')
        model.objects.filter(pk=old.pk).update(last_seen=timezone.now()-timedelta(days=31))
        self.fail_request()
        self.assertFalse(model.objects.filter(pk=old.pk).exists())

    def test_size_is_bounded(self):
        model = self.model()
        model.objects.bulk_create([model(fingerprint=f'old-{i}', exception_type='Old') for i in range(1000)])
        self.fail_request()
        self.assertEqual(model.objects.count(), 1000)
        self.assertTrue(model.objects.filter(exception_type='ValueError').exists())

    def test_anonymous_is_redirected_to_login(self):
        self.model()
        response = self.client.get(reverse('admin:app_errorevent_changelist'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)

    def test_owner_can_mark_resolved_but_cannot_forge_details(self):
        model = self.model()
        self.fail_request()
        event = model.objects.get()
        user = User.objects.create_superuser('owner', 'owner@example.test', 'test-password')
        self.client.force_login(user)
        response = self.client.post(reverse('admin:app_errorevent_change', args=[event.pk]), {
            'resolved': 'on', 'exception_type': 'Forged', '_save': 'Save',
        })
        self.assertEqual(response.status_code, 302)
        event.refresh_from_db()
        self.assertTrue(event.resolved)
        self.assertEqual(event.exception_type, 'ValueError')
