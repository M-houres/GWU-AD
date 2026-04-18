from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.constants import TASK_POINTS_PER_CHAR
from app.models import SystemConfig, TaskType

_FEN_QUANT = Decimal("1")
_RATE_MIN = Decimal("1")
_RATE_MAX = Decimal("9999")

_TASK_RATE_KEY_MAP: dict[TaskType, tuple[str, str]] = {
    TaskType.AIGC_DETECT: ("aigc_points_per_char", "aigc_rate"),
    TaskType.DEDUP: ("dedup_points_per_char", "dedup_rate"),
    TaskType.REWRITE: ("rewrite_points_per_char", "rewrite_rate"),
}


def _to_decimal_rate(value) -> Decimal | None:
    if value is None:
        return None
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None
    if amount != amount.to_integral_value():
        return None
    if amount < _RATE_MIN or amount > _RATE_MAX:
        return None
    return amount


def resolve_task_points_per_char(db: Session, task_type: TaskType) -> Decimal:
    row = (
        db.query(SystemConfig)
        .filter(SystemConfig.category == "system", SystemConfig.config_key == "billing")
        .first()
    )
    cfg = row.config_value if row and isinstance(row.config_value, dict) else {}
    primary_key, legacy_key = _TASK_RATE_KEY_MAP[task_type]
    parsed = _to_decimal_rate(cfg.get(primary_key))
    if parsed is None:
        parsed = _to_decimal_rate(cfg.get(legacy_key))
    if parsed is not None:
        return parsed
    return TASK_POINTS_PER_CHAR[task_type]


def calc_task_cost_fen(char_count: int, points_per_char: Decimal) -> int:
    chars = max(int(char_count or 0), 0)
    if chars <= 0:
        return 0
    raw = (points_per_char * Decimal(chars)).quantize(_FEN_QUANT, rounding=ROUND_HALF_UP)
    cost = int(raw)
    if cost <= 0 and points_per_char > 0:
        return 1
    return cost


def build_task_rate_payload(db: Session) -> dict:
    aigc_rate = resolve_task_points_per_char(db, TaskType.AIGC_DETECT)
    dedup_rate = resolve_task_points_per_char(db, TaskType.DEDUP)
    rewrite_rate = resolve_task_points_per_char(db, TaskType.REWRITE)
    return {
        "aigc_points_per_char": int(aigc_rate),
        "dedup_points_per_char": int(dedup_rate),
        "rewrite_points_per_char": int(rewrite_rate),
        "unit": "points_per_char",
    }
