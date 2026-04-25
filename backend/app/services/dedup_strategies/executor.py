from __future__ import annotations

from difflib import SequenceMatcher

from app.exceptions import BizError
from app.models import Task, TaskType
from app.services.dedup_strategies.config import get_active_dedup_strategy
from app.services.dedup_strategies.validators import validate_dedup_output
from app.utils import count_billable_chars


STRATEGY_LLM = "llm"


def execute_dedup_strategy(
    db,
    *,
    task: Task | None,
    platform: str,
    text: str,
    report_summary: dict | None = None,
    strategy: str = STRATEGY_LLM,
) -> dict:
    normalized_platform = str(platform or "").strip().lower()
    if normalized_platform not in {"cnki", "vip"}:
        raise BizError(code=4116, message="不支持的平台")
    normalized_strategy = get_active_dedup_strategy(db, platform=normalized_platform)
    if normalized_strategy != STRATEGY_LLM:
        raise BizError(code=4120, message="降重复率链路已冻结为大模型策略")

    if normalized_platform == "cnki":
        from app.services.dedup_strategies.cnki_llm import rewrite
    elif normalized_platform == "vip":
        from app.services.dedup_strategies.vip_llm import rewrite
    else:
        raise BizError(code=4120, message="降重复率策略配置不支持")

    rewrite_result = rewrite(db, task=task, text=text, report_summary=report_summary or {})
    output = str(rewrite_result.get("text") or "") if isinstance(rewrite_result, dict) else str(rewrite_result or "")
    rule_trace = rewrite_result.get("rule_trace") if isinstance(rewrite_result, dict) else {}
    if normalized_platform == "cnki":
        strict_result = _build_cnki_strict_dedup_result(
            source_text=text,
            output=output,
            rule_trace=rule_trace or {},
        )
        return {
            "rewritten_text": strict_result["text"],
            "strategy": normalized_strategy,
            "platform": normalized_platform,
            "task_type": TaskType.DEDUP.value,
            "length_before": strict_result["length_before"],
            "length_after": strict_result["length_after"],
            "length_delta_ratio": strict_result["length_delta_ratio"],
            "similarity_ratio": strict_result["similarity_ratio"],
            "change_ratio": strict_result["change_ratio"],
            "quality_score": strict_result["quality_score"],
            "quality_flags": strict_result["quality_flags"],
            "warnings": strict_result["warnings"],
            "rule_trace": strict_result["rule_trace"],
        }
    if normalized_platform == "vip":
        strict_result = _build_vip_strict_dedup_result(
            source_text=text,
            output=output,
            rule_trace=rule_trace or {},
        )
        return {
            "rewritten_text": strict_result["text"],
            "strategy": normalized_strategy,
            "platform": normalized_platform,
            "task_type": TaskType.DEDUP.value,
            "length_before": strict_result["length_before"],
            "length_after": strict_result["length_after"],
            "length_delta_ratio": strict_result["length_delta_ratio"],
            "similarity_ratio": strict_result["similarity_ratio"],
            "change_ratio": strict_result["change_ratio"],
            "quality_score": strict_result["quality_score"],
            "quality_flags": strict_result["quality_flags"],
            "warnings": strict_result["warnings"],
            "rule_trace": strict_result["rule_trace"],
        }
    validation = _select_dedup_candidate(
        db,
        task=task,
        platform=normalized_platform,
        strategy=normalized_strategy,
        source_text=text,
        report_summary=report_summary or {},
        output=output,
        rule_trace=rule_trace,
    )
    return {
        "rewritten_text": validation.text,
        "strategy": normalized_strategy,
        "platform": normalized_platform,
        "task_type": TaskType.DEDUP.value,
        "length_before": validation.length_before,
        "length_after": validation.length_after,
        "length_delta_ratio": validation.length_delta_ratio,
        "similarity_ratio": validation.similarity_ratio,
        "change_ratio": validation.change_ratio,
        "quality_score": validation.quality_score,
        "quality_flags": validation.quality_flags,
        "warnings": validation.warnings,
        "rule_trace": validation.rule_trace,
    }


def _select_dedup_candidate(
    db,
    *,
    task: Task | None,
    platform: str,
    strategy: str,
    source_text: str,
    report_summary: dict,
    output: str,
    rule_trace: dict,
):
    candidates: list[tuple[str, dict]] = []
    if str(output or "").strip():
        candidates.append((output, dict(rule_trace or {})))

    last_error: Exception | None = None
    best_validation = None
    best_rank = (-1.0, -1.0)
    for candidate_output, candidate_trace in candidates:
        try:
            validation = validate_dedup_output(
                platform=platform,
                source_text=source_text,
                rewritten_text=candidate_output,
                rule_trace=candidate_trace,
            )
        except Exception as exc:  # pragma: no cover - selection intentionally tolerates bad candidates
            last_error = exc
            continue
        target_ratio = 0.25 if platform == "vip" else 0.04
        rank = (
            float(getattr(validation, "quality_score", 0.0)),
            -float(abs(getattr(validation, "length_delta_ratio", 0.0) - target_ratio)),
        )
        if best_validation is None or rank > best_rank:
            best_validation = validation
            best_rank = rank
    if best_validation is not None:
        return best_validation
    if last_error is not None:
        raise last_error
    raise BizError(code=4621, message="降重复率策略输出为空")


def _build_cnki_strict_dedup_result(*, source_text: str, output: str, rule_trace: dict) -> dict:
    text = str(output or "").strip()
    if not text:
        raise BizError(code=4621, message="知网降重复率严格 V16 输出为空")
    prompt_b = dict(rule_trace.get("prompt_b_validation") or {})
    length_before = count_billable_chars(str(source_text or ""))
    length_after = count_billable_chars(text)
    length_delta_ratio = round((length_after - length_before) / length_before, 4) if length_before > 0 else 0.0
    similarity_ratio = SequenceMatcher(None, str(source_text or "")[:4000], text[:4000]).ratio()
    change_ratio = round((1 - similarity_ratio) * 100, 2)
    return {
        "text": text,
        "length_before": length_before,
        "length_after": length_after,
        "length_delta_ratio": length_delta_ratio,
        "similarity_ratio": round(similarity_ratio, 4),
        "change_ratio": change_ratio,
        "quality_score": 1.0,
        "quality_flags": {
            "strict_v16_prompt_b_passed": True,
            "semantic_ok": bool(prompt_b.get("semantic_ok", True)),
            "grammar_ok": bool(prompt_b.get("grammar_ok", True)),
            "style_ok": bool(prompt_b.get("style_ok", True)),
            "compound_ok": bool(prompt_b.get("compound_ok", True)),
            "density_ok": bool(prompt_b.get("density_ok", True)),
        },
        "warnings": [],
        "rule_trace": dict(rule_trace or {}),
    }


def _build_vip_strict_dedup_result(*, source_text: str, output: str, rule_trace: dict) -> dict:
    text = str(output or "").strip()
    if not text:
        raise BizError(code=4621, message="维普降重复率严格 WP2 输出为空")
    prompt_b = dict(rule_trace.get("prompt_b_validation") or {})
    length_before = count_billable_chars(str(source_text or ""))
    length_after = count_billable_chars(text)
    length_delta_ratio = round((length_after - length_before) / length_before, 4) if length_before > 0 else 0.0
    similarity_ratio = SequenceMatcher(None, str(source_text or "")[:4000], text[:4000]).ratio()
    change_ratio = round((1 - similarity_ratio) * 100, 2)
    return {
        "text": text,
        "length_before": length_before,
        "length_after": length_after,
        "length_delta_ratio": length_delta_ratio,
        "similarity_ratio": round(similarity_ratio, 4),
        "change_ratio": change_ratio,
        "quality_score": 1.0,
        "quality_flags": {
            "strict_wp2_prompt_b_passed": True,
            "semantic_ok": bool(prompt_b.get("semantic_ok", True)),
            "expansion_ok": bool(prompt_b.get("expansion_ok", True)),
            "additive_style": bool(prompt_b.get("additive_style", True)),
            "readability_ok": bool(prompt_b.get("readability_ok", True)),
        },
        "warnings": [],
        "rule_trace": dict(rule_trace or {}),
    }
