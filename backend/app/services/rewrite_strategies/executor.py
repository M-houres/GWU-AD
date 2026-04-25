from __future__ import annotations

from app.services.processing_text_tools import merge_short_sentences, soften_connective_prefixes, split_sentences
from app.exceptions import BizError
from app.models import Task, TaskType
from app.services.rewrite_strategies.config import STRATEGY_ALGORITHM, STRATEGY_LLM, get_active_rewrite_strategy
from app.services.rewrite_strategies.validators import adjust_to_target_length
from app.services.rewrite_strategies.validators import validate_rewrite_output
from app.utils import count_billable_chars


def execute_rewrite_strategy(
    db,
    *,
    task: Task | None,
    platform: str,
    text: str,
    report_summary: dict | None = None,
) -> dict:
    normalized_platform = str(platform or "").strip().lower()
    if normalized_platform not in {"cnki", "vip"}:
        raise BizError(code=4116, message="不支持的平台")

    strategy = get_active_rewrite_strategy(db, platform=normalized_platform)
    if strategy != STRATEGY_LLM:
        raise BizError(code=4119, message="降AIGC率链路已冻结为大模型策略")

    if normalized_platform == "cnki":
        from app.services.rewrite_strategies.cnki_llm import rewrite
    elif normalized_platform == "vip":
        from app.services.rewrite_strategies.vip_llm import rewrite
    else:
        raise BizError(code=4119, message="降AIGC率策略配置不支持")

    rewrite_result = rewrite(db, task=task, text=text, report_summary=report_summary or {})
    output = str(rewrite_result.get("text") or "") if isinstance(rewrite_result, dict) else str(rewrite_result or "")
    rule_trace = rewrite_result.get("rule_trace") if isinstance(rewrite_result, dict) else {}
    if normalized_platform == "cnki":
        strict_result = _build_cnki_strict_rewrite_result(
            source_text=text,
            output=output,
            rule_trace=rule_trace or {},
        )
        return {
            "rewritten_text": strict_result["text"],
            "strategy": strategy,
            "platform": normalized_platform,
            "task_type": TaskType.REWRITE.value,
            "length_before": strict_result["length_before"],
            "length_after": strict_result["length_after"],
            "change_ratio": strict_result["change_ratio"],
            "quality_score": strict_result["quality_score"],
            "quality_flags": strict_result["quality_flags"],
            "warnings": strict_result["warnings"],
            "rule_trace": strict_result["rule_trace"],
        }
    if normalized_platform == "vip":
        strict_result = _build_vip_strict_rewrite_result(
            source_text=text,
            output=output,
            rule_trace=rule_trace or {},
        )
        return {
            "rewritten_text": strict_result["text"],
            "strategy": strategy,
            "platform": normalized_platform,
            "task_type": TaskType.REWRITE.value,
            "length_before": strict_result["length_before"],
            "length_after": strict_result["length_after"],
            "change_ratio": strict_result["change_ratio"],
            "quality_score": strict_result["quality_score"],
            "quality_flags": strict_result["quality_flags"],
            "warnings": strict_result["warnings"],
            "rule_trace": strict_result["rule_trace"],
        }

    validation = _select_rewrite_candidate(
        db,
        task=task,
        platform=normalized_platform,
        strategy=strategy,
        source_text=text,
        report_summary=report_summary or {},
        output=output,
        rule_trace=rule_trace or {},
    )
    return {
        "rewritten_text": validation.text,
        "strategy": strategy,
        "platform": normalized_platform,
        "task_type": TaskType.REWRITE.value,
        "length_before": validation.length_before,
        "length_after": validation.length_after,
        "change_ratio": validation.change_ratio,
        "quality_score": validation.quality_score,
        "quality_flags": validation.quality_flags,
        "warnings": validation.warnings,
        "rule_trace": validation.rule_trace,
    }


def _select_rewrite_candidate(
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
    if output.strip():
        candidates.append((output, dict(rule_trace or {})))

    if platform not in {"cnki", "vip"}:
        normalized_output, normalized_trace = _style_normalize_rewrite_output(
            platform=platform,
            source_text=source_text,
            output=output,
        )
        if normalized_output.strip() and normalized_output != output:
            candidates.append((normalized_output, _merge_rule_trace(rule_trace, normalized_trace)))

    last_error: Exception | None = None
    best_validation = None
    best_rank = (-1.0, -1.0)
    for candidate_output, candidate_trace in candidates:
        try:
            validation = validate_rewrite_output(
                platform=platform,
                source_text=source_text,
                rewritten_text=candidate_output,
                rule_trace=candidate_trace,
            )
        except Exception as exc:  # pragma: no cover - selection intentionally tolerates bad candidates
            last_error = exc
            continue
        target_ratio = 0.25 if platform == "vip" else 0.06
        rank = (
            float(getattr(validation, "quality_score", 0.0)),
            -float(abs(getattr(validation, "change_ratio", 0.0) - target_ratio)),
        )
        if best_validation is None or rank > best_rank:
            best_validation = validation
            best_rank = rank
    if best_validation is not None:
        return best_validation
    if last_error is not None:
        raise last_error
    raise BizError(code=4611, message="降AIGC率策略输出为空")


def _build_cnki_strict_rewrite_result(*, source_text: str, output: str, rule_trace: dict) -> dict:
    text = str(output or "").strip()
    if not text:
        raise BizError(code=4611, message="知网降AIGC率严格 V16 输出为空")
    prompt_b = dict(rule_trace.get("prompt_b_validation") or {})
    length_before = count_billable_chars(str(source_text or ""))
    length_after = count_billable_chars(text)
    change_ratio = round((length_after - length_before) / length_before, 4) if length_before > 0 else 0.0
    return {
        "text": text,
        "length_before": length_before,
        "length_after": length_after,
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


def _build_vip_strict_rewrite_result(*, source_text: str, output: str, rule_trace: dict) -> dict:
    text = str(output or "").strip()
    if not text:
        raise BizError(code=4611, message="维普降AIGC率严格 WP2 输出为空")
    prompt_b = dict(rule_trace.get("prompt_b_validation") or {})
    length_before = count_billable_chars(str(source_text or ""))
    length_after = count_billable_chars(text)
    change_ratio = round((length_after - length_before) / length_before, 4) if length_before > 0 else 0.0
    return {
        "text": text,
        "length_before": length_before,
        "length_after": length_after,
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


def _style_normalize_rewrite_output(*, platform: str, source_text: str, output: str) -> tuple[str, dict]:
    content = str(output or "").strip()
    if not content:
        return content, {}
    applied_rules: list[str] = []
    softened = soften_connective_prefixes(content)
    if softened != content:
        content = softened
        applied_rules.append("style_normalize:soften_connective_prefixes")
    sentences = split_sentences(content)
    if len(sentences) >= 4:
        avg_len = sum(len(sentence) for sentence, _ in sentences) / len(sentences)
        if platform == "vip" and avg_len < 18:
            merged = merge_short_sentences(content, max_sentence_length=18, merge_limit=2)
            if merged != content:
                content = merged
                applied_rules.append("style_normalize:merge_short_sentences:18")
        if platform == "cnki" and avg_len < 20:
            merged = merge_short_sentences(content, max_sentence_length=20, merge_limit=3)
            if merged != content:
                content = merged
                applied_rules.append("style_normalize:merge_short_sentences:20")
    if not applied_rules:
        return content, {}
    return content, {
        "style_normalized": True,
        "applied_rules": applied_rules,
    }


def _merge_rule_trace(base: dict | None, extra: dict | None) -> dict:
    merged = dict(base or {})
    if not extra:
        return merged
    for key, value in extra.items():
        if key == "applied_rules":
            merged[key] = [*(merged.get(key) or []), *(value or [])]
            continue
        if key == "protected_hits":
            merged[key] = sorted(set([*(merged.get(key) or []), *(value or [])]))
            continue
        merged[key] = value
    return merged
