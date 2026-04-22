from app.models import TaskType


def enrich_detect_breakdown(
    breakdown: dict,
    *,
    mean_paragraph_ratio: float,
    max_paragraph_ratio: float,
    segment_ratio: float,
    fragment_weighted_ratio: float,
    high_middle_text_ratio: float,
    outline_sections: int,
    coverage_ratio: float,
    section_coverage_ratio: float,
    streak_ratio: float,
    opening_similarity_ratio: float,
    evidence_relief_ratio: float,
    abstract_section_ratio: float,
    intro_section_ratio: float,
    raw_score: float,
    score_pct: float,
) -> dict:
    enriched = dict(breakdown)
    enriched["paragraph_mean_score"] = mean_paragraph_ratio
    enriched["peak_paragraph_score"] = max_paragraph_ratio
    enriched["segment_signal"] = segment_ratio
    enriched["fragment_weighted_score"] = fragment_weighted_ratio
    enriched["high_middle_text_ratio"] = high_middle_text_ratio
    enriched["outline_sections"] = outline_sections
    enriched["coverage_ratio"] = coverage_ratio
    enriched["section_coverage_ratio"] = section_coverage_ratio
    enriched["streak_ratio"] = streak_ratio
    enriched["opening_similarity_ratio"] = opening_similarity_ratio
    enriched["evidence_relief_ratio"] = evidence_relief_ratio
    enriched["abstract_section_ratio"] = abstract_section_ratio
    enriched["intro_section_ratio"] = intro_section_ratio
    enriched["raw_score_pct"] = round(raw_score * 100, 2)
    enriched["calibrated_score_pct"] = score_pct
    return enriched


def build_detect_summary(
    *,
    platform: str,
    profile: dict,
    score_pct: float,
    source_stats: dict,
    detail_expanded: bool,
    basis_titles: list[str],
    fragment_distribution: dict,
    distribution: dict,
) -> str:
    reported_ai_chars = round(int(source_stats.get("char_count") or 0) * score_pct / 100.0)
    if platform == "cnki":
        summary = (
            f"{profile['provider_label']}检测完成，{profile['score_label']} {score_pct}%，"
            f"AI特征字符数 {reported_ai_chars}，总字符数 {int(source_stats.get('char_count') or 0)}。"
        )
        if detail_expanded and basis_titles:
            summary += f" 主要依据：{'、'.join(basis_titles[:2])}。"
        elif not detail_expanded:
            summary += " 当前未识别到稳定可计入的高置信片段。"
        summary += " 结果用于内部研判与人工复核。"
        return summary
    if platform == "vip":
        summary = (
            f"{profile['provider_label']}检测完成，{profile['score_label']} {score_pct}%，"
            f"全文人写概率 {round(max(0.0, 100.0 - score_pct), 2)}%。"
            f" AI生成文字 {reported_ai_chars}。"
        )
        if detail_expanded and basis_titles:
            summary += f" 主要依据：{'、'.join(basis_titles[:2])}。"
        elif not detail_expanded:
            summary += " 当前报告侧重低风险结论提示。"
        summary += " 结果用于内部研判与人工复核。"
        return summary
    summary = (
        f"{profile['provider_label']}全文检测完成，{profile['score_label']} {score_pct}%，"
        f"片段加权结果 {fragment_distribution.get('weighted_score_pct', 0.0)}%，"
        f"高风险段落占比 {distribution.get('high_ratio', 0.0)}%。"
    )
    if basis_titles:
        summary += f" 主要依据：{'、'.join(basis_titles[:2])}。"
    summary += " 结果用于内部研判与人工复核。"
    return summary


def build_detect_result_payload(
    *,
    platform: str,
    profile: dict,
    report_no: str,
    generated_at: str,
    mode: str,
    pipeline_usage: dict,
    score: float,
    score_pct: float,
    label: str,
    band: str,
    summary: str,
    source_stats: dict,
    report_summary: dict,
    breakdown: dict,
    distribution: dict,
    fragment_distribution: dict,
    document_metrics: dict,
    decision_basis: list[dict],
    document_outline: list[dict],
    section_distribution: list[dict],
    detail_expanded: bool,
    risk_paragraphs: list[dict],
    paragraph_details: list[dict],
    suspicious_segments: list[dict],
) -> dict:
    return {
        "type": TaskType.AIGC_DETECT.value,
        "platform": platform,
        "provider_label": profile["provider_label"],
        "score_label": profile["score_label"],
        "simulation_profile": profile["name"],
        "report_no": report_no,
        "generated_at": generated_at,
        "mode": mode,
        "llm_used": bool(pipeline_usage.get("llm_used")),
        "ai_score": score,
        "score_pct": score_pct,
        "label": label,
        "risk_band": band,
        "summary": summary,
        "source_stats": source_stats,
        "report_summary": report_summary,
        "score_breakdown": breakdown,
        "distribution": distribution,
        "fragment_distribution": fragment_distribution,
        "document_metrics": document_metrics,
        "decision_basis": decision_basis,
        "document_outline": document_outline,
        "section_distribution": section_distribution,
        "detail_expanded": detail_expanded,
        "risk_paragraphs": risk_paragraphs,
        "paragraph_details": paragraph_details,
        "suspicious_segments": suspicious_segments,
    }
