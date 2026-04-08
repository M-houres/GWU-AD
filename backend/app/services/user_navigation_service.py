from copy import deepcopy


USER_NAVIGATION_PRESETS = [
    {
        "key": "rewrite",
        "label": "学术润色",
        "path": "/app/rewrite",
        "group": "core",
        "visible": True,
        "order": 1,
        "disabled": False,
        "badge": "",
    },
    {
        "key": "dedup",
        "label": "降重复率",
        "path": "/app/dedup",
        "group": "core",
        "visible": True,
        "order": 2,
        "disabled": False,
        "badge": "",
    },
    {
        "key": "detect",
        "label": "AIGC检测",
        "path": "/app/detect",
        "group": "core",
        "visible": True,
        "order": 3,
        "disabled": False,
        "badge": "",
    },
    {
        "key": "review",
        "label": "智能审稿",
        "path": "/app/review",
        "group": "lab",
        "visible": True,
        "order": 4,
        "disabled": True,
        "badge": "开发中",
    },
    {
        "key": "defense",
        "label": "答辩服务",
        "path": "/app/defense",
        "group": "lab",
        "visible": True,
        "order": 5,
        "disabled": True,
        "badge": "开发中",
    },
    {
        "key": "referral",
        "label": "推广福利",
        "path": "/app/referral",
        "group": "account",
        "visible": True,
        "order": 6,
        "disabled": False,
        "badge": "",
    },
]

_USER_NAVIGATION_KEY_ORDER = {item["key"]: index for index, item in enumerate(USER_NAVIGATION_PRESETS)}


def _as_bool(value, default: bool = False) -> bool:
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


def _as_int(value, default: int, *, min_value: int = 1, max_value: int = 1000) -> int:
    try:
        num = int(value)
    except Exception:
        return default
    if num < min_value or num > max_value:
        return default
    return num


def default_user_navigation_config() -> dict:
    return {"items": [deepcopy(item) for item in USER_NAVIGATION_PRESETS]}


def normalize_user_navigation_config(raw: dict | None) -> dict:
    source_items = raw.get("items") if isinstance(raw, dict) else []
    incoming_map = {}
    if isinstance(source_items, list):
        for item in source_items:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key", "")).strip()
            if not key or key in incoming_map:
                continue
            incoming_map[key] = item

    normalized_items = []
    for fallback_order, preset in enumerate(USER_NAVIGATION_PRESETS, start=1):
        current = incoming_map.get(preset["key"], {})
        default_order = int(preset.get("order", fallback_order))
        normalized_items.append(
            {
                **preset,
                "visible": _as_bool(current.get("visible", preset.get("visible", True)), default=bool(preset.get("visible", True))),
                "order": _as_int(current.get("order", default_order), default_order, min_value=1, max_value=1000),
            }
        )

    normalized_items.sort(key=lambda item: (int(item.get("order", 0)), _USER_NAVIGATION_KEY_ORDER.get(item["key"], 999)))
    for index, item in enumerate(normalized_items, start=1):
        item["order"] = index

    return {"items": normalized_items}
