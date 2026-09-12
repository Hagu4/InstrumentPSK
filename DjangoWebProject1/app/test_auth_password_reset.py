from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from unittest.mock import patch
import smtplib


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PasswordResetFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="reset-user",
            email="reset@example.com",
            password="Old-password-123",
        )

    def test_login_has_working_password_reset_link(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, reverse("password_reset"))

    def test_password_reset_request_sends_email(self):
        response = self.client.post(
            reverse("password_reset"),
            {"email": self.user.email},
        )
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)

    def test_smtp_failure_does_not_expose_account_or_credentials(self):
        error = smtplib.SMTPAuthenticationError(535, b"sensitive smtp details")
        with patch("django.core.mail.EmailMultiAlternatives.send", side_effect=error):
            with self.assertLogs("app.password_reset", level="ERROR") as logs:
                response = self.client.post(reverse("password_reset"), {"email": self.user.email})
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertNotIn("sensitive smtp details", " ".join(logs.output))
        unknown = self.client.post(reverse("password_reset"), {"email": "missing@example.com"})
        self.assertEqual(response.status_code, unknown.status_code)
        self.assertEqual(response.url, unknown.url)

    def test_connection_failure_is_handled(self):
        with patch("django.core.mail.EmailMultiAlternatives.send", side_effect=TimeoutError):
            with self.assertLogs("app.password_reset", level="ERROR"):
                response = self.client.post(reverse("password_reset"), {"email": self.user.email})
        self.assertRedirects(response, reverse("password_reset_done"))

    def test_programming_errors_are_not_silently_swallowed(self):
        with patch("django.core.mail.EmailMultiAlternatives.send", side_effect=ValueError):
            with self.assertRaises(ValueError):
                self.client.post(reverse("password_reset"), {"email": self.user.email})
