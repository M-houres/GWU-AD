from __future__ import annotations

from app.exceptions import BizError
from app.models import Task, TaskType
from app.services.cnki_v5_prompt import build_cnki_v5_prompt
from app.services.llm_service import generate_with_llm
from app.services.processing_text_tools import split_sentences
from app.services.rewrite_strategies.assets import CNKI_ASSETS, CNKI_SYNONYMS
from app.services.rewrite_strategies.config import get_rewrite_runtime_config
from app.services.rewrite_strategies.cnki_rule_rewrite import rewrite as algorithm_rewrite
from app.services.rewrite_strategies.validators import validate_rewrite_output
from app.services.rewrite_strategies.validators import adjust_to_target_length


_CNKI_RULE_LIBRARY_SIZE = len(CNKI_SYNONYMS)


def _split_chunk_by_sentence_boundary(chunk: str, *, max_chars: int) -> list[str]:
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


def _chunk_text_by_semantic_units(text: str, *, min_chars: int, max_chars: int) -> list[str]:
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
                chunks.extend(_split_chunk_by_sentence_boundary(current, max_chars=max_chars))
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
                chunks.extend(_split_chunk_by_sentence_boundary(current, max_chars=max_chars))
                current = ""
            continue
        chunks.extend(_split_chunk_by_sentence_boundary(current, max_chars=max_chars))
        current = paragraph
    if current:
        chunks.extend(_split_chunk_by_sentence_boundary(current, max_chars=max_chars))
    return chunks


def _merge_semantic_chunks(original_chunks: list[str], rewritten_chunks: list[str]) -> str:
    merged: list[str] = []
    total = max(len(original_chunks), len(rewritten_chunks))
    for index in range(total):
        candidate = rewritten_chunks[index] if index < len(rewritten_chunks) else ""
        if candidate == "" and index < len(original_chunks) and original_chunks[index] == "":
            merged.append("")
            continue
        merged.append(candidate)
    return "\n".join(merged).strip()


def _prompt(
    text: str,
    *,
    chunk_index: int = 1,
    chunk_total: int = 1,
) -> str:
    return build_cnki_v5_prompt(
        text,
        mode="rewrite",
        chunk_index=chunk_index,
        chunk_total=chunk_total,
        rule_library_size=_CNKI_RULE_LIBRARY_SIZE,
    )


def rewrite(db, *, task: Task | None, text: str, report_summary: dict | None = None) -> dict:
    runtime = get_rewrite_runtime_config(db, platform="cnki")
    content = str(text or "")
    single_pass_max_chars = max(2000, int(runtime.get("llm_single_pass_max_chars", 6000) or 6000))
    if len(content) <= single_pass_max_chars:
        chunks = [content]
        technical_chunking = False
    else:
        chunk_min = max(240, int(runtime.get("chunk_min_chars", getattr(CNKI_ASSETS, "chunk_min_chars", 180) or 180)))
        chunk_max = max(1200, int(runtime.get("chunk_max_chars", getattr(CNKI_ASSETS, "chunk_max_chars", 260) or 260)))
        chunk_max = max(chunk_max, chunk_min + 40)
        chunks = _chunk_text_by_semantic_units(content, min_chars=chunk_min, max_chars=chunk_max)
        technical_chunking = True
    non_empty_chunks = [item for item in chunks if item.strip()]
    chunk_total = len(non_empty_chunks)

    try:
        rewritten_chunks: list[str] = []
        chunk_cursor = 0
        for chunk in chunks:
            if not chunk.strip():
                rewritten_chunks.append(chunk)
                continue
            chunk_cursor += 1
            output = generate_with_llm(
                db,
                task_type=TaskType.REWRITE,
                text=_prompt(
                    chunk,
                    chunk_index=chunk_cursor,
                    chunk_total=max(chunk_total, 1),
                ),
            )
            chunk_output = str(output or "").strip() or chunk
            rewritten_chunks.append(chunk_output)

        output = _merge_semantic_chunks(chunks, rewritten_chunks)
        output = adjust_to_target_length(output, source_text=text, platform="cnki")
        rule_trace = {
            "mode": "llm_prompt_technical_chunking" if technical_chunking else "llm_prompt_global",
            "applied_rules": ["llm:cnki_prompt:technical_chunking" if technical_chunking else "llm:cnki_prompt:single_pass"],
            "protected_hits": [],
            "strategy_version": "cnki_v5_llm_chunked",
            "chunk_count": chunk_total,
            "technical_chunking": technical_chunking,
            "single_pass_max_chars": single_pass_max_chars,
            "runtime": runtime,
            "template_library_size": len(CNKI_ASSETS.templates),
        }
    except Exception:
        fallback = algorithm_rewrite(db, task=task, text=text, report_summary=report_summary)
        trace = dict(fallback.get("rule_trace") or {})
        trace["llm_fallback"] = True
        trace["fallback_reason"] = "llm_exception"
        return {"text": fallback.get("text") or "", "rule_trace": trace}

    try:
        validation = validate_rewrite_output(
            platform="cnki",
            source_text=text,
            rewritten_text=output,
            rule_trace=rule_trace,
        )
        score = float(validation.quality_score)
    except BizError:
        score = -1.0

    if output.strip() and score >= 0.75:
        return {"text": output, "rule_trace": rule_trace}

    fallback = algorithm_rewrite(db, task=task, text=text, report_summary=report_summary)
    trace = dict(fallback.get("rule_trace") or {})
    trace["llm_fallback"] = True
    trace["fallback_reason"] = "quality_gate_not_passed"
    trace["llm_candidate_count"] = 1
    trace["llm_best_score"] = round(score, 4) if score >= 0 else 0.0
    return {"text": fallback.get("text") or "", "rule_trace": trace}
