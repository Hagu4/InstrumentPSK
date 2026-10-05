from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher

from .normalization import (
    extract_model_tokens,
    extract_numeric_signature,
    normalize_brand,
    normalize_sku,
    normalize_text,
)


@dataclass(frozen=True)
class CatalogEntry:
    product_id: int
    sku: str
    brand: str
    title: str
    model_tokens: tuple[str, ...]
    numeric_signature: tuple[str, ...]


@dataclass(frozen=True)
class MatchDecision:
    product_id: int | None
    method: str
    candidate_ids: tuple[int, ...] = ()
    diagnostic_code: str = ""


class CatalogIndex:
    def __init__(self):
        self.entries: dict[int, CatalogEntry] = {}
        self.saved_sku: dict[str, list[int]] = defaultdict(list)
        self.saved_identity: dict[tuple, list[int]] = defaultdict(list)
        self.by_sku: dict[str, list[int]] = defaultdict(list)
        self.by_title: dict[tuple[str, str], list[int]] = defaultdict(list)
        self.by_model: dict[tuple, list[int]] = defaultdict(list)

    @classmethod
    def from_queryset(cls, queryset, links):
        index = cls()
        for product in queryset:
            brand = normalize_brand(product.brand.name if product.brand else "")
            title = normalize_text(product.title)
            entry = CatalogEntry(
                product_id=product.pk,
                sku=normalize_sku(product.sku),
                brand=brand,
                title=title,
                model_tokens=extract_model_tokens(product.title),
                numeric_signature=extract_numeric_signature(product.title),
            )
            index.entries[product.pk] = entry
            if entry.sku:
                index.by_sku[entry.sku].append(product.pk)
            index.by_title[(entry.brand, entry.title)].append(product.pk)
            if entry.model_tokens or entry.numeric_signature:
                index.by_model[
                    (entry.brand, entry.model_tokens, entry.numeric_signature)
                ].append(product.pk)

        for link in links:
            sku = normalize_sku(link.source_sku)
            if sku:
                index.saved_sku[sku].append(link.product_id)
            identity = (
                normalize_brand(link.normalized_brand),
                normalize_text(link.normalized_title),
                tuple(link.numeric_signature or ()),
            )
            if identity[0] and identity[1]:
                index.saved_identity[identity].append(link.product_id)
        return index


def _unique_match(
    product_ids,
    method: str,
    claimed_product_ids: set[int],
) -> MatchDecision | None:
    unique_ids = tuple(dict.fromkeys(product_ids))
    if len(unique_ids) != 1:
        return None
    product_id = unique_ids[0]
    if product_id in claimed_product_ids:
        return MatchDecision(
            None,
            "needs_review",
            (product_id,),
            "product_already_matched",
        )
    return MatchDecision(product_id, method)


def match_row(row, index: CatalogIndex, claimed_product_ids=None) -> MatchDecision:
    claimed_product_ids = set(claimed_product_ids or ())
    sku = normalize_sku(row.sku)
    brand = normalize_brand(row.brand)
    title = normalize_text(row.title)
    model_tokens = extract_model_tokens(row.title)
    numeric_signature = extract_numeric_signature(row.title)

    if sku:
        decision = _unique_match(index.saved_sku.get(sku, ()), "saved_link", claimed_product_ids)
        if decision:
            return decision

    saved_key = (brand, title, numeric_signature)
    decision = _unique_match(
        index.saved_identity.get(saved_key, ()), "saved_link", claimed_product_ids
    )
    if decision:
        return decision

    if sku:
        decision = _unique_match(index.by_sku.get(sku, ()), "exact_sku", claimed_product_ids)
        if decision:
            return decision

    decision = _unique_match(
        index.by_title.get((brand, title), ()), "exact_title", claimed_product_ids
    )
    if decision:
        return decision

    model_key = (brand, model_tokens, numeric_signature)
    if model_tokens or numeric_signature:
        decision = _unique_match(
            index.by_model.get(model_key, ()), "exact_model", claimed_product_ids
        )
        if decision:
            return decision

    ranked = []
    for entry in index.entries.values():
        if entry.brand != brand:
            continue
        if numeric_signature and entry.numeric_signature != numeric_signature:
            continue
        ratio = SequenceMatcher(None, title, entry.title).ratio()
        if ratio >= 0.45:
            ranked.append((ratio, entry.product_id))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    candidates = tuple(
        product_id
        for _, product_id in ranked[:5]
        if product_id not in claimed_product_ids
    )
    return MatchDecision(
        None,
        "needs_review",
        candidates,
        "ambiguous_or_unmatched",
    )
