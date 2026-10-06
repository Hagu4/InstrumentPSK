import hashlib
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from app.models import PriceImport, PriceImportRow, Product, SupplierProductLink

from .matching import CatalogIndex, match_row
from .normalization import (
    extract_numeric_signature,
    normalize_brand,
    normalize_text,
)
from .parsing import PriceImportValidationError, parse_supplier_xlsx
from .pricing import calculate_old_price, choose_discount, is_large_change, validate_price


@dataclass(frozen=True)
class ManualPriceChange:
    product_id: int
    new_price: Decimal


@dataclass(frozen=True)
class CleanupResult:
    cleaned_imports: int
    deleted_files: int
    deleted_rows: int


class ImportNotReady(PriceImportValidationError):
    def __init__(self):
        super().__init__("import_not_ready", "Черновик ещё не готов к применению")


class ImportConflict(PriceImportValidationError):
    def __init__(self):
        super().__init__(
            "import_conflict",
            "После предпросмотра один из товаров был изменён. Создайте новый предпросмотр.",
        )


class ImportAlreadyApplied(PriceImportValidationError):
    def __init__(self):
        super().__init__("import_already_applied", "Эта операция уже применена")


class RollbackNotLatest(PriceImportValidationError):
    def __init__(self):
        super().__init__(
            "rollback_not_latest",
            "Откат доступен только для самого последнего обновления цен",
        )


class RollbackConflict(PriceImportValidationError):
    def __init__(self):
        super().__init__(
            "rollback_conflict",
            "После обновления одна из цен была изменена вручную. Откат остановлен.",
        )


def _hash_upload(uploaded_file) -> str:
    digest = hashlib.sha256()
    uploaded_file.seek(0)
    chunks = getattr(uploaded_file, "chunks", None)
    iterable = chunks() if chunks else iter(lambda: uploaded_file.read(64 * 1024), b"")
    for chunk in iterable:
        digest.update(chunk)
    uploaded_file.seek(0)
    return digest.hexdigest()


def _catalog_products():
    return Product.objects.select_related("brand").only(
        "id",
        "sku",
        "title",
        "brand_id",
        "brand__name",
        "price",
        "old_price",
        "discount_percent",
        "price_updated_at",
    )


def refresh_import_counters(price_import: PriceImport) -> None:
    rows = list(price_import.rows.all())
    matched = [row for row in rows if row.status == PriceImportRow.Status.MATCHED]
    anomalies = [
        row
        for row in matched
        if row.before_price is not None
        and row.after_price is not None
        and is_large_change(row.before_price, row.after_price)
    ]
    price_import.total_rows = len(rows)
    price_import.matched_rows = len(matched)
    price_import.skipped_rows = sum(
        row.status == PriceImportRow.Status.SKIPPED for row in rows
    )
    price_import.review_rows = sum(
        row.status in (PriceImportRow.Status.NEEDS_REVIEW, PriceImportRow.Status.INVALID)
        for row in rows
    )
    price_import.changed_rows = sum(
        row.before_price != row.after_price for row in matched
    )
    price_import.increased_rows = sum(
        row.after_price > row.before_price for row in matched
    )
    price_import.decreased_rows = sum(
        row.after_price < row.before_price for row in matched
    )
    price_import.anomaly_rows = len(anomalies)
    ready = all(row.anomaly_confirmed for row in anomalies)
    price_import.status = (
        PriceImport.Status.READY if ready else PriceImport.Status.DRAFT
    )
    price_import.save(
        update_fields=(
            "total_rows",
            "matched_rows",
            "skipped_rows",
            "review_rows",
            "changed_rows",
            "increased_rows",
            "decreased_rows",
            "anomaly_rows",
            "status",
        )
    )


def create_preview(uploaded_file, user) -> tuple[PriceImport, bool]:
    file_sha256 = _hash_upload(uploaded_file)
    existing = PriceImport.objects.filter(
        file_sha256=file_sha256,
        status__in=(
            PriceImport.Status.READY,
            PriceImport.Status.APPLIED,
            PriceImport.Status.ROLLED_BACK,
        ),
    ).first()
    if existing is not None:
        return existing, False

    price_import = PriceImport.objects.create(
        source_type=PriceImport.SourceType.SUPPLIER_XLSX,
        source_file=uploaded_file,
        original_name=Path(getattr(uploaded_file, "name", "prices.xlsx")).name[:255],
        file_sha256=file_sha256,
        supplier=settings.PRICE_IMPORT_SUPPLIER,
        uploaded_by=user,
    )
    try:
        with price_import.source_file.open("rb") as stored_file:
            source_rows = parse_supplier_xlsx(stored_file)
    except PriceImportValidationError as error:
        price_import.status = PriceImport.Status.FAILED
        price_import.failure_code = error.code
        price_import.save(update_fields=("status", "failure_code"))
        raise

    products = list(_catalog_products())
    products_by_id = {product.pk: product for product in products}
    links = SupplierProductLink.objects.filter(supplier=price_import.supplier)
    index = CatalogIndex.from_queryset(products, links)
    claimed_product_ids = set()
    preview_at = timezone.now()
    audit_rows = []
    for source_row in source_rows:
        if source_row.diagnostic_code in {
            "duplicate_same_price",
            "duplicate_conflicting_price",
        }:
            audit_rows.append(
                PriceImportRow(
                    price_import=price_import,
                    row_number=source_row.row_number,
                    source_sku=source_row.sku,
                    source_brand=source_row.brand,
                    source_title=source_row.title,
                    source_price=source_row.recommended_price,
                    status=PriceImportRow.Status.SKIPPED,
                    diagnostic_code=source_row.diagnostic_code,
                )
            )
            continue

        decision = match_row(source_row, index, claimed_product_ids)
        product = products_by_id.get(decision.product_id)
        if product is None:
            has_candidates = bool(decision.candidate_ids)
            audit_rows.append(
                PriceImportRow(
                    price_import=price_import,
                    row_number=source_row.row_number,
                    source_sku=source_row.sku,
                    source_brand=source_row.brand,
                    source_title=source_row.title,
                    source_price=source_row.recommended_price,
                    candidate_product_ids=list(decision.candidate_ids),
                    match_method=decision.method,
                    status=(
                        PriceImportRow.Status.NEEDS_REVIEW
                        if has_candidates
                        else PriceImportRow.Status.SKIPPED
                    ),
                    diagnostic_code=(
                        decision.diagnostic_code if has_candidates else "not_in_catalog"
                    ),
                )
            )
            continue

        claimed_product_ids.add(product.pk)
        discount = choose_discount(
            product.discount_percent,
            source_row.recommended_price,
            product.old_price,
        )
        old_price = calculate_old_price(source_row.recommended_price, discount)
        anomaly = is_large_change(product.price, source_row.recommended_price)
        audit_rows.append(
            PriceImportRow(
                price_import=price_import,
                row_number=source_row.row_number,
                source_sku=source_row.sku,
                source_brand=source_row.brand,
                source_title=source_row.title,
                source_price=source_row.recommended_price,
                product=product,
                match_method=decision.method,
                status=PriceImportRow.Status.MATCHED,
                diagnostic_code="large_change" if anomaly else "",
                before_price=product.price,
                before_old_price=product.old_price,
                before_discount_percent=product.discount_percent,
                before_price_updated_at=product.price_updated_at,
                after_price=source_row.recommended_price,
                after_old_price=old_price,
                after_discount_percent=discount,
                after_price_updated_at=(
                    preview_at
                    if source_row.recommended_price != product.price
                    else product.price_updated_at
                ),
            )
        )

    PriceImportRow.objects.bulk_create(audit_rows, batch_size=1000)
    refresh_import_counters(price_import)
    return price_import, True


def create_manual_preview(changes, user) -> PriceImport:
    changes = list(changes)
    if not changes:
        raise PriceImportValidationError(
            "empty_manual_batch", "Добавьте хотя бы один товар"
        )
    if len(changes) > 100:
        raise PriceImportValidationError(
            "manual_batch_too_large", "За один раз можно изменить не более 100 товаров"
        )
    product_ids = [int(change.product_id) for change in changes]
    if len(product_ids) != len(set(product_ids)):
        raise PriceImportValidationError(
            "duplicate_manual_product", "Товар добавлен в пакет несколько раз"
        )

    validated_changes = []
    for change in changes:
        try:
            new_price = validate_price(change.new_price)
        except ValidationError:
            raise PriceImportValidationError(
                "invalid_manual_price", "Введите положительную цену в допустимом диапазоне"
            )
        validated_changes.append(ManualPriceChange(int(change.product_id), new_price))

    products = {
        product.pk: product
        for product in _catalog_products().filter(pk__in=product_ids)
    }
    if len(products) != len(product_ids):
        raise PriceImportValidationError(
            "unknown_manual_product", "Один из выбранных товаров не найден"
        )

    price_import = PriceImport.objects.create(
        source_type=PriceImport.SourceType.MANUAL,
        uploaded_by=user,
    )
    preview_at = timezone.now()
    audit_rows = []
    for row_number, change in enumerate(validated_changes, start=1):
        product = products[change.product_id]
        discount = choose_discount(
            product.discount_percent,
            change.new_price,
            product.old_price,
        )
        anomaly = is_large_change(product.price, change.new_price)
        audit_rows.append(
            PriceImportRow(
                price_import=price_import,
                row_number=row_number,
                source_sku=product.sku or "",
                source_brand=product.brand.name if product.brand else "",
                source_title=product.title,
                source_price=change.new_price,
                product=product,
                match_method="manual_price",
                status=PriceImportRow.Status.MATCHED,
                diagnostic_code="large_change" if anomaly else "",
                before_price=product.price,
                before_old_price=product.old_price,
                before_discount_percent=product.discount_percent,
                before_price_updated_at=product.price_updated_at,
                after_price=change.new_price,
                after_old_price=calculate_old_price(change.new_price, discount),
                after_discount_percent=discount,
                after_price_updated_at=(
                    preview_at
                    if change.new_price != product.price
                    else product.price_updated_at
                ),
            )
        )
    PriceImportRow.objects.bulk_create(audit_rows, batch_size=100)
    refresh_import_counters(price_import)
    return price_import


@transaction.atomic
def apply_import(import_id: int, user) -> PriceImport:
    price_import = PriceImport.objects.select_for_update().get(pk=import_id)
    if price_import.status == PriceImport.Status.APPLIED:
        raise ImportAlreadyApplied()
    if price_import.status != PriceImport.Status.READY:
        raise ImportNotReady()

    if price_import.source_type == PriceImport.SourceType.SUPPLIER_XLSX:
        if not price_import.source_file.name:
            raise ImportConflict()
        with price_import.source_file.open("rb") as source_file:
            if _hash_upload(source_file) != price_import.file_sha256:
                raise ImportConflict()

    price_import.rows.filter(
        status__in=(PriceImportRow.Status.NEEDS_REVIEW, PriceImportRow.Status.INVALID)
    ).update(
        status=PriceImportRow.Status.SKIPPED,
        diagnostic_code="not_selected_for_apply",
        product=None,
        candidate_product_ids=[],
        after_price=None,
        after_old_price=None,
        after_discount_percent=None,
        after_price_updated_at=None,
    )
    refresh_import_counters(price_import)

    rows = list(
        price_import.rows.select_for_update()
        .select_related("product")
        .filter(status=PriceImportRow.Status.MATCHED)
    )
    product_ids = [row.product_id for row in rows]
    if None in product_ids or len(product_ids) != len(set(product_ids)):
        raise ImportConflict()
    products = {
        product.pk: product
        for product in Product.objects.select_for_update().filter(pk__in=product_ids)
    }
    if len(products) != len(product_ids):
        raise ImportConflict()

    for row in rows:
        product = products[row.product_id]
        current_snapshot = (
            product.price,
            product.old_price,
            product.discount_percent,
            product.price_updated_at,
        )
        expected_snapshot = (
            row.before_price,
            row.before_old_price,
            row.before_discount_percent,
            row.before_price_updated_at,
        )
        if current_snapshot != expected_snapshot:
            raise ImportConflict()
        product.price = row.after_price
        product.old_price = row.after_old_price
        product.discount_percent = row.after_discount_percent
        product.price_updated_at = row.after_price_updated_at

    Product.objects.bulk_update(
        list(products.values()),
        fields=("price", "old_price", "discount_percent", "price_updated_at"),
        batch_size=1000,
    )

    if price_import.source_type == PriceImport.SourceType.SUPPLIER_XLSX:
        for row in rows:
            SupplierProductLink.objects.update_or_create(
                supplier=price_import.supplier,
                product_id=row.product_id,
                defaults={
                    "source_sku": row.source_sku,
                    "normalized_brand": normalize_brand(row.source_brand),
                    "normalized_title": normalize_text(row.source_title),
                    "numeric_signature": list(
                        extract_numeric_signature(row.source_title)
                    ),
                    "confirmed_by": row.resolved_by,
                    "confirmed_at": row.resolved_at,
                },
            )

    price_import.status = PriceImport.Status.APPLIED
    price_import.applied_by = user
    price_import.applied_at = timezone.now()
    price_import.save(update_fields=("status", "applied_by", "applied_at"))
    transaction.on_commit(cache.clear)
    transaction.on_commit(cleanup_old_price_import_details, robust=True)
    return price_import


@transaction.atomic
def cleanup_old_price_import_details(keep: int = 12) -> CleanupResult:
    if keep < 0:
        raise ValueError("keep must be zero or greater")

    successful = PriceImport.objects.filter(
        source_type=PriceImport.SourceType.SUPPLIER_XLSX,
        status__in=(PriceImport.Status.APPLIED, PriceImport.Status.ROLLED_BACK),
        applied_at__isnull=False,
    ).order_by("-applied_at", "-pk")
    retained_ids = list(successful.values_list("pk", flat=True)[:keep])
    old_imports = list(
        successful.exclude(pk__in=retained_ids).select_for_update()
    )

    deleted_files = 0
    deleted_rows = 0
    cleaned_imports = 0
    for price_import in old_imports:
        had_file = bool(price_import.source_file.name)
        row_count, _ = price_import.rows.all().delete()
        deleted_rows += row_count
        if had_file:
            price_import.source_file.delete(save=False)
            price_import.source_file = ""
            price_import.save(update_fields=("source_file",))
            deleted_files += 1
        if row_count or had_file:
            cleaned_imports += 1

    return CleanupResult(
        cleaned_imports=cleaned_imports,
        deleted_files=deleted_files,
        deleted_rows=deleted_rows,
    )


@transaction.atomic
def rollback_import(import_id: int, user) -> PriceImport:
    price_import = PriceImport.objects.select_for_update().get(pk=import_id)
    latest_success = (
        PriceImport.objects.select_for_update()
        .filter(
            status__in=(
                PriceImport.Status.APPLIED,
                PriceImport.Status.ROLLED_BACK,
            ),
            applied_at__isnull=False,
        )
        .order_by("-applied_at", "-pk")
        .first()
    )
    if (
        latest_success is None
        or latest_success.pk != price_import.pk
        or price_import.status != PriceImport.Status.APPLIED
    ):
        raise RollbackNotLatest()

    rows = list(
        price_import.rows.select_for_update()
        .select_related("product")
        .filter(status=PriceImportRow.Status.MATCHED)
    )
    product_ids = [row.product_id for row in rows]
    products = {
        product.pk: product
        for product in Product.objects.select_for_update().filter(pk__in=product_ids)
    }
    if len(products) != len(product_ids):
        raise RollbackConflict()

    for row in rows:
        product = products[row.product_id]
        current_snapshot = (
            product.price,
            product.old_price,
            product.discount_percent,
            product.price_updated_at,
        )
        imported_snapshot = (
            row.after_price,
            row.after_old_price,
            row.after_discount_percent,
            row.after_price_updated_at,
        )
        if current_snapshot != imported_snapshot:
            raise RollbackConflict()
        product.price = row.before_price
        product.old_price = row.before_old_price
        product.discount_percent = row.before_discount_percent
        product.price_updated_at = row.before_price_updated_at

    Product.objects.bulk_update(
        list(products.values()),
        fields=("price", "old_price", "discount_percent", "price_updated_at"),
        batch_size=1000,
    )
    price_import.status = PriceImport.Status.ROLLED_BACK
    price_import.rolled_back_by = user
    price_import.rolled_back_at = timezone.now()
    price_import.save(
        update_fields=("status", "rolled_back_by", "rolled_back_at")
    )
    transaction.on_commit(cache.clear)
    return price_import


def _require_editable_import(price_import: PriceImport) -> None:
    if price_import.status not in (
        PriceImport.Status.DRAFT,
        PriceImport.Status.READY,
    ):
        raise PriceImportValidationError(
            "import_not_editable",
            "Эту операцию больше нельзя редактировать",
        )


@transaction.atomic
def confirm_anomalies(import_id: int, row_ids=None) -> PriceImport:
    price_import = PriceImport.objects.select_for_update().get(pk=import_id)
    _require_editable_import(price_import)
    rows = price_import.rows.select_for_update().filter(
        diagnostic_code="large_change"
    )
    if row_ids:
        rows = rows.filter(pk__in=row_ids)
    rows.update(anomaly_confirmed=True)
    refresh_import_counters(price_import)
    return price_import


@transaction.atomic
def skip_row(row: PriceImportRow, user) -> PriceImportRow:
    row = PriceImportRow.objects.select_for_update().select_related("price_import").get(
        pk=row.pk
    )
    if row.price_import.status not in (
        PriceImport.Status.DRAFT,
        PriceImport.Status.READY,
    ):
        raise PriceImportValidationError(
            "import_not_editable", "Эту операцию больше нельзя редактировать"
        )
    row.status = PriceImportRow.Status.SKIPPED
    row.product = None
    row.candidate_product_ids = []
    row.after_price = None
    row.after_old_price = None
    row.after_discount_percent = None
    row.after_price_updated_at = None
    row.resolved_by = user
    row.resolved_at = timezone.now()
    row.save()
    refresh_import_counters(row.price_import)
    return row


@transaction.atomic
def resolve_row(row: PriceImportRow, product: Product, user) -> PriceImportRow:
    row = PriceImportRow.objects.select_for_update().select_related("price_import").get(
        pk=row.pk
    )
    _require_editable_import(row.price_import)
    product = Product.objects.select_for_update().get(pk=product.pk)
    if row.price_import.rows.exclude(pk=row.pk).filter(product=product).exists():
        raise PriceImportValidationError(
            "product_already_matched", "Товар уже выбран в другой строке"
        )
    discount = choose_discount(product.discount_percent, row.source_price, product.old_price)
    row.product = product
    row.match_method = "manual"
    row.status = PriceImportRow.Status.MATCHED
    row.before_price = product.price
    row.before_old_price = product.old_price
    row.before_discount_percent = product.discount_percent
    row.before_price_updated_at = product.price_updated_at
    row.after_price = row.source_price
    row.after_discount_percent = discount
    row.after_old_price = calculate_old_price(row.source_price, discount)
    row.after_price_updated_at = (
        timezone.now() if row.source_price != product.price else product.price_updated_at
    )
    row.diagnostic_code = (
        "large_change" if is_large_change(product.price, row.source_price) else ""
    )
    row.resolved_by = user
    row.resolved_at = timezone.now()
    row.save()
    SupplierProductLink.objects.update_or_create(
        supplier=row.price_import.supplier,
        product=product,
        defaults={
            "source_sku": row.source_sku,
            "normalized_brand": normalize_brand(row.source_brand),
            "normalized_title": normalize_text(row.source_title),
            "numeric_signature": list(extract_numeric_signature(row.source_title)),
            "confirmed_by": user,
            "confirmed_at": timezone.now(),
        },
    )
    refresh_import_counters(row.price_import)
    return row
