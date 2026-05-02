from __future__ import annotations

import re
from typing import Any

from app.services.aigc_detect_strategies.common import (
    ParagraphFeatures,
    clamp,
    extract_features,
    label_from_score,
    paragraph_segments,
    reason_tags,
    risk_band,
    sigmoid,
    split_sentences,
    split_paragraphs,
)

PROFILE = {
    "name": "cnki_internal",
    "provider_label": "知网AIGC检测仿真",
    "score_label": "AI特征值",
    "high": 0.53,
    "medium": 0.36,
    "low": 0.18,
}

HEADING_PATTERN = re.compile(
    r"^(?:"
    r"摘要[:：]?$|关键词[:：]?$|关键字[:：]?$|引言[:：]?$|绪论[:：]?$|前言[:：]?$|结语[:：]?$|结论[:：]?$|参考文献[:：]?$|附录[:：]?$|致谢[:：]?$|"
    r"abstract[:：]?$|keywords[:：]?$|"
    r"\d+(?:\.\d+){0,3}[、.．]?\s*[\u4e00-\u9fffA-Za-z]+.*$|"
    r"第[一二三四五六七八九十百零0-9]+[章节部分篇].*$|"
    r"[一二三四五六七八九十百零]+[、.．].*$|"
    r"[（(][一二三四五六七八九十百零0-9]+[)）].*$"
    r")",
    re.IGNORECASE,
)
REFERENCE_PATTERN = re.compile(r"^\s*\[\d+\]|(?:\[J\]|\[M\]|\[D\]|\[C\]|\[N\])", re.IGNORECASE)
TABLE_FIGURE_PATTERN = re.compile(r"(?:^|[\s（(])(?:表|图)\s*\d+")
META_PATTERN = re.compile(r"(?:signature|instructor|specialty|thesis|作者[:：]|单位[:：]|学号|指导教师|姓名[:：])", re.IGNORECASE)

THEORY_HINTS = (
    "研究意义",
    "研究现状",
    "文献综述",
    "理论基础",
    "理论依据",
    "理论框架",
    "概念界定",
    "相关概念",
    "核心概念",
    "模型构建",
    "研究设计",
    "研究思路",
    "研究方法",
    "分析框架",
    "课程标准",
    "PEST",
    "SWOT",
    "STP",
    "波特五力",
)


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "")).strip()


def _heading_key(text: str, *, index: int, total: int) -> str:
    compact = _compact(text).lower()
    if compact.startswith(("摘要", "中文摘要", "英文摘要", "abstract")):
        return "abstract"
    if compact.startswith(("关键词", "关键字", "keywords")):
        return "keywords"
    if compact.startswith(("引言", "绪论", "前言")):
        return "intro"
    if compact.startswith(("参考文献", "附录", "致谢")):
        return "tail"
    body_start_threshold = max(5, min(total // 12, 20))
    if index >= body_start_threshold:
        chapter_number = _top_level_chapter_number(compact)
        if chapter_number is not None and 1 <= chapter_number <= 15:
            return f"chapter_{chapter_number}"
    if re.match(r"^(?:\d+(?:\.\d+){0,3}[、.．]?|第[一二三四五六七八九十百零0-9]+[章节部分篇]|[一二三四五六七八九十百零]+[、.．])", compact):
        return "outline"
    return ""


_CHINESE_NUMERAL_MAP: dict[str, int] = {
    "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15,
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}


def _top_level_chapter_number(compact: str) -> int | None:
    for pattern in (
        r"^(\d+)[、．]",
        r"^(\d+)(?!\.)[\u4e00-\u9fffA-Za-z]",
    ):
        match = re.match(pattern, compact)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None

    for cn, num in _CHINESE_NUMERAL_MAP.items():
        if compact.startswith(cn) and len(compact) > len(cn) + 1:
            after = compact[len(cn):]
            if after[0] in "、．" and len(after) >= 3 and len(compact) <= 30:
                return num
    return None


def _ascii_ratio(text: str) -> float:
    raw = str(text or "")
    if not raw:
        return 0.0
    return sum(1 for ch in raw if ord(ch) < 128 and ch.isalpha()) / max(len(raw), 1)


def _paragraph_role(paragraph: str, *, index: int, total: int, features: ParagraphFeatures) -> str:
    compact = _compact(paragraph)
    lowered = compact.lower()
    if not compact:
        return "blank"
    if META_PATTERN.search(paragraph) or compact == "目录":
        return "meta"
    if REFERENCE_PATTERN.search(paragraph) or "参考文献" in compact:
        return "reference"
    if TABLE_FIGURE_PATTERN.search(paragraph):
        return "table_figure"
    if index == 1 and len(compact) <= 40 and not re.search(r"[。！？!?；;:：]", compact):
        return "heading"
    if HEADING_PATTERN.match(compact) and len(compact) <= 48 and not re.search(r"[。！？!?；;]", compact):
        return "heading"
    if compact.startswith(("关键词：", "关键词:", "关键字：", "关键字:", "【关键词】", "【关键字】")):
        return "keyword_body"
    if lowered.startswith(("abstract:", "abstract：", "摘要:", "摘要：")):
        return "front_abstract"
    if index <= max(6, total // 8):
        if "摘要" in compact[:12] or lowered.startswith("abstract"):
            return "front_abstract"
        if compact.startswith(("引言", "绪论", "前言")):
            return "front_intro"
    if any(token in paragraph for token in THEORY_HINTS):
        return "theory_review"
    if features.num_density >= 1.2 or features.entity_density >= 1.0:
        return "evidence_rich"
    if _ascii_ratio(paragraph) >= 0.35 and len(compact) >= 120:
        return "english_or_mixed_abstract"
    return "body"


def _role_adjustments(paragraph: str, *, role: str, index: int, total: int, features: ParagraphFeatures) -> tuple[float, float]:
    boost = 0.0
    relief = 0.0
    if role in {"blank", "heading", "keyword_body", "reference", "table_figure", "meta"}:
        return boost, 1.0
    if role == "front_abstract":
        boost += 0.09
    elif role == "front_intro":
        boost += 0.02
    elif role == "theory_review":
        relief += 0.10
    elif role == "evidence_rich":
        relief += 0.12
    elif role == "english_or_mixed_abstract":
        relief += 0.05

    if index > int(total * 0.75):
        relief += 0.03
    if re.search(r"(?:《[^》]+》|[12]\d{3}年|\d+(?:\.\d+)?%|[一二三四五六七八九十]是|首先|其次|最后)", paragraph):
        relief += 0.03
    if re.search(r"(?:食品安全法|课程标准|问卷|访谈|样本|调查结果|图\d+|表\d+)", paragraph):
        relief += 0.05
    return boost, relief


def _paragraph_score(
    paragraph: str,
    features: ParagraphFeatures,
    *,
    index: int,
    total: int,
) -> tuple[float, dict[str, float], str]:
    role = _paragraph_role(paragraph, index=index, total=total, features=features)
    role_boost, role_relief = _role_adjustments(paragraph, role=role, index=index, total=total, features=features)
    if role_relief >= 1.0:
        return 0.0, {"role_boost": round(role_boost, 4), "role_relief": round(role_relief, 4)}, role

    fourchar_signal = clamp(max(0.0, features.fourch_density - 12.0) / 14.0)
    syntax = clamp(
        clamp((features.sent_len_mean - 24.0) / 64.0) * 0.34
        + (1.0 - clamp(features.sent_len_cv / 0.82)) * 0.20
        + features.punct_regularity * 0.16
        + clamp((0.0 - features.burstiness + 0.30) / 0.9) * 0.06
    )
    lexical = clamp(
        clamp(features.ai_noun_ratio / 3.2) * 0.28
        + clamp(features.ai_verb_ratio / 3.0) * 0.20
        + fourchar_signal * 0.08
        + clamp(features.conn_density / 4.0) * 0.08
        + (1.0 - clamp(features.ttr / 0.78)) * 0.04
    )
    discourse = clamp(
        features.tmpl_hit * 0.34
        + features.parallel_hit * 0.18
        + features.phil_hit_tail * 0.10
        + clamp(features.definition_rate / 0.9) * 0.06
        + features.dup_ngram_ratio * 0.10
        + clamp(features.conn_density / 3.6) * 0.06
    )
    specificity_relief = clamp(
        clamp(features.entity_density / 2.4) * 0.38
        + clamp(features.domain_term_density / 2.0) * 0.20
        + clamp(features.concrete_density / 2.5) * 0.18
        + clamp(features.quote_density / 1.5) * 0.10
        + clamp(features.num_density / 2.0) * 0.14
    )
    raw = syntax * 0.25 + lexical * 0.21 + discourse * 0.28 + features.dup_ngram_ratio * 0.04 + role_boost
    score = clamp(sigmoid((raw - specificity_relief * 0.48 - role_relief - 0.34) / 0.22))
    return score, {
        "role": role,
        "role_boost": round(role_boost, 4),
        "role_relief": round(role_relief, 4),
        "syntax_signal": round(syntax, 4),
        "lexical_signal": round(lexical, 4),
        "discourse_signal": round(discourse, 4),
        "specificity_relief": round(specificity_relief, 4),
        "raw_signal": round(raw, 4),
    }, role


def _sentence_role_adjustments(sentence: str, *, role: str) -> tuple[float, float]:
    boost = 0.0
    relief = 0.0
    if role == "front_abstract":
        boost += 0.12
    elif role == "front_intro":
        boost += 0.12
    elif role == "theory_review":
        relief += 0.08
    elif role == "evidence_rich":
        relief += 0.10
    elif role == "english_or_mixed_abstract":
        boost += 0.05
    if re.search(r"\[\d+\]|《[^》]{2,40}》|指南|课程标准|质量评估指南", sentence):
        relief += 0.10
    return boost, relief


def _sentence_signal(sentence: str, *, paragraph_score: float, role: str) -> tuple[float, ParagraphFeatures]:
    features = extract_features(sentence)
    if features.char_count <= 0:
        return 0.0, features
    fourchar_signal = clamp(max(0.0, features.fourch_density - 12.0) / 14.0)
    local = clamp(
        features.tmpl_hit * 0.24
        + features.parallel_hit * 0.16
        + clamp(features.ai_noun_ratio / 3.0) * 0.18
        + clamp(features.ai_verb_ratio / 3.0) * 0.16
        + clamp(features.conn_density / 3.6) * 0.08
        + fourchar_signal * 0.06
        + clamp(features.definition_rate / 0.9) * 0.04
        + features.dup_ngram_ratio * 0.08
    )
    specificity_relief = clamp(
        clamp(features.entity_density / 2.2) * 0.30
        + clamp(features.num_density / 2.0) * 0.14
        + clamp(features.concrete_density / 2.4) * 0.18
        + clamp(features.quote_density / 1.4) * 0.10
    )
    role_boost, role_relief = _sentence_role_adjustments(sentence, role=role)
    score = clamp(local * 0.58 + paragraph_score * 0.56 + role_boost - specificity_relief * 0.24 - role_relief)
    if features.char_count <= 18:
        score = clamp(score - 0.04)
    return score, features


def _sentence_label_thresholds(role: str) -> tuple[float, float, float]:
    if role == "front_abstract":
        return 0.50, 0.34, 0.18
    if role == "front_intro":
        return 0.44, 0.30, 0.18
    if role == "body":
        return 0.34, 0.24, 0.14
    return PROFILE["high"], PROFILE["medium"], PROFILE["low"]


def _build_sentence_spans(paragraphs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    cursor = 0
    for row in paragraphs:
        paragraph_text = str(row.get("text") or "")
        role = str(row.get("role") or "")
        heading_key = str(row.get("heading_key") or "")
        paragraph_score = float(row.get("score") or 0.0) / 100.0
        paragraph_char_count = int(row.get("char_count") or 0)
        paragraph_start = cursor
        if role in {"blank", "heading", "meta", "reference", "table_figure", "keyword_body"} or not paragraph_text:
            cursor += paragraph_char_count
            continue

        local_cursor = paragraph_start
        sentences = split_sentences(paragraph_text) or [paragraph_text]
        high_threshold, medium_threshold, low_threshold = _sentence_label_thresholds(role)
        for sentence_index, sentence in enumerate(sentences, start=1):
            score, sentence_features = _sentence_signal(sentence, paragraph_score=paragraph_score, role=role)
            label = label_from_score(score, high=high_threshold, medium=medium_threshold, low=low_threshold)
            sentence_char_count = int(sentence_features.char_count or 0)
            spans.append(
                {
                    "paragraph_index": int(row.get("index") or 0),
                    "sentence_index": sentence_index,
                    "text": sentence,
                    "score_pct": round(score * 100.0, 2),
                    "label": label,
                    "char_count": sentence_char_count,
                    "start": local_cursor,
                    "end": local_cursor + sentence_char_count,
                    "role": role,
                    "heading_key": heading_key,
                }
            )
            local_cursor += sentence_char_count
        cursor += paragraph_char_count
    return spans


def _build_distribution_20pct(*, total_chars: int, sentence_spans: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    if total_chars <= 0:
        return {
            "front": {"score_pct": 0.0, "ai_chars": 0, "slice_chars": 0},
            "middle": {"score_pct": 0.0, "ai_chars": 0, "slice_chars": 0},
            "back": {"score_pct": 0.0, "ai_chars": 0, "slice_chars": 0},
        }
    front_end = total_chars * 0.2
    middle_end = total_chars * 0.8
    ranges = {
        "front": (0.0, front_end),
        "middle": (front_end, middle_end),
        "back": (middle_end, float(total_chars)),
    }
    result: dict[str, dict[str, float]] = {}
    for bucket, (start, end) in ranges.items():
        ai_chars = 0.0
        for span in sentence_spans:
            if span["label"] not in {"high", "medium"}:
                continue
            overlap = max(0.0, min(float(span["end"]), end) - max(float(span["start"]), start))
            if overlap > 0:
                ai_chars += overlap
        slice_chars = max(int(round(end - start)), 0)
        result[bucket] = {
            "score_pct": round(ai_chars / max(end - start, 1.0) * 100.0, 2),
            "ai_chars": int(round(ai_chars)),
            "slice_chars": slice_chars,
        }
    return result


def _clean_section_name(text: str) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    value = re.sub(r"(?<=[\u4e00-\u9fffA-Za-z）】])\d{1,3}$", "", value).strip()
    return value


def _build_section_details(paragraphs: list[dict[str, Any]], sentence_spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    span_map: dict[int, list[dict[str, Any]]] = {}
    for span in sentence_spans:
        span_map.setdefault(int(span.get("paragraph_index") or 0), []).append(span)

    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def start_section(name: str) -> dict[str, Any]:
        section = {
            "row_no": len(sections) + 1,
            "section_name": name,
            "section_chars": 0,
            "ai_chars": 0,
            "paragraph_indexes": [],
        }
        sections.append(section)
        return section

    for row in paragraphs:
        role = str(row.get("role") or "")
        heading_key = str(row.get("heading_key") or "")
        text = str(row.get("text") or "")
        index = int(row.get("index") or 0)
        char_count = int(row.get("char_count") or 0)

        if heading_key == "abstract":
            current = start_section("中英文摘要等")
            continue
        if heading_key.startswith("chapter_"):
            current = start_section(_clean_section_name(text))
            continue
        if role in {"heading", "reference", "table_figure", "blank"}:
            continue
        if current is None:
            current = start_section("中英文摘要等" if role in {"front_abstract", "meta", "keyword_body"} else "正文")

        current["section_chars"] += char_count
        current["paragraph_indexes"].append(index)
        for span in span_map.get(index, []):
            if span["label"] in {"high", "medium"}:
                current["ai_chars"] += int(span["char_count"] or 0)

    for section in sections:
        chars = int(section["section_chars"] or 0)
        ai_chars = min(chars, int(section["ai_chars"] or 0))
        section["ai_chars"] = ai_chars
        section["score_pct"] = round(ai_chars / max(chars, 1) * 100.0, 2) if chars else 0.0
    return sections


def detect(text: str) -> dict[str, Any]:
    paragraphs = split_paragraphs(text)
    total = len(paragraphs)
    rows: list[dict[str, Any]] = []
    abstract_block = False
    intro_block = False
    previous_heading = ""
    for index, paragraph in enumerate(paragraphs, start=1):
        features = extract_features(paragraph)
        score, sub_scores, role = _paragraph_score(paragraph, features, index=index, total=total)
        heading = _heading_key(paragraph, index=index, total=total)
        if role == "heading":
            previous_heading = heading
        if heading == "abstract":
            abstract_block = True
            intro_block = False
        elif heading == "intro":
            abstract_block = False
            intro_block = True
        elif heading.startswith("chapter_"):
            abstract_block = False
            intro_block = (heading == "chapter_1")
        elif heading == "outline":
            abstract_block = False
        elif heading == "tail":
            abstract_block = False
            intro_block = False
        elif role not in {"meta", "reference", "table_figure", "keyword_body"}:
            if abstract_block or previous_heading == "abstract":
                score, sub_scores, role = _paragraph_score(
                    paragraph,
                    features,
                    index=index,
                    total=total,
                )
                role = "front_abstract"
                boost, relief = _role_adjustments(
                    paragraph,
                    role=role,
                    index=index,
                    total=total,
                    features=features,
                )
                raw = float(sub_scores.get("raw_signal", 0.0))
                specificity_relief = float(sub_scores.get("specificity_relief", 0.0))
                score = clamp(sigmoid((raw - specificity_relief * 0.44 - relief - 0.24 + boost) / 0.18) + 0.10)
                sub_scores["role"] = role
                sub_scores["role_boost"] = round(boost, 4)
                sub_scores["role_relief"] = round(relief, 4)
            elif intro_block or previous_heading == "intro":
                role = "front_intro"
                boost, relief = _role_adjustments(
                    paragraph,
                    role=role,
                    index=index,
                    total=total,
                    features=features,
                )
                raw = float(sub_scores.get("raw_signal", 0.0))
                specificity_relief = float(sub_scores.get("specificity_relief", 0.0))
                score = clamp(sigmoid((raw - specificity_relief * 0.46 - relief - 0.28 + boost) / 0.20) + 0.07)
                sub_scores["role"] = role
                sub_scores["role_boost"] = round(boost, 4)
                sub_scores["role_relief"] = round(relief, 4)
            previous_heading = ""
        label = label_from_score(score, high=PROFILE["high"], medium=PROFILE["medium"], low=PROFILE["low"])
        rows.append(
            {
                "index": index,
                "label": label,
                "role": role,
                "heading_key": heading,
                "risk_band": risk_band(label),
                "score": round(score * 100.0, 2),
                "char_count": features.char_count,
                "sentence_count": features.sentence_count,
                "text": paragraph,
                "excerpt": paragraph[:110] + ("..." if len(paragraph) > 110 else ""),
                "reason_tags": reason_tags(features, label),
                "suspicious_segments": paragraph_segments(paragraph, score, label, features),
                "features": features.as_dict(),
                "sub_scores": sub_scores,
            }
        )
    sentence_spans = _build_sentence_spans(rows)
    significant_chars = sum(int(span["char_count"] or 0) for span in sentence_spans if span["label"] == "high")
    suspected_chars = sum(int(span["char_count"] or 0) for span in sentence_spans if span["label"] == "medium")
    total_chars = sum(row["char_count"] for row in rows)
    weighted_score = (
        sum(float(row["score"]) / 100.0 * int(row["char_count"]) for row in rows) / total_chars
        if total_chars
        else 0.0
    )
    significant_ratio = significant_chars / total_chars if total_chars else 0.0
    adaptive_weight = 0.84 + 0.17 * clamp((total_chars - 3000) / 30000.0)
    overall = max(significant_ratio, clamp(weighted_score * adaptive_weight))
    distribution_20pct = _build_distribution_20pct(total_chars=total_chars, sentence_spans=sentence_spans)
    section_details = _build_section_details(rows, sentence_spans)
    return {
        "platform": "cnki",
        "profile": PROFILE,
        "paragraphs": rows,
        "overall_score": round(clamp(max(overall, weighted_score * 0.62)), 4),
        "significant_chars": significant_chars,
        "suspected_chars": suspected_chars,
        "total_chars": total_chars,
        "distribution_20pct": distribution_20pct,
        "section_details": section_details,
        "sentence_spans": sentence_spans,
        "strategy_trace": {
            "model": "cnki_internal_dual_threshold",
            "thresholds": {"suspected": 0.36, "significant": 0.53},
            "overall": "adaptive_weighted_blend_with_significant_floor",
        },
    }
