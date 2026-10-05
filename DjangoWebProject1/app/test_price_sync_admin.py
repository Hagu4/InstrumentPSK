from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from app.models import PriceImport, Product


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

    def test_manual_page_searches_products_and_creates_preview(self):
        self.client.force_login(self.superuser)
        response = self.client.get(self.manual_url, {"q": self.product.sku})
        self.assertContains(response, self.product.title)

        response = self.client.post(
            self.manual_url,
            {"product_id": [str(self.product.pk)], "new_price": ["1250.00"]},
            follow=True,
        )

        self.assertContains(response, "Предварительный просмотр")
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal("1000.00"))

    def test_price_timestamp_is_present_in_admin_but_absent_from_public_page(self):
        self.client.force_login(self.superuser)
        self.assertContains(
            self.client.get(reverse("admin:app_product_changelist")),
            "Цена обновлена",
        )
        self.client.logout()

        response = self.client.get(self.product.get_absolute_url())
        self.assertNotContains(response, "Цена обновлена")
