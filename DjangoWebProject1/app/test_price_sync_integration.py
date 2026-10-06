from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from openpyxl import Workbook
from unittest.mock import patch

from app.models import Brand, PriceImport, PriceImportRow, Product
from app.price_sync.parsing import SupplierRow
from app.price_sync.services import create_preview


def make_workbook(rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet.append(("BRAND", "NAIMEN", "ARTIKUL", "RRC_SHOP"))
    for row in rows:
        sheet.append(row)
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    return SimpleUploadedFile("integration-prices.xlsx", stream.getvalue())


class PriceSyncIntegrationTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="integration-admin",
            email="admin@example.com",
            password="test-password-123",
        )
        self.brand = Brand.objects.create(name="WORTEX", slug="wortex-integration")
        self.exact_product = Product.objects.create(
            title="Дрель WORTEX 18 В",
            sku="EXACT-1",
            brand=self.brand,
            price=Decimal("100.00"),
            quantity=5,
        )
        self.review_product = Product.objects.create(
            title="Шуруповерт WORTEX 20 В",
            sku="LOCAL-2",
            brand=self.brand,
            price=Decimal("200.00"),
            quantity=9,
        )
        self.client.force_login(self.admin)

    def tearDown(self):
        for price_import in PriceImport.objects.exclude(source_file=""):
            price_import.source_file.delete(save=False)

    def test_admin_upload_resolve_confirm_apply_and_rollback(self):
        before_ids = set(Product.objects.values_list("pk", flat=True))
        workbook = make_workbook(
            [
                ("WORTEX", "Дрель WORTEX 18 В", "EXACT-1", 125),
                (
                    "WORTEX",
                    "Шуруповерт WORTEX аккумуляторный 20В",
                    "SUPPLIER-2",
                    400,
                ),
            ]
        )

        response = self.client.post(
            reverse("admin:app_priceimport_upload"),
            {"source_file": workbook},
        )
        price_import = PriceImport.objects.get()
        self.assertRedirects(
            response,
            reverse("admin:app_priceimport_preview", args=[price_import.pk]),
            fetch_redirect_response=False,
        )
        review_row = price_import.rows.get(status=PriceImportRow.Status.NEEDS_REVIEW)

        self.client.post(
            reverse(
                "admin:app_priceimport_resolve",
                args=[price_import.pk, review_row.pk],
            ),
            {"product": self.review_product.pk},
        )
        review_row.refresh_from_db()
        self.assertEqual(review_row.product, self.review_product)
        self.assertEqual(review_row.diagnostic_code, "large_change")

        self.client.post(
            reverse("admin:app_priceimport_confirm_anomalies", args=[price_import.pk]),
            {"confirmed": "on", "row_ids": str(review_row.pk)},
        )
        price_import.refresh_from_db()
        self.assertEqual(price_import.status, PriceImport.Status.READY)

        self.client.post(
            reverse("admin:app_priceimport_apply", args=[price_import.pk])
        )
        self.exact_product.refresh_from_db()
        self.review_product.refresh_from_db()
        self.assertEqual(self.exact_product.price, Decimal("125.00"))
        self.assertEqual(self.review_product.price, Decimal("400.00"))
        self.assertEqual(self.exact_product.quantity, 5)
        self.assertEqual(self.review_product.quantity, 9)
        self.assertSetEqual(
            before_ids, set(Product.objects.values_list("pk", flat=True))
        )

        self.client.post(
            reverse("admin:app_priceimport_rollback", args=[price_import.pk])
        )
        self.exact_product.refresh_from_db()
        self.review_product.refresh_from_db()
        price_import.refresh_from_db()
        self.assertEqual(self.exact_product.price, Decimal("100.00"))
        self.assertEqual(self.review_product.price, Decimal("200.00"))
        self.assertEqual(price_import.status, PriceImport.Status.ROLLED_BACK)
        self.assertSetEqual(
            before_ids, set(Product.objects.values_list("pk", flat=True))
        )

    def test_large_preview_does_not_issue_a_query_per_supplier_row(self):
        source_rows = [
            SupplierRow(
                row_number=index + 2,
                brand="ДРУГОЙ БРЕНД",
                title=f"Позиция поставщика {index}",
                sku=f"SUP-{index}",
                recommended_price=Decimal("125.00"),
            )
            for index in range(27_340)
        ]
        upload = SimpleUploadedFile("large.xlsx", b"test workbook placeholder")

        with patch(
            "app.price_sync.services.parse_supplier_xlsx",
            return_value=source_rows,
        ), CaptureQueriesContext(connection) as queries:
            price_import, created = create_preview(upload, self.admin)

        self.assertTrue(created)
        self.assertEqual(price_import.total_rows, 27_340)
        self.assertEqual(price_import.rows.count(), 27_340)
        self.assertLess(len(queries), 700)

    def test_supplier_rows_without_catalog_candidates_are_skipped_automatically(self):
        workbook = make_workbook(
            [("_", "Смеситель для ванны вентильный, серия 08", "NNF-0015", 2790)]
        )

        price_import, created = create_preview(workbook, self.admin)

        self.assertTrue(created)
        row = price_import.rows.get()
        self.assertEqual(row.status, PriceImportRow.Status.SKIPPED)
        self.assertEqual(row.diagnostic_code, "not_in_catalog")
        self.assertEqual(price_import.review_rows, 0)

    def test_preview_matches_only_the_two_catalog_products_from_sample_price(self):
        diamond = Product.objects.create(
            title="Алмазный круг 230x22мм керамика 35 (Сплитстоун)",
            price=Decimal("2000.00"),
            quantity=10,
        )
        faucet = Product.objects.create(
            title="Смеситель для ванны вентильный, серия 07",
            sku="NNF-0016",
            price=Decimal("1500.00"),
            quantity=10,
        )
        workbook = make_workbook(
            [
                ("Нет бренда", diamond.title, None, 6840),
                ("_", faucet.title, "NNF-0016", 2330),
                ("_", "Смеситель для ванны вентильный, серия 08", "NNF-0015", 2790),
                ("_", "Смеситель для кухни D35, серия 02", "NNF-0051", 1110),
                ("_", "Смеситель для умывальника D35, серия 01", "NNF-0004", 1800),
            ]
        )

        price_import, created = create_preview(workbook, self.admin)

        self.assertTrue(created)
        self.assertEqual(price_import.total_rows, 5)
        self.assertEqual(price_import.matched_rows, 2)
        self.assertEqual(price_import.skipped_rows, 3)
        self.assertEqual(price_import.review_rows, 0)
        diamond_row = price_import.rows.get(product=diamond)
        faucet_row = price_import.rows.get(product=faucet)
        self.assertEqual(diamond_row.before_price, Decimal("2000.00"))
        self.assertEqual(diamond_row.after_price, Decimal("6840.00"))
        self.assertEqual(faucet_row.before_price, Decimal("1500.00"))
        self.assertEqual(faucet_row.after_price, Decimal("2330.00"))
