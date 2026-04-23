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

DEFAULT_REWRITE_RUNTIME_CONFIG: dict[str, int] = {
    "chunk_min_chars": 180,
    "chunk_max_chars": 260,
    "algorithm_chunk_max_changes": 6,
    "llm_short_chunk_max_changes": 2,
    "llm_medium_chunk_max_changes": 3,
    "llm_standard_chunk_max_changes": 4,
    "llm_long_chunk_max_changes": 5,
    "llm_xlong_chunk_max_changes": 6,
}

DEFAULT_REWRITE_STRATEGY_CONFIG: dict[str, Any] = {
    "cnki": {
        "rewrite": {
            "enabled": True,
            "active_strategy": STRATEGY_ALGORITHM,
        },
        "runtime": deepcopy(DEFAULT_REWRITE_RUNTIME_CONFIG),
    },
    "vip": {
        "rewrite": {
            "enabled": True,
            "active_strategy": STRATEGY_ALGORITHM,
        },
        "runtime": deepcopy(DEFAULT_REWRITE_RUNTIME_CONFIG),
    },
}

_RUNTIME_BOUNDS: dict[str, tuple[int, int]] = {
    "chunk_min_chars": (80, 1200),
    "chunk_max_chars": (100, 1600),
    "algorithm_chunk_max_changes": (1, 20),
    "llm_short_chunk_max_changes": (1, 20),
    "llm_medium_chunk_max_changes": (1, 20),
    "llm_standard_chunk_max_changes": (1, 20),
    "llm_long_chunk_max_changes": (1, 20),
    "llm_xlong_chunk_max_changes": (1, 20),
}

_LLM_CHUNK_KEYS: tuple[str, ...] = (
    "llm_short_chunk_max_changes",
    "llm_medium_chunk_max_changes",
    "llm_standard_chunk_max_changes",
    "llm_long_chunk_max_changes",
    "llm_xlong_chunk_max_changes",
)


def normalize_strategy_name(raw: Any) -> str:
    value = str(raw or "").strip().lower()
    if value in {"algo", "rule", "rules", "rule_based"}:
        return STRATEGY_ALGORITHM
    if value in {"model", "llm_only", "large_model", "ai"}:
        return STRATEGY_LLM
    if value in SUPPORTED_REWRITE_STRATEGIES:
        return value
    raise BizError(code=4341, message="降AIGC率策略仅支持 algorithm 或 llm")


def _as_runtime_int(raw: Any, *, field: str, fallback: int) -> int:
    minimum, maximum = _RUNTIME_BOUNDS[field]
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = int(fallback)
    return max(minimum, min(maximum, value))


def normalize_rewrite_runtime_config(raw: dict | None, *, fallback: dict | None = None) -> dict[str, int]:
    source = raw if isinstance(raw, dict) else {}
    base = fallback if isinstance(fallback, dict) else DEFAULT_REWRITE_RUNTIME_CONFIG
    result = {
        key: _as_runtime_int(
            source.get(key, base.get(key, DEFAULT_REWRITE_RUNTIME_CONFIG[key])),
            field=key,
            fallback=base.get(key, DEFAULT_REWRITE_RUNTIME_CONFIG[key]),
        )
        for key in DEFAULT_REWRITE_RUNTIME_CONFIG.keys()
    }
    result["chunk_max_chars"] = max(result["chunk_max_chars"], result["chunk_min_chars"] + 20)
    previous = 1
    for key in _LLM_CHUNK_KEYS:
        result[key] = max(previous, result[key])
        previous = result[key]
    return result


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
        runtime_source = platform_source.get("runtime")
        result[platform]["runtime"] = normalize_rewrite_runtime_config(
            runtime_source,
            fallback=result[platform].get("runtime"),
        )
    for platform in SUPPORTED_REWRITE_PLATFORMS:
        result[platform]["runtime"] = normalize_rewrite_runtime_config(
            result[platform].get("runtime"),
            fallback=DEFAULT_REWRITE_RUNTIME_CONFIG,
        )
    return result


def load_rewrite_strategy_config(db: Session) -> dict[str, Any]:
    if db is None:
        return normalize_rewrite_strategy_config({})
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


def get_rewrite_runtime_config(db: Session, *, platform: str) -> dict[str, int]:
    normalized_platform = str(platform or "").strip().lower()
    if normalized_platform not in SUPPORTED_REWRITE_PLATFORMS:
        raise BizError(code=4116, message="不支持的平台")
    config = load_rewrite_strategy_config(db)
    slot = config.get(normalized_platform) if isinstance(config, dict) else {}
    runtime = slot.get("runtime") if isinstance(slot, dict) else {}
    return normalize_rewrite_runtime_config(runtime, fallback=DEFAULT_REWRITE_RUNTIME_CONFIG)


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
            resolved = normalize_strategy_name(slot["active_strategy"])
            strategy_label = "算法策略" if resolved == STRATEGY_ALGORITHM else "大模型策略"
            summary.append(f"{label}:{strategy_label}")
        else:
            summary.append(f"{label}:未启用")
    return {"status": "ready", "message": "；".join(summary)}
