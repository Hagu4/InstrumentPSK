import secrets
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP

from django.core.exceptions import ValidationError


MIN_DISCOUNT = 10
MAX_DISCOUNT = 30
MAX_PRODUCT_PRICE = Decimal("99999999.99")
MONEY_QUANTUM = Decimal("0.01")


def validate_price(value) -> Decimal:
    try:
        price = Decimal(str(value)).quantize(MONEY_QUANTUM)
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("Цена должна быть числом")
    if not price.is_finite() or price <= 0:
        raise ValidationError("Цена должна быть больше нуля")
    if price > MAX_PRODUCT_PRICE:
        raise ValidationError("Цена превышает допустимое значение")
    return price


def choose_discount(existing_discount, price, old_price) -> int:
    price = validate_price(price)
    if existing_discount is not None and MIN_DISCOUNT <= int(existing_discount) <= MAX_DISCOUNT:
        return int(existing_discount)
    if old_price is not None:
        old_price = Decimal(str(old_price))
        if old_price > price:
            derived = int(
                ((Decimal("1") - price / old_price) * 100).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                )
            )
            if MIN_DISCOUNT <= derived <= MAX_DISCOUNT:
                return derived
    return MIN_DISCOUNT + secrets.randbelow(MAX_DISCOUNT - MIN_DISCOUNT + 1)


def calculate_old_price(price: Decimal, percent: int) -> Decimal:
    price = validate_price(price)
    if not MIN_DISCOUNT <= int(percent) <= MAX_DISCOUNT:
        raise ValidationError("Скидка должна быть от 10 до 30 процентов")
    gross = price / (Decimal("1") - Decimal(percent) / Decimal("100"))
    rounded = (gross / Decimal("10")).to_integral_value(rounding=ROUND_CEILING) * 10
    return validate_price(rounded)


def is_large_change(before: Decimal, after: Decimal) -> bool:
    before = validate_price(before)
    after = validate_price(after)
    return abs(after - before) / before > Decimal("0.50")
