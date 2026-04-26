from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable

from app.exceptions import BizError
from app.models import TaskType
from app.services.llm_service import generate_with_llm, load_llm_config
from app.services.processing_text_tools import clean_llm_user_facing_text
from app.utils import count_billable_chars

_REFERENCE_HEADINGS = {"参考文献", "参考文献:", "参考文献：", "references", "REFERENCES"}
_KEYWORD_PREFIXES = ("关键词：", "关键词:", "关键字：", "关键字:")
_PRESERVED_FRONT_HEADINGS = {
    "摘要",
    "摘要:",
    "摘要：",
    "【摘要】",
    "引言",
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
    "Abstract",
    "ABSTRACT",
}
_PROCESS_PREFIXES = (
    "改写：",
    "改写:",
    "输出：",
    "输出:",
    "结果：",
    "结果:",
    "重写：",
    "重写:",
)


@dataclass
class CnkiPipelineRunResult:
    text: str
    paragraph_count: int
    total_chars: int
    llm_provider: str
    llm_model: str


@dataclass
class CnkiTextRunResult:
    text: str
    run: CnkiPipelineRunResult


@dataclass
class CnkiTextBlock:
    kind: str
    text: str


@dataclass
class CnkiTextLayout:
    blocks: list[CnkiTextBlock]

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


def execute_cnki_text_pipeline(
    db,
    *,
    task_type: TaskType,
    source_text: str,
    prompt_builder: Callable[[str], str],
    pipeline_label: str,
    empty_message: str,
) -> CnkiTextRunResult:
    layout = build_cnki_text_layout(source_text)
    if not layout.body_paragraphs:
        raise BizError(code=4621, message=empty_message)
    run = execute_cnki_paragraph_pipeline(
        db,
        task_type=task_type,
        paragraphs=layout.body_paragraphs,
        prompt_builder=prompt_builder,
        pipeline_label=pipeline_label,
        empty_message=empty_message,
    )
    rebuilt = layout.rebuild(split_rewritten_paragraphs(run.text))
    return CnkiTextRunResult(text=rebuilt, run=run)


def execute_cnki_paragraph_pipeline(
    db,
    *,
    task_type: TaskType,
    paragraphs: list[str],
    prompt_builder: Callable[[str], str],
    pipeline_label: str,
    empty_message: str,
) -> CnkiPipelineRunResult:
    cleaned_paragraphs = [str(item or "").strip() for item in paragraphs if str(item or "").strip()]
    if not cleaned_paragraphs:
        raise BizError(code=4621, message=empty_message)
    llm_cfg = load_llm_config(db)
    rewritten: list[str] = []
    for index, paragraph in enumerate(cleaned_paragraphs, start=1):
        prompt = prompt_builder(paragraph)
        raw_output = str(generate_with_llm(db, task_type=task_type, text=prompt) or "").strip()
        normalized = normalize_cnki_paragraph_output(raw_output)
        if not normalized:
            raise BizError(code=4621, message=f"{pipeline_label} 第 {index} 段输出为空")
        rewritten.append(normalized)
    return CnkiPipelineRunResult(
        text="\n\n".join(rewritten).strip(),
        paragraph_count=len(rewritten),
        total_chars=sum(count_billable_chars(item) for item in cleaned_paragraphs),
        llm_provider=str(llm_cfg.get("provider") or ""),
        llm_model=str(llm_cfg.get("model") or ""),
    )


def build_cnki_text_layout(source_text: str) -> CnkiTextLayout:
    normalized = str(source_text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return CnkiTextLayout(blocks=[])
    raw_blocks = re.split(r"\n\s*\n", normalized)
    blocks = [item.strip() for item in raw_blocks if item and item.strip()]
    if len(blocks) == 1:
        blocks = [line.strip() for line in normalized.splitlines() if line.strip()]
    layout_blocks: list[CnkiTextBlock] = []
    in_reference_section = False
    previous_kind = ""
    for index, block in enumerate(blocks):
        if in_reference_section:
            layout_blocks.append(CnkiTextBlock(kind="preserved", text=block))
            previous_kind = "reference_body"
            continue
        if is_reference_heading(block):
            in_reference_section = True
            layout_blocks.append(CnkiTextBlock(kind="preserved", text=block))
            previous_kind = "reference_heading"
            continue
        preserved_kind = classify_preserved_text_block(block, index=index, previous_kind=previous_kind)
        if preserved_kind:
            layout_blocks.append(CnkiTextBlock(kind="preserved", text=block))
            previous_kind = preserved_kind
            continue
        layout_blocks.append(CnkiTextBlock(kind="body", text=block))
        previous_kind = "body"
    return CnkiTextLayout(blocks=layout_blocks)


def split_rewritten_paragraphs(text: str) -> list[str]:
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    blocks = [item.strip() for item in re.split(r"\n\s*\n", normalized) if item and item.strip()]
    if len(blocks) <= 1:
        blocks = [line.strip() for line in normalized.splitlines() if line.strip()]
    return blocks


def normalize_cnki_paragraph_output(text: str) -> str:
    content = clean_llm_user_facing_text(str(text or "").strip())
    if not content:
        return ""
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        return ""
    merged = "".join(lines)
    for prefix in _PROCESS_PREFIXES:
        if merged.startswith(prefix):
            merged = merged[len(prefix) :].lstrip()
    merged = merged.strip().strip('"').strip("'").strip()
    return merged


def is_reference_heading(text: str) -> bool:
    normalized = re.sub(r"\s+", "", str(text or ""))
    return normalized in _REFERENCE_HEADINGS


def classify_preserved_text_block(text: str, *, index: int, previous_kind: str) -> str | None:
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
