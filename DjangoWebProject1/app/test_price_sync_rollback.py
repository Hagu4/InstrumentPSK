from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase

from app.models import PriceImport, Product
from app.price_sync.services import (
    ManualPriceChange,
    RollbackConflict,
    RollbackNotLatest,
    apply_import,
    create_manual_preview,
    rollback_import,
)


class PriceSyncRollbackTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="rollback-user")
        self.product = Product.objects.create(
            title="Товар для отката",
            sku="ROLLBACK-1",
            price=Decimal("100.00"),
            old_price=Decimal("130.00"),
            discount_percent=23,
        )

    def apply_price(self, price):
        import_obj = create_manual_preview(
            [ManualPriceChange(self.product.pk, Decimal(price))],
            self.user,
        )
        row = import_obj.rows.get()
        apply_import(import_obj.pk, self.user)
        return import_obj, row

    def test_latest_import_restores_complete_price_snapshot(self):
        import_obj, row = self.apply_price("120")

        rollback_import(import_obj.pk, self.user)

        self.product.refresh_from_db()
        import_obj.refresh_from_db()
        self.assertEqual(self.product.price, row.before_price)
        self.assertEqual(self.product.old_price, row.before_old_price)
        self.assertEqual(self.product.discount_percent, row.before_discount_percent)
        self.assertEqual(self.product.price_updated_at, row.before_price_updated_at)
        self.assertEqual(import_obj.status, PriceImport.Status.ROLLED_BACK)
        self.assertEqual(import_obj.rolled_back_by, self.user)

    def test_older_applied_import_cannot_be_rolled_back(self):
        older, _ = self.apply_price("110")
        newest, _ = self.apply_price("120")

        with self.assertRaises(RollbackNotLatest):
            rollback_import(older.pk, self.user)

        self.assertEqual(
            PriceImport.objects.get(pk=newest.pk).status,
            PriceImport.Status.APPLIED,
        )

    def test_manual_price_edit_blocks_rollback(self):
        import_obj, _ = self.apply_price("120")
        Product.objects.filter(pk=self.product.pk).update(price=Decimal("999"))

        with self.assertRaises(RollbackConflict):
            rollback_import(import_obj.pk, self.user)

    def test_rolling_back_newest_does_not_unlock_older_import(self):
        older, _ = self.apply_price("110")
        newest, _ = self.apply_price("120")
        rollback_import(newest.pk, self.user)

        with self.assertRaises(RollbackNotLatest):
            rollback_import(older.pk, self.user)
