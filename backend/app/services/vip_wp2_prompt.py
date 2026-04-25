from __future__ import annotations

from functools import lru_cache
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
VIP_WP2_PROMPT_PATH = REPO_ROOT / "data" / "strategy_assets" / "rewrite_system_WP2_Wanfang.md"
_PROMPT_A_HEADING = "## Prompt A"
_PROMPT_B_HEADING = "## Prompt B（校验）"


def _extract_first_code_block(content: str, *, heading: str) -> str:
    if not content:
        return ""
    start = content.find(heading)
    if start < 0:
        return ""
    scoped = content[start:]
    code_start = scoped.find("```")
    if code_start < 0:
        return ""
    code_start += 3
    code_end = scoped.find("```", code_start)
    if code_end < 0:
        return ""
    return scoped[code_start:code_end].strip()


def _require_vip_wp2_markdown() -> str:
    if not VIP_WP2_PROMPT_PATH.exists():
        raise RuntimeError(f"维普 WP2 策略文件缺失: {VIP_WP2_PROMPT_PATH}")
    try:
        return VIP_WP2_PROMPT_PATH.read_text(encoding="utf-8")
    except Exception as exc:  # pragma: no cover - filesystem failure
        raise RuntimeError(f"维普 WP2 策略文件读取失败: {exc}") from exc


def _require_code_block(content: str, *, heading: str, section: str) -> str:
    block = _extract_first_code_block(content, heading=heading)
    if not block:
        raise RuntimeError(f"维普 WP2 {section} 缺失或格式不合法")
    return block


@lru_cache(maxsize=1)
def load_vip_wp2_markdown() -> str:
    return _require_vip_wp2_markdown()


@lru_cache(maxsize=1)
def vip_wp2_prompt_template() -> str:
    content = load_vip_wp2_markdown()
    return _require_code_block(content, heading=_PROMPT_A_HEADING, section="Prompt A")


@lru_cache(maxsize=1)
def vip_wp2_validation_template() -> str:
    content = load_vip_wp2_markdown()
    return _require_code_block(content, heading=_PROMPT_B_HEADING, section="Prompt B")


def build_vip_wp2_prompt(
    text: str,
    *,
    task_label: str,
    chunk_index: int = 1,
    chunk_total: int = 1,
) -> str:
    template = vip_wp2_prompt_template()
    return template.replace("{{原文}}", str(text or ""))


def build_vip_wp2_validation_prompt(source_text: str, rewritten_text: str, *, task_label: str) -> str:
    template = vip_wp2_validation_template()
    return template.replace("{{原文}}", str(source_text or "")).replace("{{改写文}}", str(rewritten_text or ""))


def build_vip_rewrite_prompt(text: str, *, chunk_index: int = 1, chunk_total: int = 1) -> str:
    return build_vip_wp2_prompt(
        text,
        task_label="维普降AIGC率改写",
        chunk_index=chunk_index,
        chunk_total=chunk_total,
    )


def build_vip_dedup_prompt(text: str, *, chunk_index: int = 1, chunk_total: int = 1) -> str:
    return build_vip_wp2_prompt(
        text,
        task_label="维普降重复率改写",
        chunk_index=chunk_index,
        chunk_total=chunk_total,
    )


def build_vip_rewrite_validation_prompt(source_text: str, rewritten_text: str) -> str:
    return build_vip_wp2_validation_prompt(
        source_text,
        rewritten_text,
        task_label="维普降AIGC率改写",
    )


def build_vip_dedup_validation_prompt(source_text: str, rewritten_text: str) -> str:
    return build_vip_wp2_validation_prompt(
        source_text,
        rewritten_text,
        task_label="维普降重复率改写",
    )
