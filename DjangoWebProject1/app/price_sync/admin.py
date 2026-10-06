from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Case, F, IntegerField, Q, Value, When
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.views.decorators.http import require_POST

from app.models import PriceImport, PriceImportRow, Product

from .forms import (
    ConfirmAnomaliesForm,
    ManualPriceBatchForm,
    PriceImportUploadForm,
    ResolvePriceImportRowForm,
)
from .parsing import PriceImportValidationError
from .services import (
    confirm_anomalies,
    create_manual_preview,
    create_preview,
    resolve_row,
    skip_row,
    skip_rows,
)


@admin.register(PriceImport)
class PriceImportAdmin(admin.ModelAdmin):
    change_list_template = "admin/app/priceimport/change_list.html"
    list_display = (
        "preview_link",
        "source_type",
        "status",
        "original_name",
        "total_rows",
        "matched_rows",
        "review_rows",
        "uploaded_by",
        "created_at",
        "applied_at",
    )
    list_filter = ("source_type", "status", "created_at")
    search_fields = ("original_name", "file_sha256", "uploaded_by__username")
    readonly_fields = tuple(field.name for field in PriceImport._meta.fields)
    actions = None
    list_display_links = None

    @admin.display(description="ID", ordering="id")
    def preview_link(self, obj):
        url = reverse("admin:app_priceimport_preview", args=[obj.pk])
        return format_html('<a href="{}">{}</a>', url, obj.pk)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        return HttpResponseRedirect(
            reverse("admin:app_priceimport_preview", args=[object_id])
        )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        custom = [
            path("upload/", self.admin_site.admin_view(self.upload_view), name="app_priceimport_upload"),
            path("manual/", self.admin_site.admin_view(self.manual_view), name="app_priceimport_manual"),
            path("<int:pk>/preview/", self.admin_site.admin_view(self.preview_view), name="app_priceimport_preview"),
            path("<int:pk>/resolve/<int:row_id>/", self.admin_site.admin_view(require_POST(self.resolve_view)), name="app_priceimport_resolve"),
            path("<int:pk>/skip/<int:row_id>/", self.admin_site.admin_view(require_POST(self.skip_view)), name="app_priceimport_skip"),
            path("<int:pk>/skip-selected/", self.admin_site.admin_view(require_POST(self.skip_selected_view)), name="app_priceimport_skip_selected"),
            path("<int:pk>/confirm-anomalies/", self.admin_site.admin_view(require_POST(self.confirm_anomalies_view)), name="app_priceimport_confirm_anomalies"),
            path("<int:pk>/apply/", self.admin_site.admin_view(require_POST(self.apply_view)), name="app_priceimport_apply"),
            path("<int:pk>/rollback/", self.admin_site.admin_view(require_POST(self.rollback_view)), name="app_priceimport_rollback"),
        ]
        return custom + super().get_urls()

    def _require(self, request, permission):
        if not request.user.has_perm(permission):
            raise PermissionDenied

    def _context(self, request, **extra):
        return {**self.admin_site.each_context(request), **extra}

    @staticmethod
    def _is_ajax(request):
        return request.headers.get("x-requested-with") == "XMLHttpRequest"

    @staticmethod
    def _summary(price_import):
        price_import.refresh_from_db()
        return {
            "total": price_import.total_rows,
            "matched": price_import.matched_rows,
            "review": price_import.review_rows,
            "skipped": price_import.skipped_rows,
            "changed": price_import.changed_rows,
            "anomalies": price_import.anomaly_rows,
        }

    def upload_view(self, request):
        self._require(request, "app.preview_priceimport")
        form = PriceImportUploadForm(request.POST or None, request.FILES or None)
        if request.method == "POST" and form.is_valid():
            try:
                price_import, created = create_preview(form.cleaned_data["source_file"], request.user)
            except PriceImportValidationError as error:
                form.add_error("source_file", error.message)
            else:
                if not created:
                    messages.info(request, "Этот файл уже загружался — открыта существующая операция.")
                return HttpResponseRedirect(reverse("admin:app_priceimport_preview", args=[price_import.pk]))
        return TemplateResponse(
            request,
            "admin/app/priceimport/upload.html",
            self._context(request, title="Загрузить прайс поставщика", form=form),
        )

    def manual_view(self, request):
        self._require(request, "app.create_manual_priceimport")
        query = (request.GET.get("q") or request.POST.get("q") or "").strip()
        page_number = request.GET.get("page") or request.POST.get("page")
        products = Product.objects.select_related("brand").order_by("title", "pk")
        if query:
            products = products.filter(
                Q(title__icontains=query)
                | Q(sku__icontains=query)
                | Q(brand__name__icontains=query)
            )
        products = Paginator(products, 100).get_page(page_number)
        form = ManualPriceBatchForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            try:
                price_import = create_manual_preview(form.cleaned_data["changes"], request.user)
            except PriceImportValidationError as error:
                form.add_error(None, error.message)
            else:
                return HttpResponseRedirect(reverse("admin:app_priceimport_preview", args=[price_import.pk]))
        return TemplateResponse(
            request,
            "admin/app/priceimport/manual.html",
            self._context(
                request,
                title="Изменить цены вручную",
                form=form,
                products=products,
                query=query,
            ),
        )

    def preview_view(self, request, pk):
        self._require(request, "app.view_priceimport")
        price_import = get_object_or_404(PriceImport, pk=pk)
        rows = price_import.rows.select_related("product", "product__brand")
        state = request.GET.get("state")
        attention_filter = Q(
            status__in=(
                PriceImportRow.Status.NEEDS_REVIEW,
                PriceImportRow.Status.INVALID,
            )
        ) | Q(
            status=PriceImportRow.Status.MATCHED,
            diagnostic_code="large_change",
        )
        if state:
            rows = rows.filter(status=state)
        else:
            changed_filter = Q(status=PriceImportRow.Status.MATCHED) & ~Q(
                before_price=F("after_price")
            )
            rows = rows.filter(attention_filter | changed_filter).annotate(
                attention_order=Case(
                    When(attention_filter, then=Value(0)),
                    default=Value(1),
                    output_field=IntegerField(),
                )
            ).order_by("attention_order", "row_number", "pk")
        query = request.GET.get("q", "").strip()
        if query:
            rows = rows.filter(
                Q(source_sku__icontains=query)
                | Q(source_title__icontains=query)
                | Q(source_brand__icontains=query)
                | Q(product__title__icontains=query)
            )
        attention_count = rows.filter(attention_filter).count() if not state else 0
        page = Paginator(rows, 100).get_page(request.GET.get("page"))
        candidate_ids = {
            product_id
            for row in page.object_list
            for product_id in (row.candidate_product_ids or [])
        }
        candidate_products = {
            product.pk: product
            for product in Product.objects.select_related("brand").filter(
                pk__in=candidate_ids
            )
        }
        for row in page.object_list:
            row.candidate_products = [
                candidate_products[product_id]
                for product_id in (row.candidate_product_ids or [])
                if product_id in candidate_products
            ]
        if not state and page.object_list:
            first_position = page.start_index()
            for offset, row in enumerate(page.object_list):
                position = first_position + offset
                row.requires_attention = (
                    row.status
                    in (
                        PriceImportRow.Status.NEEDS_REVIEW,
                        PriceImportRow.Status.INVALID,
                    )
                    or (
                        row.status == PriceImportRow.Status.MATCHED
                        and row.diagnostic_code == "large_change"
                    )
                )
                row.starts_attention_section = (
                    offset == 0 and row.requires_attention
                )
                row.starts_regular_section = (
                    (offset == 0 and not row.requires_attention)
                    or position == attention_count + 1
                )
        pagination_query = request.GET.copy()
        pagination_query.pop("page", None)
        latest_success = PriceImport.objects.filter(applied_at__isnull=False).order_by("-applied_at", "-pk").first()
        return TemplateResponse(
            request,
            "admin/app/priceimport/preview.html",
            self._context(
                request,
                title="Предварительный просмотр",
                price_import=price_import,
                page=page,
                pagination_query=pagination_query.urlencode(),
                latest_success=latest_success,
                resolve_form=ResolvePriceImportRowForm(),
            ),
        )

    def resolve_view(self, request, pk, row_id):
        self._require(request, "app.resolve_priceimport")
        row = get_object_or_404(PriceImportRow, pk=row_id, price_import_id=pk)
        form = ResolvePriceImportRowForm(request.POST)
        if form.is_valid():
            try:
                resolve_row(row, form.cleaned_data["product"], request.user)
            except PriceImportValidationError as error:
                messages.error(request, error.message)
            else:
                messages.success(request, "Соответствие сохранено.")
        else:
            messages.error(request, "Выберите существующий товар.")
        return HttpResponseRedirect(reverse("admin:app_priceimport_preview", args=[pk]))

    def skip_view(self, request, pk, row_id):
        self._require(request, "app.resolve_priceimport")
        row = get_object_or_404(PriceImportRow, pk=row_id, price_import_id=pk)
        try:
            skip_row(row, request.user)
        except PriceImportValidationError as error:
            if self._is_ajax(request):
                return JsonResponse({"error": error.message}, status=409)
            messages.error(request, error.message)
        else:
            if self._is_ajax(request):
                return JsonResponse(
                    {
                        "removed_ids": [row.pk],
                        "summary": self._summary(row.price_import),
                        "status": row.price_import.status,
                        "status_display": row.price_import.get_status_display(),
                    }
                )
            messages.success(request, "Строка пропущена.")
        return HttpResponseRedirect(reverse("admin:app_priceimport_preview", args=[pk]))

    def skip_selected_view(self, request, pk):
        self._require(request, "app.resolve_priceimport")
        price_import = get_object_or_404(PriceImport, pk=pk)
        raw_ids = request.POST.getlist("row_ids")
        try:
            row_ids = list(dict.fromkeys(int(row_id) for row_id in raw_ids))
        except (TypeError, ValueError):
            error = PriceImportValidationError(
                "invalid_row_ids", "Получен неверный список товаров"
            )
        else:
            if len(row_ids) > 100:
                error = PriceImportValidationError(
                    "too_many_rows", "За один раз можно убрать не более 100 товаров"
                )
            else:
                try:
                    removed_rows = skip_rows(price_import.pk, row_ids, request.user)
                except PriceImportValidationError as caught_error:
                    error = caught_error
                else:
                    payload = {
                        "removed_ids": [row.pk for row in removed_rows],
                        "summary": self._summary(price_import),
                        "status": price_import.status,
                        "status_display": price_import.get_status_display(),
                    }
                    if self._is_ajax(request):
                        return JsonResponse(payload)
                    messages.success(
                        request, f"Убрано из обновления: {len(removed_rows)}."
                    )
                    return HttpResponseRedirect(
                        reverse("admin:app_priceimport_preview", args=[pk])
                    )

        if self._is_ajax(request):
            return JsonResponse({"error": error.message}, status=400)
        messages.error(request, error.message)
        return HttpResponseRedirect(reverse("admin:app_priceimport_preview", args=[pk]))

    def confirm_anomalies_view(self, request, pk):
        self._require(request, "app.resolve_priceimport")
        price_import = get_object_or_404(PriceImport, pk=pk)
        form = ConfirmAnomaliesForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Подтвердите подозрительные изменения.")
        else:
            try:
                confirm_anomalies(price_import.pk, form.cleaned_data["row_ids"])
            except PriceImportValidationError as error:
                messages.error(request, error.message)
            else:
                messages.success(request, "Подозрительные изменения подтверждены.")
        return HttpResponseRedirect(reverse("admin:app_priceimport_preview", args=[pk]))

    def apply_view(self, request, pk):
        self._require(request, "app.apply_priceimport")
        from .services import apply_import

        try:
            apply_import(pk, request.user)
        except PriceImportValidationError as error:
            messages.error(request, error.message)
        else:
            messages.success(request, "Цены обновлены.")
        return HttpResponseRedirect(reverse("admin:app_priceimport_preview", args=[pk]))

    def rollback_view(self, request, pk):
        self._require(request, "app.rollback_priceimport")
        from .services import rollback_import

        try:
            rollback_import(pk, request.user)
        except PriceImportValidationError as error:
            messages.error(request, error.message)
        else:
            messages.success(request, "Последнее обновление цен отменено.")
        return HttpResponseRedirect(reverse("admin:app_priceimport_preview", args=[pk]))
