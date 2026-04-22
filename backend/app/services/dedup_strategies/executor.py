from __future__ import annotations

from app.exceptions import BizError
from app.models import Task, TaskType
from app.services.processing_text_tools import merge_short_sentences, soften_connective_prefixes, split_long_sentences
from app.services.strategy_style_profiles import dedup_style_profile
from app.services.dedup_strategies.assets import CNKI_DEDUP_ASSETS, VIP_DEDUP_ASSETS
from app.services.dedup_strategies.rule_engine import apply_dedup_rules
from app.services.dedup_strategies.validators import validate_dedup_output


STRATEGY_ALGORITHM = "algorithm"
STRATEGY_LLM = "llm"


def _build_fallback_output(*, platform: str, source_text: str) -> tuple[str, dict]:
    output = str(source_text or "").strip()
    if not output:
        return "", {}

    replacements = [
        ("因此", "所以"),
        ("但是", "然而"),
        ("首先", "第一"),
        ("其次", "第二"),
        ("总之", "总体来看"),
        ("可以看出", "据此可见"),
    ]
    if platform == "vip":
        replacements.extend(
            [
                ("构建", "建立"),
                ("依赖", "借助"),
            ]
        )
    else:
        replacements.extend(
            [
                ("本文认为", "本文进一步指出"),
                ("需要", "有必要"),
            ]
        )

    applied_rules: list[str] = []
    for source, target in replacements:
        if source in output:
            output = output.replace(source, target, 1)
            applied_rules.append(f"fallback_replace:{source}->{target}")

    if platform == "cnki":
        threshold = 96
        shaped = split_long_sentences(output, threshold, clause_joiner="；", min_clauses=4)
    else:
        threshold = 38
        shaped = split_long_sentences(output, threshold)
    if shaped != output:
        applied_rules.append(f"fallback_sentence_shape:split_long:{threshold}")
        output = shaped
    if not applied_rules:
        applied_rules.append("fallback_pass_through")

    return output, {
        "mode": "dedup_fallback",
        "fallback_applied": True,
        "fallback_reason": "empty_strategy_output",
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


def _style_normalize_dedup_output(*, platform: str, source_text: str, output: str) -> tuple[str, dict]:
    normalized_platform = str(platform or "").strip().lower()
    content = str(output or "").strip()
    if not content:
        return content, {}

    profile = dedup_style_profile(normalized_platform)
    if profile is None:
        return content, {}

    applied_rules: list[str] = []
    softened = soften_connective_prefixes(content)
    if softened != content:
        content = softened
        applied_rules.append("style_normalize:soften_connective_prefixes")

    source_sentence_count = max(content.count("。") + content.count("！") + content.count("？"), 1)
    avg_target_sentence_length = round(len(content) / source_sentence_count, 4)
    if (
        source_sentence_count >= 4
        and avg_target_sentence_length < profile.avg_sentence_length * 0.52
    ):
        merge_length = max(18, int(profile.avg_sentence_length * 0.42))
        merged = merge_short_sentences(content, max_sentence_length=merge_length, merge_limit=5)
        if merged != content:
            content = merged
            applied_rules.append(f"style_normalize:merge_short_sentences:{merge_length}")

    if not applied_rules:
        return content, {}
    return content, {
        "style_normalized": True,
        "applied_rules": applied_rules,
    }


def execute_dedup_strategy(
    db,
    *,
    task: Task | None,
    platform: str,
    text: str,
    report_summary: dict | None = None,
    strategy: str = STRATEGY_ALGORITHM,
) -> dict:
    normalized_platform = str(platform or "").strip().lower()
    normalized_strategy = str(strategy or STRATEGY_ALGORITHM).strip().lower()
    if normalized_platform not in {"cnki", "vip"}:
        raise BizError(code=4116, message="不支持的平台")

    if normalized_platform == "cnki" and normalized_strategy == STRATEGY_ALGORITHM:
        from app.services.dedup_strategies.cnki_algorithm import rewrite
    elif normalized_platform == "cnki" and normalized_strategy == STRATEGY_LLM:
        from app.services.dedup_strategies.cnki_llm import rewrite
    elif normalized_platform == "vip" and normalized_strategy == STRATEGY_ALGORITHM:
        from app.services.dedup_strategies.vip_algorithm import rewrite
    elif normalized_platform == "vip" and normalized_strategy == STRATEGY_LLM:
        from app.services.dedup_strategies.vip_llm import rewrite
    else:
        raise BizError(code=4120, message="降重复率策略配置不支持")

    rewrite_result = rewrite(db, task=task, text=text, report_summary=report_summary or {})
    output = str(rewrite_result.get("text") or "") if isinstance(rewrite_result, dict) else str(rewrite_result or "")
    rule_trace = rewrite_result.get("rule_trace") if isinstance(rewrite_result, dict) else {}
    if not output.strip() and str(text or "").strip():
        fallback_output, fallback_trace = _build_fallback_output(
            platform=normalized_platform,
            source_text=text,
        )
        if fallback_output.strip():
            output = fallback_output
            rule_trace = _merge_rule_trace(rule_trace, fallback_trace)
    if str(rule_trace.get("mode") or "") in {"dedup_rule_engine", "dedup_fallback"}:
        output, style_trace = _style_normalize_dedup_output(
            platform=normalized_platform,
            source_text=text,
            output=output,
        )
        rule_trace = _merge_rule_trace(rule_trace, style_trace)
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

    fallback_output, fallback_trace = _build_algorithm_fallback_candidate(
        db,
        task=task,
        platform=platform,
        source_text=source_text,
        report_summary=report_summary,
        current_strategy=strategy,
    )
    if fallback_output.strip() and not any(existing_output == fallback_output for existing_output, _ in candidates):
        candidates.append((fallback_output, _merge_rule_trace(rule_trace, fallback_trace)))

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
        rank = (
            float(getattr(validation, "quality_score", 0.0)),
            -float(abs(getattr(validation, "length_delta_ratio", 0.0) - 0.04)),
        )
        if best_validation is None or rank > best_rank:
            best_validation = validation
            best_rank = rank
    if best_validation is not None:
        return best_validation
    if last_error is not None:
        raise last_error
    raise BizError(code=4621, message="降重复率策略输出为空")


def _build_algorithm_fallback_candidate(
    db,
    *,
    task: Task | None,
    platform: str,
    source_text: str,
    report_summary: dict,
    current_strategy: str,
) -> tuple[str, dict]:
    assets = CNKI_DEDUP_ASSETS if platform == "cnki" else VIP_DEDUP_ASSETS
    fallback_output, fallback_trace = apply_dedup_rules(
        db,
        text=source_text,
        assets=assets,
        report_summary=report_summary or {},
    )
    if str(fallback_trace.get("mode") or "") in {"dedup_rule_engine", ""}:
        fallback_output, style_trace = _style_normalize_dedup_output(
            platform=platform,
            source_text=source_text,
            output=fallback_output,
        )
        fallback_trace = _merge_rule_trace(fallback_trace, style_trace)
    if not fallback_output.strip():
        return "", {}
    trace = {
        **(fallback_trace or {}),
        "mode": "dedup_rule_engine",
    }
    if current_strategy == STRATEGY_LLM:
        trace["llm_fallback"] = True
        trace["fallback_reason"] = "quality_gate_or_empty_output"
    else:
        trace["candidate_role"] = "algorithm_refresh"
    return fallback_output, trace
