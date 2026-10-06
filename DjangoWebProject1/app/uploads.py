"""Validate and re-encode user photos before saving any related database rows."""
from io import BytesIO
from pathlib import Path
import uuid
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile


MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 12_000_000
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
ALLOWED_FORMATS = {'JPEG', 'PNG', 'WEBP', 'GIF'}


def prepare_image(upload):
    if Path(upload.name).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValidationError('Разрешены только изображения JPEG, PNG, WebP и GIF.')
    if upload.size > MAX_IMAGE_BYTES:
        raise ValidationError('Размер одного изображения не должен превышать 5 МБ.')
    upload.seek(0)
    data = upload.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise ValidationError('Размер одного изображения не должен превышать 5 МБ.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as source:
                if source.format not in ALLOWED_FORMATS:
                    raise ValidationError('Этот формат изображения не поддерживается.')
                if source.width * source.height > MAX_IMAGE_PIXELS:
                    raise ValidationError('Изображение должно содержать не более 12 мегапикселей.')
                source.verify()
            with Image.open(BytesIO(data)) as source:
                # Only decoded pixels survive; filenames, appended HTML and metadata do not.
                source = ImageOps.exif_transpose(source)
                mode = 'RGBA' if 'A' in source.getbands() or 'transparency' in source.info else 'RGB'
                pixels = source.convert(mode)
                clean = Image.new(mode, pixels.size)
                clean.paste(pixels)
                output = BytesIO()
                clean.save(output, format='PNG')
        if output.tell() > MAX_IMAGE_BYTES:
            raise ValidationError('После обработки изображение превышает 5 МБ. Уменьшите его размер.')
        return ContentFile(output.getvalue(), name=f'{uuid.uuid4().hex}.png')
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError,
            Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ValidationError('Файл не является корректным поддерживаемым изображением.') from error


def prepare_images(uploads, *, max_count):
    if len(uploads) > max_count:
        raise ValidationError(f'Можно загрузить не более {max_count} изображений за один раз.')
    return [prepare_image(upload) for upload in uploads]
