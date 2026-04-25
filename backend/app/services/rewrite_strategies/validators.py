from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from app.exceptions import BizError
from app.services.strategy_style_profiles import rewrite_text_style_signals
from app.services.rewrite_strategies.assets import extract_dynamic_domain_terms, platform_assets
from app.utils import count_billable_chars


@dataclass
class RewriteValidationResult:
    text: str
    quality_flags: dict[str, bool]
    warnings: list[str] = field(default_factory=list)
    rule_trace: dict = field(default_factory=dict)
    length_before: int = 0
    length_after: int = 0
    change_ratio: float = 0.0
    quality_score: float = 0.0

def chinese_length(text: str) -> int:
    return count_billable_chars(str(text or ""))


def change_ratio(source_text: str, rewritten_text: str) -> float:
    before = chinese_length(source_text)
    after = chinese_length(rewritten_text)
    if before <= 0:
        return 0.0
    return round((after - before) / before, 4)


def adjust_to_target_length(
    text: str,
    *,
    source_text: str,
    platform: str = "",
    min_ratio: float = 0.03,
    max_ratio: float = 0.10,
    allow_soft_expansion: bool = True,
) -> str:
    output = str(text or "").strip()
    source_len = chinese_length(source_text)
    if source_len <= 0 or not output:
        return output
    normalized_platform = str(platform or "").strip().lower()
    if normalized_platform == "vip" and min_ratio == 0.03 and max_ratio == 0.10:
        min_ratio = 0.20
        max_ratio = 0.30
    min_len = int(source_len * (1 + min_ratio))
    max_len = int(source_len * (1 + max_ratio))
    current = chinese_length(output)
    if min_len <= current <= max_len:
        return output
    if current < min_len:
        expanded = _expand_with_contextual_modifiers(output, min_len=min_len, platform=normalized_platform)
        if chinese_length(expanded) > current:
            output = expanded
            current = chinese_length(output)
        if current < min_len and allow_soft_expansion and normalized_platform not in {"cnki", "vip"}:
            expanded = _expand_with_sentence_connectors(output, min_len=min_len)
            if chinese_length(expanded) > current:
                output = expanded
                current = chinese_length(output)
        if current < min_len and not allow_soft_expansion:
            return output
    while chinese_length(output) > max_len:
        next_output = re.sub(r"^(总体来看|进一步看|同时|此外|在此基础上)，", "", output, count=1).strip()
        if next_output == output:
            break
        output = next_output
    return output


def validate_rewrite_output(
    *,
    platform: str,
    source_text: str,
    rewritten_text: str,
    rule_trace: dict | None = None,
    strict_length: bool = True,
) -> RewriteValidationResult:
    output = _normalize_punctuation(str(rewritten_text or "")).strip()
    if not output:
        raise BizError(code=4611, message="降AIGC率策略输出为空")

    normalized_platform = str(platform or "").strip().lower()
    assets = platform_assets(normalized_platform)
    source_len = chinese_length(source_text)
    output_len = chinese_length(output)
    ratio = change_ratio(source_text, output)
    warnings: list[str] = []

    bad_hits: list[str] = []
    for item in assets.bad_patterns:
        if item.regex:
            if re.search(item.pattern, output):
                bad_hits.append(item.pattern)
        elif item.pattern in output:
            bad_hits.append(item.pattern)

    source_terms = [item.term for item in assets.protected_terms if item.term and item.term in source_text]
    dynamic_terms = list(extract_dynamic_domain_terms(source_text))
    source_terms.extend(dynamic_terms)
    missing_terms = [term for term in dict.fromkeys(source_terms) if term not in output]
    missing_dynamic_terms = [term for term in dynamic_terms if term not in output]
    term_integrity_ok = not missing_terms
    if missing_terms:
        warnings.append(f"保护术语缺失: {','.join(missing_terms[:5])}")

    if bad_hits:
        raise BizError(code=4613, message=f"降AIGC率结果存在明显异常表达: {','.join(bad_hits[:5])}")
    if _has_mechanical_prefix_cascade(output):
        raise BizError(code=4613, message="降AIGC率结果存在明显异常表达: 机械连接词堆叠")
    structure_natural_ok = not _has_soft_mechanical_prefix_usage(output)
    if not structure_natural_ok:
        warnings.append("衔接表达偏机械，建议复核段内句序与连接词密度")
    style_signals = rewrite_text_style_signals(normalized_platform, output)
    if bool(style_signals.get("style_profile_available")) and not bool(style_signals.get("style_alignment_ok")):
        warnings.append("当前结果与平台高质量改写样本的句长/衔接风格偏离较大")
    shallow_rewrite_ok = not _has_shallow_rewrite_risk(source_text, output)
    if not shallow_rewrite_ok:
        warnings.append("改写幅度偏浅，句法和论述重组仍然不足")
    discourse_diversity_ok = not _has_repetitive_sentence_pattern(output)
    if not discourse_diversity_ok:
        warnings.append("段内句式重复度偏高，整体阅读质感不足")

    length_ok = True
    if strict_length and source_len >= 40:
        if normalized_platform == "vip":
            length_ok = 0.20 <= ratio <= 0.30
            if not length_ok:
                warnings.append(f"维普WP2扩写量未达到建议 20%~30%: {ratio:.2%}")
            if not (0.10 <= ratio <= 0.40):
                raise BizError(code=4612, message=f"维普WP2扩写量超出允许范围: {ratio:.2%}")
        else:
            length_ok = 0.03 <= ratio <= 0.10
            if not length_ok:
                warnings.append(f"降AIGC率结果字数浮动未达到建议 3%~10%: {ratio:.2%}")
            if not (-0.1 <= ratio <= 0.2):
                raise BizError(code=4612, message=f"降AIGC率结果字数浮动超出可处理范围: {ratio:.2%}")
    elif source_len >= 40:
        if normalized_platform == "vip":
            length_ok = 0.20 <= ratio <= 0.30
            if not length_ok:
                warnings.append(f"维普WP2扩写量未达到建议 20%~30%: {ratio:.2%}")
        else:
            length_ok = 0.03 <= ratio <= 0.10
            if not length_ok:
                warnings.append(f"降AIGC率结果字数浮动未达到建议 3%~10%: {ratio:.2%}")
    elif source_len > 0 and not (0 <= output_len <= max(int(source_len * 1.35), source_len + 30)):
        length_ok = False
        warnings.append("短文本字数浮动偏离较大")

    return RewriteValidationResult(
        text=output,
        length_before=source_len,
        length_after=output_len,
        change_ratio=ratio,
        quality_score=_build_quality_score(
            quality_flags={
                "length_ok": length_ok,
                "protected_content_ok": term_integrity_ok,
                "cross_domain_terms_ok": not missing_dynamic_terms,
                "structure_natural_ok": structure_natural_ok,
                "style_profile_available": bool(style_signals.get("style_profile_available")),
                "style_alignment_ok": bool(style_signals.get("style_alignment_ok")),
                "shallow_rewrite_ok": shallow_rewrite_ok,
                "discourse_diversity_ok": discourse_diversity_ok,
                "basic_legality_ok": not bad_hits,
            },
            warnings=warnings,
        ),
        quality_flags={
            "length_ok": length_ok,
            "protected_content_ok": term_integrity_ok,
            "cross_domain_terms_ok": not missing_dynamic_terms,
            "structure_natural_ok": structure_natural_ok,
            "style_profile_available": bool(style_signals.get("style_profile_available")),
            "style_alignment_ok": bool(style_signals.get("style_alignment_ok")),
            "shallow_rewrite_ok": shallow_rewrite_ok,
            "discourse_diversity_ok": discourse_diversity_ok,
            "basic_legality_ok": not bad_hits,
        },
        warnings=warnings,
        rule_trace=rule_trace or {},
    )


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


def _expand_with_sentence_connectors(text: str, *, min_len: int) -> str:
    output = str(text or "").strip()
    if chinese_length(output) >= min_len:
        return output
    parts = re.split(r"(。|！|？)", output)
    if len(parts) < 4:
        return output
    prefixes = ("同时，", "此外，", "进一步看，", "在此基础上，")
    prefix_index = 0
    rebuilt: list[str] = []
    sentence_index = 0
    for index in range(0, len(parts), 2):
        sentence = parts[index].strip()
        punct = parts[index + 1] if index + 1 < len(parts) else ""
        if not sentence:
            continue
        if sentence_index > 0 and chinese_length("".join(rebuilt)) < min_len and prefix_index < len(prefixes):
            if not re.match(r"^(同时|此外|进一步看|在此基础上)，", sentence):
                sentence = f"{prefixes[prefix_index]}{sentence}"
                prefix_index += 1
        rebuilt.append(f"{sentence}{punct}")
        sentence_index += 1
    return "".join(rebuilt).strip()


def _expand_with_contextual_modifiers(text: str, *, min_len: int, platform: str) -> str:
    output = str(text or "").strip()
    if chinese_length(output) >= min_len:
        return output
    replacements = (
        ("研究表明", "研究结果表明"),
        ("可以", "可以进一步"),
        ("能够", "能够有效"),
        ("需要", "仍然需要"),
        ("优化", "持续优化"),
        ("提升", "提升整体"),
        ("分析", "系统分析"),
        ("探讨", "深入探讨"),
        ("路径", "实施路径"),
    )
    for source, target in replacements:
        if chinese_length(output) >= min_len:
            break
        if source in output:
            output = output.replace(source, target, 1)

    if chinese_length(output) < min_len:
        sentence_suffix = "，以增强论证完整性"
        if platform == "vip":
            sentence_suffix = "，以保持表达连贯性"
        punct_match = re.search(r"[。！？!?；;]$", output)
        if punct_match:
            punct = punct_match.group(0)
            head = output[: -len(punct)]
            if not head.endswith(("完整性", "连贯性")):
                output = f"{head}{sentence_suffix}{punct}"
        else:
            output = f"{output}{sentence_suffix}。"
    return output


def _has_mechanical_prefix_cascade(text: str) -> bool:
    prefixes = ("同时，", "此外，", "进一步看，", "在此基础上，")
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


def _has_shallow_rewrite_risk(source_text: str, rewritten_text: str) -> bool:
    source = str(source_text or "").strip()
    output = str(rewritten_text or "").strip()
    if not source or not output:
        return False
    if chinese_length(source) < 70:
        return False
    similarity = SequenceMatcher(None, source[:4000], output[:4000]).ratio()
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
        "protected_content_ok": 0.18,
        "cross_domain_terms_ok": 0.08,
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
