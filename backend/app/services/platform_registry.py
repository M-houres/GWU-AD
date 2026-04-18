from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.exceptions import BizError
from app.models import SystemConfig, TaskType

PLATFORM_CATEGORY = "algo_platforms_v1"
SUPPORTED_TASK_TYPES = tuple(item.value for item in TaskType)
_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,31}$")


@dataclass(frozen=True)
class TaskPlatform:
    key: str
    label: str
    aigc_label: str
    task_types: tuple[str, ...]
    enabled: bool = True
    sort_order: int = 100


DEFAULT_PLATFORMS: tuple[TaskPlatform, ...] = (
    TaskPlatform(
        key="cnki",
        label="知网",
        aigc_label="模拟知网",
        task_types=SUPPORTED_TASK_TYPES,
        sort_order=1,
    ),
    TaskPlatform(
        key="vip",
        label="维普",
        aigc_label="模拟维普",
        task_types=SUPPORTED_TASK_TYPES,
        sort_order=2,
    ),
)

DEFAULT_PLATFORM_ALIASES = {
    "cnki": "cnki",
    "zhiwang": "cnki",
    "知网": "cnki",
    "vip": "vip",
    "weipu": "vip",
    "维普": "vip",
}


def _normalize_task_types(raw: Any) -> tuple[str, ...]:
    values = raw if isinstance(raw, (list, tuple, set)) else []
    normalized: list[str] = []
    for item in values:
        key = str(item or "").strip().lower()
        if key in SUPPORTED_TASK_TYPES and key not in normalized:
            normalized.append(key)
    if not normalized:
        return SUPPORTED_TASK_TYPES
    return tuple(normalized)


def _safe_bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        raw = value.strip().lower()
        if raw in {"1", "true", "yes", "on", "y"}:
            return True
        if raw in {"0", "false", "no", "off", "n", ""}:
            return False
    return default


def _safe_sort_order(value: Any, default: int = 100) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _serialize_platform(item: TaskPlatform) -> dict[str, Any]:
    return {
        "key": item.key,
        "label": item.label,
        "aigc_label": item.aigc_label,
        "task_types": list(item.task_types),
        "enabled": bool(item.enabled),
        "sort_order": int(item.sort_order),
    }


def _default_platform_dicts() -> list[dict[str, Any]]:
    return [_serialize_platform(item) for item in DEFAULT_PLATFORMS]


def _load_platform_rows(db: Session | None = None) -> list[dict[str, Any]]:
    if db is None:
        return _default_platform_dicts()
    row = (
        db.query(SystemConfig)
        .filter(
            SystemConfig.category == PLATFORM_CATEGORY,
            SystemConfig.config_key == "registry",
        )
        .first()
    )
    if row is None or not isinstance(row.config_value, list):
        return _default_platform_dicts()

    items: list[dict[str, Any]] = []
    for raw in row.config_value:
        if not isinstance(raw, dict):
            continue
        key = str(raw.get("key") or "").strip().lower()
        if not _KEY_PATTERN.fullmatch(key):
            continue
        label = str(raw.get("label") or key).strip() or key
        task_types = _normalize_task_types(raw.get("task_types"))
        items.append(
            {
                "key": key,
                "label": label,
                "aigc_label": str(raw.get("aigc_label") or f"模拟{label}").strip() or f"模拟{label}",
                "task_types": list(task_types),
                "enabled": _safe_bool(raw.get("enabled"), default=True),
                "sort_order": _safe_sort_order(raw.get("sort_order"), default=100),
            }
        )
    if not items:
        return _default_platform_dicts()
    return sorted(items, key=lambda item: (int(item.get("sort_order") or 100), str(item.get("key") or "")))


def list_platforms(db: Session | None = None, *, enabled_only: bool = True) -> list[dict[str, Any]]:
    rows = _load_platform_rows(db)
    if enabled_only:
        rows = [item for item in rows if bool(item.get("enabled", True))]
    return rows


def supported_platform_keys(db: Session | None = None, *, enabled_only: bool = True) -> tuple[str, ...]:
    return tuple(item["key"] for item in list_platforms(db, enabled_only=enabled_only))


def platform_label(platform: str, *, task_type: str | None = None, db: Session | None = None) -> str:
    key = str(platform or "").strip().lower()
    for item in list_platforms(db, enabled_only=False):
        if item["key"] != key:
            continue
        if task_type == TaskType.AIGC_DETECT.value:
            return item.get("aigc_label") or item.get("label") or key
        return item.get("label") or key
    return platform or "-"


def _alias_mapping(db: Session | None = None) -> dict[str, str]:
    mapping = dict(DEFAULT_PLATFORM_ALIASES)
    for item in list_platforms(db, enabled_only=False):
        key = str(item.get("key") or "").strip().lower()
        label = str(item.get("label") or "").strip().lower()
        aigc_label = str(item.get("aigc_label") or "").replace("模拟", "").strip().lower()
        if key:
            mapping[key] = key
        if label:
            mapping[label] = key
        if aigc_label:
            mapping[aigc_label] = key
    return mapping


def normalize_platform(raw: str, *, task_type: str | TaskType | None = None, db: Session | None = None) -> str:
    key = str(raw or "").strip().lower()
    value = _alias_mapping(db).get(key)
    if not value:
        raise BizError(code=4116, message=f"不支持的平台: {raw}")

    normalized_task_type = task_type.value if isinstance(task_type, TaskType) else str(task_type or "").strip().lower()
    for item in list_platforms(db, enabled_only=False):
        if item["key"] != value:
            continue
        if not bool(item.get("enabled", True)):
            raise BizError(code=4117, message="当前平台暂未开放")
        task_types = tuple(item.get("task_types") or [])
        if normalized_task_type and normalized_task_type not in task_types:
            raise BizError(code=4117, message="当前平台暂不支持该功能")
        return value
    raise BizError(code=4116, message=f"不支持的平台: {raw}")


def validate_platform_payload(payload: dict[str, Any]) -> dict[str, Any]:
    key = str(payload.get("key") or "").strip().lower()
    if not _KEY_PATTERN.fullmatch(key):
        raise BizError(code=4351, message="平台标识只能使用小写字母、数字和下划线，且需以字母开头")
    label = str(payload.get("label") or "").strip()
    if not label:
        raise BizError(code=4352, message="平台名称不能为空")
    aigc_label = str(payload.get("aigc_label") or f"模拟{label}").strip() or f"模拟{label}"
    task_types = _normalize_task_types(payload.get("task_types"))
    return {
        "key": key,
        "label": label,
        "aigc_label": aigc_label,
        "task_types": list(task_types),
        "enabled": _safe_bool(payload.get("enabled"), default=True),
        "sort_order": _safe_sort_order(payload.get("sort_order"), default=100),
    }


def upsert_platform(
    db: Session,
    *,
    payload: dict[str, Any],
    updated_by: int | None = None,
) -> dict[str, Any]:
    normalized = validate_platform_payload(payload)
    items = list_platforms(db, enabled_only=False)
    replaced = False
    for index, item in enumerate(items):
        if item["key"] != normalized["key"]:
            continue
        items[index] = normalized
        replaced = True
        break
    if not replaced:
        items.append(normalized)
    items = sorted(items, key=lambda item: (int(item.get("sort_order") or 100), str(item.get("key") or "")))

    row = (
        db.query(SystemConfig)
        .filter(
            SystemConfig.category == PLATFORM_CATEGORY,
            SystemConfig.config_key == "registry",
        )
        .first()
    )
    if row is None:
        row = SystemConfig(
            category=PLATFORM_CATEGORY,
            config_key="registry",
            config_value=items,
            updated_by=updated_by,
        )
        db.add(row)
    else:
        row.config_value = items
        row.updated_by = updated_by
    db.flush()
    return normalized
