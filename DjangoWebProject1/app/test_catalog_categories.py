from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .models import Category, Product


class CatalogCategoryQueryTests(TestCase):
    def setUp(self):
        self.root = Category.objects.create(name="Садовая техника", slug="garden")
        self.parent = Category.objects.create(
            name="Цепные пилы",
            slug="chainsaws",
            parent=self.root,
        )
        self.leaf = Category.objects.create(
            name="Бензиновые",
            slug="petrol",
            parent=self.parent,
        )
        self.product = Product.objects.create(
            title="Бензопила",
            price=100,
            category=self.leaf,
        )

    def test_root_and_parent_pages_include_leaf_products(self):
        for slug in (self.root.slug, self.parent.slug):
            with self.subTest(slug=slug):
                response = self.client.get(reverse("catalog_category", args=[slug]))
                self.assertContains(response, "Бензопила")

    def test_leaf_page_excludes_sibling_products(self):
        sibling = Category.objects.create(
            name="Электрические",
            slug="electric",
            parent=self.parent,
        )
        Product.objects.create(
            title="Электропила",
            price=100,
            category=sibling,
        )

        response = self.client.get(
            reverse("catalog_category", args=[self.leaf.slug])
        )

        self.assertContains(response, "Бензопила")
        self.assertNotContains(response, "Электропила")

    def test_context_includes_empty_child_tiles_for_nested_navigation(self):
        Category.objects.create(name="Пустая", slug="empty", parent=self.parent)

        response = self.client.get(
            reverse("catalog_category", args=[self.parent.slug])
        )

        empty = Category.objects.filter(parent=self.parent).exclude(pk=self.leaf.pk).first()
        self.assertEqual(
            list(response.context["current_category_children"]),
            [self.leaf, empty],
        )

    def test_parent_page_renders_empty_child_tiles_for_nested_navigation(self):
        empty = Category.objects.create(
            name="Пустая",
            slug="empty",
            parent=self.parent,
        )

        response = self.client.get(
            reverse("catalog_category", args=[self.parent.slug])
        )

        content = response.content.decode()
        self.assertIn('<div class="category-child-tiles"', content)
        tiles_start = content.index('<div class="category-child-tiles"')
        tiles_end = content.index("</div>", tiles_start)
        tiles = content[tiles_start:tiles_end]
        self.assertIn(self.leaf.name, tiles)
        self.assertIn(
            reverse("catalog_category", args=[self.leaf.slug]),
            tiles,
        )
        self.assertIn(empty.name, tiles)

    def test_leaf_page_breadcrumbs_contain_the_full_category_path(self):
        response = self.client.get(
            reverse("catalog_category", args=[self.leaf.slug])
        )

        content = response.content.decode()
        breadcrumb_start = content.index('<ol class="breadcrumb">')
        breadcrumb_end = content.index("</ol>", breadcrumb_start)
        breadcrumb = content[breadcrumb_start:breadcrumb_end]
        positions = [
            breadcrumb.index(category.name)
            for category in (self.root, self.parent, self.leaf)
        ]
        self.assertEqual(positions, sorted(positions))

    def test_nested_category_toggle_controls_its_associated_list(self):
        response = self.client.get(reverse("catalog"))

        control_id = f"nested-subcategories-{self.parent.pk}"
        self.assertContains(response, 'type="button"')
        self.assertContains(response, 'aria-expanded="false"')
        self.assertContains(response, f'aria-controls="{control_id}"')
        self.assertContains(response, f'id="{control_id}"')

    def test_catalog_precomputes_direct_child_and_grandchild_product_counts(self):
        Product.objects.create(title="Root product", price=10, category=self.root)
        Product.objects.create(title="Parent product", price=20, category=self.parent)

        response = self.client.get(
            reverse("catalog_category", args=[self.root.slug])
        )

        rendered_root = next(
            category
            for category in response.context["top_level_categories"]
            if category.pk == self.root.pk
        )
        rendered_parent = list(rendered_root.children.all())[0]
        rendered_leaf = list(rendered_parent.children.all())[0]
        self.assertEqual(
            (
                rendered_root.catalog_product_count,
                rendered_parent.catalog_product_count,
                rendered_leaf.catalog_product_count,
            ),
            (3, 2, 1),
        )
        self.assertContains(
            response, '<span class="sub-item-count">2</span>', html=True
        )
        self.assertContains(
            response,
            '<span class="nested-subcategory-count">1</span>',
            html=True,
        )
        self.assertContains(
            response,
            '<span class="category-child-tile-count">2</span>',
            html=True,
        )

    def test_catalog_query_count_does_not_grow_with_category_nodes(self):
        urls = (
            reverse("catalog"),
            reverse("catalog_category", args=[self.root.slug]),
        )
        baseline_query_counts = {}
        for url in urls:
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            baseline_query_counts[url] = len(queries)

        for index in range(6):
            root = Category.objects.create(
                name=f"Extra root {index}", slug=f"extra-root-{index}"
            )
            parent = Category.objects.create(
                name=f"Extra parent {index}",
                slug=f"extra-parent-{index}",
                parent=root,
            )
            Category.objects.create(
                name=f"Extra leaf {index}",
                slug=f"extra-leaf-{index}",
                parent=parent,
            )

        for url in urls:
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(queries), baseline_query_counts[url])
