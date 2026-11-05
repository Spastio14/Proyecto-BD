from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def minimum_advance(total: Decimal) -> Decimal:
    return money(total * Decimal("0.50"))
