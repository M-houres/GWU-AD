from __future__ import annotations

from dataclasses import dataclass
import math
import re

from app.exceptions import BizError
from app.models import TaskType
from app.services.llm_service import generate_with_llm, load_llm_config
from app.services.processing_text_tools import clean_llm_user_facing_text
from app.services.vip_w4_prompt import build_vip_w4_prompt
from app.utils import count_billable_chars

_FINAL_HEADER_RE = re.compile(r"===\s*改写完成\s*总改写次数[：:]\s*(\d+)\s*次\s*===", flags=re.IGNORECASE)
_REFERENCE_HEADINGS = {"参考文献", "参考文献:", "参考文献：", "references", "REFERENCES"}
_KEYWORD_PREFIXES = ("关键词：", "关键词:", "关键字：", "关键字:")
_STYLE_FLOOR_FORBIDDEN = ("拿", "搞", "弄", "蛮好", "挺好", "非常棒", "很厉害")
_PROTECTED_TITLE_HEADINGS = {"摘要", "引言", "结论", "结语", "致谢", "参考文献", "Abstract", "ABSTRACT"}
_PRESERVED_FRONT_HEADINGS = _PROTECTED_TITLE_HEADINGS | {
    "摘要:",
    "摘要：",
    "【摘要】",
    "引言:",
    "引言：",
    "绪论",
    "绪论:",
    "绪论：",
    "前言",
    "前言:",
    "前言：",
    "导论",
    "导论:",
    "导论：",
    "关键词",
    "关键词:",
    "关键词：",
    "关键字",
    "关键字:",
    "关键字：",
    "【关键词】",
    "【关键字】",
}
_MIN_OUTPUT_LENGTH_RATIO = 0.75
_PROCESS_MARKER_PATTERNS = (
    r"→\s*通过，继续处理下一段",
    r"通过，继续处理下一段",
    r"【初始化】.*",
    r"【P[_\s]?\d+\s*改写计划[^】]*】",
    r"【P[_\s]?\d+\s*改写结果(?:（修订版）)?】",
    r"【P[_\s]?\d+\s*验证】.*",
    r"===\s*改写完成.*?===",
)


@dataclass
class VipW4ParagraphQuota:
    index: int
    text: str
    char_count: int
    quota: int


@dataclass
class VipW4Plan:
    paragraphs: list[VipW4ParagraphQuota]
    total_chars: int
    total_quota: int

    @property
    def paragraph_count(self) -> int:
        return len(self.paragraphs)

    @property
    def init_line(self) -> str:
        quota_text = ", ".join(f"P{item.index}={item.quota}" for item in self.paragraphs) or "无正文段"
        return f"【初始化】正文约{self.total_chars}字，全文配额{self.total_quota}次，共{self.paragraph_count}段，各段配额：{quota_text}"


@dataclass
class VipW4RunResult:
    text: str
    reported_total_rewrites: int
    plan: VipW4Plan
    raw_output: str
    llm_provider: str
    llm_model: str


@dataclass
class VipW4TextRunResult:
    text: str
    run: VipW4RunResult


@dataclass
class VipW4TextBlock:
    kind: str
    text: str


@dataclass
class VipW4TextLayout:
    blocks: list[VipW4TextBlock]

    @property
    def body_paragraphs(self) -> list[str]:
        return [block.text for block in self.blocks if block.kind == "body"]

    def rebuild(self, rewritten_paragraphs: list[str]) -> str:
        rewritten_iter = iter(rewritten_paragraphs)
        output_blocks: list[str] = []
        for block in self.blocks:
            if block.kind == "body":
                output_blocks.append(next(rewritten_iter, block.text))
            else:
                output_blocks.append(block.text)
        return "\n\n".join(item for item in output_blocks if str(item or "").strip()).strip()


def execute_vip_w4(db, *, task_type: TaskType, paragraphs: list[str]) -> VipW4RunResult:
    cleaned_paragraphs = [str(item or "").strip() for item in paragraphs if str(item or "").strip()]
    if not cleaned_paragraphs:
        raise BizError(code=4631, message="维普 W4 无可改写正文")
    plan = build_vip_w4_plan(cleaned_paragraphs)
    llm_cfg = load_llm_config(db)
    prompt = build_vip_w4_prompt("\n\n".join(cleaned_paragraphs), runtime_context=_build_runtime_context(plan))
    issues: list[str] = []
    raw_output = ""
    for attempt in range(1, 3):
        current_prompt = prompt if attempt == 1 else _build_retry_prompt(plan=plan, previous_output=raw_output, issues=issues)
        raw_output = str(generate_with_llm(db, task_type=task_type, text=current_prompt) or "").strip()
        try:
            final_text, reported_total = _extract_final_text(raw_output, plan=plan)
            rewritten_paragraphs = _normalize_rewritten_paragraphs(final_text, plan=plan)
            rewritten_paragraphs = [_repair_vip_w4_paragraph(text) for text in rewritten_paragraphs]
            _validate_vip_w4_output(
                plan=plan,
                original_paragraphs=cleaned_paragraphs,
                rewritten_paragraphs=rewritten_paragraphs,
                reported_total=reported_total,
            )
            return VipW4RunResult(
                text="\n\n".join(rewritten_paragraphs).strip(),
                reported_total_rewrites=reported_total,
                plan=plan,
                raw_output=raw_output,
                llm_provider=str(llm_cfg.get("provider") or ""),
                llm_model=str(llm_cfg.get("model") or ""),
            )
        except BizError as exc:
            issues = [str(exc)]
            if attempt >= 2:
                raise
    raise BizError(code=4631, message="维普 W4 执行失败")


def execute_vip_w4_text(db, *, task_type: TaskType, source_text: str) -> VipW4TextRunResult:
    layout = build_vip_w4_text_layout(source_text)
    if not layout.body_paragraphs:
        raise BizError(code=4631, message="维普 W4 无可改写正文")
    run = execute_vip_w4(db, task_type=task_type, paragraphs=layout.body_paragraphs)
    rebuilt = layout.rebuild(_split_rewritten_paragraphs(run.text))
    return VipW4TextRunResult(text=rebuilt, run=run)


def build_vip_w4_plan(paragraphs: list[str]) -> VipW4Plan:
    normalized = [str(item or "").strip() for item in paragraphs if str(item or "").strip()]
    quotas: list[VipW4ParagraphQuota] = []
    total_chars = 0
    for index, paragraph in enumerate(normalized, start=1):
        char_count = count_billable_chars(paragraph)
        total_chars += char_count
        quota = max(3, math.ceil(max(char_count, 1) / 100) * 5)
        quotas.append(VipW4ParagraphQuota(index=index, text=paragraph, char_count=char_count, quota=quota))
    total_quota = math.ceil(max(total_chars, 1) / 100) * 5
    return VipW4Plan(paragraphs=quotas, total_chars=total_chars, total_quota=total_quota)


def build_vip_w4_text_layout(source_text: str) -> VipW4TextLayout:
    normalized = str(source_text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return VipW4TextLayout(blocks=[])
    raw_blocks = re.split(r"\n\s*\n", normalized)
    blocks = [item.strip() for item in raw_blocks if item and item.strip()]
    if len(blocks) == 1:
        blocks = [line.strip() for line in normalized.splitlines() if line.strip()]
    layout_blocks: list[VipW4TextBlock] = []
    in_reference_section = False
    previous_kind = ""
    for index, block in enumerate(blocks):
        if in_reference_section:
            layout_blocks.append(VipW4TextBlock(kind="preserved", text=block))
            previous_kind = "reference_body"
            continue
        if _is_reference_heading(block):
            in_reference_section = True
            layout_blocks.append(VipW4TextBlock(kind="preserved", text=block))
            previous_kind = "reference_heading"
            continue
        preserved_kind = _classify_preserved_text_block(block, index=index, previous_kind=previous_kind)
        if preserved_kind:
            layout_blocks.append(VipW4TextBlock(kind="preserved", text=block))
            previous_kind = preserved_kind
            continue
        layout_blocks.append(VipW4TextBlock(kind="body", text=block))
        previous_kind = "body"
    return VipW4TextLayout(blocks=layout_blocks)


def _build_runtime_context(plan: VipW4Plan) -> str:
    return (
        "系统预计算校验值如下，你必须在内部执行时遵守，但不得把这些校验值输出到最终成稿：\n"
        f"{plan.init_line}\n"
        "额外硬约束：\n"
        f"1. 本次输入仅包含允许改写的正文段，共 {plan.paragraph_count} 段。\n"
        "2. 段落顺序不得调整，不得合并，不得拆分。\n"
        "3. 你必须在内部完成配额、自检和字数控制，但最终只输出改写后的正文段落，不得输出计划、验证、统计或说明。\n"
        "4. 段落之间保留一个空行。"
    )


def _build_retry_prompt(*, plan: VipW4Plan, previous_output: str, issues: list[str]) -> str:
    issue_text = "；".join(item for item in issues if item) or "最终输出未通过系统校验"
    return (
        "你上一轮的维普 W4 输出未通过系统校验，必须重新执行内部改写流程并修正错误。\n"
        f"错误原因：{issue_text}\n"
        f"必须继续满足：{plan.init_line}\n"
        "最终段落数必须与原文正文段数完全一致，只允许输出干净正文，不得混入计划、验证、通过提示或任何说明。\n"
        "以下是你上一轮的原始输出，仅供修正参考：\n"
        f"{previous_output}"
    )


def _extract_final_text(raw_output: str, *, plan: VipW4Plan) -> tuple[str, int]:
    text = str(raw_output or "").strip()
    matches = list(_FINAL_HEADER_RE.finditer(text))
    if matches:
        match = matches[-1]
        reported_total = int(match.group(1))
        final_text = clean_llm_user_facing_text(text[match.end() :].strip())
        if not final_text:
            raise BizError(code=4636, message="维普 W4 最终改写文为空")
        return final_text, reported_total
    fallback_text, fallback_total = _extract_fallback_final_text(text, plan=plan)
    if fallback_text:
        return fallback_text, fallback_total
    raise BizError(code=4636, message="维普 W4 未输出最终完成头")


def _split_rewritten_paragraphs(text: str) -> list[str]:
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    blocks = [item.strip() for item in re.split(r"\n\s*\n", normalized) if item and item.strip()]
    if len(blocks) <= 1:
        blocks = [line.strip() for line in normalized.splitlines() if line.strip()]
    return blocks


def _extract_fallback_final_text(raw_output: str, *, plan: VipW4Plan) -> tuple[str, int]:
    paragraph_results = _extract_paragraph_results(raw_output)
    if len(paragraph_results) == plan.paragraph_count:
        reported_total = _sum_validation_rewrites(raw_output)
        if reported_total <= 0:
            reported_total = max(plan.total_quota, plan.paragraph_count)
        return "\n\n".join(paragraph_results).strip(), reported_total
    cleaned_output = _clean_runtime_output_text(raw_output)
    if not cleaned_output:
        return "", 0
    reported_total = _sum_validation_rewrites(raw_output)
    if reported_total <= 0:
        reported_total = max(plan.total_quota, plan.paragraph_count)
    return cleaned_output, reported_total


def _extract_paragraph_results(raw_output: str) -> list[str]:
    pattern = re.compile(
        r"【P[_\s]?\d+\s*改写结果(?:（修订版）)?】\s*(.*?)\s*(?=【P[_\s]?\d+\s*验证】|【P[_\s]?\d+\s*改写计划|===\s*改写完成|\Z)",
        flags=re.DOTALL,
    )
    results: list[str] = []
    for match in pattern.finditer(str(raw_output or "")):
        paragraph_text = clean_llm_user_facing_text(match.group(1).strip())
        if paragraph_text:
            results.append(paragraph_text)
    return results


def _clean_runtime_output_text(raw_output: str) -> str:
    lines: list[str] = []
    for raw_line in str(raw_output or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            lines.append("")
            continue
        if re.match(r"^【初始化】", line):
            continue
        if re.match(r"^【P[_\s]?\d+\s*改写计划", line):
            continue
        if re.match(r"^【P[_\s]?\d+\s*改写结果", line):
            continue
        if re.match(r"^【P[_\s]?\d+\s*验证】", line):
            continue
        if re.match(r"^\d+\.\s", line):
            continue
        if line.startswith("===") and "改写完成" in line:
            continue
        cleaned_line = _strip_process_markers(raw_line.rstrip())
        if cleaned_line:
            lines.append(cleaned_line)
    cleaned = clean_llm_user_facing_text("\n".join(lines))
    return cleaned.strip()


def _normalize_rewritten_paragraphs(text: str, *, plan: VipW4Plan) -> list[str]:
    paragraphs = _split_rewritten_paragraphs(text)
    if len(paragraphs) == plan.paragraph_count:
        return paragraphs
    if plan.paragraph_count <= 1:
        merged = clean_llm_user_facing_text("\n".join(paragraphs or [text]).strip())
        return [merged] if merged else []
    merged_text = clean_llm_user_facing_text("\n".join(paragraphs or [text]).strip())
    if not merged_text:
        return []
    return _redistribute_text_to_expected_paragraphs(merged_text, plan=plan)


def _redistribute_text_to_expected_paragraphs(text: str, *, plan: VipW4Plan) -> list[str]:
    normalized = str(text or "").strip()
    if not normalized:
        return []
    total_length = sum(max(item.char_count, 1) for item in plan.paragraphs)
    if total_length <= 0:
        return [normalized]
    cursor = 0
    assigned_length = 0
    output: list[str] = []
    for index, item in enumerate(plan.paragraphs):
        if index == len(plan.paragraphs) - 1:
            chunk = normalized[cursor:].strip()
        else:
            assigned_length += max(item.char_count, 1)
            target_end = round(len(normalized) * assigned_length / total_length)
            target_end = max(cursor, min(len(normalized), target_end))
            split_at = normalized.rfind("。", cursor, target_end)
            if split_at == -1 or split_at <= cursor:
                split_at = normalized.rfind("\n", cursor, target_end)
            if split_at != -1 and split_at + 1 < len(normalized):
                target_end = split_at + 1
            chunk = normalized[cursor:target_end].strip()
            cursor = target_end
        output.append(chunk or item.text)
    return output


def _sum_validation_rewrites(raw_output: str) -> int:
    matches = re.findall(r"【P[_\s]?\d+\s*验证】实际完成\s*(\d+)\s*处改写", str(raw_output or ""))
    return sum(int(item) for item in matches if str(item).isdigit())


def _repair_vip_w4_paragraph(text: str) -> str:
    output = _strip_process_markers(str(text or "").strip())
    output = output.replace("重要的", "主要的")
    output = output.replace("重要作用", "主要作用")
    output = output.replace("重要意义", "主要意义")
    output = re.sub(r"(进行|实施|开展)(理念|观念|本质)", r"强调\2", output)
    output = re.sub(r"\b当前\b", "目前", output)
    output = re.sub(r"\b机制\b", "方式", output)
    output = re.sub(r"\b路径\b", "途径", output)
    return output.strip()


def _validate_vip_w4_output(
    *,
    plan: VipW4Plan,
    original_paragraphs: list[str],
    rewritten_paragraphs: list[str],
    reported_total: int,
) -> None:
    if len(rewritten_paragraphs) != plan.paragraph_count:
        raise BizError(code=4636, message="维普 W4 最终正文为空或无法按段恢复")
    original_total = sum(count_billable_chars(item) for item in original_paragraphs)
    rewritten_total = sum(count_billable_chars(item) for item in rewritten_paragraphs)
    if original_total > 0 and rewritten_total < original_total * _MIN_OUTPUT_LENGTH_RATIO:
        raise BizError(code=4636, message="维普 W4 最终正文长度异常缩水")
    for original, rewritten, quota in zip(original_paragraphs, rewritten_paragraphs, plan.paragraphs):
        if count_billable_chars(rewritten) <= 0:
            raise BizError(code=4636, message=f"维普 W4 P{quota.index} 输出为空")
        if _contains_process_markers(rewritten):
            raise BizError(code=4636, message=f"维普 W4 P{quota.index} 混入过程控制文本")
        if original == rewritten:
            continue


def _contains_forbidden_style_floor(text: str) -> bool:
    content = str(text or "")
    for token in _STYLE_FLOOR_FORBIDDEN:
        if token in {"拿", "搞", "弄"}:
            if re.search(rf"(?<![A-Za-z]){token}(?![A-Za-z])", content):
                return True
            continue
        if token in content:
            return True
    return False


def _within_length_delta(source_length: int, rewritten_length: int) -> bool:
    if source_length <= 0:
        return rewritten_length <= 0
    delta_ratio = abs(rewritten_length - source_length) / max(source_length, 1)
    return delta_ratio <= 0.05


def _ensure_protected_fragments(source_text: str, rewritten_text: str, *, paragraph_index: int) -> None:
    protected_tokens = set(re.findall(r"\d+(?:\.\d+)?%?|\b[A-Za-z][A-Za-z0-9_-]*\b|“[^”]+”|\"[^\"]+\"|'[^']+'", str(source_text or "")))
    for token in protected_tokens:
        if token and token not in rewritten_text:
            raise BizError(code=4636, message=f"维普 W4 P{paragraph_index} 丢失受保护片段：{token}")


def _is_reference_heading(text: str) -> bool:
    normalized = re.sub(r"\s+", "", str(text or ""))
    return normalized in _REFERENCE_HEADINGS


def _classify_preserved_text_block(text: str, *, index: int, previous_kind: str) -> str | None:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    if not lines:
        return "blank"
    if any(("｜" in line or "|" in line) for line in lines):
        return "table"
    if len(lines) == 1:
        content = lines[0]
        normalized = re.sub(r"\s+", "", content)
        if index == 0 and len(content) <= 48 and not re.search(r"[。！？；;:：]", content):
            return "title"
        if previous_kind in {"title", "subtitle"} and index <= 2:
            if content.startswith(("——", "—", "--", "-", "副标题")) or (
                len(content) <= 48 and not re.search(r"[。！？；;:：]", content)
            ):
                return "subtitle"
        if any(content.startswith(prefix) for prefix in _KEYWORD_PREFIXES):
            return "keyword_heading"
        if normalized in _PRESERVED_FRONT_HEADINGS:
            return "front_heading"
        if previous_kind == "keyword_heading" and len(content) <= 120 and any(token in content for token in ("；", ";", "、", "，")):
            return "keyword_body"
        if re.match(r"^(图|表)\s*[0-9一二三四五六七八九十]+", content):
            return "caption"
        if len(content) <= 28 and not re.search(r"[。！？；;:：]", content):
            if re.match(r"^([一二三四五六七八九十]+[、.．]|第[一二三四五六七八九十百零0-9]+[章节部分篇]|[（(][一二三四五六七八九十百零0-9]+[)）])", content):
                return "heading"
    return None


def _strip_process_markers(text: str) -> str:
    output = str(text or "")
    for pattern in _PROCESS_MARKER_PATTERNS:
        output = re.sub(pattern, "", output, flags=re.IGNORECASE)
    output = re.sub(r"\s*→\s*$", "", output)
    return clean_llm_user_facing_text(output).strip()


def _contains_process_markers(text: str) -> bool:
    content = str(text or "")
    return any(re.search(pattern, content, flags=re.IGNORECASE) for pattern in _PROCESS_MARKER_PATTERNS)
