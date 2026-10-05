# Supplier Price Synchronization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить в закрытую админку безопасную загрузку прайс-листа `old.stiooo.ru`, предварительную проверку сопоставлений и цен, атомарное применение, историю и откат последнего обновления без создания или удаления товаров.

**Architecture:** Функция живёт в изолированном пакете `app.price_sync`: чистые функции разбирают XLSX, нормализуют данные и рассчитывают цены; сервисы создают неизменяемый черновик, применяют его и откатывают в транзакциях; Django Admin даёт загрузку, ручное разрешение неоднозначностей и аудит. Исходные файлы хранятся в отдельном непубличном volume, а подробные данные сохраняются только для 12 последних успешных импортов.

**Tech Stack:** Python 3.12, Django 4.2.13, PostgreSQL 15, `openpyxl==3.1.5`, Django Admin/Jazzmin, Docker Compose, `unittest`/Django `TestCase`.

**Spec:** `docs/superpowers/specs/2026-10-05-supplier-price-sync-design.md`

## Global Constraints

- Реализацию начинать от commit `14596d3` (`feature/security-critical-fixes`) либо от более нового `main`, уже содержащего этот commit и развёрнутый журнал сбоев; не строить feature поверх устаревшего `8602b3b`.
- Единственный источник новой цены — колонка `REKOMEND_CENA`; `RRC_SHOP` не участвует в расчёте.
- Импорт не создаёт, не удаляет и не скрывает товары и не меняет остатки, описание, изображения, категории или характеристики.
- Постоянная скидка — целое число от 10 до 30 включительно, назначается один раз криптографически безопасным генератором и затем сохраняется.
- `old_price = ceil((price / (1 - discount_percent / 100)) / 10) * 10` рублей.
- Автоматическое сопоставление идёт в порядке: сохранённая связь, точный SKU, точные бренд и нормализованное название, уникальная комбинация бренд + модель + числовая сигнатура.
- Нечёткое сходство формирует только кандидатов для ручного выбора и никогда само не связывает товар.
- Изменение цены более чем на 50% требует отдельного подтверждения.
- Предпросмотр не меняет `Product`; применение и откат выполняются через `transaction.atomic()` и `select_for_update()`.
- Откат разрешён только для последнего применённого импорта и блокируется при последующем ручном изменении любой затронутой цены.
- Дата последнего обновления цен и `Product.price_updated_at` отображаются только в админке.
- Исходный XLSX и строки аудита хранятся для 12 последних успешных импортов; публичного URL у файла нет.
- Все изменяющие admin endpoints принимают только POST, проверяют CSRF и отдельные model permissions.
- Полный supplier-файл не коммитится; тесты создают небольшие XLSX in-memory.

---

## File map

- `requirements.txt` — фиксированная зависимость чтения XLSX.
- `docker-compose.yml` — непубличный persistent volume `/app/private-price-imports` только у `web`.
- `DjangoWebProject1/DjangoWebProject1/settings.py` — `PRICE_IMPORT_ROOT`, лимиты размера/строк и поставщик по умолчанию.
- `DjangoWebProject1/app/models.py` — два поля `Product` и реэкспорт price-sync моделей; публичные свойства товара не меняются.
- `DjangoWebProject1/app/price_sync/models.py` — импорт, строки импорта и постоянные связи поставщика.
- `DjangoWebProject1/app/price_sync/storage.py` — закрытое файловое хранилище и безопасное имя.
- `DjangoWebProject1/app/price_sync/parsing.py` — ограниченная и потоковая проверка/чтение XLSX.
- `DjangoWebProject1/app/price_sync/normalization.py` — нормализация SKU, бренда, названия, модели и чисел.
- `DjangoWebProject1/app/price_sync/pricing.py` — постоянная скидка, старая цена, проверка отклонения.
- `DjangoWebProject1/app/price_sync/matching.py` — индекс каталога и детерминированный подбор товара.
- `DjangoWebProject1/app/price_sync/services.py` — создание предпросмотра, ручное решение, применение, откат и очистка.
- `DjangoWebProject1/app/price_sync/forms.py` — upload/resolve/confirm формы.
- `DjangoWebProject1/app/price_sync/admin.py` — ModelAdmin, permissions и POST actions.
- `DjangoWebProject1/app/admin.py` — импорт регистраций price-sync и журнала сбоев.
- `DjangoWebProject1/app/templates/admin/app/priceimport/*.html` — история, загрузка, предпросмотр и подтверждения.
- `DjangoWebProject1/app/static/app/css/price_import_admin.css` — локальные стили экранов импорта.
- `DjangoWebProject1/app/management/commands/cleanup_price_imports.py` — идемпотентная очистка старых файлов/строк.
- `DjangoWebProject1/app/migrations/0045_price_sync.py` — схема и permissions; фактический следующий номер создать после объединения журнала.
- `DjangoWebProject1/app/test_price_sync_*.py` — модульные, сервисные, admin и regression-тесты.
- `docs/price-import-runbook.md` — инструкция менеджеру и production rollback/runbook.

### Task 1: Reconcile the implementation baseline

**Files:**
- Modify: Git history only
- Verify: `DjangoWebProject1/app/error_models.py`
- Verify: `DjangoWebProject1/app/test_auth_password_reset.py`

**Interfaces:**
- Consumes: secure commit `14596d3` and the committed error-journal implementation.
- Produces: clean feature branch `feature/supplier-price-sync` with all currently deployed fixes represented in Git.

- [ ] **Step 1: Verify that the secure commit and journal are present in the selected base**

```powershell
git log --oneline --decorate -20
git merge-base --is-ancestor 14596d3 HEAD
Test-Path DjangoWebProject1/app/error_models.py
```

Expected: `git merge-base` exits `0`, and `Test-Path` prints `True`. If the journal is still only an uncommitted production hotfix, commit and merge that isolated change before continuing; do not copy the dirty historical workspace wholesale.

- [ ] **Step 2: Create the feature branch from that reconciled commit**

```powershell
git switch -c feature/supplier-price-sync
git status --short
```

Expected: empty status on `feature/supplier-price-sync`.

- [ ] **Step 3: Run the security and journal regression tests**

```powershell
$env:DEBUG='True'
$env:SECRET_KEY='test-only-secret-key-with-more-than-fifty-characters-123456789'
python DjangoWebProject1/manage.py test app.test_auth_password_reset app.test_error_journal app.test_product_cache_regression --noinput
```

Expected: PASS. Treat any failure as a baseline problem and fix it in its owning branch, not inside price synchronization.

### Task 2: Add protected storage and the audit schema

**Files:**
- Modify: `requirements.txt`
- Modify: `docker-compose.yml`
- Modify: `DjangoWebProject1/DjangoWebProject1/settings.py`
- Modify: `DjangoWebProject1/app/models.py`
- Create: `DjangoWebProject1/app/price_sync/__init__.py`
- Create: `DjangoWebProject1/app/price_sync/storage.py`
- Create: `DjangoWebProject1/app/price_sync/models.py`
- Create: `DjangoWebProject1/app/migrations/0045_price_sync.py`
- Test: `DjangoWebProject1/app/test_price_sync_models.py`

**Interfaces:**
- Consumes: existing `app.Product` and `auth.User`.
- Produces: `PriceImport`, `PriceImportRow`, `SupplierProductLink`, `private_price_import_storage`, `price_import_upload_to`; adds nullable `Product.discount_percent` and `Product.price_updated_at`.

- [ ] **Step 1: Write schema and storage tests**

```python
class PriceSyncModelTests(TestCase):
    def test_supplier_sku_is_unique_per_supplier_when_non_empty(self):
        product_a = make_product(sku="LOCAL-A")
        product_b = make_product(sku="LOCAL-B")
        SupplierProductLink.objects.create(
            supplier="stiooo", product=product_a, source_sku="SUP-1"
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SupplierProductLink.objects.create(
                    supplier="stiooo", product=product_b, source_sku="SUP-1"
                )

    def test_import_file_has_no_public_url(self):
        field = PriceImport._meta.get_field("source_file")
        self.assertNotEqual(Path(field.storage.location), Path(settings.MEDIA_ROOT))
        import_obj = PriceImport(source_file="2026/10/private.xlsx")
        with self.assertRaisesRegex(ValueError, "do not have public URLs"):
            _ = import_obj.source_file.url

    def test_product_discount_accepts_only_ten_through_thirty(self):
        product = make_product(discount_percent=31)
        with self.assertRaises(ValidationError):
            product.full_clean()
```

- [ ] **Step 2: Run the model tests and confirm they fail**

```powershell
python DjangoWebProject1/manage.py test app.test_price_sync_models --noinput
```

Expected: FAIL because price-sync models and fields do not exist.

- [ ] **Step 3: Pin XLSX support and configure protected storage**

Add to `requirements.txt`:

```text
openpyxl==3.1.5
```

Add to settings:

```python
PRICE_IMPORT_ROOT = Path(
    os.environ.get("PRICE_IMPORT_ROOT", Path(BASE_DIR) / "private-price-imports")
).resolve()
PRICE_IMPORT_MAX_BYTES = int(os.environ.get("PRICE_IMPORT_MAX_BYTES", 10 * 1024 * 1024))
PRICE_IMPORT_MAX_ROWS = int(os.environ.get("PRICE_IMPORT_MAX_ROWS", 100_000))
PRICE_IMPORT_MAX_UNCOMPRESSED_BYTES = int(
    os.environ.get("PRICE_IMPORT_MAX_UNCOMPRESSED_BYTES", 100 * 1024 * 1024)
)
PRICE_IMPORT_SUPPLIER = "stiooo"
```

Mount only into `web`:

```yaml
volumes:
  - price_import_data:/app/private-price-imports

volumes:
  postgres_data:
  static_data:
  price_import_data:
```

Do not mount this volume into nginx.

- [ ] **Step 4: Implement the private storage helpers**

```python
class PrivatePriceImportStorage(FileSystemStorage):
    def __init__(self, *args, **kwargs):
        kwargs.update(location=settings.PRICE_IMPORT_ROOT, base_url=None)
        super().__init__(*args, **kwargs)

    def url(self, name):
        raise ValueError("Price import files do not have public URLs")

private_price_import_storage = PrivatePriceImportStorage()

def price_import_upload_to(instance, filename):
    suffix = Path(filename).suffix.lower()
    return f"{timezone.now():%Y/%m}/{uuid.uuid4().hex}{suffix}"
```

- [ ] **Step 5: Implement the models and constraints**

Use these exact choices and fields:

```python
class PriceImport(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        READY = "ready", "Готов к применению"
        APPLIED = "applied", "Применён"
        ROLLED_BACK = "rolled_back", "Отменён"
        FAILED = "failed", "Ошибка"

    source_file = models.FileField(storage=private_price_import_storage,
                                   upload_to=price_import_upload_to)
    original_name = models.CharField(max_length=255)
    file_sha256 = models.CharField(max_length=64, unique=True)
    supplier = models.CharField(max_length=32, default="stiooo")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                    on_delete=models.SET_NULL,
                                    related_name="uploaded_price_imports")
    applied_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL,
                                   related_name="applied_price_imports")
    rolled_back_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                       on_delete=models.SET_NULL,
                                       related_name="rolled_back_price_imports")
    created_at = models.DateTimeField(auto_now_add=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    rolled_back_at = models.DateTimeField(null=True, blank=True)
    total_rows = models.PositiveIntegerField(default=0)
    matched_rows = models.PositiveIntegerField(default=0)
    skipped_rows = models.PositiveIntegerField(default=0)
    review_rows = models.PositiveIntegerField(default=0)
    changed_rows = models.PositiveIntegerField(default=0)
    increased_rows = models.PositiveIntegerField(default=0)
    decreased_rows = models.PositiveIntegerField(default=0)
    anomaly_rows = models.PositiveIntegerField(default=0)
    failure_code = models.CharField(max_length=64, blank=True)

    class Meta:
        permissions = [
            ("preview_priceimport", "Can create price import previews"),
            ("resolve_priceimport", "Can resolve price import rows"),
            ("apply_priceimport", "Can apply price imports"),
            ("rollback_priceimport", "Can rollback price imports"),
        ]
```

Define the remaining models with these exact interfaces (verbose names may be Russian):

```python
class SupplierProductLink(models.Model):
    supplier = models.CharField(max_length=32, default="stiooo")
    product = models.ForeignKey("app.Product", on_delete=models.CASCADE,
                                related_name="supplier_links")
    source_sku = models.CharField(max_length=100, blank=True)
    normalized_brand = models.CharField(max_length=200, blank=True)
    normalized_title = models.CharField(max_length=500, blank=True)
    numeric_signature = models.JSONField(default=list, blank=True)
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("supplier", "product"),
                                    name="uniq_supplier_product_link"),
            models.UniqueConstraint(fields=("supplier", "source_sku"),
                                    condition=~models.Q(source_sku=""),
                                    name="uniq_supplier_nonempty_sku"),
        ]

class PriceImportRow(models.Model):
    class Status(models.TextChoices):
        MATCHED = "matched", "Сопоставлен"
        NEEDS_REVIEW = "needs_review", "Требует проверки"
        SKIPPED = "skipped", "Пропущен"
        INVALID = "invalid", "Некорректен"

    price_import = models.ForeignKey(PriceImport, on_delete=models.CASCADE,
                                     related_name="rows")
    row_number = models.PositiveIntegerField()
    source_sku = models.CharField(max_length=100, blank=True)
    source_brand = models.CharField(max_length=200, blank=True)
    source_title = models.CharField(max_length=500)
    source_price = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    product = models.ForeignKey("app.Product", null=True, blank=True,
                                on_delete=models.PROTECT,
                                related_name="price_import_rows")
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
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("price_import", "row_number"),
                                    name="uniq_price_import_row_number"),
            models.UniqueConstraint(fields=("price_import", "product"),
                                    condition=models.Q(product__isnull=False),
                                    name="uniq_price_import_product"),
        ]
```

- [ ] **Step 6: Add Product fields and re-export models**

```python
discount_percent = models.PositiveSmallIntegerField(
    null=True, blank=True,
    validators=[MinValueValidator(10), MaxValueValidator(30)],
    verbose_name="Постоянная скидка, %",
)
price_updated_at = models.DateTimeField(
    null=True, blank=True,
    verbose_name="Цена обновлена",
)
```

At the end of `app/models.py`, import the three price-sync models so Django registers them under the existing `app` application.

- [ ] **Step 7: Generate and inspect the migration**

```powershell
python DjangoWebProject1/manage.py makemigrations app --name price_sync
python DjangoWebProject1/manage.py sqlmigrate app 0045
python DjangoWebProject1/manage.py makemigrations --check --dry-run
```

Expected: constraints are present; no destructive operation touches existing product rows. Rename `0045` if journal integration has already consumed that number.

- [ ] **Step 8: Run tests and commit**

```powershell
python DjangoWebProject1/manage.py test app.test_price_sync_models --noinput
git add requirements.txt docker-compose.yml DjangoWebProject1/DjangoWebProject1/settings.py DjangoWebProject1/app/models.py DjangoWebProject1/app/price_sync DjangoWebProject1/app/migrations DjangoWebProject1/app/test_price_sync_models.py
git commit -m "feat: add price import audit schema"
```

### Task 3: Implement deterministic normalization and pricing rules

**Files:**
- Create: `DjangoWebProject1/app/price_sync/normalization.py`
- Create: `DjangoWebProject1/app/price_sync/pricing.py`
- Test: `DjangoWebProject1/app/test_price_sync_rules.py`

**Interfaces:**
- Produces: `normalize_sku(value) -> str`, `normalize_text(value) -> str`, `normalize_brand(value) -> str`, `extract_model_tokens(value) -> tuple[str, ...]`, `extract_numeric_signature(value) -> tuple[str, ...]`, `choose_discount(existing_discount, price, old_price) -> int`, `calculate_old_price(price, percent) -> Decimal`, `is_large_change(before, after) -> bool`.

- [ ] **Step 1: Write failing rule tests**

```python
class PriceSyncRuleTests(SimpleTestCase):
    def test_normalization_preserves_model_numbers_and_units(self):
        self.assertEqual(normalize_text("  WORTEX  CAG 1818 E  "), "wortex cag 1818 e")
        self.assertEqual(extract_numeric_signature("18 В, 2 А·ч"), ("18v", "2ah"))

    def test_different_numeric_models_do_not_share_signature(self):
        self.assertNotEqual(
            extract_numeric_signature("дрель 12 В 2 А·ч"),
            extract_numeric_signature("дрель 18 В 2 А·ч"),
        )

    @patch("app.price_sync.pricing.secrets.randbelow", return_value=7)
    def test_discount_is_generated_once_in_inclusive_range(self, _randbelow):
        self.assertEqual(choose_discount(None, Decimal("100"), None), 17)
        self.assertEqual(choose_discount(23, Decimal("100"), Decimal("130")), 23)

    def test_old_price_rounds_up_to_ten_rubles(self):
        self.assertEqual(calculate_old_price(Decimal("1000"), 17), Decimal("1210.00"))

    def test_more_than_fifty_percent_is_anomaly(self):
        self.assertTrue(is_large_change(Decimal("100"), Decimal("151")))
        self.assertFalse(is_large_change(Decimal("100"), Decimal("150")))
```

- [ ] **Step 2: Run and observe the missing modules**

```powershell
python DjangoWebProject1/manage.py test app.test_price_sync_rules --noinput
```

Expected: FAIL with import errors.

- [ ] **Step 3: Implement normalization without lossy number removal**

```python
def normalize_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = text.replace("ё", "е")
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())[:500]

def normalize_sku(value: object) -> str:
    return re.sub(r"[\s\-_./]+", "", normalize_text(value)).upper()[:100]
```

Normalize Cyrillic unit aliases (`в` → `v`, `а ч`/`ач` → `ah`, `мм`, `см`, `м`, `вт`, `квт`) before extracting number+unit pairs. Return sorted tuples so comparisons are deterministic. Never remove numeric tokens from titles.

- [ ] **Step 4: Implement pricing with Decimal only**

```python
MIN_DISCOUNT = 10
MAX_DISCOUNT = 30

def choose_discount(existing_discount, price, old_price):
    if existing_discount is not None and MIN_DISCOUNT <= existing_discount <= MAX_DISCOUNT:
        return int(existing_discount)
    if old_price and old_price > price:
        derived = int(round((Decimal("1") - price / old_price) * 100))
        if MIN_DISCOUNT <= derived <= MAX_DISCOUNT:
            return derived
    return MIN_DISCOUNT + secrets.randbelow(MAX_DISCOUNT - MIN_DISCOUNT + 1)

def calculate_old_price(price: Decimal, percent: int) -> Decimal:
    gross = price / (Decimal("1") - Decimal(percent) / Decimal("100"))
    rounded = (gross / Decimal("10")).to_integral_value(rounding=ROUND_CEILING) * 10
    return rounded.quantize(Decimal("0.01"))
```

Reject values `<= 0`, values exceeding `Decimal("99999999.99")`, and derived old prices exceeding the same database limit.

- [ ] **Step 5: Run tests and commit**

```powershell
python DjangoWebProject1/manage.py test app.test_price_sync_rules --noinput
git add DjangoWebProject1/app/price_sync/normalization.py DjangoWebProject1/app/price_sync/pricing.py DjangoWebProject1/app/test_price_sync_rules.py
git commit -m "feat: define supplier matching and pricing rules"
```

### Task 4: Parse the supplier XLSX safely and in bounded memory

**Files:**
- Create: `DjangoWebProject1/app/price_sync/parsing.py`
- Test: `DjangoWebProject1/app/test_price_sync_parsing.py`

**Interfaces:**
- Consumes: binary seekable file and settings limits.
- Produces: `SupplierRow(row_number, brand, title, sku, recommended_price, diagnostic_code="")` and `parse_supplier_xlsx(file_obj) -> list[SupplierRow]`.
- Raises: `PriceImportValidationError(code: str, message: str)` with non-sensitive codes.

- [ ] **Step 1: Write in-memory workbook tests**

```python
def workbook_bytes(rows, headers=("BRAND", "NAIMEN", "ARTIKUL", "RRC_SHOP", "REKOMEND_CENA", "OKDP", "BARCODE", "EDIZM")):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    return stream

class PriceSyncParsingTests(SimpleTestCase):
    def test_reads_real_supplier_headers_and_recommended_price(self):
        rows = parse_supplier_xlsx(workbook_bytes([
            ("WORTEX", "Дрель 18 В", "00123", 900, 1000, "", "", "шт")
        ]))
        self.assertEqual(rows[0].sku, "00123")
        self.assertEqual(rows[0].recommended_price, Decimal("1000.00"))

    def test_rejects_missing_recommended_price_column(self):
        stream = workbook_bytes([], headers=("BRAND", "NAIMEN", "ARTIKUL"))
        with self.assertRaisesRegex(PriceImportValidationError, "missing_columns"):
            parse_supplier_xlsx(stream)

    def test_formula_is_not_executed_or_accepted_without_cached_value(self):
        stream = workbook_bytes([("WORTEX", "Дрель", "A1", 900, "=1+1", "", "", "шт")])
        with self.assertRaisesRegex(PriceImportValidationError, "invalid_price"):
            parse_supplier_xlsx(stream)
```

Also test wrong extension/signature, oversized upload, zip uncompressed-size limit, more than 100,000 rows, empty/non-positive/oversized price, overly long text, numeric SKU formatting, identical duplicate rows and contradictory duplicate prices.

- [ ] **Step 2: Run and verify the parser tests fail**

```powershell
python DjangoWebProject1/manage.py test app.test_price_sync_parsing --noinput
```

Expected: FAIL because the parser is absent.

- [ ] **Step 3: Validate the ZIP container before openpyxl**

```python
def validate_xlsx_container(file_obj):
    if file_obj.size > settings.PRICE_IMPORT_MAX_BYTES:
        raise PriceImportValidationError("file_too_large", "Файл превышает допустимый размер")
    with ZipFile(file_obj) as archive:
        total = sum(item.file_size for item in archive.infolist())
        if total > settings.PRICE_IMPORT_MAX_UNCOMPRESSED_BYTES:
            raise PriceImportValidationError("xlsx_expands_too_large", "Содержимое XLSX слишком велико")
        if "[Content_Types].xml" not in archive.namelist():
            raise PriceImportValidationError("invalid_xlsx", "Файл не является XLSX")
    file_obj.seek(0)
```

- [ ] **Step 4: Parse saved values without executing formulas**

```python
workbook = load_workbook(file_obj, read_only=True, data_only=True, keep_links=False)
sheet = workbook["Sheet1"] if "Sheet1" in workbook.sheetnames else workbook.active
```

Map headers case-insensitively after trimming, iterate with `values_only=False`, convert prices via `Decimal(str(value).replace(" ", "").replace(",", "."))`, and preserve numeric SKUs with a zero-only Excel number format when available. Stop at the configured row limit. Close the workbook in `finally`.

- [ ] **Step 5: Apply duplicate rules**

An identical normalized SKU with the same recommended price leaves one canonical row and returns later occurrences with diagnostic `duplicate_same_price` so preview counts them as skipped duplicates. The same normalized SKU with different recommended prices raises `PriceImportValidationError("duplicate_conflicting_price", "Один артикул содержит разные цены")`: the import becomes `failed`, no Product changes occur, and the manager must correct and upload a changed workbook. This keeps the parser behavior consistent with a file-level blocking error.

- [ ] **Step 6: Run tests and commit**

```powershell
python DjangoWebProject1/manage.py test app.test_price_sync_parsing --noinput
git add DjangoWebProject1/app/price_sync/parsing.py DjangoWebProject1/app/test_price_sync_parsing.py
git commit -m "feat: parse supplier price workbooks safely"
```

### Task 5: Build the deterministic catalog matcher

**Files:**
- Create: `DjangoWebProject1/app/price_sync/matching.py`
- Test: `DjangoWebProject1/app/test_price_sync_matching.py`

**Interfaces:**
- Consumes: `SupplierRow`, products with brand, and saved `SupplierProductLink` records.
- Produces: `CatalogIndex.from_queryset(queryset, links)`, `match_row(row, index) -> MatchDecision(product_id, method, candidate_ids, diagnostic_code)`.

- [ ] **Step 1: Write matching-order and ambiguity tests**

```python
class PriceSyncMatchingTests(TestCase):
    def test_saved_link_wins_before_changed_supplier_sku(self):
        product = make_product(sku="LOCAL-1", title="Дрель 18 В", brand="WORTEX")
        SupplierProductLink.objects.create(
            supplier="stiooo", product=product, source_sku="OLD-SUP"
        )
        decision = match_row(supplier_row(sku="OLD-SUP"), self.index())
        self.assertEqual((decision.product_id, decision.method), (product.pk, "saved_link"))

    def test_exact_sku_is_automatic(self):
        product = make_product(sku="ABC-123")
        decision = match_row(supplier_row(sku="abc 123"), self.index())
        self.assertEqual((decision.product_id, decision.method), (product.pk, "exact_sku"))

    def test_same_brand_and_title_but_conflicting_numbers_is_not_automatic(self):
        make_product(title="Дрель 12 В 2 Ач", brand="WORTEX")
        decision = match_row(
            supplier_row(title="Дрель 18 В 2 Ач", brand="WORTEX", sku=""), self.index()
        )
        self.assertIsNone(decision.product_id)
        self.assertEqual(decision.method, "needs_review")

    def test_fuzzy_similarity_only_returns_candidates(self):
        product = make_product(title="Дрель аккумуляторная 18 В", brand="WORTEX")
        decision = match_row(
            supplier_row(title="Аккумуляторная дрель 18В", brand="WORTEX", sku=""), self.index()
        )
        self.assertIsNone(decision.product_id)
        self.assertIn(product.pk, decision.candidate_ids)
```

Add a test that two source rows cannot automatically select the same product in one import.

- [ ] **Step 2: Run and confirm matching tests fail**

```powershell
python DjangoWebProject1/manage.py test app.test_price_sync_matching --noinput
```

- [ ] **Step 3: Build one in-memory index per preview**

```python
@dataclass(frozen=True)
class CatalogEntry:
    product_id: int
    sku: str
    brand: str
    title: str
    model_tokens: tuple[str, ...]
    numeric_signature: tuple[str, ...]

@dataclass(frozen=True)
class MatchDecision:
    product_id: int | None
    method: str
    candidate_ids: tuple[int, ...] = ()
    diagnostic_code: str = ""
```

Load `Product.objects.select_related("brand").only("id", "sku", "title", "brand_id", "brand__name", "price", "old_price", "discount_percent", "price_updated_at")` and all supplier links once. Index by saved SKU, exact product SKU, `(brand, title)`, and `(brand, model_tokens, numeric_signature)`. This prevents 27,000 per-row database queries.

- [ ] **Step 4: Implement strict order and candidate generation**

Accept an automatic match only when the selected index key has exactly one product and no already-claimed product exists for that import. For fuzzy candidates, first restrict to the same brand and compatible numeric signature, then rank at most five using `difflib.SequenceMatcher`; store candidates but leave `product_id=None`.

- [ ] **Step 5: Run tests and commit**

```powershell
python DjangoWebProject1/manage.py test app.test_price_sync_matching --noinput
git add DjangoWebProject1/app/price_sync/matching.py DjangoWebProject1/app/test_price_sync_matching.py
git commit -m "feat: match supplier rows to catalog products"
```

### Task 6: Create an immutable preview without changing products

**Files:**
- Create: `DjangoWebProject1/app/price_sync/services.py`
- Test: `DjangoWebProject1/app/test_price_sync_preview.py`

**Interfaces:**
- Produces: `create_preview(uploaded_file, user) -> tuple[PriceImport, bool]`, `refresh_import_counters(price_import) -> None`, `resolve_row(row, product, user) -> PriceImportRow`, `skip_row(row, user) -> PriceImportRow`.

- [ ] **Step 1: Write preview invariants**

```python
class PriceSyncPreviewTests(TestCase):
    def test_preview_changes_no_product_fields_and_stores_one_discount(self):
        product = make_product(sku="A1", price=Decimal("100"), old_price=None,
                               discount_percent=None, price_updated_at=None)
        import_obj, created = create_preview(upload("prices.xlsx", one_row_xlsx("A1", 120)), self.user)
        product.refresh_from_db()
        row = import_obj.rows.get()
        self.assertTrue(created)
        self.assertEqual(product.price, Decimal("100"))
        self.assertIsNone(product.discount_percent)
        self.assertGreaterEqual(row.after_discount_percent, 10)
        self.assertLessEqual(row.after_discount_percent, 30)

    def test_same_sha_returns_existing_import(self):
        first, created_first = create_preview(upload("one.xlsx", self.xlsx), self.user)
        second, created_second = create_preview(upload("two.xlsx", self.xlsx), self.user)
        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first.pk, second.pk)

    def test_preview_never_creates_or_deletes_products(self):
        before_ids = set(Product.objects.values_list("pk", flat=True))
        create_preview(upload("prices.xlsx", self.xlsx), self.user)
        self.assertSetEqual(before_ids, set(Product.objects.values_list("pk", flat=True)))
```

Also cover summary counts, increase/decrease/no-change, unresolved rows, explicit skip, and >50% anomalies.

- [ ] **Step 2: Run and confirm preview tests fail**

```powershell
python DjangoWebProject1/manage.py test app.test_price_sync_preview --noinput
```

- [ ] **Step 3: Hash and persist the upload safely**

Stream the upload through SHA-256 in chunks, rewind it, and use `file_sha256` to return an existing import before writing a second file. Store `Path(uploaded_file.name).name[:255]` only as display text; storage generates the physical name.

- [ ] **Step 4: Parse, match and bulk-create audit rows**

For each row, snapshot `before_price`, `before_old_price`, `before_discount_percent`, and `before_price_updated_at`; calculate and persist `after_price`, `after_old_price`, and `after_discount_percent`. Set `after_price_updated_at` to one preview timestamp only when `after_price != before_price`; otherwise preserve `before_price_updated_at`. Use `PriceImportRow.objects.bulk_create(audit_rows, batch_size=1000)`. Catch only expected validation errors and set `failure_code`; never put row content or filesystem paths in `ErrorEvent`.

- [ ] **Step 5: Implement manual resolution and persistent links**

`resolve_row()` verifies the import is `draft`/`ready`, verifies no other row in the import uses that product, snapshots current product values, saves the selected product/method `manual`, and `update_or_create`s `SupplierProductLink` with `confirmed_by`/`confirmed_at`. `skip_row()` changes only the audit row. Both refresh counters and set `ready` only when no actionable row or unconfirmed anomaly remains.

- [ ] **Step 6: Run tests and commit**

```powershell
python DjangoWebProject1/manage.py test app.test_price_sync_preview --noinput
git add DjangoWebProject1/app/price_sync/services.py DjangoWebProject1/app/test_price_sync_preview.py
git commit -m "feat: build auditable price import previews"
```

### Task 7: Add the admin-only workflow and latest-update visibility

**Files:**
- Create: `DjangoWebProject1/app/admin.py` if not already merged from the journal branch
- Create: `DjangoWebProject1/app/price_sync/forms.py`
- Create: `DjangoWebProject1/app/price_sync/admin.py`
- Create: `DjangoWebProject1/app/templates/admin/app/priceimport/change_list.html`
- Create: `DjangoWebProject1/app/templates/admin/app/priceimport/upload.html`
- Create: `DjangoWebProject1/app/templates/admin/app/priceimport/preview.html`
- Create: `DjangoWebProject1/app/templates/admin/app/priceimport/confirm_apply.html`
- Create: `DjangoWebProject1/app/static/app/css/price_import_admin.css`
- Modify: `DjangoWebProject1/app/models.py` (`ProductAdmin` display only)
- Test: `DjangoWebProject1/app/test_price_sync_admin.py`

**Interfaces:**
- Consumes: Task 6 services and Django model permissions.
- Produces: named admin routes `admin:app_priceimport_upload`, `admin:app_priceimport_preview`, `admin:app_priceimport_resolve`, `admin:app_priceimport_skip`, `admin:app_priceimport_confirm_anomalies`, `admin:app_priceimport_apply`, `admin:app_priceimport_rollback`.

- [ ] **Step 1: Write access and workflow tests**

```python
class PriceSyncAdminTests(TestCase):
    def test_public_and_staff_without_permission_cannot_view_imports(self):
        self.assertEqual(self.client.get(self.history_url).status_code, 302)
        self.client.force_login(self.staff_without_permissions)
        self.assertEqual(self.client.get(self.history_url).status_code, 403)

    def test_get_cannot_apply_or_rollback(self):
        self.client.force_login(self.authorized_user)
        self.assertEqual(self.client.get(self.apply_url).status_code, 405)
        self.assertEqual(self.client.get(self.rollback_url).status_code, 405)

    def test_upload_rejects_non_xlsx_and_oversized_file(self):
        self.client.force_login(self.authorized_user)
        response = self.client.post(self.upload_url, {"source_file": upload("prices.csv", b"x")})
        self.assertContains(response, "Только файлы XLSX", status_code=200)

    def test_price_timestamp_is_present_in_admin_but_absent_from_public_pages(self):
        self.client.force_login(self.superuser)
        self.assertContains(self.client.get(reverse("admin:app_product_changelist")), "Цена обновлена")
        self.client.logout()
        self.assertNotContains(self.client.get(self.product.get_absolute_url()), "Цена обновлена")
```

- [ ] **Step 2: Run and confirm admin tests fail**

```powershell
python DjangoWebProject1/manage.py test app.test_price_sync_admin --noinput
```

- [ ] **Step 3: Implement forms with exact validation**

`PriceImportUploadForm` accepts one `source_file`, checks `.xlsx` and `PRICE_IMPORT_MAX_BYTES`. `ResolvePriceImportRowForm` exposes the `product` relation with Django's `AutocompleteSelect`. `ConfirmAnomaliesForm` requires a boolean confirmation and hidden filtered row IDs. None of these forms expose source paths.

- [ ] **Step 4: Register admin URLs and enforce permission per action**

```python
def get_urls(self):
    custom = [
        path("upload/", self.admin_site.admin_view(self.upload_view), name="app_priceimport_upload"),
        path("<int:pk>/preview/", self.admin_site.admin_view(self.preview_view), name="app_priceimport_preview"),
        path("<int:pk>/apply/", self.admin_site.admin_view(require_POST(self.apply_view)), name="app_priceimport_apply"),
        path("<int:pk>/rollback/", self.admin_site.admin_view(require_POST(self.rollback_view)), name="app_priceimport_rollback"),
    ]
    return custom + super().get_urls()
```

Add resolve, skip, and anomaly-confirm routes in the same form. Each view calls `request.user.has_perm("app.<permission>")` and raises `PermissionDenied` when absent.

- [ ] **Step 5: Build the preview screen**

Show summary cards, the latest successful `applied_at`, filters for matched/review/skipped/anomaly, search over SKU/title/brand, and a paginated table with before/after values. The apply button is disabled until status is `ready`; anomaly confirmation and manual selection use POST forms with CSRF tokens. Escape all supplier strings through normal Django template rendering.

- [ ] **Step 6: Expose timestamps only in admin**

Extend `ProductAdmin.list_display` with `discount_percent` and `price_updated_at`, add them to `readonly_fields`, and do not modify `product_card.html`, `product_detail.html`, APIs, sitemaps or public context processors.

- [ ] **Step 7: Run tests and commit**

```powershell
python DjangoWebProject1/manage.py test app.test_price_sync_admin --noinput
git add DjangoWebProject1/app/admin.py DjangoWebProject1/app/models.py DjangoWebProject1/app/price_sync DjangoWebProject1/app/templates/admin DjangoWebProject1/app/static/app/css/price_import_admin.css DjangoWebProject1/app/test_price_sync_admin.py
git commit -m "feat: add admin price import review workflow"
```

### Task 8: Apply an approved import atomically

**Files:**
- Modify: `DjangoWebProject1/app/price_sync/services.py`
- Modify: `DjangoWebProject1/app/price_sync/admin.py`
- Test: `DjangoWebProject1/app/test_price_sync_apply.py`

**Interfaces:**
- Produces: `apply_import(import_id: int, user) -> PriceImport` and domain exceptions `ImportNotReady`, `ImportConflict`, `ImportAlreadyApplied`.

- [ ] **Step 1: Write atomicity and idempotency tests**

```python
class PriceSyncApplyTests(TransactionTestCase):
    def test_apply_updates_only_price_fields_and_keeps_product_count(self):
        before_count = Product.objects.count()
        before_title = self.product.title
        apply_import(self.import_obj.pk, self.user)
        self.product.refresh_from_db()
        self.assertEqual(Product.objects.count(), before_count)
        self.assertEqual(self.product.title, before_title)
        self.assertEqual(self.product.price, self.row.after_price)
        self.assertEqual(self.product.old_price, self.row.after_old_price)
        self.assertEqual(self.product.discount_percent, self.row.after_discount_percent)
        self.assertIsNotNone(self.product.price_updated_at)

    def test_unchanged_price_preserves_previous_update_timestamp(self):
        unchanged = make_ready_row(before_price=Decimal("100"), after_price=Decimal("100"),
                                   before_price_updated_at=self.previous_timestamp,
                                   after_price_updated_at=self.previous_timestamp)
        apply_import(unchanged.price_import_id, self.user)
        unchanged.product.refresh_from_db()
        self.assertEqual(unchanged.product.price_updated_at, self.previous_timestamp)

    def test_second_apply_is_rejected_without_changes(self):
        apply_import(self.import_obj.pk, self.user)
        with self.assertRaises(ImportAlreadyApplied):
            apply_import(self.import_obj.pk, self.user)

    def test_one_failed_row_rolls_back_all_products(self):
        with patch("app.price_sync.services.Product.objects.bulk_update", side_effect=DatabaseError):
            with self.assertRaises(DatabaseError):
                apply_import(self.import_obj.pk, self.user)
        self.first.refresh_from_db()
        self.second.refresh_from_db()
        self.assertEqual(self.first.price, self.first_before)
        self.assertEqual(self.second.price, self.second_before)
```

Add stale-preview, changed file hash, unresolved row and unconfirmed anomaly tests.

- [ ] **Step 2: Run and confirm apply tests fail**

```powershell
python DjangoWebProject1/manage.py test app.test_price_sync_apply --noinput
```

- [ ] **Step 3: Implement the lock/verify/update transaction**

```python
@transaction.atomic
def apply_import(import_id: int, user) -> PriceImport:
    import_obj = PriceImport.objects.select_for_update().get(pk=import_id)
    if import_obj.status == PriceImport.Status.APPLIED:
        raise ImportAlreadyApplied()
    if import_obj.status != PriceImport.Status.READY:
        raise ImportNotReady()
    rows = list(import_obj.rows.select_related("product").filter(status="matched"))
    product_ids = [row.product_id for row in rows]
    products = {
        product.pk: product
        for product in Product.objects.select_for_update().filter(pk__in=product_ids)
    }
```

Re-hash `source_file`, compare every current Product snapshot with `before_*`, reject duplicate product IDs, then assign only `price`, `old_price`, `discount_percent`, and the row's stored `after_price_updated_at`. Unchanged prices preserve their previous timestamp. Use `bulk_update` with those exact four fields. Mark the import applied by the user in the same transaction and update/create supplier links. Register cache invalidation with `transaction.on_commit(cache.clear)`.

- [ ] **Step 4: Convert expected domain failures into admin messages**

The POST view catches only `ImportNotReady`, `ImportConflict`, `ImportAlreadyApplied`, and safe validation errors; it returns to preview with an error message. Unexpected exceptions are recorded by the existing closed error journal and shown through the custom 500 page, without spreadsheet data in the journal message.

- [ ] **Step 5: Run tests and commit**

```powershell
python DjangoWebProject1/manage.py test app.test_price_sync_apply --noinput
git add DjangoWebProject1/app/price_sync/services.py DjangoWebProject1/app/price_sync/admin.py DjangoWebProject1/app/test_price_sync_apply.py
git commit -m "feat: apply approved price imports atomically"
```

### Task 9: Roll back only the latest safe import

**Files:**
- Modify: `DjangoWebProject1/app/price_sync/services.py`
- Modify: `DjangoWebProject1/app/price_sync/admin.py`
- Test: `DjangoWebProject1/app/test_price_sync_rollback.py`

**Interfaces:**
- Produces: `rollback_import(import_id: int, user) -> PriceImport`, `RollbackNotLatest`, `RollbackConflict`.

- [ ] **Step 1: Write rollback boundary tests**

```python
class PriceSyncRollbackTests(TransactionTestCase):
    def test_latest_import_restores_complete_price_snapshot(self):
        rollback_import(self.import_obj.pk, self.user)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, self.row.before_price)
        self.assertEqual(self.product.old_price, self.row.before_old_price)
        self.assertEqual(self.product.discount_percent, self.row.before_discount_percent)
        self.assertEqual(self.product.price_updated_at, self.row.before_price_updated_at)

    def test_older_applied_import_cannot_be_rolled_back(self):
        with self.assertRaises(RollbackNotLatest):
            rollback_import(self.older_import.pk, self.user)

    def test_manual_price_edit_blocks_rollback(self):
        Product.objects.filter(pk=self.product.pk).update(price=Decimal("999"))
        with self.assertRaises(RollbackConflict):
            rollback_import(self.import_obj.pk, self.user)
```

- [ ] **Step 2: Run and confirm rollback tests fail**

```powershell
python DjangoWebProject1/manage.py test app.test_price_sync_rollback --noinput
```

- [ ] **Step 3: Implement rollback with the same locking discipline**

Inside one transaction, lock the import and determine the chronologically newest successful import by `applied_at`/PK across both `applied` and `rolled_back` states. The requested import must be that record and must still have status `applied`; this prevents cascading rollback into older history after the newest import was already rolled back. Lock its products and compare current `price`, `old_price`, `discount_percent`, and `price_updated_at` to every `after_*` snapshot. Restore all four `before_*` values with `bulk_update`; set `rolled_back`, actor and timestamp. Keep `PriceImport` and its audit rows. Do not remove saved supplier links.

- [ ] **Step 4: Run tests and commit**

```powershell
python DjangoWebProject1/manage.py test app.test_price_sync_rollback --noinput
git add DjangoWebProject1/app/price_sync/services.py DjangoWebProject1/app/price_sync/admin.py DjangoWebProject1/app/test_price_sync_rollback.py
git commit -m "feat: safely rollback the latest price import"
```

### Task 10: Retain only twelve detailed successful imports

**Files:**
- Create: `DjangoWebProject1/app/management/commands/cleanup_price_imports.py`
- Modify: `DjangoWebProject1/app/price_sync/services.py`
- Test: `DjangoWebProject1/app/test_price_sync_retention.py`

**Interfaces:**
- Produces: `cleanup_old_price_import_details(keep: int = 12) -> CleanupResult` and management command `cleanup_price_imports --keep 12`.

- [ ] **Step 1: Write retention and idempotency tests**

```python
class PriceSyncRetentionTests(TestCase):
    def test_keeps_details_and_files_for_latest_twelve_successes(self):
        imports = [make_applied_import(index) for index in range(13)]
        cleanup_old_price_import_details(keep=12)
        imports[0].refresh_from_db()
        self.assertFalse(imports[0].source_file.name)
        self.assertFalse(imports[0].rows.exists())
        self.assertTrue(imports[-1].source_file.name)
        self.assertTrue(imports[-1].rows.exists())
        self.assertEqual(imports[0].status, PriceImport.Status.APPLIED)
        self.assertGreater(imports[0].total_rows, 0)

    def test_cleanup_is_idempotent(self):
        first = cleanup_old_price_import_details(keep=12)
        second = cleanup_old_price_import_details(keep=12)
        self.assertGreaterEqual(first.deleted_files, 0)
        self.assertEqual(second.deleted_files, 0)
```

- [ ] **Step 2: Run and confirm retention tests fail**

```powershell
python DjangoWebProject1/manage.py test app.test_price_sync_retention --noinput
```

- [ ] **Step 3: Implement cleanup after commit and as a command**

Keep summary counters and timestamps forever. Consider both `applied` and `rolled_back` records successful and order them by `applied_at`/PK. For successful imports older than the newest twelve, delete `PriceImportRow` records and call `source_file.delete(save=False)` followed by clearing the field. Never delete `Product`, `SupplierProductLink`, or the `PriceImport` summary. Invoke cleanup through `transaction.on_commit()` after apply, and expose the command for daily maintenance.

- [ ] **Step 4: Run tests and commit**

```powershell
python DjangoWebProject1/manage.py test app.test_price_sync_retention --noinput
git add DjangoWebProject1/app/management/commands/cleanup_price_imports.py DjangoWebProject1/app/price_sync/services.py DjangoWebProject1/app/test_price_sync_retention.py
git commit -m "feat: retain twelve detailed price imports"
```

### Task 11: Add end-to-end safety, query and performance regression tests

**Files:**
- Create: `DjangoWebProject1/app/test_price_sync_integration.py`
- Modify: implementation files only if a failing regression demonstrates a defect

**Interfaces:**
- Validates: complete upload → review → resolve/skip → confirm anomaly → apply → rollback flow.

- [ ] **Step 1: Add an end-to-end admin test**

```python
def test_authorized_admin_can_preview_resolve_apply_and_rollback(self):
    before_ids = set(Product.objects.values_list("pk", flat=True))
    response = self.client.post(self.upload_url, {"source_file": self.workbook}, follow=True)
    self.assertContains(response, "Требуют проверки")
    self.client.post(self.resolve_url, {"product": self.product.pk})
    self.client.post(self.confirm_anomalies_url, {"confirmed": True, "row_ids": [self.row.pk]})
    self.client.post(self.apply_url)
    self.product.refresh_from_db()
    self.assertEqual(self.product.price, Decimal("1250.00"))
    self.client.post(self.rollback_url)
    self.assertSetEqual(before_ids, set(Product.objects.values_list("pk", flat=True)))
```

- [ ] **Step 2: Add a representative 27,340-row service test**

Generate rows in-memory rather than committing supplier data. Patch the parser output for the service performance test, assert a bounded query count for catalog loading, `batch_size=1000`, and no query per source row. Record an engineering ceiling of 30 seconds on the production-like PostgreSQL staging run; do not make CI fail on workstation wall-clock variance.

- [ ] **Step 3: Run focused and full suites**

```powershell
python DjangoWebProject1/manage.py test app.test_price_sync_models app.test_price_sync_rules app.test_price_sync_parsing app.test_price_sync_matching app.test_price_sync_preview app.test_price_sync_admin app.test_price_sync_apply app.test_price_sync_rollback app.test_price_sync_retention app.test_price_sync_integration --noinput
python DjangoWebProject1/manage.py test app --noinput
python DjangoWebProject1/manage.py check --deploy
```

Expected: price-sync suite passes. The full suite must not add failures; any previously documented baseline failure must be reconciled before merge. `check --deploy` may report only environment-dependent warnings that are already satisfied by production environment variables.

- [ ] **Step 4: Verify public templates and API payloads did not change**

```powershell
git diff --name-only 14596d3...HEAD -- DjangoWebProject1/app/templates/app DjangoWebProject1/app/views.py DjangoWebProject1/app/urls.py
```

Expected: no public template/view/URL change for this feature.

- [ ] **Step 5: Commit integration coverage**

```powershell
git add DjangoWebProject1/app/test_price_sync_integration.py
git commit -m "test: cover price import lifecycle"
```

### Task 12: Document, stage and deploy without risking the catalog

**Files:**
- Create: `docs/price-import-runbook.md`
- Modify: `README.md` (admin capability and runbook link only)

**Interfaces:**
- Produces: operator procedure for preview, approval, rollback, backup and cleanup.

- [ ] **Step 1: Write the runbook with exact production checks**

Document these commands and decision points:

```powershell
docker compose exec -T db pg_dump -U $env:POSTGRES_USER $env:POSTGRES_DB > "backup-before-price-import.sql"
docker compose run --rm web python manage.py migrate --plan
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py check --deploy
docker compose exec -T web python manage.py cleanup_price_imports --keep 12
```

The runbook must say: first upload on a staging copy of the database; reconcile matched/review/skipped/anomaly totals with the XLSX; sample at least 20 products across increases/decreases; apply only after backup; verify catalog, product page, search, cart and error journal; use the admin rollback only before any later price import or manual price edit.

- [ ] **Step 2: Validate with the real workbook on staging**

Use `C:\Users\XPLOUS\Downloads\price-2026-10-05_12-19-11.xlsx` only as an operator input. Confirm the preview reads 27,340 source rows, reports duplicate/missing-SKU rows explicitly, and never adds the file to Git. Record counts and the sample validation in the deployment ticket/runbook log, not in application source.

- [ ] **Step 3: Run migration rollback rehearsal on a database copy**

```powershell
python DjangoWebProject1/manage.py migrate app 0044
python DjangoWebProject1/manage.py migrate app 0045
```

Use the actual preceding and generated migration numbers after journal integration. Verify product count and a checksum/sample of existing `price`/`old_price` values are unchanged by schema migration alone.

- [ ] **Step 4: Perform final verification and commit docs**

```powershell
python DjangoWebProject1/manage.py test app --noinput
git status --short
git diff --check
git add docs/price-import-runbook.md README.md
git commit -m "docs: add price import operations runbook"
```

- [ ] **Step 5: Open a PR and deploy only the reviewed merge commit**

Push `feature/supplier-price-sync`, require the CI check, review migrations and permissions, merge into `main`, tag the release, and deploy that exact commit. After deployment, run migration/check commands, perform one preview before any apply, and verify the private volume is absent from nginx mounts.

## Definition of done

- The real supplier workbook can be uploaded only by an authorized staff user and produces a reviewable preview.
- Automatic matches follow the approved strict order; doubtful matches require a human.
- Prices use `REKOMEND_CENA`; every product keeps one 10–30% discount and an old price rounded upward to 10 rubles.
- Preview changes no products; apply changes only the four approved Product fields in one transaction.
- Product count and IDs remain unchanged across preview, apply and rollback.
- The last update time is visible in admin only.
- The latest safe import can be rolled back; stale/manual changes are reported as conflicts.
- Duplicate application, malformed XLSX, oversized XLSX, zip expansion, formula cells, invalid prices and unauthorized requests are covered by tests.
- Twelve newest successful imports keep full details; older ones retain summaries only.
- Production deployment is traceable to a clean reviewed commit and begins with a PostgreSQL backup.
