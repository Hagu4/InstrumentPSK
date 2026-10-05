from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from openpyxl import Workbook

from app.models import Brand, PriceImportRow, Product
from app.price_sync.services import create_preview


def price_workbook(rows, filename="prices.xlsx"):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet.append(
        ("BRAND", "NAIMEN", "ARTIKUL", "RRC_SHOP", "REKOMEND_CENA", "OKDP", "BARCODE", "EDIZM")
    )
    for row in rows:
        sheet.append(row)
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    return SimpleUploadedFile(filename, stream.getvalue())


class PriceSyncPreviewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="previewer")
        self.brand = Brand.objects.create(name="WORTEX", slug="wortex")
        self.product = Product.objects.create(
            title="Дрель 18 В",
            sku="A1",
            brand=self.brand,
            price=Decimal("100.00"),
        )

    def tearDown(self):
        for import_obj in self.user.uploaded_price_imports.all():
            if import_obj.source_file.name:
                import_obj.source_file.delete(save=False)

    def upload(self, sku="A1", title="Дрель 18 В", price=120):
        return price_workbook([
            ("WORTEX", title, sku, price, price, "", "", "шт")
        ])

    def test_preview_changes_no_product_fields_and_stores_one_discount(self):
        import_obj, created = create_preview(self.upload(), self.user)

        self.product.refresh_from_db()
        row = import_obj.rows.get()
        self.assertTrue(created)
        self.assertEqual(self.product.price, Decimal("100.00"))
        self.assertIsNone(self.product.discount_percent)
        self.assertGreaterEqual(row.after_discount_percent, 10)
        self.assertLessEqual(row.after_discount_percent, 30)
        self.assertGreater(row.after_old_price, row.after_price)

    def test_same_sha_returns_existing_import(self):
        workbook = self.upload()
        payload = workbook.read()
        first, created_first = create_preview(
            SimpleUploadedFile("one.xlsx", payload), self.user
        )
        second, created_second = create_preview(
            SimpleUploadedFile("two.xlsx", payload), self.user
        )

        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first.pk, second.pk)

    def test_same_sha_can_be_reprocessed_when_previous_preview_is_still_draft(self):
        workbook = self.upload(price=200)
        payload = workbook.read()
        first, created_first = create_preview(
            SimpleUploadedFile("one.xlsx", payload), self.user
        )
        second, created_second = create_preview(
            SimpleUploadedFile("two.xlsx", payload), self.user
        )

        self.assertTrue(created_first)
        self.assertEqual(first.status, first.Status.DRAFT)
        self.assertTrue(created_second)
        self.assertNotEqual(first.pk, second.pk)

    def test_preview_never_creates_or_deletes_products(self):
        before_ids = set(Product.objects.values_list("pk", flat=True))

        create_preview(self.upload(), self.user)

        self.assertSetEqual(before_ids, set(Product.objects.values_list("pk", flat=True)))

    def test_unmatched_row_without_candidates_is_skipped_automatically(self):
        import_obj, _ = create_preview(
            self.upload(sku="UNKNOWN", title="Совсем другой товар"),
            self.user,
        )
        row = import_obj.rows.get()
        self.assertEqual(row.status, PriceImportRow.Status.SKIPPED)
        self.assertEqual(row.diagnostic_code, "not_in_catalog")
        self.assertEqual(import_obj.status, import_obj.Status.READY)

    def test_change_over_fifty_percent_blocks_ready_state(self):
        import_obj, _ = create_preview(self.upload(price=151), self.user)

        self.assertEqual(import_obj.anomaly_rows, 1)
        self.assertEqual(import_obj.status, import_obj.Status.DRAFT)

    def test_summary_counts_increase_and_change(self):
        import_obj, _ = create_preview(self.upload(price=120), self.user)

        self.assertEqual(import_obj.total_rows, 1)
        self.assertEqual(import_obj.matched_rows, 1)
        self.assertEqual(import_obj.changed_rows, 1)
        self.assertEqual(import_obj.increased_rows, 1)
