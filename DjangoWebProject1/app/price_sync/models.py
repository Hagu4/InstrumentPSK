from django.conf import settings
from django.db import models

from .storage import private_price_import_storage, price_import_upload_to


class SupplierProductLink(models.Model):
    supplier = models.CharField(max_length=32, default="stiooo")
    product = models.ForeignKey(
        "app.Product", on_delete=models.CASCADE, related_name="supplier_links"
    )
    source_sku = models.CharField(max_length=100, blank=True)
    normalized_brand = models.CharField(max_length=200, blank=True)
    normalized_title = models.CharField(max_length=500, blank=True)
    numeric_signature = models.JSONField(default=list, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Связь с товаром поставщика"
        verbose_name_plural = "Связи с товарами поставщика"
        constraints = [
            models.UniqueConstraint(
                fields=("supplier", "product"), name="uniq_supplier_product_link"
            ),
            models.UniqueConstraint(
                fields=("supplier", "source_sku"),
                condition=~models.Q(source_sku=""),
                name="uniq_supplier_nonempty_sku",
            ),
        ]

    def __str__(self):
        return f"{self.supplier}: {self.product}"


class PriceImport(models.Model):
    class SourceType(models.TextChoices):
        SUPPLIER_XLSX = "supplier_xlsx", "Прайс поставщика"
        MANUAL = "manual", "Ручное изменение"

    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        READY = "ready", "Готов к применению"
        APPLIED = "applied", "Применён"
        ROLLED_BACK = "rolled_back", "Отменён"
        FAILED = "failed", "Ошибка"

    source_type = models.CharField(
        max_length=16, choices=SourceType.choices, verbose_name="Тип источника"
    )
    source_file = models.FileField(
        storage=private_price_import_storage,
        upload_to=price_import_upload_to,
        blank=True,
        verbose_name="Файл прайса",
    )
    original_name = models.CharField(max_length=255, blank=True, verbose_name="Имя файла")
    file_sha256 = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="SHA-256 файла",
    )
    supplier = models.CharField(max_length=32, default="stiooo", verbose_name="Поставщик")
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name="Состояние",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="uploaded_price_imports",
        verbose_name="Загрузил",
    )
    applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="applied_price_imports",
        verbose_name="Применил",
    )
    rolled_back_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rolled_back_price_imports",
        verbose_name="Отменил",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    applied_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата применения")
    rolled_back_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата отмены")
    total_rows = models.PositiveIntegerField(default=0, verbose_name="Всего строк")
    matched_rows = models.PositiveIntegerField(default=0, verbose_name="Сопоставлено")
    skipped_rows = models.PositiveIntegerField(default=0, verbose_name="Пропущено")
    review_rows = models.PositiveIntegerField(default=0, verbose_name="Требуют проверки")
    changed_rows = models.PositiveIntegerField(default=0, verbose_name="Изменится")
    increased_rows = models.PositiveIntegerField(default=0, verbose_name="Подорожает")
    decreased_rows = models.PositiveIntegerField(default=0, verbose_name="Подешевеет")
    anomaly_rows = models.PositiveIntegerField(default=0, verbose_name="Изменение более 50%")
    failure_code = models.CharField(max_length=64, blank=True, verbose_name="Код ошибки")

    class Meta:
        ordering = ("-created_at", "-pk")
        verbose_name = "Обновление цен"
        verbose_name_plural = "Обновление цен"
        permissions = [
            ("preview_priceimport", "Can create price import previews"),
            ("create_manual_priceimport", "Can create manual price batches"),
            ("resolve_priceimport", "Can resolve price import rows"),
            ("apply_priceimport", "Can apply price imports"),
            ("rollback_priceimport", "Can rollback price imports"),
        ]

    def __str__(self):
        return f"#{self.pk or 'new'} — {self.get_source_type_display()}"


class PriceImportRow(models.Model):
    class Status(models.TextChoices):
        MATCHED = "matched", "Сопоставлен"
        NEEDS_REVIEW = "needs_review", "Требует проверки"
        SKIPPED = "skipped", "Пропущен"
        INVALID = "invalid", "Некорректен"

    price_import = models.ForeignKey(
        PriceImport, on_delete=models.CASCADE, related_name="rows"
    )
    row_number = models.PositiveIntegerField()
    source_sku = models.CharField(max_length=100, blank=True)
    source_brand = models.CharField(max_length=200, blank=True)
    source_title = models.CharField(max_length=500)
    source_price = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    product = models.ForeignKey(
        "app.Product",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="price_import_rows",
    )
    candidate_product_ids = models.JSONField(default=list, blank=True)
    match_method = models.CharField(max_length=32, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices)
    diagnostic_code = models.CharField(max_length=64, blank=True)
    before_price = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    before_old_price = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    before_discount_percent = models.PositiveSmallIntegerField(null=True)
    before_price_updated_at = models.DateTimeField(null=True)
    after_price = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    after_old_price = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    after_discount_percent = models.PositiveSmallIntegerField(null=True)
    after_price_updated_at = models.DateTimeField(null=True)
    anomaly_confirmed = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("row_number",)
        verbose_name = "Строка обновления цен"
        verbose_name_plural = "Строки обновления цен"
        constraints = [
            models.UniqueConstraint(
                fields=("price_import", "row_number"),
                name="uniq_price_import_row_number",
            ),
            models.UniqueConstraint(
                fields=("price_import", "product"),
                condition=models.Q(product__isnull=False),
                name="uniq_price_import_product",
            ),
        ]

    def __str__(self):
        return f"#{self.price_import_id}:{self.row_number} {self.source_title}"
