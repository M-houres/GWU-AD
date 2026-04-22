from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy.orm import Session

from app.exceptions import BizError
from app.models import SystemConfig

CONFIG_KEY = "aigc_detect_strategy"
STRATEGY_ALGORITHM = "algorithm"
SUPPORTED_AIGC_DETECT_PLATFORMS = ("cnki", "vip")

DEFAULT_AIGC_DETECT_STRATEGY_CONFIG: dict[str, Any] = {
    "cnki": {
        "aigc_detect": {
            "enabled": True,
        }
    },
    "vip": {
        "aigc_detect": {
            "enabled": True,
        }
    },
}


def normalize_aigc_detect_strategy_config(raw: dict | None) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    result = deepcopy(DEFAULT_AIGC_DETECT_STRATEGY_CONFIG)
    for platform in SUPPORTED_AIGC_DETECT_PLATFORMS:
        platform_source = source.get(platform)
        if not isinstance(platform_source, dict):
            continue
        slot_source = platform_source.get("aigc_detect")
        if not isinstance(slot_source, dict):
            continue
        result[platform]["aigc_detect"]["enabled"] = bool(
            slot_source.get("enabled", result[platform]["aigc_detect"]["enabled"])
        )
    return result


def load_aigc_detect_strategy_config(db: Session) -> dict[str, Any]:
    row = (
        db.query(SystemConfig)
        .filter(SystemConfig.category == "system", SystemConfig.config_key == CONFIG_KEY)
        .first()
    )
    value = row.config_value if row and isinstance(row.config_value, dict) else {}
    return normalize_aigc_detect_strategy_config(value)


def ensure_aigc_detect_enabled(db: Session, *, platform: str) -> str:
    normalized_platform = str(platform or "").strip().lower()
    if normalized_platform not in SUPPORTED_AIGC_DETECT_PLATFORMS:
        raise BizError(code=4116, message="不支持的平台")
    config = load_aigc_detect_strategy_config(db)
    slot = config[normalized_platform]["aigc_detect"]
    if not bool(slot.get("enabled", True)):
        raise BizError(code=4117, message="当前平台暂不支持AIGC检测")
    return STRATEGY_ALGORITHM


def aigc_detect_strategy_readiness(value: dict) -> dict:
    config = normalize_aigc_detect_strategy_config(value)
    disabled = [
        platform
        for platform in SUPPORTED_AIGC_DETECT_PLATFORMS
        if not bool(config.get(platform, {}).get("aigc_detect", {}).get("enabled", False))
    ]
    if len(disabled) == len(SUPPORTED_AIGC_DETECT_PLATFORMS):
        return {"status": "error", "message": "知网和维普AIGC检测策略均未启用"}
    summary = []
    for platform in SUPPORTED_AIGC_DETECT_PLATFORMS:
        label = "知网" if platform == "cnki" else "维普"
        enabled = bool(config[platform]["aigc_detect"]["enabled"])
        summary.append(f"{label}:{'算法策略' if enabled else '未启用'}")
    return {"status": "ready", "message": "；".join(summary)}

