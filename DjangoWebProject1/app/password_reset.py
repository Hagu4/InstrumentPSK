"""Password recovery with non-disclosing SMTP failure handling."""
import logging
import smtplib

from django.contrib.auth.forms import PasswordResetForm
from django.core.mail import EmailMultiAlternatives
from django.template import loader

logger = logging.getLogger(__name__)


class SafePasswordResetForm(PasswordResetForm):
    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
    ):
        subject = loader.render_to_string(subject_template_name, context)
        subject = "".join(subject.splitlines())
        body = loader.render_to_string(email_template_name, context)
        email_message = EmailMultiAlternatives(
            subject,
            body,
            from_email,
            [to_email],
        )
        if html_email_template_name is not None:
            html_email = loader.render_to_string(html_email_template_name, context)
            email_message.attach_alternative(html_email, "text/html")

        try:
            return email_message.send()
        except (smtplib.SMTPException, OSError) as error:
            # The same response for existing/missing accounts prevents enumeration.
            # Do not log recipients, credentials, reset tokens or SMTP response bodies.
            logger.error("Password reset delivery failed (%s)", type(error).__name__)
