from __future__ import annotations

import json
import re

from app.exceptions import BizError
from app.models import TaskType
from app.services.llm_service import generate_with_llm
from app.services.processing_text_tools import split_sentences


WP2_MECHANISM_KEYS = (
    "M1动词叠加",
    "M2名词叠加",
    "M3功能词并置",
    "M4进行化",
    "M5字符融合",
)


def split_chunk_by_sentence_boundary(chunk: str, *, max_chars: int) -> list[str]:
    if len(chunk) <= max_chars:
        return [chunk]
    sentences = split_sentences(chunk)
    if len(sentences) <= 1:
        return [chunk[i : i + max_chars] for i in range(0, len(chunk), max_chars)]
    outputs: list[str] = []
    current = ""
    for sentence, punct in sentences:
        piece = f"{sentence}{punct}"
        candidate = f"{current}{piece}" if current else piece
        if current and len(candidate) > max_chars:
            outputs.append(current)
            current = piece
        else:
            current = candidate
    if current:
        outputs.append(current)
    return outputs


def chunk_text_by_semantic_units(text: str, *, min_chars: int, max_chars: int) -> list[str]:
    content = str(text or "")
    if not content.strip():
        return [content]
    paragraphs = content.splitlines()
    chunks: list[str] = []
    current = ""
    for raw_paragraph in paragraphs:
        paragraph = raw_paragraph.strip()
        if not paragraph:
            if current:
                chunks.extend(split_chunk_by_sentence_boundary(current, max_chars=max_chars))
                current = ""
            chunks.append("")
            continue
        if not current:
            current = paragraph
            continue
        candidate = f"{current}\n{paragraph}"
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if len(current) < min_chars:
            current = candidate
            if len(current) > max_chars:
                chunks.extend(split_chunk_by_sentence_boundary(current, max_chars=max_chars))
                current = ""
            continue
        chunks.extend(split_chunk_by_sentence_boundary(current, max_chars=max_chars))
        current = paragraph
    if current:
        chunks.extend(split_chunk_by_sentence_boundary(current, max_chars=max_chars))
    return chunks


def merge_semantic_chunks(original_chunks: list[str], rewritten_chunks: list[str]) -> str:
    merged: list[str] = []
    total = max(len(original_chunks), len(rewritten_chunks))
    for index in range(total):
        candidate = rewritten_chunks[index] if index < len(rewritten_chunks) else ""
        if candidate == "" and index < len(original_chunks) and original_chunks[index] == "":
            merged.append("")
            continue
        merged.append(candidate)
    return "\n".join(merged).strip()


def extract_json_payload(raw: str) -> dict | None:
    text = str(raw or "").strip()
    if not text:
        return None
    candidates = [text]
    fenced = re.findall(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
    if fenced:
        candidates = [item.strip() for item in fenced if str(item).strip()] + candidates
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        candidates.insert(0, match.group(0))
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except Exception:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def generate_json_payload(
    db,
    *,
    prompt: str,
    task_type: TaskType,
    error_code: int,
    error_message: str,
) -> dict:
    raw = generate_with_llm(db, task_type=task_type, text=prompt)
    last_raw = str(raw or "").strip()
    payload = extract_json_payload(last_raw)
    if isinstance(payload, dict):
        return payload
    preview = re.sub(r"\s+", " ", last_raw)[:160]
    raise BizError(code=error_code, message=f"{error_message}，响应片段：{preview or 'empty'}")


def parse_ratio_percent(value: str) -> float | None:
    text = str(value or "").strip()
    match = re.search(r"([+-]?\d+(?:\.\d+)?)\s*%", text)
    if not match:
        return None
    try:
        return float(match.group(1)) / 100.0
    except ValueError:
        return None


def _is_json_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _normalize_additive_style(value, *, error_code: int, stage_label: str) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"true", "叠加", "是", "yes", "additive"}:
        return True
    if text in {"false", "纯替换", "否", "no", "replace"}:
        return False
    raise BizError(code=error_code, message=f"{stage_label} additive_style 不符合WP2")


def validate_wp2_prompt_b_payload(payload: dict, *, error_code: int, stage_label: str) -> dict:
    required_keys = {
        "semantic_ok",
        "expansion_ratio",
        "expansion_ok",
        "additive_style",
        "readability_ok",
        "mechanism_distribution",
        "issues",
        "verdict",
    }
    if set(payload.keys()) != required_keys:
        raise BizError(code=error_code, message=f"{stage_label} JSON字段不符合WP2")
    for key in ("semantic_ok", "expansion_ok", "readability_ok"):
        if not isinstance(payload.get(key), bool):
            raise BizError(code=error_code, message=f"{stage_label} 字段 {key} 不符合WP2")
    if not isinstance(payload.get("expansion_ratio"), str):
        raise BizError(code=error_code, message=f"{stage_label} expansion_ratio 不符合WP2")
    mechanism_distribution = payload.get("mechanism_distribution")
    if not isinstance(mechanism_distribution, dict):
        raise BizError(code=error_code, message=f"{stage_label} mechanism_distribution 不符合WP2")
    if set(mechanism_distribution.keys()) != set(WP2_MECHANISM_KEYS):
        raise BizError(code=error_code, message=f"{stage_label} mechanism_distribution 键不符合WP2")
    for key in WP2_MECHANISM_KEYS:
        if not _is_json_number(mechanism_distribution.get(key)):
            raise BizError(code=error_code, message=f"{stage_label} mechanism_distribution.{key} 不符合WP2")
    issues = payload.get("issues")
    if not isinstance(issues, list):
        raise BizError(code=error_code, message=f"{stage_label} issues 不符合WP2")
    for item in issues:
        if not isinstance(item, dict):
            raise BizError(code=error_code, message=f"{stage_label} issues 项不符合WP2")
        if set(item.keys()) != {"location", "type", "detail"}:
            raise BizError(code=error_code, message=f"{stage_label} issues 字段不符合WP2")
    verdict = str(payload.get("verdict") or "").strip().lower()
    if verdict not in {"pass", "fail"}:
        raise BizError(code=error_code, message=f"{stage_label} verdict 不符合WP2")
    normalized = dict(payload)
    normalized["additive_style"] = _normalize_additive_style(
        payload.get("additive_style"),
        error_code=error_code,
        stage_label=stage_label,
    )
    return normalized


def wp2_prompt_b_passed(payload: dict) -> bool:
    verdict = str(payload.get("verdict") or "").strip().lower()
    expansion_ratio = parse_ratio_percent(payload.get("expansion_ratio"))
    hard_expansion_ok = expansion_ratio is None or 0.10 <= expansion_ratio <= 0.40
    return (
        verdict == "pass"
        and bool(payload.get("semantic_ok"))
        and bool(payload.get("readability_ok"))
        and bool(payload.get("additive_style"))
        and hard_expansion_ok
    )
