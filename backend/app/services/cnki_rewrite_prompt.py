from __future__ import annotations

from functools import lru_cache

from app.services.strategy_asset_paths import resolve_strategy_asset_path


CNKI_REWRITE_PROMPT_PATH = resolve_strategy_asset_path("rewrite_system_V16.md")
_PROMPT_A_HEADING = "## Prompt A"
_PROMPT_B_HEADING = "## Prompt B"


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


def _require_cnki_v16_markdown() -> str:
    if not CNKI_REWRITE_PROMPT_PATH.exists():
        raise RuntimeError(f"知网 V16 策略文件缺失: {CNKI_REWRITE_PROMPT_PATH}")
    try:
        return CNKI_REWRITE_PROMPT_PATH.read_text(encoding="utf-8")
    except Exception as exc:  # pragma: no cover - filesystem failure
        raise RuntimeError(f"知网 V16 策略文件读取失败: {exc}") from exc


def _require_code_block(content: str, *, heading: str, section: str) -> str:
    block = _extract_first_code_block(content, heading=heading)
    if not block:
        raise RuntimeError(f"知网 V16 {section} 缺失或格式不合法")
    return block


@lru_cache(maxsize=1)
def load_cnki_rewrite_markdown() -> str:
    return _require_cnki_v16_markdown()


@lru_cache(maxsize=1)
def cnki_rewrite_prompt_template() -> str:
    content = load_cnki_rewrite_markdown()
    return _require_code_block(content, heading=_PROMPT_A_HEADING, section="Prompt A")


@lru_cache(maxsize=1)
def cnki_rewrite_validation_template() -> str:
    content = load_cnki_rewrite_markdown()
    return _require_code_block(content, heading=_PROMPT_B_HEADING, section="Prompt B")


def build_cnki_v16_prompt(
    text: str,
    *,
    task_label: str,
    chunk_index: int = 1,
    chunk_total: int = 1,
) -> str:
    template = cnki_rewrite_prompt_template()
    return template.replace("{{原文}}", str(text or ""))


def build_cnki_v16_validation_prompt(source_text: str, rewritten_text: str, *, task_label: str) -> str:
    template = cnki_rewrite_validation_template()
    return template.replace("{{原文}}", str(source_text or "")).replace("{{改写文}}", str(rewritten_text or ""))


def build_cnki_rewrite_prompt(
    text: str,
    *,
    chunk_index: int = 1,
    chunk_total: int = 1,
) -> str:
    return build_cnki_v16_prompt(
        text,
        task_label="知网降AIGC率改写",
        chunk_index=chunk_index,
        chunk_total=chunk_total,
    )


def build_cnki_dedup_prompt(
    text: str,
    *,
    chunk_index: int = 1,
    chunk_total: int = 1,
) -> str:
    return build_cnki_v16_prompt(
        text,
        task_label="知网降重复率改写",
        chunk_index=chunk_index,
        chunk_total=chunk_total,
    )


def build_cnki_rewrite_validation_prompt(source_text: str, rewritten_text: str) -> str:
    return build_cnki_v16_validation_prompt(
        source_text,
        rewritten_text,
        task_label="知网降AIGC率改写",
    )


def build_cnki_dedup_validation_prompt(source_text: str, rewritten_text: str) -> str:
    return build_cnki_v16_validation_prompt(
        source_text,
        rewritten_text,
        task_label="知网降重复率改写",
    )
