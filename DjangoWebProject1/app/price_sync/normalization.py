import re
import unicodedata


_UNIT_ALIASES = {
    "в": "v",
    "v": "v",
    "а ч": "ah",
    "ач": "ah",
    "ah": "ah",
    "вт": "w",
    "w": "w",
    "квт": "kw",
    "kw": "kw",
    "мм": "mm",
    "mm": "mm",
    "см": "cm",
    "cm": "cm",
    "м": "m",
    "m": "m",
    "кг": "kg",
    "kg": "kg",
    "л": "l",
    "l": "l",
}
_NUMBER_WITH_UNIT = re.compile(
    r"(?<!\w)(\d+(?:[.,]\d+)?)\s*(квт|kw|вт|w|а\s*ч|ач|ah|мм|mm|см|cm|кг|kg|в|v|м|m|л|l)(?!\w)",
    re.IGNORECASE,
)


def normalize_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = text.replace("ё", "е").replace("_", " ")
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())[:500]


def normalize_brand(value: object) -> str:
    brand = normalize_text(value)[:200]
    if brand in {"", "нет бренда", "без бренда", "no brand", "none", "n a"}:
        return ""
    return brand


def normalize_sku(value: object) -> str:
    return re.sub(r"[\s\-_./]+", "", normalize_text(value)).upper()[:100]


def extract_numeric_signature(value: object) -> tuple[str, ...]:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = text.replace("ё", "е").replace("·", " ")
    found = []
    for number, raw_unit in _NUMBER_WITH_UNIT.findall(text):
        number = number.replace(",", ".")
        unit = re.sub(r"\s+", " ", raw_unit)
        token = f"{number}{_UNIT_ALIASES[unit]}"
        if token not in found:
            found.append(token)
    return tuple(found)


def extract_model_tokens(value: object) -> tuple[str, ...]:
    tokens = normalize_text(value).split()
    result = {
        token
        for token in tokens
        if any(char.isdigit() for char in token)
        or (token.isascii() and token.isalpha() and 2 <= len(token) <= 4)
    }
    return tuple(sorted(result))
