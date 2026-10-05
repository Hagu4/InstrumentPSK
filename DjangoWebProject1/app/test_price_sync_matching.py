from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from app.models import Brand, Product, SupplierProductLink
from app.price_sync.matching import CatalogIndex, match_row
from app.price_sync.parsing import SupplierRow


class PriceSyncMatchingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="matcher")
        self.brand = Brand.objects.create(name="WORTEX", slug="wortex")

    def make_product(self, title="Дрель 18 В", sku=None, brand=None):
        return Product.objects.create(
            title=title,
            sku=sku,
            brand=self.brand if brand is None else brand,
            price=Decimal("100.00"),
        )

    def supplier_row(self, title="Дрель 18 В", sku="", brand="WORTEX"):
        return SupplierRow(
            row_number=2,
            brand=brand,
            title=title,
            sku=sku,
            recommended_price=Decimal("120.00"),
        )

    def index(self):
        return CatalogIndex.from_queryset(
            Product.objects.select_related("brand"),
            SupplierProductLink.objects.all(),
        )

    def test_saved_link_wins_before_changed_supplier_sku(self):
        product = self.make_product(sku="LOCAL-1")
        SupplierProductLink.objects.create(
            supplier="stiooo",
            product=product,
            source_sku="OLD-SUP",
            normalized_brand="wortex",
            normalized_title="дрель 18 в",
            numeric_signature=["18v"],
            confirmed_by=self.user,
        )

        decision = match_row(self.supplier_row(sku="OLD-SUP"), self.index())

        self.assertEqual((decision.product_id, decision.method), (product.pk, "saved_link"))

    def test_exact_sku_is_automatic(self):
        product = self.make_product(sku="ABC-123")

        decision = match_row(self.supplier_row(sku="abc 123"), self.index())

        self.assertEqual((decision.product_id, decision.method), (product.pk, "exact_sku"))

    def test_exact_brand_and_title_is_automatic_without_sku(self):
        product = self.make_product(title="Дрель аккумуляторная 18 В")

        decision = match_row(
            self.supplier_row(title="Дрель аккумуляторная 18 В"),
            self.index(),
        )

        self.assertEqual((decision.product_id, decision.method), (product.pk, "exact_title"))

    def test_no_brand_placeholder_matches_product_without_brand_by_exact_title(self):
        product = Product.objects.create(
            title="Алмазный круг 230x22мм керамика 35 (Сплитстоун)",
            price=Decimal("100.00"),
        )

        decision = match_row(
            self.supplier_row(
                title="Алмазный круг 230x22мм керамика 35 (Сплитстоун)",
                brand="Нет бренда",
            ),
            self.index(),
        )

        self.assertEqual((decision.product_id, decision.method), (product.pk, "exact_title"))

    def test_same_brand_but_conflicting_numbers_is_not_automatic(self):
        self.make_product(title="Дрель 12 В 2 Ач")

        decision = match_row(
            self.supplier_row(title="Дрель 18 В 2 Ач"),
            self.index(),
        )

        self.assertIsNone(decision.product_id)
        self.assertEqual(decision.method, "needs_review")

    def test_fuzzy_similarity_only_returns_candidates(self):
        product = self.make_product(title="Дрель аккумуляторная 18 В")

        decision = match_row(
            self.supplier_row(title="Аккумуляторная дрель 18В"),
            self.index(),
        )

        self.assertIsNone(decision.product_id)
        self.assertIn(product.pk, decision.candidate_ids)

    def test_fuzzy_candidates_do_not_cross_conflicting_model_numbers(self):
        product = Product.objects.create(
            title="Смеситель для ванны вентильный, серия 07",
            sku="NNF-0016",
            price=Decimal("100.00"),
        )

        decision = match_row(
            self.supplier_row(
                title="Смеситель для ванны вентильный, серия 08",
                sku="NNF-0015",
                brand="_",
            ),
            self.index(),
        )

        self.assertIsNone(decision.product_id)
        self.assertNotIn(product.pk, decision.candidate_ids)

    def test_product_already_claimed_in_import_requires_review(self):
        product = self.make_product(sku="ABC-123")

        decision = match_row(
            self.supplier_row(sku="ABC123"),
            self.index(),
            claimed_product_ids={product.pk},
        )

        self.assertIsNone(decision.product_id)
        self.assertEqual(decision.diagnostic_code, "product_already_matched")
