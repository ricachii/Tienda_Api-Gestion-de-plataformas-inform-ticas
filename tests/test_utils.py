from decimal import Decimal

from app.backend.utils import quantize_money


def test_quantize_money_accepts_various_inputs():
    assert quantize_money(1) == Decimal("1.00")
    assert quantize_money("2.5") == Decimal("2.50")
    assert quantize_money(Decimal("3.456")) == Decimal("3.46")


def test_quantize_money_uses_half_up():
    # 2.345 -> 2.35 (half up)
    assert quantize_money("2.345") == Decimal("2.35")
    # 2.344 -> 2.34
    assert quantize_money("2.344") == Decimal("2.34")
