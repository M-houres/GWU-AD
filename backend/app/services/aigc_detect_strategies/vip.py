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
    "name": "vip_internal",
    "provider_label": "维普AIGC检测仿真",
    "score_label": "全文疑似AIGC生成",
    "high": 0.90,
    "medium": 0.70,
    "low": 0.50,
}


def _paragraph_score(features: ParagraphFeatures) -> tuple[float, dict[str, float]]:
    p_ling = clamp(
        clamp(features.ai_verb_ratio / 2.4) * 0.24
        + clamp(features.ai_noun_ratio / 2.4) * 0.24
        + clamp(features.conn_density / 3.0) * 0.18
        + clamp(features.fourch_density / 4.8) * 0.18
        + (1.0 - clamp(features.ttr / 0.70)) * 0.16
    )
    p_tmpl = clamp(
        features.tmpl_hit * 0.35
        + features.parallel_hit * 0.28
        + features.phil_hit_tail * 0.20
        + clamp(features.definition_rate / 0.6) * 0.17
    )
    p_ent = clamp(
        1.0
        - (
            clamp(features.entity_density / 2.8) * 0.34
            + clamp(features.domain_term_density / 2.2) * 0.30
            + clamp(features.concrete_density / 2.8) * 0.22
            + clamp(features.num_density / 2.0) * 0.14
        )
    )
    p_sem = clamp(
        features.dup_ngram_ratio * 0.36
        + (1.0 - clamp(features.sent_len_cv / 0.85)) * 0.30
        + clamp((features.sent_len_mean - 20.0) / 45.0) * 0.22
        + features.punct_regularity * 0.12
    )
    fused = p_ling * 0.28 + p_tmpl * 0.32 + p_ent * 0.25 + p_sem * 0.15
    amplified = fused * 1.18 + clamp(features.conn_density / 2.5) * 0.10 + features.parallel_hit * 0.08
    score = clamp(sigmoid((amplified - 0.43 - 0.12) / 0.72 * 4.0))
    return score, {
        "p_ling": round(p_ling, 4),
        "p_tmpl": round(p_tmpl, 4),
        "p_ent": round(p_ent, 4),
        "p_sem": round(p_sem, 4),
        "fused": round(fused, 4),
        "amplified": round(amplified, 4),
        "temperature": 0.85,
        "bias": -0.12,
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
    total_chars = sum(row["char_count"] for row in rows)
    overall = (
        sum(float(row["score"]) / 100.0 * int(row["char_count"]) for row in rows) / total_chars
        if total_chars
        else 0.0
    )
    return {
        "platform": "vip",
        "profile": PROFILE,
        "paragraphs": rows,
        "overall_score": round(clamp(overall), 4),
        "significant_chars": sum(row["char_count"] for row in rows if row["label"] == "high"),
        "suspected_chars": sum(row["char_count"] for row in rows if row["label"] in {"medium", "low"}),
        "total_chars": total_chars,
        "strategy_trace": {
            "model": "vip_internal_18_feature_fusion",
            "thresholds": {"high": 0.90, "medium": 0.70, "low": 0.50},
            "fusion_weights": {"p_ling": 0.28, "p_tmpl": 0.32, "p_ent": 0.25, "p_sem": 0.15},
        },
    }
