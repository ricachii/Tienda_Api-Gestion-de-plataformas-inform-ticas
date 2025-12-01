from decimal import Decimal, ROUND_HALF_UP
from typing import Union

NumberLike = Union[Decimal, float, int, str]


def quantize_money(val: NumberLike) -> Decimal:
    """Normaliza montos a 2 decimales usando HALF_UP, compatible con DECIMAL(12,2)."""
    if isinstance(val, Decimal):
        base = val
    else:
        base = Decimal(str(val))
    return base.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
