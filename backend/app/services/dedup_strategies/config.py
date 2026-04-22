from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy.orm import Session

from app.exceptions import BizError
from app.models import SystemConfig

CONFIG_KEY = "dedup_strategy"
STRATEGY_ALGORITHM = "algorithm"
STRATEGY_LLM = "llm"
SUPPORTED_DEDUP_PLATFORMS = ("cnki", "vip")
SUPPORTED_DEDUP_STRATEGIES = {STRATEGY_ALGORITHM, STRATEGY_LLM}

DEFAULT_DEDUP_STRATEGY_CONFIG: dict[str, Any] = {
    "cnki": {
        "dedup": {
            "enabled": True,
            "active_strategy": STRATEGY_ALGORITHM,
        }
    },
    "vip": {
        "dedup": {
            "enabled": True,
            "active_strategy": STRATEGY_ALGORITHM,
        }
    },
}


def normalize_strategy_name(raw: Any) -> str:
    value = str(raw or "").strip().lower()
    if value in {"algo", "rule", "rules", "rule_based"}:
        return STRATEGY_ALGORITHM
    if value in {"model", "llm_only", "large_model", "ai"}:
        return STRATEGY_LLM
    if value in SUPPORTED_DEDUP_STRATEGIES:
        return value
    raise BizError(code=4341, message="降重复率策略仅支持 algorithm 或 llm")


def normalize_dedup_strategy_config(raw: dict | None) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    result = deepcopy(DEFAULT_DEDUP_STRATEGY_CONFIG)
    for platform in SUPPORTED_DEDUP_PLATFORMS:
        platform_source = source.get(platform)
        if not isinstance(platform_source, dict):
            continue
        dedup_source = platform_source.get("dedup")
        if not isinstance(dedup_source, dict):
            continue
        result[platform]["dedup"]["enabled"] = bool(dedup_source.get("enabled", result[platform]["dedup"]["enabled"]))
        result[platform]["dedup"]["active_strategy"] = normalize_strategy_name(
            dedup_source.get("active_strategy", result[platform]["dedup"]["active_strategy"])
        )
    return result


def load_dedup_strategy_config(db: Session) -> dict[str, Any]:
    row = (
        db.query(SystemConfig)
        .filter(SystemConfig.category == "system", SystemConfig.config_key == CONFIG_KEY)
        .first()
    )
    value = row.config_value if row and isinstance(row.config_value, dict) else {}
    return normalize_dedup_strategy_config(value)


def get_active_dedup_strategy(db: Session, *, platform: str) -> str:
    normalized_platform = str(platform or "").strip().lower()
    if normalized_platform not in SUPPORTED_DEDUP_PLATFORMS:
        raise BizError(code=4116, message="不支持的平台")
    config = load_dedup_strategy_config(db)
    slot = config[normalized_platform]["dedup"]
    if not bool(slot.get("enabled", True)):
        raise BizError(code=4117, message="当前平台暂不支持降重复率")
    return normalize_strategy_name(slot.get("active_strategy"))


def dedup_strategy_readiness(value: dict) -> dict:
    config = normalize_dedup_strategy_config(value)
    disabled = [
        platform
        for platform in SUPPORTED_DEDUP_PLATFORMS
        if not bool(config.get(platform, {}).get("dedup", {}).get("enabled", False))
    ]
    if len(disabled) == len(SUPPORTED_DEDUP_PLATFORMS):
        return {"status": "error", "message": "知网和维普降重复率策略均未启用"}
    summary = []
    for platform in SUPPORTED_DEDUP_PLATFORMS:
        slot = config[platform]["dedup"]
        label = "知网" if platform == "cnki" else "维普"
        if slot["enabled"]:
            strategy_label = "算法策略" if slot["active_strategy"] == STRATEGY_ALGORITHM else "大模型策略"
            summary.append(f"{label}:{strategy_label}")
        else:
            summary.append(f"{label}:未启用")
    return {"status": "ready", "message": "；".join(summary)}
