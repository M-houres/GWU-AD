from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models import TaskType
from app.services.aigc_detect_strategies.common import clamp, text_stats


def _distribution(paragraphs: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(paragraphs)
    scores = [float(item.get("score") or 0.0) for item in paragraphs]
    counts = {
        "high_count": sum(1 for item in paragraphs if item.get("label") == "high"),
        "medium_count": sum(1 for item in paragraphs if item.get("label") == "medium"),
        "low_count": sum(1 for item in paragraphs if item.get("label") == "low"),
        "clean_count": sum(1 for item in paragraphs if item.get("label") == "clean"),
    }
    return {
        "paragraph_count": total,
        **counts,
        "high_ratio": round(counts["high_count"] / total * 100.0, 2) if total else 0.0,
        "medium_ratio": round(counts["medium_count"] / total * 100.0, 2) if total else 0.0,
        "low_ratio": round(counts["low_count"] / total * 100.0, 2) if total else 0.0,
        "clean_ratio": round(counts["clean_count"] / total * 100.0, 2) if total else 0.0,
        "avg_score": round(sum(scores) / total, 2) if total else 0.0,
        "max_score": round(max(scores), 2) if scores else 0.0,
    }


def _fragment_distribution(paragraphs: list[dict[str, Any]], total_chars: int) -> dict[str, Any]:
    high_chars = sum(int(item.get("char_count") or 0) for item in paragraphs if item.get("label") == "high")
    medium_chars = sum(int(item.get("char_count") or 0) for item in paragraphs if item.get("label") == "medium")
    low_chars = sum(int(item.get("char_count") or 0) for item in paragraphs if item.get("label") == "low")
    risky_chars = high_chars + medium_chars + low_chars
    weighted = (
        sum(float(item.get("score") or 0.0) * int(item.get("char_count") or 0) for item in paragraphs) / total_chars
        if total_chars
        else 0.0
    )
    return {
        "fragment_count": sum(1 for item in paragraphs if item.get("label") != "clean"),
        "high_fragment_count": sum(1 for item in paragraphs if item.get("label") == "high"),
        "middle_fragment_count": sum(1 for item in paragraphs if item.get("label") == "medium"),
        "low_fragment_count": sum(1 for item in paragraphs if item.get("label") == "low"),
        "severe_fragment_count": sum(1 for item in paragraphs if float(item.get("score") or 0.0) >= 90.0),
        "high_suspected_text_ratio": round(high_chars / total_chars * 100.0, 2) if total_chars else 0.0,
        "middle_suspected_text_ratio": round(medium_chars / total_chars * 100.0, 2) if total_chars else 0.0,
        "low_suspected_text_ratio": round(low_chars / total_chars * 100.0, 2) if total_chars else 0.0,
        "high_and_middle_suspected_text_ratio": round((high_chars + medium_chars) / total_chars * 100.0, 2) if total_chars else 0.0,
        "total_suspected_text_ratio": round(risky_chars / total_chars * 100.0, 2) if total_chars else 0.0,
        "weighted_score_pct": round(weighted, 2),
    }


def _document_metrics(paragraphs: list[dict[str, Any]], total_chars: int) -> dict[str, Any]:
    paragraph_count = len(paragraphs)
    risky_indexes = [int(item.get("index") or 0) for item in paragraphs if item.get("label") in {"high", "medium"}]
    longest = 0
    current = 0
    previous = None
    for index in risky_indexes:
        current = current + 1 if previous is not None and index == previous + 1 else 1
        longest = max(longest, current)
        previous = index
    risk_chars = sum(int(item.get("char_count") or 0) for item in paragraphs if item.get("label") in {"high", "medium"})
    return {
        "paragraph_count": paragraph_count,
        "high_medium_paragraph_ratio": round(len(risky_indexes) / paragraph_count * 100.0, 2) if paragraph_count else 0.0,
        "section_coverage_ratio": round(len(risky_indexes) / paragraph_count * 100.0, 2) if paragraph_count else 0.0,
        "longest_risk_streak": longest,
        "longest_risk_streak_ratio": round(longest / paragraph_count * 100.0, 2) if paragraph_count else 0.0,
        "opening_similarity_ratio": 0.0,
        "evidence_relief_pct": 0.0,
        "abstract_avg_score": round(float(paragraphs[0].get("score") or 0.0), 2) if paragraphs else 0.0,
        "intro_avg_score": round(float(paragraphs[1].get("score") or 0.0), 2) if len(paragraphs) > 1 else 0.0,
        "risk_char_ratio": round(risk_chars / total_chars * 100.0, 2) if total_chars else 0.0,
    }


def _decision_basis(paragraphs: list[dict[str, Any]], strategy_trace: dict[str, Any]) -> list[dict[str, str]]:
    basis: list[dict[str, str]] = []
    tag_counts: dict[str, int] = {}
    for row in paragraphs:
        for tag in row.get("reason_tags") or []:
            tag_counts[str(tag)] = tag_counts.get(str(tag), 0) + 1
    for tag, count in sorted(tag_counts.items(), key=lambda item: item[1], reverse=True)[:4]:
        basis.append({"title": tag, "detail": f"段落级命中 {count} 次。", "direction": "risk"})
    model = str(strategy_trace.get("model") or "internal")
    basis.append({"title": "内部算法策略", "detail": f"执行链路：{model}。", "direction": "neutral"})
    return basis


def _collect_segments(paragraphs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for row in paragraphs:
        for segment in row.get("suspicious_segments") or []:
            segments.append({**segment, "paragraph_index": row.get("index")})
    return sorted(segments, key=lambda item: float(item.get("score") or 0.0), reverse=True)[:20]


def _summary(platform: str, profile: dict[str, Any], score_pct: float, stats: dict[str, Any], basis: list[dict[str, str]]) -> str:
    provider = str(profile.get("provider_label") or "AIGC检测")
    label = str(profile.get("score_label") or "AIGC疑似度")
    ai_chars = round(int(stats.get("char_count") or 0) * score_pct / 100.0)
    title = basis[0]["title"] if basis else "段落级综合特征"
    if platform == "cnki":
        return f"{provider}完成，{label} {score_pct}%，AI特征字符数 {ai_chars}，主要依据：{title}。结果用于内部研判与人工复核。"
    return f"{provider}完成，{label} {score_pct}%，全文人写概率 {round(max(0.0, 100.0 - score_pct), 2)}%，主要依据：{title}。结果用于内部研判与人工复核。"


def build_report_payload(
    *,
    text: str,
    platform: str,
    detect_output: dict[str, Any],
    report_summary: dict[str, Any],
    mode: str,
    task_id: int | None,
) -> dict[str, Any]:
    profile = detect_output["profile"]
    paragraphs = detect_output["paragraphs"]
    stats = text_stats(text)
    total_chars = int(stats.get("char_count") or 0)
    distribution = _distribution(paragraphs)
    fragment_distribution = _fragment_distribution(paragraphs, total_chars)
    document_metrics = _document_metrics(paragraphs, total_chars)
    decision_basis = _decision_basis(paragraphs, detect_output.get("strategy_trace") or {})
    segments = _collect_segments(paragraphs)
    score = clamp(float(detect_output.get("overall_score") or 0.0))
    score_pct = round(score * 100.0, 2)
    if score >= float(profile.get("high", 0.65)):
        label = "high"
    elif score >= float(profile.get("medium", 0.35)):
        label = "medium"
    elif score >= float(profile.get("low", 0.18)):
        label = "low"
    else:
        label = "clean"
    risk_band = "高风险" if label == "high" else "中风险" if label == "medium" else "低风险"
    detail_expanded = bool(score_pct >= (12.0 if platform == "cnki" else 35.0) or segments)
    risk_paragraphs = sorted(paragraphs, key=lambda item: float(item.get("score") or 0.0), reverse=True)[:5]
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report_no = f"GW-AIGC-{platform.upper()}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{task_id or 0}"
    breakdown = {
        "strategy": "algorithm",
        "strategy_source": "internal_aigc_detect_strategy",
        "model": detect_output.get("strategy_trace", {}).get("model"),
        "thresholds": detect_output.get("strategy_trace", {}).get("thresholds", {}),
        "score_source": "internal_feature_chain",
        "paragraph_mean_score": round(float(distribution.get("avg_score") or 0.0) / 100.0, 4),
        "peak_paragraph_score": round(float(distribution.get("max_score") or 0.0) / 100.0, 4),
        "fragment_weighted_score": round(float(fragment_distribution.get("weighted_score_pct") or 0.0) / 100.0, 4),
        "raw_score_pct": score_pct,
        "calibrated_score_pct": score_pct,
        "llm_blended": False,
    }
    return {
        "type": TaskType.AIGC_DETECT.value,
        "platform": platform,
        "provider_label": profile["provider_label"],
        "score_label": profile["score_label"],
        "simulation_profile": profile["name"],
        "report_no": report_no,
        "generated_at": generated_at,
        "mode": mode,
        "llm_used": False,
        "ai_score": score,
        "score_pct": score_pct,
        "label": label,
        "risk_band": risk_band,
        "summary": _summary(platform, profile, score_pct, stats, decision_basis),
        "source_stats": stats,
        "report_summary": report_summary,
        "score_breakdown": breakdown,
        "distribution": distribution,
        "fragment_distribution": fragment_distribution,
        "document_metrics": document_metrics,
        "decision_basis": decision_basis,
        "document_outline": [],
        "section_distribution": [],
        "detail_expanded": detail_expanded,
        "risk_paragraphs": risk_paragraphs if detail_expanded else [],
        "paragraph_details": paragraphs,
        "suspicious_segments": segments if detail_expanded else [],
        "aigc_detect_strategy": {
            "strategy": "algorithm",
            "platform": platform,
            "task_type": TaskType.AIGC_DETECT.value,
            "rule_trace": detect_output.get("strategy_trace") or {},
        },
    }
