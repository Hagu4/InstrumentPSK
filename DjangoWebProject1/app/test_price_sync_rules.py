from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from app.price_sync.normalization import (
    extract_model_tokens,
    extract_numeric_signature,
    normalize_sku,
    normalize_text,
)
from app.price_sync.pricing import (
    calculate_old_price,
    choose_discount,
    is_large_change,
    validate_price,
)


class PriceSyncRuleTests(SimpleTestCase):
    def test_normalization_preserves_model_numbers_and_units(self):
        self.assertEqual(normalize_text("  WORTEX  CAG 1818 E  "), "wortex cag 1818 e")
        self.assertEqual(extract_numeric_signature("18 В, 2 А·ч"), ("18v", "2ah"))

    def test_sku_normalization_preserves_leading_zeroes(self):
        self.assertEqual(normalize_sku(" 001-23 "), "00123")

    def test_different_numeric_models_do_not_share_signature(self):
        self.assertNotEqual(
            extract_numeric_signature("дрель 12 В 2 А·ч"),
            extract_numeric_signature("дрель 18 В 2 А·ч"),
        )

    def test_model_tokens_keep_alphanumeric_designations(self):
        self.assertEqual(extract_model_tokens("WORTEX CAG 1818 E"), ("1818", "cag"))

    @patch("app.price_sync.pricing.secrets.randbelow", return_value=7)
    def test_discount_is_generated_once_in_inclusive_range(self, _randbelow):
        self.assertEqual(choose_discount(None, Decimal("100"), None), 17)
        self.assertEqual(choose_discount(23, Decimal("100"), Decimal("130")), 23)

    def test_existing_old_price_can_supply_valid_discount(self):
        self.assertEqual(
            choose_discount(None, Decimal("100"), Decimal("125")),
            20,
        )

    def test_old_price_rounds_up_to_ten_rubles(self):
        self.assertEqual(calculate_old_price(Decimal("1000"), 17), Decimal("1210.00"))

    def test_more_than_fifty_percent_is_anomaly(self):
        self.assertTrue(is_large_change(Decimal("100"), Decimal("151")))
        self.assertFalse(is_large_change(Decimal("100"), Decimal("150")))

    def test_price_must_fit_product_decimal_field(self):
        for value in (Decimal("0"), Decimal("-1"), Decimal("100000000")):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                validate_price(value)
