from django.core.exceptions import ValidationError
from django.test import TestCase
from decimal import Decimal

from .models import Category, Product


class CategoryTreeTests(TestCase):
    def setUp(self):
        self.root = Category.objects.create(name="Садовая техника", slug="garden")
        self.parent = Category.objects.create(
            name="Цепные пилы", slug="chainsaws", parent=self.root
        )
        self.leaf = Category.objects.create(
            name="Бензиновые", slug="petrol", parent=self.parent
        )

    def test_tree_properties_return_full_three_level_path(self):
        self.assertEqual(self.leaf.level, 3)
        self.assertEqual(
            self.leaf.full_path,
            "Садовая техника → Цепные пилы → Бензиновые",
        )
        self.assertEqual(
            self.root.descendant_ids(include_self=True),
            [self.root.id, self.parent.id, self.leaf.id],
        )

    def test_category_rejects_a_fourth_level(self):
        fourth = Category(
            name="Профессиональные", slug="professional", parent=self.leaf
        )
        with self.assertRaisesMessage(
            ValidationError, "не более трёх уровней"
        ):
            fourth.full_clean()

    def test_category_rejects_a_cycle(self):
        self.root.parent = self.leaf
        with self.assertRaisesMessage(ValidationError, "цикл"):
            self.root.full_clean()

    def test_saved_third_level_category_is_valid(self):
        self.leaf.full_clean()

    def test_category_rejects_reparenting_subtree_beyond_maximum_depth(self):
        other_root = Category.objects.create(name="Другой корень", slug="other")
        self.root.parent = other_root
        with self.assertRaisesMessage(ValidationError, "не более трёх уровней"):
            self.root.full_clean()

    def test_unsaved_self_parent_is_rejected_without_hanging(self):
        category = Category(name="Новая", slug="new")
        category.parent = category
        with self.assertRaisesMessage(ValidationError, "цикл"):
            category.full_clean()

    def test_total_product_count_includes_each_descendant_once(self):
        for index, category in enumerate((self.root, self.parent, self.leaf)):
            Product.objects.create(
                title=f"Товар {index}",
                price=Decimal("10.00"),
                category=category,
            )
        self.assertEqual(self.root.get_total_products_count(), 3)
        self.assertEqual(self.parent.get_total_products_count(), 2)
        self.assertEqual(self.leaf.get_total_products_count(), 1)
