from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.test import TransactionTestCase

from app.models import PriceImport, Product
from app.price_sync.services import (
    ImportAlreadyApplied,
    ImportConflict,
    ImportNotReady,
    ManualPriceChange,
    apply_import,
    create_manual_preview,
)


class PriceSyncApplyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="applier")
        self.product = Product.objects.create(
            title="Неизменяемое название",
            sku="APPLY-1",
            price=Decimal("100.00"),
            quantity=7,
        )

    def ready_import(self, price=Decimal("120")):
        return create_manual_preview(
            [ManualPriceChange(self.product.pk, price)],
            self.user,
        )

    def test_apply_updates_only_price_fields_and_keeps_product_count(self):
        import_obj = self.ready_import()
        row = import_obj.rows.get()
        before_count = Product.objects.count()

        apply_import(import_obj.pk, self.user)

        self.product.refresh_from_db()
        import_obj.refresh_from_db()
        self.assertEqual(Product.objects.count(), before_count)
        self.assertEqual(self.product.title, "Неизменяемое название")
        self.assertEqual(self.product.quantity, 7)
        self.assertEqual(self.product.price, row.after_price)
        self.assertEqual(self.product.old_price, row.after_old_price)
        self.assertEqual(self.product.discount_percent, row.after_discount_percent)
        self.assertEqual(self.product.price_updated_at, row.after_price_updated_at)
        self.assertEqual(import_obj.status, PriceImport.Status.APPLIED)
        self.assertEqual(import_obj.applied_by, self.user)

    def test_second_apply_is_rejected_without_changes(self):
        import_obj = self.ready_import()
        apply_import(import_obj.pk, self.user)

        with self.assertRaises(ImportAlreadyApplied):
            apply_import(import_obj.pk, self.user)

    def test_product_changed_after_preview_blocks_apply(self):
        import_obj = self.ready_import()
        Product.objects.filter(pk=self.product.pk).update(price=Decimal("105"))

        with self.assertRaises(ImportConflict):
            apply_import(import_obj.pk, self.user)

        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal("105"))

    def test_unready_import_is_rejected(self):
        import_obj = self.ready_import(price=Decimal("151"))
        self.assertEqual(import_obj.status, PriceImport.Status.DRAFT)

        with self.assertRaises(ImportNotReady):
            apply_import(import_obj.pk, self.user)

    def test_database_error_rolls_back_all_products(self):
        second = Product.objects.create(
            title="Второй товар",
            sku="APPLY-2",
            price=Decimal("200.00"),
        )
        import_obj = create_manual_preview(
            [
                ManualPriceChange(self.product.pk, Decimal("120")),
                ManualPriceChange(second.pk, Decimal("220")),
            ],
            self.user,
        )
        original_save = PriceImport.save

        def fail_when_marking_applied(instance, *args, **kwargs):
            if instance.status == PriceImport.Status.APPLIED:
                raise DatabaseError("forced failure")
            return original_save(instance, *args, **kwargs)

        from unittest.mock import patch

        with patch.object(PriceImport, "save", fail_when_marking_applied):
            with self.assertRaises(DatabaseError):
                apply_import(import_obj.pk, self.user)

        self.product.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(self.product.price, Decimal("100.00"))
        self.assertEqual(second.price, Decimal("200.00"))
