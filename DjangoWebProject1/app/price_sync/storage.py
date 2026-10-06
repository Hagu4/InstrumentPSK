import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils import timezone
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivatePriceImportStorage(FileSystemStorage):
    def __init__(self):
        super().__init__(location=settings.PRICE_IMPORT_ROOT, base_url=None)

    def url(self, name):
        raise ValueError("Price import files do not have public URLs")


private_price_import_storage = PrivatePriceImportStorage()


def price_import_upload_to(instance, filename):
    suffix = Path(filename).suffix.lower()
    return f"{timezone.now():%Y/%m}/{uuid.uuid4().hex}{suffix}"
