from decimal import Decimal
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from openpyxl import Workbook

from app.price_sync.parsing import PriceImportValidationError, parse_supplier_xlsx


HEADERS = (
    "BRAND",
    "NAIMEN",
    "ARTIKUL",
    "RRC_SHOP",
    "REKOMEND_CENA",
    "OKDP",
    "BARCODE",
    "EDIZM",
)


def workbook_upload(rows, headers=HEADERS, filename="prices.xlsx", configure=None):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    if configure:
        configure(sheet)
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    return SimpleUploadedFile(
        filename,
        stream.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


class PriceSyncParsingTests(SimpleTestCase):
    def test_uses_rrc_shop_instead_of_recommended_price(self):
        rows = parse_supplier_xlsx(
            workbook_upload([
                ("WORTEX", "Дрель 18 В", "00123", 900, 1000, "", "", "шт")
            ])
        )

        self.assertEqual(rows[0].sku, "00123")
        self.assertEqual(rows[0].recommended_price, Decimal("900.00"))

    def test_preserves_numeric_sku_using_excel_number_format(self):
        upload = workbook_upload(
            [("WORTEX", "Дрель", 123, 900, 1000, "", "", "шт")],
            configure=lambda sheet: setattr(sheet["C2"], "number_format", "00000"),
        )

        self.assertEqual(parse_supplier_xlsx(upload)[0].sku, "00123")

    def test_rejects_missing_rrc_shop_column(self):
        upload = workbook_upload([], headers=("BRAND", "NAIMEN", "ARTIKUL"))

        with self.assertRaisesRegex(PriceImportValidationError, "missing_columns"):
            parse_supplier_xlsx(upload)

    def test_formula_is_not_executed_or_accepted_without_cached_value(self):
        upload = workbook_upload([
            ("WORTEX", "Дрель", "A1", "=1+1", 900, "", "", "шт")
        ])

        with self.assertRaisesRegex(PriceImportValidationError, "invalid_price"):
            parse_supplier_xlsx(upload)

    def test_conflicting_duplicate_sku_prices_are_marked_for_safe_skipping(self):
        upload = workbook_upload([
            ("WORTEX", "Дрель", "A-1", 1000, 900, "", "", "шт"),
            ("WORTEX", "Дрель", "A 1", 1200, 900, "", "", "шт"),
            ("WORTEX", "Шуруповёрт", "B-2", 900, 1500, "", "", "шт"),
        ])

        rows = parse_supplier_xlsx(upload)

        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0].diagnostic_code, "duplicate_conflicting_price")
        self.assertEqual(rows[1].diagnostic_code, "duplicate_conflicting_price")
        self.assertEqual(rows[2].diagnostic_code, "")

    def test_identical_duplicate_is_returned_as_skipped_diagnostic(self):
        upload = workbook_upload([
            ("WORTEX", "Дрель", "A-1", 900, 1000, "", "", "шт"),
            ("WORTEX", "Дрель", "A 1", 900, 1000, "", "", "шт"),
        ])

        rows = parse_supplier_xlsx(upload)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1].diagnostic_code, "duplicate_same_price")

    def test_rejects_non_xlsx_container(self):
        upload = SimpleUploadedFile("prices.xlsx", b"not-a-zip")

        with self.assertRaisesRegex(PriceImportValidationError, "invalid_xlsx"):
            parse_supplier_xlsx(upload)

    @override_settings(PRICE_IMPORT_MAX_ROWS=1)
    def test_rejects_workbook_over_row_limit(self):
        upload = workbook_upload([
            ("WORTEX", "Дрель 1", "A1", 900, 1000, "", "", "шт"),
            ("WORTEX", "Дрель 2", "A2", 900, 1200, "", "", "шт"),
        ])

        with self.assertRaisesRegex(PriceImportValidationError, "too_many_rows"):
            parse_supplier_xlsx(upload)
