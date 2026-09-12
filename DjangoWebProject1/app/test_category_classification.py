from dataclasses import FrozenInstanceError

from django.db.models import Count
from django.test import TestCase

from .category_classification import (
    Classification, LeafRule, ParentRule, classify_product, classify_text,
    normalize_text, product_search_text,
)
from .models import Category, Characteristic, Product, ProductCharacteristic


class CategoryClassifierTests(TestCase):
    def test_normalization_handles_case_punctuation_and_russian_yo(self):
        self.assertEqual(normalize_text("АККУМ. пила, Ёмкость\t18-В"), "аккум пила емкость 18 в")

    def test_unique_match_is_confident(self):
        rules = ParentRule("chainsaws", (
            LeafRule("battery", "Аккумуляторные", ("аккумуляторный", "аккум")),
            LeafRule("petrol", "Бензиновые", ("бензиновый", "бензопила")),
        ))
        result = classify_text("Аккумуляторная цепная пила 18 В", rules)
        self.assertEqual(result, Classification("matched", "battery", ("аккумуляторный",), ("battery",)))

    def test_tied_match_is_ambiguous(self):
        rules = ParentRule("chainsaws", (
            LeafRule("battery", "Аккумуляторные", ("аккумуляторный",)),
            LeafRule("electric", "Электрические", ("электрический",)),
        ))
        result = classify_text("Электрическая аккумуляторная пила", rules)
        self.assertEqual((result.status, result.leaf_slug), ("ambiguous", None))
        self.assertEqual(result.candidates, ("battery", "electric"))
        self.assertEqual(result, classify_text("Электрическая аккумуляторная пила", ParentRule("chainsaws", tuple(reversed(rules.leaves)))))

    def test_exclusion_prevents_false_positive(self):
        rules = ParentRule("chainsaws", (LeafRule("petrol", "Бензиновые", ("бензиновый",), exclude=("масло",)),))
        self.assertEqual(classify_text("Масло для бензиновых пил", rules).status, "unmatched")

    def test_all_terms_are_required_and_any_cannot_be_empty(self):
        rule = LeafRule("saw", "Пила", ("пила",), include_all=("цепной", "аккумуляторный"))
        for text in ("Пила цепная", "Цепная аккумуляторная", "Пила аккумуляторная"):
            with self.subTest(text=text):
                self.assertEqual(classify_text(text, ParentRule("tools", (rule,))).status, "unmatched")
        self.assertEqual(classify_text("Цепная аккумуляторная пила", ParentRule("tools", (rule,))).leaf_slug, "saw")
        self.assertEqual(classify_text("Пила", ParentRule("tools", (LeafRule("empty", "Empty", ()),))).status, "unmatched")

    def test_score_counts_distinct_normalized_terms_not_occurrences(self):
        rules = ParentRule("tools", (
            LeafRule("a", "A", ("ПИЛА", "пила", "пила!"), include_all=("пила",)),
            LeafRule("b", "B", ("цепной",), priority=1),
        ))
        result = classify_text("пила пила пила цепная", rules)
        self.assertEqual((result.leaf_slug, result.candidates), ("b", ("b", "a")))

    def test_word_boundaries_and_explicit_prefixes_prevent_substring_matches(self):
        rule = ParentRule("tools", (LeafRule("saw", "Saw", ("пила",), exclude=("цепь", "диск")),))
        self.assertEqual(classify_text("Пила дисковая цепная", rule).status, "matched")
        self.assertEqual(classify_text("Лесопила", rule).status, "unmatched")
        prefix_rule = ParentRule("tools", (LeafRule("saw", "Saw", ("бензопил*",)),))
        self.assertEqual(classify_text("Бензопилы", prefix_rule).status, "matched")
        self.assertEqual(classify_text("Супербензопилы", prefix_rule).status, "unmatched")

    def test_phrase_matching_requires_consecutive_words(self):
        rule = ParentRule("tools", (LeafRule("charger", "Charger", ("зарядное устройство",)),))
        self.assertEqual(classify_text("Зарядное-устройство", rule).status, "matched")
        self.assertEqual(classify_text("Зарядное питание и устройство", rule).status, "unmatched")

    def test_empty_text_cannot_match_empty_or_punctuation_terms(self):
        rules = ParentRule("tools", (LeafRule("empty", "Empty", ("", "!!!")),))
        self.assertEqual(classify_text("", rules), Classification("unmatched", None, (), ()))

    def test_rule_and_result_objects_are_frozen(self):
        for obj, field in ((LeafRule("saw", "Saw", ("пила",)), "slug"), (ParentRule("tools", ()), "parent_slug"), (Classification("unmatched", None, (), ()), "status")):
            with self.subTest(obj=obj), self.assertRaises(FrozenInstanceError):
                setattr(obj, field, "changed")

    def test_product_text_uses_all_fields_and_prefetch_without_extra_queries(self):
        first = Product.objects.create(title="Пила", description="Цепная", price=1)
        second = Product.objects.create(title="Другая пила", description=None, price=1)
        for name, value in (("Тип питания", "Аккумуляторный"), ("Ёмкость", "5 Ач")):
            characteristic = Characteristic.objects.create(name=name)
            for product in (first, second):
                ProductCharacteristic.objects.create(product=product, characteristic=characteristic, value=value)
        with self.assertNumQueries(3):
            products = list(Product.objects.order_by("pk").prefetch_related("characteristics__characteristic"))
        rules = ParentRule("tools", (LeafRule("battery", "Battery", ("аккумуляторный",)),))
        with self.assertNumQueries(0):
            texts = [product_search_text(product) for product in products]
            results = [classify_product(product, rules) for product in products]
        self.assertIn("Пила", texts[0])
        self.assertIn("Цепная", texts[0])
        self.assertIn("Тип питания", texts[0])
        self.assertIn("Аккумуляторный", texts[0])
        self.assertIn("Ёмкость", texts[0])
        self.assertEqual([result.leaf_slug for result in results], ["battery", "battery"])

    def test_catalog_covers_qualifying_parent_fixtures(self):
        from .category_rules import CATEGORY_RULES

        # Stable slugs from the initial catalog, independently of the rules.
        slugs = (
            "instrument-dlya-razmetki", "malyarnyy-instrument", "obshchestroitelnyy-instrument",
            "slesarno-stolyarnyy-instrument", "shtukaturno-otdelochnyy-instrument",
            "niveliry-lazernye-i-postroiteli-ploskostey", "ruletki-mernye-lenty", "urovni",
            "vozduhoduvki-i-opryskivateli-benzinovye", "gazonokosilki-motokosy-i-trimmery",
            "motonozhnitsy-elektronozhnitsy-kustorezy-vysotorezy", "benzopily-i-pily-tsepnye-elektricheskie",
            "perchatki", "sredstva-zashchity-golovyzreniyasluha", "sredstva-zashchity-organov-dyhaniya",
            "tachki-i-telezhki", "elektrostantsii", "akkumulyatornaya-tehnika", "derevoobrabotka",
            "metalloobrabotka", "obrabotka-betona", "obshchestroitelnyy-instrument-2109",
            "pilenie", "shlifovanie-i-polirovka",
        )
        root = Category.objects.create(name="Каталог", slug="root")
        for slug in slugs:
            parent = Category.objects.create(name=slug[:100], slug=slug, parent=root)
            Product.objects.bulk_create([Product(title="Fixture", price=1, category=parent) for _ in range(10)])
        qualifying = set(Category.objects.filter(parent__isnull=False, parent__parent__isnull=True).annotate(n=Count("product")).filter(n__gte=10).values_list("slug", flat=True))
        self.assertEqual(len(qualifying), 24)
        self.assertLessEqual(qualifying, CATEGORY_RULES.keys())
        for slug, rule in CATEGORY_RULES.items():
            with self.subTest(parent=slug):
                self.assertEqual(rule.parent_slug, slug)
                self.assertGreaterEqual(len(rule.leaves), 2)
                self.assertEqual(len({leaf.slug for leaf in rule.leaves}), len(rule.leaves))

    def test_catalog_machine_rules_exclude_consumables(self):
        from .category_rules import CATEGORY_RULES

        examples = (
            ("benzopily-i-pily-tsepnye-elektricheskie", "Масло для бензиновых пил"),
            ("benzopily-i-pily-tsepnye-elektricheskie", "Цепь для аккумуляторной пилы"),
            ("gazonokosilki-motokosy-i-trimmery", "Леска для триммеров"),
            ("pilenie", "Диск для дисковой пилы"),
            ("pilenie", "Чехол для сабельной пилы"),
            ("obrabotka-betona", "Запчасть для перфоратора"),
            ("gazonokosilki-motokosy-i-trimmery", "Нож для газонокосилки WORTEX CLM 4536-4"),
            ("gazonokosilki-motokosy-i-trimmery", "Насадка-кусторез без привода для триммера"),
            ("tachki-i-telezhki", "Шина для колеса тачки 3.25/3.00-8"),
            ("tachki-i-telezhki", "Ручки для тачки ECO 32мм"),
            ("tachki-i-telezhki", "Поворотные рукоятки для тачки WB-P123"),
        )
        for parent, text in examples:
            with self.subTest(text=text):
                self.assertEqual(classify_text(text, CATEGORY_RULES[parent]).status, "unmatched")

    def test_catalog_resolves_overlapping_specializations(self):
        from .category_rules import CATEGORY_RULES

        examples = (
            ("elektrostantsii", "Бензиновый инверторный генератор", "inverter"),
            ("urovni", "Уровень пузырьковый магнитный", "magnetic"),
            ("ruletki-mernye-lenty", "Рулетка геодезическая", "geodesic"),
            ("akkumulyatornaya-tehnika", "Аккумуляторная дрель-шуруповерт", "drills"),
            ("akkumulyatornaya-tehnika", "Аккумулятор для дрели-шуруповерта", "batteries-chargers"),
            ("pilenie", "Пила дисковая", "circular"),
        )
        for parent, text, expected in examples:
            with self.subTest(text=text):
                self.assertEqual(classify_text(text, CATEGORY_RULES[parent]).leaf_slug, expected)

    def test_catalog_overlapping_aliases_do_not_force_a_winner(self):
        from .category_rules import CATEGORY_RULES

        result = classify_text("Угловая полировальная машина", CATEGORY_RULES["shlifovanie-i-polirovka"])
        self.assertEqual(result.status, "ambiguous")
