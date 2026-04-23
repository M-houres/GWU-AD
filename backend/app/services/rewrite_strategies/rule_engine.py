from __future__ import annotations
from collections import defaultdict
import re
from dataclasses import dataclass, field

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
from app.services.strategy_style_profiles import rewrite_style_profile
from app.services.rewrite_strategies.assets import PlatformAssets, extract_dynamic_domain_terms


@dataclass
class RewriteContext:
    platform: str
    report_summary: dict
    applied_rules: list[str] = field(default_factory=list)
    protected_hits: list[str] = field(default_factory=list)


def apply_platform_rules(db, *, text: str, assets: PlatformAssets, report_summary: dict | None = None) -> tuple[str, dict]:
    context = RewriteContext(platform=assets.platform, report_summary=report_summary or {})
    protected_text, placeholders = _protect_terms(text, assets, context)
    quality_tiers = _resolve_active_quality_tiers(assets)
    output = _apply_synonyms(
        protected_text,
        assets,
        context,
        active_quality_tiers=quality_tiers,
        max_changes=None,
    )
    output = _apply_templates(output, assets, context)
    output = _apply_sentence_shape(db, output, assets, context)

    output = _apply_cohesion(output, assets, context)
    output = _harmonize_connectives(output, context)
    output = _restore_terms(output, placeholders)
    output = _polish_rewrite_output(output, context)
    return output, {
        "applied_rules": context.applied_rules,
        "protected_hits": sorted(set(context.protected_hits)),
        "chunk_count": 1 if str(protected_text or "").strip() else 0,
        "active_quality_tiers": list(quality_tiers),
    }


def _protect_terms(text: str, assets: PlatformAssets, context: RewriteContext) -> tuple[str, dict[str, str]]:
    output = str(text or "")
    placeholders: dict[str, str] = {}
    terms = {
        item.term
        for item in assets.protected_terms
        if item.term
    }
    terms.update(extract_dynamic_domain_terms(output))
    ordered_terms = sorted(terms, key=len, reverse=True)
    for index, term in enumerate(ordered_terms):
        if term not in output:
            continue
        marker = f"__GW_TERM_{index}__"
        output = output.replace(term, marker)
        placeholders[marker] = term
        context.protected_hits.append(term)
    output = _protect_dynamic_patterns(output, placeholders, context)
    return output, placeholders


def _restore_terms(text: str, placeholders: dict[str, str]) -> str:
    output = str(text or "")
    for marker, term in placeholders.items():
        output = output.replace(marker, term)
    return output


def _apply_synonyms(
    text: str,
    assets: PlatformAssets,
    context: RewriteContext,
    *,
    active_quality_tiers: tuple[str, ...] | None = None,
    max_changes: int | None = None,
) -> str:
    output = text
    enabled_quality_tiers = active_quality_tiers or _resolve_active_quality_tiers(assets)
    if isinstance(max_changes, int) and max_changes > 0:
        resolved_max_changes = max_changes
    else:
        resolved_max_changes = max(len(tuple(assets.synonyms or ())), 1)
    changes = 0
    layer_limits = _layer_limits_for_assets(assets, max_changes=resolved_max_changes)
    layer_changes: dict[str, int] = defaultdict(int)
    for rule in _iter_synonym_rules(assets, active_quality_tiers=enabled_quality_tiers):
        if changes >= resolved_max_changes:
            break
        layer = str(getattr(rule, "layer", "L2") or "L2").upper()
        if layer_changes[layer] >= layer_limits.get(layer, resolved_max_changes):
            continue
        if rule.source not in output:
            continue
        if any(token and token in output for token in rule.forbidden_contexts):
            continue
        target = _pick_target(rule.targets, output)
        if not target or target == rule.source:
            continue
        next_output = output.replace(rule.source, target, 1)
        if next_output != output:
            output = next_output
            changes += 1
            layer_changes[layer] += 1
            context.applied_rules.append(f"synonym:{rule.category}:{rule.source}->{target}")
    return output


def _resolve_active_quality_tiers(assets: PlatformAssets) -> tuple[str, ...]:
    tiers = tuple(str(item or "").strip().upper() for item in (assets.active_quality_tiers or ("S", "A")) if str(item or "").strip())
    return tiers or ("S", "A")


def _iter_synonym_rules(assets: PlatformAssets, *, active_quality_tiers: tuple[str, ...]):
    layer_order = {"L1": 0, "L2": 1, "L3": 2, "L4": 3, "L5": 4}
    enabled = set(active_quality_tiers)
    eligible = [
        item
        for item in assets.synonyms
        if str(getattr(item, "quality_tier", "A") or "A").upper() in enabled
    ]
    eligible.sort(
        key=lambda item: (
            layer_order.get(str(getattr(item, "layer", "L2") or "L2").upper(), 9),
            -int(getattr(item, "priority", 0) or 0),
        )
    )
    return eligible


def _layer_limits_for_assets(assets: PlatformAssets, *, max_changes: int) -> dict[str, int]:
    configured = {
        str(layer).upper(): max(0, int(limit))
        for layer, limit in tuple(getattr(assets, "layer_change_limits", ()) or ())
        if str(layer or "").strip()
    }
    if not configured:
        return {"L1": max_changes}
    return configured


def _pick_target(targets: tuple[str, ...], current_text: str) -> str:
    if not targets:
        return ""
    for target in targets:
        if target and target not in current_text:
            return target
    return targets[0]


def _harmonize_connectives(text: str, context: RewriteContext) -> str:
    normalized = soften_connective_prefixes(text, keep_first=1)
    if normalized != text:
        context.applied_rules.append("global:soften_connective_prefixes")
    return normalized


def _apply_templates(text: str, assets: PlatformAssets, context: RewriteContext) -> str:
    output = text
    max_changes = 1 if assets.platform == "cnki" else 2
    changes = 0
    for rule in sorted(assets.templates, key=lambda item: item.priority, reverse=True):
        if changes >= max_changes:
            break
        next_output, count = re.subn(rule.pattern, rule.replacement, output, count=1)
        if count <= 0 or next_output == output:
            continue
        output = next_output
        changes += 1
        context.applied_rules.append(f"template:{rule.id}")
    return output


def _apply_sentence_shape(db, text: str, assets: PlatformAssets, context: RewriteContext) -> str:
    pressure = (context.report_summary or {}).get("pressure")
    profile = rewrite_style_profile(assets.platform)
    if assets.platform == "cnki":
        base_threshold = 96 if pressure == "high" else 132
        profile_threshold = int(profile.avg_sentence_length * 1.72) if profile is not None else base_threshold
        threshold = max(88, min(base_threshold, profile_threshold))
        output = split_long_sentences(text, threshold, clause_joiner="；", min_clauses=4)
    else:
        base_threshold = 56 if pressure == "high" else 78
        profile_threshold = int(profile.avg_sentence_length * 1.02) if profile is not None else base_threshold
        threshold = max(48, min(base_threshold, profile_threshold))
        output = split_long_sentences(text, threshold)
    if output != text:
        context.applied_rules.append(f"sentence_shape:split_long:{threshold}")
    output = _rewrite_sentence_openings(output, context)
    output = _apply_structural_operators(output, assets, context)
    output = _apply_rewrite_style_shaping(output, assets, context, profile=profile)
    if assets.platform == "cnki":
        output = _cnki_sentence_reframe(output, context)
    if assets.platform == "vip":
        output = _vip_nominalization_shift(output, context)
        output = _vip_rewrite_flow_shift(output, context)
    return output


def _apply_structural_operators(text: str, assets: PlatformAssets, context: RewriteContext) -> str:
    output = text
    academic = rewrite_academic_frames(
        output,
        max_changes=2 if assets.platform == "cnki" else 1,
        prefer_compact=assets.platform == "vip",
    )
    if academic != output:
        output = academic
        context.applied_rules.append(f"structural:academic_frame:{assets.platform}")
    parallel = rewrite_parallel_targets(
        output,
        max_changes=2 if assets.platform == "cnki" else 1,
        prefer_compact=assets.platform == "vip",
    )
    if parallel != output:
        output = parallel
        context.applied_rules.append(f"structural:parallel_targets:{assets.platform}")
    causal = rewrite_causal_chains(
        output,
        max_changes=1 if assets.platform == "cnki" else 2,
        prefer_compact=assets.platform == "vip",
    )
    if causal != output:
        output = causal
        context.applied_rules.append(f"structural:causal_chain:{assets.platform}")
    reordered = reorder_comma_clauses(
        output,
        max_changes=2 if assets.platform == "cnki" else 1,
        min_clause_len=4,
    )
    if reordered != output:
        output = reordered
        context.applied_rules.append(f"structural:clause_reorder:{assets.platform}")
    return output


def _apply_rewrite_style_shaping(
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
            context.applied_rules.append("rewrite_style:cnki_soften_connectives")
    else:
        softened = soften_connective_prefixes(output, keep_first=1)
        if softened != output:
            output = softened
            context.applied_rules.append("rewrite_style:vip_soften_connectives")

    if profile is None:
        return output

    sentences = split_sentences(output)
    if len(sentences) < 4:
        return output
    avg_sentence_length = sum(len(sentence) for sentence, _ in sentences) / len(sentences)

    if assets.platform == "cnki" and avg_sentence_length < profile.avg_sentence_length * 0.58:
        merge_length = max(20, int(profile.avg_sentence_length * 0.42))
        merged = merge_short_sentences(output, max_sentence_length=merge_length, merge_limit=3)
        if merged != output:
            output = merged
            context.applied_rules.append(f"rewrite_style:cnki_merge_short:{merge_length}")
    if assets.platform == "vip" and avg_sentence_length < profile.avg_sentence_length * 0.54:
        merge_length = max(22, int(profile.avg_sentence_length * 0.46))
        merged = merge_short_sentences(output, max_sentence_length=merge_length, merge_limit=2)
        if merged != output:
            output = merged
            context.applied_rules.append(f"rewrite_style:vip_merge_short:{merge_length}")
    return output


def _vip_nominalization_shift(text: str, context: RewriteContext) -> str:
    patterns = (
        (r"开展([^。！？；;，,]{2,10})工作", r"推进\1相关工作"),
        (r"形成([^。！？；;，,]{2,12})机制", r"推动\1机制形成"),
        (r"实现([^。！？；;，,]{2,12})转化", r"完成\1转化"),
    )
    output = text
    for pattern, replacement in patterns:
        output, count = re.subn(pattern, replacement, output, count=1)
        if count:
            context.applied_rules.append(f"nominalization:{pattern}")
            break
    return output


def _vip_rewrite_flow_shift(text: str, context: RewriteContext) -> str:
    patterns = (
        (r"(?:(?:本研究|该研究)的)?理论贡献在于：", r"从理论层面看，"),
        (r"(?:(?:本研究|该研究)的)?实践价值在于：", r"就实践层面而言，"),
        (r"总体来看，", r"就整体情况而言，"),
        (r"([^。！？；;，,]{2,16})能够([^。！？；;，,]{2,22})", r"\1可以\2"),
        (r"对于([^。！？；;，,]{2,16})进行分析", r"围绕\1展开分析"),
        (r"在([^。！？；;，,\n]{2,16})过程中", r"在\1环节中"),
    )
    output = text
    for pattern, replacement in patterns:
        output, count = re.subn(pattern, replacement, output, count=1)
        if count:
            context.applied_rules.append(f"vip_flow:{pattern}")
            break
    return output


def _apply_cohesion(text: str, assets: PlatformAssets, context: RewriteContext) -> str:
    if not assets.cohesion_rules:
        return text
    paragraphs = text.splitlines() or [text]
    output_paragraphs: list[str] = []
    max_changes = 1 if assets.platform == "cnki" else 2
    changes = 0
    for paragraph in paragraphs:
        current = paragraph.strip()
        if not current:
            output_paragraphs.append(paragraph)
            continue
        if changes < max_changes and not current.startswith(_all_connectors(assets)):
            rule = _match_cohesion_rule(current, assets)
            if rule is not None:
                current = f"{rule.connector}，{current}"
                changes += 1
                context.applied_rules.append(f"cohesion:{rule.relation}:{rule.connector}")
        output_paragraphs.append(current)
    return "\n".join(output_paragraphs)


def _match_cohesion_rule(text: str, assets: PlatformAssets):
    for rule in sorted(assets.cohesion_rules, key=lambda item: item.priority, reverse=True):
        if any(token in text for token in rule.trigger):
            return rule
    return None


def _all_connectors(assets: PlatformAssets) -> tuple[str, ...]:
    common = ("因此", "然而", "同时", "此外", "由此可见", "据此可见", "与此同时")
    return common + tuple(rule.connector for rule in assets.cohesion_rules)


def _rewrite_sentence_openings(text: str, context: RewriteContext) -> str:
    if context.platform == "cnki":
        patterns = (
            (r"(^|[。！？]\s*)本文", r"\1本研究"),
            (r"(^|[。！？]\s*)本研究", r"\1该研究"),
            (r"(^|[。！？]\s*)研究显示", r"\1研究结果显示"),
        )
    else:
        patterns = (
            (r"(^|[。！？]\s*)本文", r"\1本研究"),
            (r"(^|[。！？]\s*)本研究", r"\1该研究"),
            (r"(^|[。！？]\s*)研究显示", r"\1研究结果显示"),
        )
    output = text
    for pattern, replacement in patterns:
        next_output, count = re.subn(pattern, replacement, output, count=1)
        if count and next_output != output:
            output = next_output
            context.applied_rules.append(f"sentence_opening:{pattern}")
            break
    return output


def _cnki_sentence_reframe(text: str, context: RewriteContext) -> str:
    patterns = (
        (r"(?:(?:本研究|该研究)的)?理论贡献在于：", r"从理论层面看，"),
        (r"(?:(?:本研究|该研究)的)?实践价值在于：", r"就实践层面而言，"),
        (r"总体来看，", r"从整体情况看，"),
        (r"从([^。！？；;，,\n]{2,18})来看", r"从\1看"),
        (r"研究认为", r"研究指出"),
        (r"其核心在于", r"关键在于"),
        (r"这意味着", r"这表明"),
        (r"在([^。！？；;，,\n]{2,18})过程中", r"在\1环节中"),
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
            context.applied_rules.append(f"cnki_reframe:{pattern}")
    return output


def _polish_rewrite_output(text: str, context: RewriteContext) -> str:
    output = str(text or "")
    replacements = (
        ("作为属于", "作为"),
        ("蕴含包括", "蕴含"),
        ("融结合", "融合"),
        ("将把", "将"),
        ("能够可以", "可以"),
        ("可以能够", "可以"),
        ("应当需要", "需要"),
        ("路径方式", "路径"),
        ("模型式", "模型"),
        ("改变革", "改变"),
        ("进行研究", "研究"),
        ("进行分析", "分析"),
        ("进行说明", "说明"),
        ("图像表现出", "图像呈现"),
        ("通用表现出", "通用呈现"),
        ("表现出层", "呈现层"),
        ("至关关键", "至关重要"),
        ("探索与探索", "探索"),
        ("关键参考", "重要参考"),
        ("关键力量", "重要力量"),
        ("关键组成部分", "重要组成部分"),
    )
    changed = False
    for src, dst in replacements:
        if src in output:
            output = output.replace(src, dst)
            changed = True
    if changed:
        context.applied_rules.append("postprocess:artifact_cleanup")
    return output


def _protect_dynamic_patterns(text: str, placeholders: dict[str, str], context: RewriteContext) -> str:
    output = str(text or "")
    marker_index = len(placeholders)
    patterns = (
        ("citation", r"\[[0-9,\-–\s]+\]"),
        ("year_citation", r"[（(]\d{4}[a-z]?[)）]"),
        ("stat_value", r"\b[pPnN]\s*[<=>]\s*[\d.]+\b"),
        ("percent", r"\d+(?:\.\d+)?%"),
        ("figure_table", r"(?:图|表)\s*\d+"),
        ("english_term", r"\b[A-Za-z]{2,}(?:[A-Za-z0-9\-_/]*[A-Za-z0-9])?\b"),
        ("alpha_numeric_term", r"\b[A-Za-z]+\d+(?:[A-Za-z0-9\-_/]*)\b"),
    )

    for label, pattern in patterns:
        def _repl(match: re.Match[str]) -> str:
            nonlocal marker_index
            token = match.group(0)
            marker = f"__GW_DYNAMIC_{marker_index}__"
            marker_index += 1
            placeholders[marker] = token
            context.protected_hits.append(token)
            return marker

        output = re.sub(pattern, _repl, output)
    return output
