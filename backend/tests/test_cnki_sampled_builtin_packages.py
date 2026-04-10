from app.services.algo_package_service import run_active_package
from app.services.builtin_algo_packages import bootstrap_builtin_algo_packages
from app.services.processing_engine import ProcessingEngine


HIGH_RISK_CNKI_TEXT = """
摘要
本研究以X餐饮连锁公司为研究对象，旨在系统分析其营销策略问题，并构建客户体验优化路径。研究结论显示，本文提出的实施保障机制能够提升客户满意度和品牌忠诚度。
Abstract
This study takes X catering chain as the research object and aims to build an optimization framework for customer experience.
绪论
在消费升级背景下，本研究围绕客户体验展开系统分析。基于上述诊断，本文提出相应策略与实施保障方案。
相关概念、理论基础
本部分主要梳理客户体验与4C理论的相关概念，并结合既有研究说明理论基础。
实证分析
2024年共回收问卷312份，访谈18人，N=312。结果显示顾客复购率提升12.6%，见表3。
""".strip()


LOW_RISK_TEXT = """
实证分析
2024年共回收问卷312份，访谈18人，N=312。样本来自三家门店，共形成18份访谈记录和312份有效问卷，统计结果见表3和表4。
""".strip()


def test_cnki_builtin_aigc_package_emphasizes_abstract_intro_patterns(
    db_session,
    settings_override,
) -> None:
    bootstrap_builtin_algo_packages(db_session, uploaded_by=1, activate_after_upload=True)

    high_risk_result, _meta = run_active_package(
        db_session,
        platform="cnki",
        function_type="aigc_detect",
        text=HIGH_RISK_CNKI_TEXT,
    )
    low_risk_result, _meta = run_active_package(
        db_session,
        platform="cnki",
        function_type="aigc_detect",
        text=LOW_RISK_TEXT,
    )

    assert isinstance(high_risk_result, dict)
    assert high_risk_result["algorithm"].startswith("cnki_like_aigc_sim_v1_6_0")
    assert high_risk_result["ai_score"] > low_risk_result["ai_score"]
    assert high_risk_result["document_metrics"]["abstract_avg_score"] >= 45
    assert high_risk_result["document_metrics"]["intro_avg_score"] >= 35
    assert any("摘要" in item["title"] for item in high_risk_result["decision_basis"])


def test_cnki_builtin_rewrite_package_reduces_template_score_and_fixes_artifacts(
    db_session,
    settings_override,
) -> None:
    bootstrap_builtin_algo_packages(db_session, uploaded_by=1, activate_after_upload=True)
    source = (
        "摘要：本研究以X餐饮连锁公司为研究对象，旨在构建客户体验优化体系。"
        "基于上述诊断，本文提出实施保障机制。当前文本存在需要求、知识得到等不自然表达。"
    )

    result, _meta = run_active_package(
        db_session,
        platform="cnki",
        function_type="rewrite",
        text=source,
    )

    assert isinstance(result, dict)
    assert result["algorithm"] == "cnki_rewrite_sim_v1_2_0"
    assert result["rewritten_aigc_score"] < result["original_aigc_score"]
    assert result["transformation_count"] > 0
    assert "需要求" not in result["text"]
    assert "知识得到" not in result["text"]
    assert "需求" in result["text"]
    assert "知识获取" in result["text"]
    assert "本文围绕X餐饮连锁公司展开分析" in result["text"]


def test_cnki_builtin_dedup_package_rewrites_cnki_style_expressions(
    db_session,
    settings_override,
) -> None:
    bootstrap_builtin_algo_packages(db_session, uploaded_by=1, activate_after_upload=True)
    source = (
        "研究表明，客户体验是企业营销策略优化的重要组成部分。"
        "通过构建评价体系，实现客户满意度提升。"
    )

    result, _meta = run_active_package(
        db_session,
        platform="cnki",
        function_type="dedup",
        text=source,
    )

    assert isinstance(result, dict)
    assert result["algorithm"] == "cnki_dedup_sim_v1_2_0"
    assert result["changes"] > 0
    assert result["text"] != source
    assert "研究表明" not in result["text"]
    assert "已有研究指出" in result["text"]


def test_processing_engine_cnki_detect_tracks_abstract_and_intro_bias(db_session) -> None:
    engine = ProcessingEngine(db_session)

    result = engine._build_detect_result(
        text=HIGH_RISK_CNKI_TEXT,
        platform="cnki",
        mode="ALGO_ONLY",
        report_summary={"available": False, "metrics": [], "highlights": [], "recommended_actions": [], "pressure": "low"},
        algo_result=None,
        llm_result=None,
    )

    assert result["document_metrics"]["abstract_avg_score"] > result["document_metrics"]["review_avg_score"]
    assert result["document_metrics"]["intro_avg_score"] >= result["document_metrics"]["review_avg_score"]
    assert any("摘要" in item["title"] for item in result["decision_basis"])
