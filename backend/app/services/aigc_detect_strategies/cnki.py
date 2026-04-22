from __future__ import annotations

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
    split_paragraphs,
)

PROFILE = {
    "name": "cnki_internal",
    "provider_label": "知网AIGC检测仿真",
    "score_label": "AI特征值",
    "high": 0.60,
    "medium": 0.40,
    "low": 0.18,
}


def _paragraph_score(features: ParagraphFeatures) -> tuple[float, dict[str, float]]:
    syntax = clamp(
        clamp((features.sent_len_mean - 18.0) / 42.0) * 0.48
        + (1.0 - clamp(features.sent_len_cv / 0.9)) * 0.26
        + features.punct_regularity * 0.18
        + clamp((0.0 - features.burstiness + 0.35) / 0.7) * 0.08
    )
    lexical = clamp(
        clamp(features.ai_noun_ratio / 2.8) * 0.34
        + clamp(features.ai_verb_ratio / 2.8) * 0.26
        + clamp(features.fourch_density / 5.0) * 0.20
        + clamp(features.conn_density / 3.8) * 0.14
        + (1.0 - clamp(features.ttr / 0.72)) * 0.06
    )
    discourse = clamp(
        features.tmpl_hit * 0.32
        + features.parallel_hit * 0.30
        + features.phil_hit_tail * 0.16
        + clamp(features.definition_rate / 0.7) * 0.12
        + features.dup_ngram_ratio * 0.10
    )
    specificity_relief = clamp(
        clamp(features.entity_density / 2.8) * 0.34
        + clamp(features.domain_term_density / 2.4) * 0.24
        + clamp(features.concrete_density / 3.0) * 0.22
        + clamp(features.quote_density / 2.0) * 0.10
        + clamp(features.num_density / 2.4) * 0.10
    )
    raw = syntax * 0.31 + lexical * 0.30 + discourse * 0.31 + features.dup_ngram_ratio * 0.08
    score = clamp(sigmoid((raw - specificity_relief * 0.28 - 0.33) / 0.18))
    return score, {
        "syntax_signal": round(syntax, 4),
        "lexical_signal": round(lexical, 4),
        "discourse_signal": round(discourse, 4),
        "specificity_relief": round(specificity_relief, 4),
        "raw_signal": round(raw, 4),
    }


def detect(text: str) -> dict[str, Any]:
    paragraphs = split_paragraphs(text)
    rows: list[dict[str, Any]] = []
    for index, paragraph in enumerate(paragraphs, start=1):
        features = extract_features(paragraph)
        score, sub_scores = _paragraph_score(features)
        label = label_from_score(score, high=PROFILE["high"], medium=PROFILE["medium"], low=PROFILE["low"])
        rows.append(
            {
                "index": index,
                "label": label,
                "risk_band": risk_band(label),
                "score": round(score * 100.0, 2),
                "char_count": features.char_count,
                "sentence_count": features.sentence_count,
                "excerpt": paragraph[:110] + ("..." if len(paragraph) > 110 else ""),
                "reason_tags": reason_tags(features, label),
                "suspicious_segments": paragraph_segments(paragraph, score, label, features),
                "features": features.as_dict(),
                "sub_scores": sub_scores,
            }
        )
    significant_chars = sum(row["char_count"] for row in rows if row["label"] == "high")
    suspected_chars = sum(row["char_count"] for row in rows if row["label"] == "medium")
    total_chars = sum(row["char_count"] for row in rows)
    overall = significant_chars / total_chars if total_chars else 0.0
    weighted_score = (
        sum(float(row["score"]) / 100.0 * int(row["char_count"]) for row in rows) / total_chars
        if total_chars
        else 0.0
    )
    return {
        "platform": "cnki",
        "profile": PROFILE,
        "paragraphs": rows,
        "overall_score": round(clamp(max(overall, weighted_score * 0.62)), 4),
        "significant_chars": significant_chars,
        "suspected_chars": suspected_chars,
        "total_chars": total_chars,
        "strategy_trace": {
            "model": "cnki_internal_dual_threshold",
            "thresholds": {"suspected": 0.40, "significant": 0.60},
            "overall": "significant_fragment_chars_with_weighted_floor",
        },
    }

