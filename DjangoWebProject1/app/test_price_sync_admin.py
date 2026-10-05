from decimal import Decimal

from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from app.models import PriceImport, PriceImportRow, Product


class PriceSyncAdminTests(TestCase):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser(
            username="price-admin",
            email="admin@example.com",
            password="test-password-123",
        )
        self.staff_without_permissions = get_user_model().objects.create_user(
            username="staff",
            password="test-password-123",
            is_staff=True,
        )
        self.product = Product.objects.create(
            title="Товар для ручной цены",
            sku="ADMIN-PRICE-1",
            price=Decimal("1000.00"),
        )
        self.history_url = reverse("admin:app_priceimport_changelist")
        self.upload_url = reverse("admin:app_priceimport_upload")
        self.manual_url = reverse("admin:app_priceimport_manual")

    def test_price_import_has_a_visible_sidebar_position_and_icon(self):
        self.assertIn("app.PriceImport", settings.JAZZMIN_SETTINGS["order_with_respect_to"])
        self.assertEqual(
            settings.JAZZMIN_SETTINGS["icons"]["app.PriceImport"],
            "fas fa-ruble-sign",
        )

    def test_price_import_history_uses_russian_column_and_filter_labels(self):
        price_import = PriceImport.objects.create(
            source_type=PriceImport.SourceType.SUPPLIER_XLSX,
            original_name="prices.xlsx",
            uploaded_by=self.superuser,
        )
        self.client.force_login(self.superuser)

        response = self.client.get(self.history_url)

        for label in (
            "Тип источника",
            "Состояние",
            "Имя файла",
            "Всего строк",
            "Сопоставлено",
            "Требуют проверки",
            "Загрузил",
            "Дата создания",
            "Дата применения",
        ):
            self.assertContains(response, label)
        self.assertContains(
            response,
            reverse("admin:app_priceimport_preview", args=[price_import.pk]),
        )

    def test_default_change_url_redirects_to_private_import_preview(self):
        price_import = PriceImport.objects.create(
            source_type=PriceImport.SourceType.SUPPLIER_XLSX,
            source_file="2026/10/private.xlsx",
            original_name="prices.xlsx",
            uploaded_by=self.superuser,
        )
        self.client.force_login(self.superuser)

        response = self.client.get(
            reverse("admin:app_priceimport_change", args=[price_import.pk])
        )

        self.assertRedirects(
            response,
            reverse("admin:app_priceimport_preview", args=[price_import.pk]),
            fetch_redirect_response=False,
        )

    def test_preview_hides_automatically_skipped_supplier_rows_by_default(self):
        price_import = PriceImport.objects.create(
            source_type=PriceImport.SourceType.SUPPLIER_XLSX,
            uploaded_by=self.superuser,
        )
        PriceImportRow.objects.create(
            price_import=price_import,
            row_number=2,
            source_title="Отсутствующий в каталоге товар",
            source_price=Decimal("120.00"),
            status=PriceImportRow.Status.SKIPPED,
            diagnostic_code="not_in_catalog",
        )
        self.client.force_login(self.superuser)
        preview_url = reverse("admin:app_priceimport_preview", args=[price_import.pk])

        response = self.client.get(preview_url)
        skipped_response = self.client.get(preview_url, {"state": "skipped"})

        self.assertNotContains(response, "Отсутствующий в каталоге товар")
        self.assertContains(skipped_response, "Отсутствующий в каталоге товар")

    def test_public_and_staff_without_permission_cannot_view_imports(self):
        self.assertEqual(self.client.get(self.history_url).status_code, 302)
        self.client.force_login(self.staff_without_permissions)
        self.assertNotEqual(self.client.get(self.history_url).status_code, 200)

    def test_get_cannot_apply_or_rollback(self):
        import_obj = PriceImport.objects.create(
            source_type=PriceImport.SourceType.MANUAL,
            uploaded_by=self.superuser,
        )
        self.client.force_login(self.superuser)
        apply_url = reverse("admin:app_priceimport_apply", args=[import_obj.pk])
        rollback_url = reverse("admin:app_priceimport_rollback", args=[import_obj.pk])

        self.assertEqual(self.client.get(apply_url).status_code, 405)
        self.assertEqual(self.client.get(rollback_url).status_code, 405)

    def test_upload_rejects_non_xlsx(self):
        self.client.force_login(self.superuser)

        response = self.client.post(
            self.upload_url,
            {"source_file": SimpleUploadedFile("prices.csv", b"x")},
        )

        self.assertContains(response, "Только файлы XLSX", status_code=200)

    def test_manual_page_lists_products_without_requiring_search_or_checkboxes(self):
        self.client.force_login(self.superuser)

        response = self.client.get(self.manual_url)

        self.assertContains(response, self.product.title)
        self.assertContains(response, f'name="price_{self.product.pk}"')
        self.assertNotContains(response, 'type="checkbox"')
        self.assertContains(response, "Сохранить изменения")

    def test_manual_page_searches_products_and_creates_preview_only_for_changed_prices(self):
        unchanged = Product.objects.create(
            title="Товар с неизменной ценой",
            sku="ADMIN-PRICE-2",
            price=Decimal("700.00"),
        )
        self.client.force_login(self.superuser)
        response = self.client.get(self.manual_url, {"q": self.product.sku})
        self.assertContains(response, self.product.title)

        response = self.client.post(
            self.manual_url,
            {
                "product_id": [str(self.product.pk), str(unchanged.pk)],
                f"price_{self.product.pk}": "1250.00",
                f"price_{unchanged.pk}": "700.00",
            },
            follow=True,
        )

        self.assertContains(response, "Предварительный просмотр")
        price_import = PriceImport.objects.latest("pk")
        self.assertEqual(price_import.rows.count(), 1)
        self.assertEqual(price_import.rows.get().product, self.product)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal("1000.00"))

    def test_manual_page_rejects_submission_when_no_price_changed(self):
        self.client.force_login(self.superuser)

        response = self.client.post(
            self.manual_url,
            {
                "product_id": [str(self.product.pk)],
                f"price_{self.product.pk}": "1000.00",
            },
        )

        self.assertContains(response, "Измените цену хотя бы у одного товара")
        self.assertFalse(PriceImport.objects.exists())

    def test_manual_page_paginates_products_by_one_hundred(self):
        Product.objects.bulk_create(
            [
                Product(
                    title=f"Товар {index:03d}",
                    sku=f"PAGE-{index:03d}",
                    price=Decimal("100.00"),
                )
                for index in range(101)
            ]
        )
        self.client.force_login(self.superuser)

        first_page = self.client.get(self.manual_url)
        second_page = self.client.get(self.manual_url, {"page": 2})

        self.assertEqual(len(first_page.context["products"]), 100)
        self.assertEqual(len(second_page.context["products"]), 2)
        self.assertContains(first_page, "Следующая")

    def test_applied_import_rows_cannot_be_resolved(self):
        import_obj = PriceImport.objects.create(
            source_type=PriceImport.SourceType.SUPPLIER_XLSX,
            status=PriceImport.Status.APPLIED,
            uploaded_by=self.superuser,
        )
        row = PriceImportRow.objects.create(
            price_import=import_obj,
            row_number=2,
            source_title="Неизвестный товар",
            source_price=Decimal("120.00"),
            status=PriceImportRow.Status.NEEDS_REVIEW,
        )
        self.client.force_login(self.superuser)

        self.client.post(
            reverse(
                "admin:app_priceimport_resolve", args=[import_obj.pk, row.pk]
            ),
            {"product": self.product.pk},
        )

        row.refresh_from_db()
        import_obj.refresh_from_db()
        self.assertIsNone(row.product_id)
        self.assertEqual(import_obj.status, PriceImport.Status.APPLIED)

    def test_preview_offers_candidate_resolution_and_manual_product_id(self):
        candidate = Product.objects.create(
            title="Подходящий кандидат",
            sku="CANDIDATE-1",
            price=Decimal("900.00"),
        )
        import_obj = PriceImport.objects.create(
            source_type=PriceImport.SourceType.SUPPLIER_XLSX,
            status=PriceImport.Status.DRAFT,
            uploaded_by=self.superuser,
        )
        PriceImportRow.objects.create(
            price_import=import_obj,
            row_number=2,
            source_title="Кандидат поставщика",
            source_price=Decimal("950.00"),
            candidate_product_ids=[candidate.pk],
            status=PriceImportRow.Status.NEEDS_REVIEW,
        )
        PriceImportRow.objects.create(
            price_import=import_obj,
            row_number=3,
            source_title="Без кандидатов",
            source_price=Decimal("750.00"),
            status=PriceImportRow.Status.NEEDS_REVIEW,
        )
        self.client.force_login(self.superuser)

        response = self.client.get(
            reverse("admin:app_priceimport_preview", args=[import_obj.pk])
        )

        self.assertContains(response, candidate.title)
        self.assertContains(response, 'name="product"')
        self.assertContains(response, 'type="number"')
        self.assertContains(response, "Сопоставить")

    def test_applied_import_anomalies_cannot_be_changed(self):
        import_obj = PriceImport.objects.create(
            source_type=PriceImport.SourceType.MANUAL,
            status=PriceImport.Status.APPLIED,
            uploaded_by=self.superuser,
        )
        row = PriceImportRow.objects.create(
            price_import=import_obj,
            row_number=1,
            source_title=self.product.title,
            source_price=Decimal("2000.00"),
            product=self.product,
            status=PriceImportRow.Status.MATCHED,
            diagnostic_code="large_change",
            anomaly_confirmed=False,
        )
        self.client.force_login(self.superuser)

        self.client.post(
            reverse(
                "admin:app_priceimport_confirm_anomalies", args=[import_obj.pk]
            ),
            {"confirmed": "on", "row_ids": str(row.pk)},
        )

        row.refresh_from_db()
        self.assertFalse(row.anomaly_confirmed)

    def test_price_timestamp_is_present_in_admin_but_absent_from_public_page(self):
        self.client.force_login(self.superuser)
        self.assertContains(
            self.client.get(reverse("admin:app_product_changelist")),
            "Цена обновлена",
        )
        self.client.logout()

        response = self.client.get(self.product.get_absolute_url())
        self.assertNotContains(response, "Цена обновлена")
