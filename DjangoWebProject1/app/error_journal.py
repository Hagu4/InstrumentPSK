"""Exception metadata only: never collect request values, source lines or locals."""
from datetime import timedelta
import hashlib
import logging
from pathlib import Path
import sys

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .error_models import ErrorEvent


def record_exception(sender, request, **kwargs):
    try:
        exc_type, _, tb = sys.exc_info()
        if exc_type is None:
            return
        kind = exc_type.__name__[:100]
        match = getattr(request, 'resolver_match', None)
        route = str(getattr(match, 'route', '') or '[unresolved]')[:300]
        method = request.method if request.method in {'GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'} else 'OTHER'
        frames = []
        while tb is not None and len(frames) < 40:
            code = tb.tb_frame.f_code
            frames.append(f'{Path(code.co_filename).name[:100]}:{tb.tb_lineno} in {code.co_name[:100]}')
            tb = tb.tb_next
        stack = '\n'.join(frames)
        fingerprint = hashlib.sha256(f'{kind}|{route}|{method}|{stack}'.encode()).hexdigest()
        now = timezone.now()
        # Isolate database errors from any surrounding transaction.
        with transaction.atomic():
            event, created = ErrorEvent.objects.get_or_create(fingerprint=fingerprint, defaults={
                'exception_type': kind, 'route': route, 'method': method, 'stack': stack,
            })
            if not created:
                ErrorEvent.objects.filter(pk=event.pk).update(
                    last_seen=now, occurrences=F('occurrences') + 1, resolved=False)
            ErrorEvent.objects.filter(last_seen__lt=now-timedelta(days=30)).delete()
            overflow = list(ErrorEvent.objects.order_by('-last_seen', '-pk').values_list('pk', flat=True)[1000:])
            if overflow:
                ErrorEvent.objects.filter(pk__in=overflow).delete()
    except Exception:
        # No exception text or exc_info: even database errors may contain secrets.
        try:
            logging.getLogger('app.error_journal.fallback').error(
                'Error journal unavailable; exception_type=%s', locals().get('kind', 'unknown'))
        except Exception:
            pass
