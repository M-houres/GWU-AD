from app.services.processing_detect_result_builder import (
    build_detect_result_payload,
    build_detect_summary,
    enrich_detect_breakdown,
)


def test_enrich_detect_breakdown_adds_expected_metrics() -> None:
    result = enrich_detect_breakdown(
        {"base_score": 0.3},
        mean_paragraph_ratio=0.41,
        max_paragraph_ratio=0.62,
        segment_ratio=0.52,
        fragment_weighted_ratio=0.48,
        high_middle_text_ratio=0.37,
        outline_sections=6,
        coverage_ratio=0.55,
        section_coverage_ratio=0.44,
        streak_ratio=0.18,
        opening_similarity_ratio=0.13,
        evidence_relief_ratio=0.09,
        abstract_section_ratio=0.61,
        intro_section_ratio=0.43,
        raw_score=0.5123,
        score_pct=47.8,
    )

    assert result["base_score"] == 0.3
    assert result["paragraph_mean_score"] == 0.41
    assert result["outline_sections"] == 6
    assert result["raw_score_pct"] == 51.23
    assert result["calibrated_score_pct"] == 47.8


def test_build_detect_summary_formats_cnki_compact_message() -> None:
    summary = build_detect_summary(
        platform="cnki",
        profile={"provider_label": "知网AIGC检测仿真", "score_label": "AI特征值"},
        score_pct=23.4,
        source_stats={"char_count": 1000},
        detail_expanded=False,
        basis_titles=[],
        fragment_distribution={"weighted_score_pct": 21.0},
        distribution={"high_ratio": 11.0},
    )

    assert "知网AIGC检测仿真检测完成" in summary
    assert "AI特征值 23.4%" in summary
    assert "AI特征字符数 234" in summary
    assert "当前未识别到稳定可计入的高置信片段" in summary


def test_build_detect_summary_formats_vip_detailed_message() -> None:
    summary = build_detect_summary(
        platform="vip",
        profile={"provider_label": "维普AIGC检测仿真", "score_label": "全文疑似AIGC生成"},
        score_pct=41.2,
        source_stats={"char_count": 800},
        detail_expanded=True,
        basis_titles=["摘要风险偏高", "段首模板化"],
        fragment_distribution={"weighted_score_pct": 39.0},
        distribution={"high_ratio": 20.0},
    )

    assert "维普AIGC检测仿真检测完成" in summary
    assert "全文人写概率 58.8%" in summary
    assert "主要依据：摘要风险偏高、段首模板化" in summary


def test_build_detect_result_payload_keeps_fields_stable() -> None:
    result = build_detect_result_payload(
        platform="cnki",
        profile={"provider_label": "知网AIGC检测仿真", "score_label": "AI特征值", "name": "cnki_like"},
        report_no="GW-AIGC-CNKI-1",
        generated_at="2026-04-19 17:40:00",
        mode="ALGO_ONLY",
        pipeline_usage={"llm_used": False},
        score=0.38,
        score_pct=38.0,
        label="medium",
        band="中风险",
        summary="summary",
        source_stats={"char_count": 1234},
        report_summary={"available": True},
        breakdown={"raw_score_pct": 41.0},
        distribution={"high_ratio": 10.0},
        fragment_distribution={"weighted_score_pct": 31.0},
        document_metrics={"section_coverage_ratio": 22.0},
        decision_basis=[{"title": "摘要风险偏高", "direction": "risk"}],
        document_outline=[{"title": "摘要"}],
        section_distribution=[{"label": "前部20%"}],
        detail_expanded=True,
        risk_paragraphs=[{"index": 1}],
        paragraph_details=[{"index": 1}],
        suspicious_segments=[{"text": "片段"}],
    )

    assert result["type"] == "aigc_detect"
    assert result["platform"] == "cnki"
    assert result["simulation_profile"] == "cnki_like"
    assert "algo_package_used" not in result
    assert result["detail_expanded"] is True
    assert result["risk_paragraphs"] == [{"index": 1}]
