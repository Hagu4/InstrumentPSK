from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from app.models import PriceImport, Product, SupplierProductLink


@override_settings(PRICE_IMPORT_ROOT=Path(__file__).resolve().parent / "test-private-imports")
class PriceSyncModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="price-manager",
            password="test-password-123",
        )

    def make_product(self, sku):
        return Product.objects.create(
            title=f"Тестовый товар {sku}",
            sku=sku,
            price=Decimal("100.00"),
        )

    def test_supplier_sku_is_unique_per_supplier_when_non_empty(self):
        product_a = self.make_product("LOCAL-A")
        product_b = self.make_product("LOCAL-B")
        SupplierProductLink.objects.create(
            supplier="stiooo",
            product=product_a,
            source_sku="SUP-1",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SupplierProductLink.objects.create(
                    supplier="stiooo",
                    product=product_b,
                    source_sku="SUP-1",
                )

    def test_import_file_has_no_public_url(self):
        import_obj = PriceImport(
            source_type=PriceImport.SourceType.SUPPLIER_XLSX,
            source_file="2026/10/private.xlsx",
        )

        with self.assertRaisesRegex(ValueError, "do not have public URLs"):
            _ = import_obj.source_file.url

    def test_product_discount_accepts_only_ten_through_thirty(self):
        product = self.make_product("RANGE-1")
        product.discount_percent = 31

        with self.assertRaises(ValidationError):
            product.full_clean()

    def test_manual_import_does_not_require_a_file_or_hash(self):
        import_obj = PriceImport.objects.create(
            source_type=PriceImport.SourceType.MANUAL,
            uploaded_by=self.user,
        )

        import_obj.full_clean()
        self.assertFalse(import_obj.source_file.name)
        self.assertIsNone(import_obj.file_sha256)
