from django.apps import AppConfig


class StoreConfig(AppConfig):
    name = 'app'

    def ready(self):
        from django.core.signals import got_request_exception
        from .error_journal import record_exception
        got_request_exception.connect(record_exception, dispatch_uid='store-error-journal', weak=False)
