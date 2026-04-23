from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
CNKI_V5_PROMPT_PATH = REPO_ROOT / "data" / "strategy_assets" / "rewrite_prompt_system_v5.md"

_PROMPT_A_HEADING = "## Prompt A：主改写 Prompt（v5版）"
_FALLBACK_PROMPT_A = (
    "你是中文改写执行器。严格按步骤改写，直接输出结果，不加说明。\n\n"
    "【参数】强度：{{N}}（1=每句1-2处 / 2=每句2-3处 / 3=每句3-4处）\n\n"
    "【质量红线】\n"
    "Q1 不得产生错别字或的地得误用\n"
    "Q2 不得破坏动宾搭配\n"
    "Q3 同一替换词全文上限2次\n"
    "Q4 信息量不得增减，不得改变语义\n"
    "Q5 语体风格须与原文一致\n\n"
    "【规则执行顺序：L1→L5，L4仅在改动不足时补充】\n"
    "L1/L2/L3/L4/L5 按顺序执行。\n\n"
    "输入：{{原文}}"
)

_TEMPLATE_SECTION_PATTERN = re.compile(
    r"###\s*【(C\d+)】([^\n]+)\n+```(?P<body>.*?)```",
    re.DOTALL,
)


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


@lru_cache(maxsize=1)
def load_cnki_v5_markdown() -> str:
    if not CNKI_V5_PROMPT_PATH.exists():
        return ""
    try:
        return CNKI_V5_PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return ""


@lru_cache(maxsize=1)
def cnki_v5_prompt_a_template() -> str:
    content = load_cnki_v5_markdown()
    block = _extract_first_code_block(content, heading=_PROMPT_A_HEADING)
    return block or _FALLBACK_PROMPT_A


def _clean_template_phrase(value: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"[（(][^）)]*[）)]", "", text)
    text = re.sub(r"\s+", "", text)
    text = text.strip("`")
    return text


def _tokenize_template_phrase(value: str) -> list[tuple[str, str]]:
    text = str(value or "")
    tokens: list[tuple[str, str]] = []
    cursor = 0
    while cursor < len(text):
        if text.startswith("YYYY", cursor):
            tokens.append(("VAR", "YEAR"))
            cursor += 4
            continue
        ch = text[cursor]
        if ch in {"X", "Y"}:
            tokens.append(("VAR", ch))
            cursor += 1
            continue
        tokens.append(("LIT", ch))
        cursor += 1
    return tokens


def _build_template_pattern(source_phrase: str) -> tuple[str, dict[str, str]]:
    tokens = _tokenize_template_phrase(source_phrase)
    bindings: dict[str, str] = {}
    pattern_parts: list[str] = []
    for kind, value in tokens:
        if kind == "LIT":
            pattern_parts.append(re.escape(value))
            continue
        if value in bindings:
            pattern_parts.append(fr"(?P={bindings[value]})")
            continue
        group_name = value if value != "YEAR" else "YEAR"
        bindings[value] = group_name
        if value == "YEAR":
            pattern_parts.append(r"(?P<YEAR>\d{4})")
        else:
            pattern_parts.append(fr"(?P<{group_name}>[^，。！？；;、\n]{{1,24}})")
    return "".join(pattern_parts), bindings


def _build_template_replacement(target_phrase: str, *, bindings: dict[str, str]) -> str:
    tokens = _tokenize_template_phrase(target_phrase)
    replacement_parts: list[str] = []
    for kind, value in tokens:
        if kind == "LIT":
            replacement_parts.append(value)
            continue
        group_name = bindings.get(value)
        if not group_name:
            replacement_parts.append(value if value != "YEAR" else "YYYY")
            continue
        replacement_parts.append(fr"\g<{group_name}>")
    return "".join(replacement_parts)


@lru_cache(maxsize=1)
def cnki_v5_sentence_template_rules() -> tuple[dict[str, str], ...]:
    content = load_cnki_v5_markdown()
    if not content:
        return ()
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    section_index = 0
    for section_match in _TEMPLATE_SECTION_PATTERN.finditer(content):
        section_index += 1
        section_id = str(section_match.group(1) or "").strip().lower()
        section_body = str(section_match.group("body") or "")
        line_index = 0
        for raw_line in section_body.splitlines():
            line = str(raw_line or "").strip()
            if not line or "→" not in line:
                continue
            left, right = line.split("→", 1)
            source = _clean_template_phrase(left)
            targets = [
                _clean_template_phrase(item)
                for item in re.split(r"[\/／]", right)
                if _clean_template_phrase(item)
            ]
            if not source or not targets:
                continue
            primary_target = targets[0]
            if "→" in source or "→" in primary_target:
                continue
            pattern, bindings = _build_template_pattern(source)
            replacement = _build_template_replacement(primary_target, bindings=bindings)
            if not pattern or not replacement:
                continue
            dedup_key = (pattern, replacement)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            line_index += 1
            rows.append(
                {
                    "id": f"cnki_v5_{section_id}_{line_index:03d}",
                    "pattern": pattern,
                    "replacement": replacement,
                    "source": source,
                    "target": primary_target,
                    "category": f"v5_{section_id}",
                    "priority": str(max(50, 100 - section_index)),
                }
            )
    return tuple(rows)


def build_cnki_v5_prompt(
    text: str,
    *,
    mode: str,
    chunk_index: int = 1,
    chunk_total: int = 1,
    rule_library_size: int = 0,
) -> str:
    template = cnki_v5_prompt_a_template()
    prompt_body = template.replace("{{N}}", "2").replace("{{原文}}", "（见下方【输入】）")
    if rule_library_size > 0:
        prompt_body = re.sub(
            r"规则库词对总数：[^\n]*",
            f"规则库词对总数：{int(rule_library_size)}（L1/L2/L3/L5 按规则库分层执行）",
            prompt_body,
            count=1,
        )
    mode_label = "知网降重复率改写" if str(mode or "").strip().lower() == "dedup" else "知网降AIGC率改写"
    header = (
        f"任务类型：{mode_label}。\n"
        f"当前处理片段：第{chunk_index}/{max(chunk_total, 1)}块。\n"
        "执行原则：命中规则即改（以句法骨架改写为主，词替换为辅），禁止机械扩写。"
    )
    return f"{header}\n\n{prompt_body}\n\n【输入】\n{text}"
