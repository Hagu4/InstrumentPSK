from decimal import Decimal, InvalidOperation
from pathlib import Path

from django import forms
from django.conf import settings

from app.models import Product

from .services import ManualPriceChange


class PriceImportUploadForm(forms.Form):
    source_file = forms.FileField(label="Файл XLSX")

    def clean_source_file(self):
        source_file = self.cleaned_data["source_file"]
        if Path(source_file.name).suffix.casefold() != ".xlsx":
            raise forms.ValidationError("Только файлы XLSX")
        if source_file.size > settings.PRICE_IMPORT_MAX_BYTES:
            raise forms.ValidationError("Файл превышает допустимый размер")
        return source_file


class ManualPriceBatchForm(forms.Form):
    def clean(self):
        cleaned = super().clean()
        raw_ids = self.data.getlist("product_id")
        if not raw_ids:
            raise forms.ValidationError("На странице нет товаров для изменения")
        if len(raw_ids) > 100:
            raise forms.ValidationError("За один раз можно изменить не более 100 товаров")

        try:
            product_ids = [int(raw_id) for raw_id in raw_ids]
        except (TypeError, ValueError):
            raise forms.ValidationError("Некорректный список товаров")
        if len(product_ids) != len(set(product_ids)):
            raise forms.ValidationError("Товар указан несколько раз")

        current_prices = dict(
            Product.objects.filter(pk__in=product_ids).values_list("pk", "price")
        )
        if len(current_prices) != len(product_ids):
            raise forms.ValidationError("Один из товаров больше не существует")

        changes = []
        for product_id in product_ids:
            raw_price = self.data.get(f"price_{product_id}", "")
            try:
                new_price = Decimal(raw_price.replace(",", "."))
            except (AttributeError, InvalidOperation, TypeError, ValueError):
                raise forms.ValidationError("Для каждого товара укажите корректную цену")
            if new_price != current_prices[product_id]:
                changes.append(ManualPriceChange(product_id, new_price))

        if not changes:
            raise forms.ValidationError("Измените цену хотя бы у одного товара")
        cleaned["changes"] = changes
        return cleaned


class ResolvePriceImportRowForm(forms.Form):
    product = forms.ModelChoiceField(
        queryset=Product.objects.select_related("brand").order_by("title"),
        label="Товар",
    )


class ConfirmAnomaliesForm(forms.Form):
    confirmed = forms.BooleanField(label="Подтверждаю изменения более чем на 50%")
    row_ids = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean_row_ids(self):
        value = self.cleaned_data.get("row_ids", "")
        try:
            return [int(item) for item in value.split(",") if item.strip()]
        except ValueError:
            raise forms.ValidationError("Некорректный список строк")
