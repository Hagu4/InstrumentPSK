from decimal import Decimal

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from .models import Category, Product


class CategoryAdminTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            "admin", "a@example.com", "pass"
        )
        self.client.force_login(self.user)
        self.root = Category.objects.create(name="Садовая техника", slug="garden")
        self.parent = Category.objects.create(
            name="Цепные пилы", slug="chainsaws", parent=self.root
        )
        self.leaf = Category.objects.create(
            name="Бензиновые", slug="petrol", parent=self.parent
        )
        self.other_root = Category.objects.create(
            name="Электроинструмент", slug="power-tools"
        )
        self.other_parent = Category.objects.create(
            name="Дрели", slug="drills", parent=self.other_root
        )
        self.other_leaf = Category.objects.create(
            name="Ударные", slug="impact", parent=self.other_parent
        )

    def test_changelist_shows_path_level_counts_and_add_child_link(self):
        response = self.client.get(reverse("admin:app_category_changelist"))

        self.assertContains(response, "Садовая техника → Цепные пилы")
        self.assertContains(response, "Добавить подподкатегорию")
        self.assertContains(response, "Уровень")

    def test_add_child_link_prefills_parent(self):
        response = self.client.get(
            reverse("admin:app_category_add"), {"parent": self.parent.pk}
        )

        self.assertContains(response, f'value="{self.parent.pk}" selected')

    def test_bulk_delete_action_is_disabled(self):
        model_admin = admin.site._registry[Category]
        request = RequestFactory().get("/admin/app/category/")
        request.user = self.user

        self.assertNotIn("delete_selected", model_admin.get_actions(request))

    def test_level_filter_returns_categories_at_each_requested_level(self):
        model_admin = admin.site._registry[Category]
        category_ids = {
            self.root.pk,
            self.parent.pk,
            self.leaf.pk,
            self.other_root.pk,
            self.other_parent.pk,
            self.other_leaf.pk,
        }
        expected_names = {
            "1": {"Садовая техника", "Электроинструмент"},
            "2": {"Цепные пилы", "Дрели"},
            "3": {"Бензиновые", "Ударные"},
        }

        for level, names in expected_names.items():
            with self.subTest(level=level):
                request = RequestFactory().get(
                    "/admin/app/category/", {"level": level}
                )
                level_filter = model_admin.list_filter[0](
                    request,
                    {"level": level},
                    Category,
                    model_admin,
                )
                self.assertSetEqual(
                    set(
                        level_filter.queryset(
                            request, Category.objects.filter(pk__in=category_ids)
                        ).values_list("name", flat=True)
                    ),
                    names,
                )

    def test_root_filter_returns_only_selected_three_level_branch(self):
        response = self.client.get(
            reverse("admin:app_category_changelist"), {"root": self.root.pk}
        )

        self.assertEqual(response.status_code, 200)
        self.assertSetEqual(
            set(response.context["cl"].queryset.values_list("name", flat=True)),
            {"Садовая техника", "Цепные пилы", "Бензиновые"},
        )

    def test_root_filter_lookups_are_root_categories(self):
        response = self.client.get(reverse("admin:app_category_changelist"))
        root_filter = next(
            (
                filter_spec
                for filter_spec in response.context["cl"].filter_specs
                if getattr(filter_spec, "parameter_name", None) == "root"
            ),
            None,
        )

        self.assertIsNotNone(root_filter)
        self.assertIn(
            (self.root.pk, "Садовая техника"), root_filter.lookup_choices
        )
        self.assertIn(
            (self.other_root.pk, "Электроинструмент"), root_filter.lookup_choices
        )
        self.assertNotIn(
            (self.parent.pk, "Цепные пилы"), root_filter.lookup_choices
        )

    def test_admin_product_counts_use_one_annotated_queryset(self):
        quantities = {
            self.root: 1,
            self.parent: 2,
            self.leaf: 3,
            self.other_root: 1,
            self.other_parent: 1,
            self.other_leaf: 1,
        }
        for category, quantity in quantities.items():
            for index in range(quantity):
                Product.objects.create(
                    title=f"{category.name} {index}",
                    price=Decimal("10.00"),
                    category=category,
                )
        model_admin = admin.site._registry[Category]
        request = RequestFactory().get("/admin/app/category/")
        request.user = self.user
        category_ids = [category.pk for category in quantities]

        with self.assertNumQueries(1):
            counts = {
                category.name: (
                    model_admin.own_product_count(category),
                    model_admin.branch_product_count(category),
                )
                for category in model_admin.get_queryset(request).filter(
                    pk__in=category_ids
                )
            }

        self.assertEqual(
            counts,
            {
                "Садовая техника": (1, 6),
                "Цепные пилы": (2, 5),
                "Бензиновые": (3, 3),
                "Электроинструмент": (1, 3),
                "Дрели": (1, 2),
                "Ударные": (1, 1),
            },
        )

    def test_third_level_category_has_no_add_child_link(self):
        model_admin = admin.site._registry[Category]

        self.assertEqual(model_admin.add_child_link(self.leaf), "")

    def assert_delete_is_refused(self, category):
        delete_url = reverse("admin:app_category_delete", args=[category.pk])

        for method in ("get", "post"):
            with self.subTest(method=method, category=category.slug):
                request = getattr(self.client, method)
                response = request(
                    delete_url,
                    {"post": "yes"} if method == "post" else None,
                    follow=True,
                )

                self.assertContains(response, "Нельзя удалить категорию")
                self.assertTrue(Category.objects.filter(pk=category.pk).exists())

    def test_single_delete_refuses_category_with_children_on_get_and_post(self):
        self.assert_delete_is_refused(self.parent)

    def test_single_delete_refuses_category_with_products_on_get_and_post(self):
        product = Product.objects.create(
            title="Protected product",
            price=Decimal("10.00"),
            category=self.other_leaf,
        )

        self.assert_delete_is_refused(self.other_leaf)
        product.refresh_from_db()
        self.assertEqual(product.category, self.other_leaf)

    def test_single_delete_still_allows_an_empty_leaf(self):
        empty_leaf = Category.objects.create(
            name="Empty leaf", slug="empty-leaf", parent=self.other_parent
        )
        delete_url = reverse("admin:app_category_delete", args=[empty_leaf.pk])

        response = self.client.get(delete_url)
        self.assertEqual(response.status_code, 200)

        response = self.client.post(delete_url, {"post": "yes"})
        self.assertRedirects(response, reverse("admin:app_category_changelist"))
        self.assertFalse(Category.objects.filter(pk=empty_leaf.pk).exists())
