"""Deterministic, conservative matching shared by taxonomy preview and apply.

Terms match whole words (or consecutive words for phrases). Russian adjective
endings are interchangeable; an explicit trailing ``*`` matches a word prefix.
Nouns are otherwise exact, so ``диск`` cannot exclude ``дисковая``.
"""

from dataclasses import dataclass
from functools import lru_cache
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Product


@dataclass(frozen=True)
class LeafRule:
    slug: str
    name: str
    include_any: tuple[str, ...]
    include_all: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    priority: int = 0


@dataclass(frozen=True)
class ParentRule:
    parent_slug: str
    leaves: tuple[LeafRule, ...]


@dataclass(frozen=True)
class Classification:
    status: str
    leaf_slug: str | None
    matched_terms: tuple[str, ...]
    candidates: tuple[str, ...]


def normalize_text(value: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", value.lower().replace("ё", "е")).split())


# Only dictionary-form adjectives are expanded; noun endings stay literal.
_ADJECTIVE_ENDINGS = (
    "ый", "ий", "ой", "ая", "яя", "ое", "ее", "ые", "ие", "ого", "его",
    "ому", "ему", "ым", "им", "ом", "ем", "ую", "юю", "ых", "их", "ыми", "ими",
)


@lru_cache(maxsize=2048)
def _term_pattern(term: str) -> tuple[str, re.Pattern]:
    # Keep explicit prefix markers while applying the public normalization.
    normalized = " ".join(re.sub(r"[^\w*]+", " ", term.lower().replace("ё", "е")).split())
    parts = []
    for token in normalized.split():
        if token.endswith("*") and token[:-1].isalnum():
            parts.append(re.escape(token[:-1]) + r"\w*")
        elif len(token) > 4 and re.fullmatch(r"[а-я]+(?:ый|ий|ой)", token):
            parts.append(re.escape(token[:-2]) + "(?:" + "|".join(_ADJECTIVE_ENDINGS) + ")")
        else:
            parts.append(re.escape(token))
    pattern = r"(?<!\w)" + " ".join(parts) + r"(?!\w)" if parts else r"(?!)"
    return normalized, re.compile(pattern)


def _matched_terms(text: str, terms: tuple[str, ...]) -> set[str]:
    return {normalized for term in terms for normalized, pattern in (_term_pattern(term),)
            if normalized and pattern.search(text)}


def classify_text(text: str, parent_rule: ParentRule) -> Classification:
    normalized = normalize_text(text)
    ranked = []
    for leaf in parent_rule.leaves:
        any_matches = _matched_terms(normalized, leaf.include_any)
        if not any_matches or _matched_terms(normalized, leaf.exclude):
            continue
        all_matches = _matched_terms(normalized, leaf.include_all)
        required = {_term_pattern(term)[0] for term in leaf.include_all}
        if not required.issubset(all_matches):
            continue
        matched = any_matches | all_matches
        ranked.append((len(matched) + leaf.priority, leaf.slug, matched))
    if not ranked:
        return Classification("unmatched", None, (), ())
    ranked.sort(key=lambda entry: (-entry[0], entry[1]))
    winners = [entry for entry in ranked if entry[0] == ranked[0][0]]
    candidates = tuple(entry[1] for entry in ranked)
    matched_terms = tuple(sorted(set().union(*(entry[2] for entry in winners))))
    if len(winners) > 1:
        return Classification("ambiguous", None, matched_terms, candidates)
    return Classification("matched", winners[0][1], matched_terms, candidates)


def product_search_text(product: "Product") -> str:
    parts = [product.title or "", product.description or ""]
    # .all() preserves the caller's nested prefetch cache. Do not use
    # values_list/select_related here: they would re-query prefetched relations.
    for value in product.characteristics.all():
        parts.extend((value.characteristic.name, value.value))
    return " ".join(parts)


def classify_product(product: "Product", parent_rule: ParentRule) -> Classification:
    return classify_text(product_search_text(product), parent_rule)
