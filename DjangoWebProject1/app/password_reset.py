"""Password recovery with non-disclosing SMTP failure handling."""
import logging
import smtplib

from django.contrib.auth.forms import PasswordResetForm

logger = logging.getLogger(__name__)


class SafePasswordResetForm(PasswordResetForm):
    def send_mail(self, *args, **kwargs):
        try:
            return super().send_mail(*args, **kwargs)
        except (smtplib.SMTPException, OSError) as error:
            # The same response for existing/missing accounts prevents enumeration.
            # Do not log recipients, credentials, reset tokens or SMTP response bodies.
            logger.error("Password reset delivery failed (%s)", type(error).__name__)
