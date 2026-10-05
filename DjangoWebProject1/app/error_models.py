from django.db import models
from django.utils import timezone


class ErrorEvent(models.Model):
    fingerprint = models.CharField(max_length=64, unique=True, editable=False)
    first_seen = models.DateTimeField(default=timezone.now, verbose_name='Первый сбой')
    last_seen = models.DateTimeField(default=timezone.now, db_index=True, verbose_name='Последний сбой')
    exception_type = models.CharField(max_length=100, verbose_name='Тип ошибки')
    route = models.CharField(max_length=300, blank=True, verbose_name='Шаблон адреса')
    method = models.CharField(max_length=10, blank=True, verbose_name='Метод')
    stack = models.TextField(blank=True, verbose_name='Файлы, функции и строки')
    occurrences = models.PositiveIntegerField(default=1, verbose_name='Повторений')
    resolved = models.BooleanField(default=False, verbose_name='Разобрано')

    class Meta:
        ordering = ['-last_seen']
        verbose_name = 'Сбой'
        verbose_name_plural = 'Журнал сбоев'

    def __str__(self):
        return f'{self.exception_type} — {self.route}'
