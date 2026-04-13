from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


CNY_ZERO = Decimal("0.00")
_CNY_QUANT = Decimal("0.01")
_CNY_FEN_FACTOR = Decimal("100")


def to_cny_decimal(value, *, allow_none: bool = False) -> Decimal | None:
    if value is None:
        return None if allow_none else CNY_ZERO

    if isinstance(value, Decimal):
        amount = value
    elif isinstance(value, int):
        amount = Decimal(value)
    elif isinstance(value, float):
        amount = Decimal(str(value))
    else:
        raw = str(value).strip()
        if not raw:
            return None if allow_none else CNY_ZERO
        try:
            amount = Decimal(raw)
        except InvalidOperation as exc:
            raise ValueError(f"invalid cny amount: {value!r}") from exc

    return amount.quantize(_CNY_QUANT, rounding=ROUND_HALF_UP)


def cny_to_api(value) -> float:
    return float(to_cny_decimal(value) or CNY_ZERO)


def cny_to_fen(value) -> int:
    amount = to_cny_decimal(value) or CNY_ZERO
    return int((amount * _CNY_FEN_FACTOR).to_integral_value(rounding=ROUND_HALF_UP))


def fen_to_cny(value: int | str | Decimal | None) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None
    fen = Decimal(str(value).strip())
    return (fen / _CNY_FEN_FACTOR).quantize(_CNY_QUANT, rounding=ROUND_HALF_UP)


def cny_to_display(value) -> str:
    return f"{to_cny_decimal(value) or CNY_ZERO:.2f}"


def cny_sum(values) -> Decimal:
    total = CNY_ZERO
    for value in values:
        total += to_cny_decimal(value) or CNY_ZERO
    return total.quantize(_CNY_QUANT, rounding=ROUND_HALF_UP)
