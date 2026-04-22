from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy.orm import Session

from app.exceptions import BizError
from app.models import SystemConfig

CONFIG_KEY = "rewrite_strategy"
STRATEGY_ALGORITHM = "algorithm"
STRATEGY_LLM = "llm"
SUPPORTED_REWRITE_PLATFORMS = ("cnki", "vip")
SUPPORTED_REWRITE_STRATEGIES = {STRATEGY_ALGORITHM, STRATEGY_LLM}

DEFAULT_REWRITE_STRATEGY_CONFIG: dict[str, Any] = {
    "cnki": {
        "rewrite": {
            "enabled": True,
            "active_strategy": STRATEGY_ALGORITHM,
        }
    },
    "vip": {
        "rewrite": {
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
    if value in SUPPORTED_REWRITE_STRATEGIES:
        return value
    raise BizError(code=4341, message="降AIGC率策略仅支持 algorithm 或 llm")


def normalize_rewrite_strategy_config(raw: dict | None) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    result = deepcopy(DEFAULT_REWRITE_STRATEGY_CONFIG)
    for platform in SUPPORTED_REWRITE_PLATFORMS:
        platform_source = source.get(platform)
        if not isinstance(platform_source, dict):
            continue
        rewrite_source = platform_source.get("rewrite")
        if not isinstance(rewrite_source, dict):
            continue
        result[platform]["rewrite"]["enabled"] = bool(rewrite_source.get("enabled", result[platform]["rewrite"]["enabled"]))
        result[platform]["rewrite"]["active_strategy"] = normalize_strategy_name(
            rewrite_source.get("active_strategy", result[platform]["rewrite"]["active_strategy"])
        )
    return result


def load_rewrite_strategy_config(db: Session) -> dict[str, Any]:
    row = (
        db.query(SystemConfig)
        .filter(SystemConfig.category == "system", SystemConfig.config_key == CONFIG_KEY)
        .first()
    )
    value = row.config_value if row and isinstance(row.config_value, dict) else {}
    return normalize_rewrite_strategy_config(value)


def get_active_rewrite_strategy(db: Session, *, platform: str) -> str:
    normalized_platform = str(platform or "").strip().lower()
    if normalized_platform not in SUPPORTED_REWRITE_PLATFORMS:
        raise BizError(code=4116, message="不支持的平台")
    config = load_rewrite_strategy_config(db)
    slot = config[normalized_platform]["rewrite"]
    if not bool(slot.get("enabled", True)):
        raise BizError(code=4117, message="当前平台暂不支持降AIGC率")
    return normalize_strategy_name(slot.get("active_strategy"))


def rewrite_strategy_readiness(value: dict) -> dict:
    config = normalize_rewrite_strategy_config(value)
    disabled = [
        platform
        for platform in SUPPORTED_REWRITE_PLATFORMS
        if not bool(config.get(platform, {}).get("rewrite", {}).get("enabled", False))
    ]
    if len(disabled) == len(SUPPORTED_REWRITE_PLATFORMS):
        return {"status": "error", "message": "知网和维普降AIGC率策略均未启用"}
    summary = []
    for platform in SUPPORTED_REWRITE_PLATFORMS:
        slot = config[platform]["rewrite"]
        label = "知网" if platform == "cnki" else "维普"
        if slot["enabled"]:
            strategy_label = "算法策略" if slot["active_strategy"] == STRATEGY_ALGORITHM else "大模型策略"
            summary.append(f"{label}:{strategy_label}")
        else:
            summary.append(f"{label}:未启用")
    return {"status": "ready", "message": "；".join(summary)}

