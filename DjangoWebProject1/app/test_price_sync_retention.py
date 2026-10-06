from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from app.models import PriceImport, PriceImportRow, Product
from app.price_sync.services import cleanup_old_price_import_details


class PriceSyncRetentionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="retention-admin", password="test-password"
        )
        self.product = Product.objects.create(
            title="Тестовый товар",
            price="100.00",
        )

    def _make_import(self, index, source_type=PriceImport.SourceType.SUPPLIER_XLSX):
        price_import = PriceImport.objects.create(
            source_type=source_type,
            source_file=(f"price-imports/{index}.xlsx" if source_type == PriceImport.SourceType.SUPPLIER_XLSX else ""),
            original_name=(f"price-{index}.xlsx" if source_type == PriceImport.SourceType.SUPPLIER_XLSX else ""),
            status=PriceImport.Status.APPLIED,
            uploaded_by=self.user,
            applied_by=self.user,
            applied_at=timezone.now() + timedelta(seconds=index),
            total_rows=1,
            matched_rows=1,
            changed_rows=1,
        )
        PriceImportRow.objects.create(
            price_import=price_import,
            row_number=1,
            source_title=f"Товар {index}",
            source_price="110.00",
            product=self.product,
            status=PriceImportRow.Status.MATCHED,
            before_price="100.00",
            after_price="110.00",
        )
        return price_import

    @patch("app.price_sync.storage.private_price_import_storage.delete")
    def test_keeps_details_and_files_for_latest_twelve_supplier_imports(self, delete_file):
        imports = [self._make_import(index) for index in range(13)]

        result = cleanup_old_price_import_details(keep=12)

        imports[0].refresh_from_db()
        imports[-1].refresh_from_db()
        self.assertFalse(imports[0].source_file.name)
        self.assertFalse(imports[0].rows.exists())
        self.assertTrue(imports[-1].source_file.name)
        self.assertTrue(imports[-1].rows.exists())
        self.assertEqual(imports[0].status, PriceImport.Status.APPLIED)
        self.assertEqual(imports[0].total_rows, 1)
        self.assertEqual(result.cleaned_imports, 1)
        self.assertEqual(result.deleted_files, 1)
        self.assertEqual(result.deleted_rows, 1)
        delete_file.assert_called_once_with("price-imports/0.xlsx")

    @patch("app.price_sync.storage.private_price_import_storage.delete")
    def test_cleanup_is_idempotent(self, delete_file):
        for index in range(13):
            self._make_import(index)

        first = cleanup_old_price_import_details(keep=12)
        second = cleanup_old_price_import_details(keep=12)

        self.assertEqual(first.deleted_files, 1)
        self.assertEqual(second.deleted_files, 0)
        self.assertEqual(second.deleted_rows, 0)
        delete_file.assert_called_once()

    @patch("app.price_sync.storage.private_price_import_storage.delete")
    def test_manual_history_is_never_pruned(self, delete_file):
        manual_imports = [
            self._make_import(index, PriceImport.SourceType.MANUAL)
            for index in range(15)
        ]

        result = cleanup_old_price_import_details(keep=1)

        self.assertEqual(result.cleaned_imports, 0)
        self.assertTrue(all(item.rows.exists() for item in manual_imports))
        delete_file.assert_not_called()

    def test_rejects_negative_retention_limit(self):
        with self.assertRaises(ValueError):
            cleanup_old_price_import_details(keep=-1)
