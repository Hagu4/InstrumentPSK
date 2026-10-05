from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from app.models import PriceImport, Product
from app.price_sync.parsing import PriceImportValidationError
from app.price_sync.services import ManualPriceChange, create_manual_preview


class ManualPricePreviewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="manual-pricer")
        self.first = Product.objects.create(
            title="Первый товар",
            sku="MANUAL-1",
            price=Decimal("100.00"),
            discount_percent=17,
        )
        self.second = Product.objects.create(
            title="Второй товар",
            sku="MANUAL-2",
            price=Decimal("200.00"),
            discount_percent=23,
        )

    def test_manual_preview_accepts_several_unique_existing_products(self):
        import_obj = create_manual_preview(
            [
                ManualPriceChange(self.first.pk, Decimal("110")),
                ManualPriceChange(self.second.pk, Decimal("180")),
            ],
            self.user,
        )

        self.assertEqual(import_obj.source_type, PriceImport.SourceType.MANUAL)
        self.assertEqual(import_obj.rows.count(), 2)
        self.assertEqual(
            import_obj.rows.get(product=self.first).after_discount_percent,
            17,
        )
        self.first.refresh_from_db()
        self.assertEqual(self.first.price, Decimal("100.00"))

    def test_manual_preview_rejects_duplicate_product(self):
        with self.assertRaisesRegex(PriceImportValidationError, "duplicate_manual_product"):
            create_manual_preview(
                [
                    ManualPriceChange(self.first.pk, Decimal("100")),
                    ManualPriceChange(self.first.pk, Decimal("110")),
                ],
                self.user,
            )

    def test_manual_preview_rejects_empty_batch(self):
        with self.assertRaisesRegex(PriceImportValidationError, "empty_manual_batch"):
            create_manual_preview([], self.user)

    def test_manual_preview_rejects_missing_product(self):
        with self.assertRaisesRegex(PriceImportValidationError, "unknown_manual_product"):
            create_manual_preview(
                [ManualPriceChange(999999, Decimal("100"))],
                self.user,
            )

    def test_manual_preview_rejects_non_positive_price(self):
        with self.assertRaisesRegex(PriceImportValidationError, "invalid_manual_price"):
            create_manual_preview(
                [ManualPriceChange(self.first.pk, Decimal("0"))],
                self.user,
            )

    def test_manual_preview_over_fifty_percent_requires_confirmation(self):
        import_obj = create_manual_preview(
            [ManualPriceChange(self.first.pk, Decimal("151"))],
            self.user,
        )

        self.assertEqual(import_obj.status, PriceImport.Status.DRAFT)
        self.assertEqual(import_obj.anomaly_rows, 1)
        self.assertFalse(import_obj.source_file.name)
        self.assertIsNone(import_obj.file_sha256)
