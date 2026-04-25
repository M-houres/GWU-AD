from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from app.exceptions import BizError
from app.services.dedup_strategies.assets import dedup_assets
from app.services.strategy_style_profiles import dedup_text_style_signals
from app.services.rewrite_strategies.assets import extract_dynamic_domain_terms
from app.services.rewrite_strategies.validators import chinese_length


@dataclass
class DedupValidationResult:
    text: str
    quality_flags: dict[str, bool]
    warnings: list[str] = field(default_factory=list)
    rule_trace: dict = field(default_factory=dict)
    length_before: int = 0
    length_after: int = 0
    length_delta_ratio: float = 0.0
    similarity_ratio: float = 1.0
    change_ratio: float = 0.0
    quality_score: float = 0.0


def validate_dedup_output(
    *,
    platform: str,
    source_text: str,
    rewritten_text: str,
    rule_trace: dict | None = None,
) -> DedupValidationResult:
    output = _normalize_punctuation(str(rewritten_text or "")).strip()
    if not output:
        raise BizError(code=4621, message="降重复率策略输出为空")

    normalized_platform = str(platform or "").strip().lower()
    source_len = chinese_length(source_text)
    output_len = chinese_length(output)
    length_delta_ratio = round((output_len - source_len) / source_len, 4) if source_len > 0 else 0.0
    warnings: list[str] = []
    if (rule_trace or {}).get("fallback_applied"):
        warnings.append("降重复率策略空输出，已切换兜底改写")
    length_ok = True
    if source_len >= 40:
        if normalized_platform == "vip":
            length_ok = 0.20 <= length_delta_ratio <= 0.30
            if not length_ok:
                warnings.append("维普WP2扩写量未达到建议 20%~30%")
            if not (0.10 <= length_delta_ratio <= 0.40):
                raise BizError(code=4622, message=f"维普WP2扩写量超出允许范围: {length_delta_ratio:.2%}")
        elif not (-0.1 <= length_delta_ratio <= 0.2):
            length_ok = False
            warnings.append("降重结果字数浮动超出建议范围")

    similarity = SequenceMatcher(None, str(source_text or "")[:4000], output[:4000]).ratio()
    change = round((1 - similarity) * 100, 2)
    variation_ok = True
    if source_len >= 40 and change < 3:
        variation_ok = False
        warnings.append("降重改写幅度偏低")

    assets = dedup_assets(normalized_platform)
    bad_hits = []
    for item in assets.bad_patterns:
        if item.regex:
            if re.search(item.pattern, output):
                bad_hits.append(item.pattern)
        elif item.pattern in output:
            bad_hits.append(item.pattern)
    if bad_hits:
        raise BizError(code=4623, message=f"降重复率结果存在明显异常表达: {','.join(bad_hits[:5])}")
    if _has_mechanical_prefix_cascade(output):
        raise BizError(code=4623, message="降重复率结果存在明显异常表达: 机械连接词堆叠")

    missing_terms = []
    for item in assets.protected_terms:
        if item.term and item.term in source_text and item.term not in output:
            missing_terms.append(item.term)
    dynamic_terms = list(extract_dynamic_domain_terms(source_text))
    for term in dynamic_terms:
        if term not in output:
            missing_terms.append(term)
    missing_terms = list(dict.fromkeys(missing_terms))
    missing_dynamic_terms = [term for term in dynamic_terms if term not in output]
    protected_content_ok = not missing_terms
    if missing_terms:
        warnings.append(f"保护术语缺失: {','.join(missing_terms[:5])}")

    numbers_preserved = _numbers(source_text) <= _numbers(output)
    if not numbers_preserved:
        warnings.append("数字或百分比信息可能缺失")
    structure_natural_ok = not _has_soft_mechanical_prefix_usage(output)
    if not structure_natural_ok:
        warnings.append("衔接表达偏机械，建议复核句序与连接词使用")
    style_signals = dedup_text_style_signals(normalized_platform, output)
    if bool(style_signals.get("style_profile_available")) and not bool(style_signals.get("style_alignment_ok")):
        warnings.append("当前结果与平台高质量降重样本的句长/衔接风格偏离较大")
    shallow_rewrite_ok = not _has_shallow_rewrite_risk(source_text, output, similarity)
    if not shallow_rewrite_ok:
        warnings.append("降重改写仍偏浅，结构调整幅度不足")
    discourse_diversity_ok = not _has_repetitive_sentence_pattern(output)
    if not discourse_diversity_ok:
        warnings.append("句式重复度偏高，段落改写质感不足")

    return DedupValidationResult(
        text=output,
        length_before=source_len,
        length_after=output_len,
        length_delta_ratio=length_delta_ratio,
        similarity_ratio=round(similarity, 4),
        change_ratio=change,
        quality_score=_build_quality_score(
            quality_flags={
                "length_ok": length_ok,
                "variation_ok": variation_ok,
                "protected_content_ok": protected_content_ok,
                "cross_domain_terms_ok": not missing_dynamic_terms,
                "structure_natural_ok": structure_natural_ok,
                "numbers_preserved": numbers_preserved,
                "basic_legality_ok": not bad_hits,
                "style_profile_available": bool(style_signals.get("style_profile_available")),
                "style_alignment_ok": bool(style_signals.get("style_alignment_ok")),
                "shallow_rewrite_ok": shallow_rewrite_ok,
                "discourse_diversity_ok": discourse_diversity_ok,
            },
            warnings=warnings,
        ),
        quality_flags={
            "length_ok": length_ok,
            "variation_ok": variation_ok,
            "protected_content_ok": protected_content_ok,
            "cross_domain_terms_ok": not missing_dynamic_terms,
            "structure_natural_ok": structure_natural_ok,
            "numbers_preserved": numbers_preserved,
            "basic_legality_ok": not bad_hits,
            "style_profile_available": bool(style_signals.get("style_profile_available")),
            "style_alignment_ok": bool(style_signals.get("style_alignment_ok")),
            "shallow_rewrite_ok": shallow_rewrite_ok,
            "discourse_diversity_ok": discourse_diversity_ok,
        },
        warnings=warnings,
        rule_trace=rule_trace or {},
    )


def _numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+(?:\.\d+)?%?", str(text or "")))


def _normalize_punctuation(text: str) -> str:
    output = str(text or "")
    output = re.sub(r"，{2,}", "，", output)
    output = re.sub(r"。{2,}", "。", output)
    output = re.sub(r"、{2,}", "、", output)
    output = re.sub(r"；{2,}", "；", output)
    output = re.sub(r"：{2,}", "：", output)
    output = re.sub(r"！{2,}", "！", output)
    output = re.sub(r"？{2,}", "？", output)
    output = re.sub(r",{2,}", ",", output)
    output = re.sub(r"\.{2,}", ".", output)
    output = re.sub(r";{2,}", ";", output)
    output = re.sub(r":{2,}", ":", output)
    output = re.sub(r"!{2,}", "!", output)
    output = re.sub(r"\?{2,}", "?", output)
    return output


def _has_mechanical_prefix_cascade(text: str) -> bool:
    prefixes = ("同时，", "此外，", "进一步看，", "在此基础上，", "由此可见，")
    paragraphs = [part.strip() for part in str(text or "").splitlines() if part.strip()]
    for paragraph in paragraphs:
        sentences = [part.strip() for part in re.split(r"[。！？!?；;]+", paragraph) if part.strip()]
        if len(sentences) < 4:
            continue
        prefix_hits = 0
        streak = 0
        for sentence in sentences:
            if sentence.startswith(prefixes):
                prefix_hits += 1
                streak += 1
                if streak >= 3 or prefix_hits >= 4:
                    return True
            else:
                streak = 0
    return False


def _has_soft_mechanical_prefix_usage(text: str) -> bool:
    prefixes = ("同时，", "此外，", "进一步看，", "在此基础上，", "由此可见，")
    paragraphs = [part.strip() for part in str(text or "").splitlines() if part.strip()]
    for paragraph in paragraphs:
        sentences = [part.strip() for part in re.split(r"[。！？!?；;]+", paragraph) if part.strip()]
        if len(sentences) < 3:
            continue
        prefix_hits = sum(1 for sentence in sentences if sentence.startswith(prefixes))
        if prefix_hits >= 2:
            return True
    return False


def _has_shallow_rewrite_risk(source_text: str, rewritten_text: str, similarity: float) -> bool:
    source = str(source_text or "").strip()
    output = str(rewritten_text or "").strip()
    if not source or not output:
        return False
    if chinese_length(source) < 70:
        return False
    source_sentences = len([item for item in re.split(r"[。！？!?；;]+", source) if item.strip()])
    output_sentences = len([item for item in re.split(r"[。！？!?；;]+", output) if item.strip()])
    if similarity >= 0.98:
        return True
    if similarity >= 0.95 and abs(source_sentences - output_sentences) <= 1:
        return True
    return False


def _has_repetitive_sentence_pattern(text: str) -> bool:
    sentences = [item.strip() for item in re.split(r"[。！？!?；;]+", str(text or "")) if item.strip()]
    if len(sentences) < 4:
        return False
    prefixes: dict[str, int] = {}
    short_sentence_hits = 0
    for sentence in sentences:
        if len(sentence) <= 10:
            short_sentence_hits += 1
        normalized = re.sub(r"[（(【\[]?[一二三四五六七八九十0-9]+[)）】\]]?", "", sentence)
        key = normalized[:4]
        if len(key) >= 2:
            prefixes[key] = prefixes.get(key, 0) + 1
    if short_sentence_hits >= max(3, len(sentences) - 1):
        return True
    return any(count >= 3 for count in prefixes.values())


def _build_quality_score(*, quality_flags: dict[str, bool], warnings: list[str]) -> float:
    score = 1.0
    weighted_penalties = {
        "basic_legality_ok": 0.45,
        "protected_content_ok": 0.16,
        "cross_domain_terms_ok": 0.08,
        "numbers_preserved": 0.06,
        "variation_ok": 0.08,
        "structure_natural_ok": 0.12,
        "style_alignment_ok": 0.08,
        "shallow_rewrite_ok": 0.12,
        "discourse_diversity_ok": 0.08,
        "length_ok": 0.05,
    }
    for key, penalty in weighted_penalties.items():
        if key in quality_flags and not bool(quality_flags.get(key)):
            score -= penalty
    score -= min(len(warnings), 4) * 0.03
    return round(max(0.0, min(1.0, score)), 4)
