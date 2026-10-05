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
            raise forms.ValidationError("Выберите хотя бы один товар")
        if len(raw_ids) > 100:
            raise forms.ValidationError("За один раз можно изменить не более 100 товаров")
        if len(raw_ids) != len(set(raw_ids)):
            raise forms.ValidationError("Товар выбран несколько раз")

        list_prices = self.data.getlist("new_price")
        changes = []
        for index, raw_id in enumerate(raw_ids):
            raw_price = (
                list_prices[index]
                if len(list_prices) == len(raw_ids)
                else self.data.get(f"price_{raw_id}", "")
            )
            try:
                changes.append(
                    ManualPriceChange(int(raw_id), Decimal(raw_price.replace(",", ".")))
                )
            except (InvalidOperation, TypeError, ValueError):
                raise forms.ValidationError("Для каждого товара укажите корректную цену")
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
