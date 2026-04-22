from __future__ import annotations

import re

from app.services.processing_text_tools import (
    merge_short_sentences,
    reorder_comma_clauses,
    rewrite_academic_frames,
    rewrite_causal_chains,
    rewrite_parallel_targets,
    soften_connective_prefixes,
    split_long_sentences,
    split_sentences,
)
from app.services.strategy_style_profiles import dedup_style_profile
from app.services.rewrite_strategies.assets import PlatformAssets
from app.services.rewrite_strategies.rule_engine import (
    RewriteContext,
    _apply_cohesion,
    _apply_synonyms,
    _apply_templates,
    _protect_terms,
    _rewrite_sentence_openings,
    _polish_rewrite_output,
    _restore_terms,
)


def apply_dedup_rules(db, *, text: str, assets: PlatformAssets, report_summary: dict | None = None) -> tuple[str, dict]:
    context = RewriteContext(platform=assets.platform, report_summary=report_summary or {})
    protected_text, placeholders = _protect_terms(text, assets, context)
    output = _apply_synonyms(protected_text, assets, context)
    output = _apply_templates(output, assets, context)
    output = _apply_dedup_sentence_shape(output, assets, context)
    output = _apply_cohesion(output, assets, context)
    output = _restore_terms(output, placeholders)
    output = _polish_rewrite_output(output, context)
    return output, {
        "mode": "dedup_rule_engine",
        "applied_rules": context.applied_rules,
        "protected_hits": sorted(set(context.protected_hits)),
    }


def _apply_dedup_sentence_shape(text: str, assets: PlatformAssets, context: RewriteContext) -> str:
    pressure = (context.report_summary or {}).get("pressure")
    profile = dedup_style_profile(assets.platform)
    if assets.platform == "cnki":
        base_threshold = 96 if pressure == "high" else 132
        profile_threshold = int(profile.avg_sentence_length * 1.8) if profile is not None else base_threshold
        threshold = max(88, min(base_threshold, profile_threshold))
        output = split_long_sentences(text, threshold, clause_joiner="；", min_clauses=4)
    else:
        base_threshold = 38 if pressure == "high" else 48
        profile_threshold = int(profile.avg_sentence_length * 0.78) if profile is not None else base_threshold
        threshold = max(34, min(base_threshold, profile_threshold))
        output = split_long_sentences(text, threshold)
    if output != text:
        context.applied_rules.append(f"dedup_sentence_shape:split_long:{threshold}")
    output = _rewrite_sentence_openings(output, context)
    output = _apply_dedup_structural_operators(output, assets, context)
    output = _apply_dedup_style_shaping(output, assets, context, profile=profile)
    if assets.platform == "cnki":
        output = _cnki_dedup_compact_reframe(output, context)
    if assets.platform == "vip":
        output = _vip_dedup_structure_shift(output, context)
    return output


def _apply_dedup_structural_operators(text: str, assets: PlatformAssets, context: RewriteContext) -> str:
    output = text
    compact_academic = rewrite_academic_frames(
        output,
        max_changes=1,
        prefer_compact=True,
    )
    if compact_academic != output:
        output = compact_academic
        context.applied_rules.append(f"dedup_structural:academic_frame:{assets.platform}")
    compact_parallel = rewrite_parallel_targets(
        output,
        max_changes=1,
        prefer_compact=True,
    )
    if compact_parallel != output:
        output = compact_parallel
        context.applied_rules.append(f"dedup_structural:parallel_targets:{assets.platform}")
    compact_causal = rewrite_causal_chains(
        output,
        max_changes=1,
        prefer_compact=True,
    )
    if compact_causal != output:
        output = compact_causal
        context.applied_rules.append(f"dedup_structural:causal_chain:{assets.platform}")
    reordered = reorder_comma_clauses(output, max_changes=1, min_clause_len=4)
    if reordered != output:
        output = reordered
        context.applied_rules.append(f"dedup_structural:clause_reorder:{assets.platform}")
    return output


def _apply_dedup_style_shaping(
    text: str,
    assets: PlatformAssets,
    context: RewriteContext,
    *,
    profile,
) -> str:
    output = text
    if assets.platform == "cnki":
        softened = soften_connective_prefixes(output, keep_first=0)
        if softened != output:
            output = softened
            context.applied_rules.append("dedup_style:cnki_soften_connectives")
    else:
        softened = soften_connective_prefixes(output, keep_first=1)
        if softened != output:
            output = softened
            context.applied_rules.append("dedup_style:vip_soften_connectives")

    if profile is None:
        return output

    sentences = split_sentences(output)
    if len(sentences) < 4:
        return output
    avg_sentence_length = sum(len(sentence) for sentence, _ in sentences) / len(sentences)

    if assets.platform == "cnki" and avg_sentence_length < profile.avg_sentence_length * 0.6:
        merge_length = max(20, int(profile.avg_sentence_length * 0.38))
        merged = merge_short_sentences(output, max_sentence_length=merge_length, merge_limit=3)
        if merged != output:
            output = merged
            context.applied_rules.append(f"dedup_style:cnki_merge_short:{merge_length}")
    if assets.platform == "vip" and avg_sentence_length < profile.avg_sentence_length * 0.56:
        merge_length = max(22, int(profile.avg_sentence_length * 0.42))
        merged = merge_short_sentences(output, max_sentence_length=merge_length, merge_limit=2)
        if merged != output:
            output = merged
            context.applied_rules.append(f"dedup_style:vip_merge_short:{merge_length}")
    return output


def _cnki_dedup_compact_reframe(text: str, context: RewriteContext) -> str:
    patterns = (
        (r"需要进一步优化", r"仍需优化"),
        (r"需要持续优化", r"仍需优化"),
        (r"这表明", r"这说明"),
    )
    output = text
    changes = 0
    for pattern, replacement in patterns:
        if changes >= 2:
            break
        next_output, count = re.subn(pattern, replacement, output, count=1)
        if count and next_output != output:
            output = next_output
            changes += 1
            context.applied_rules.append(f"cnki_dedup_reframe:{pattern}")
    return output


def _vip_dedup_structure_shift(text: str, context: RewriteContext) -> str:
    patterns = (
        (r"开展([^。！？；;，,]{2,10})工作", r"推进\1相关工作"),
        (r"形成([^。！？；;，,]{2,12})机制", r"推动\1机制形成"),
        (r"实现([^。！？；;，,]{2,12})转化", r"完成\1转化"),
        (r"([^。！？；;，,]{2,18})能够([^。！？；;，,]{2,22})", r"\1可以\2"),
        (r"对于([^。！？；;，,]{2,16})进行分析", r"对\1加以分析"),
    )
    output = text
    for pattern, replacement in patterns:
        output, count = re.subn(pattern, replacement, output, count=1)
        if count:
            context.applied_rules.append(f"dedup_structure:{pattern}")
            break
    return output
