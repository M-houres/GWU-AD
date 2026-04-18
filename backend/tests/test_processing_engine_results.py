from pathlib import Path

from docx import Document
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.models import TaskType
from app.services.processing_engine import ProcessingEngine


def _write_docx(path: Path, paragraphs: list[str]) -> None:
    doc = Document()
    for paragraph in paragraphs:
        doc.add_paragraph(paragraph)
    doc.save(path)


def test_rewrite_process_uses_report_summary(tmp_path: Path, db_session: Session, monkeypatch) -> None:
    source_path = tmp_path / "paper.docx"
    report_path = tmp_path / "report.docx"
    output_path = tmp_path / "result.docx"

    _write_docx(
        source_path,
        [
            "研究表明，这一方法非常重要，而且很多场景都可以看出类似趋势。",
            "这个结论在教学和管理实践中具有较强参考价值。",
        ],
    )
    _write_docx(
        report_path,
        [
            "全文AIGC检测报告",
            "总体风险 52%",
            "高风险段落占比 24%",
        ],
    )

    monkeypatch.setattr(ProcessingEngine, "_run_llm", lambda self, *_args, **_kwargs: None)
    monkeypatch.setattr(ProcessingEngine, "_run_algo_package", lambda self, *_args, **_kwargs: None)

    engine = ProcessingEngine(db_session)
    result = engine.process(
        TaskType.REWRITE,
        "cnki",
        source_path,
        output_path,
        task_id=1,
        report_path=report_path,
    )

    assert output_path.exists()
    assert result.result_json["type"] == "rewrite"
    assert result.result_json["report_summary"]["available"] is True
    assert result.result_json["report_summary"]["pressure"] == "high"
    assert len(result.result_json["report_summary"]["metrics"]) >= 1
    assert len(result.result_json["review_points"]) >= 1
    assert isinstance(result.result_json["output_preview"], str)
    assert result.result_json["source_stats"]["char_count"] > 0
    assert result.result_json["output_stats"]["char_count"] > 0


def test_aigc_detect_returns_structured_result(tmp_path: Path, db_session: Session, monkeypatch) -> None:
    source_path = tmp_path / "paper.txt"
    output_path = tmp_path / "result.pdf"
    source_path.write_text(
        "本研究围绕教学改革展开讨论。"
        "研究表明该方案在多个学院中具有稳定的执行路径，因此能够快速复制。"
        "\n"
        "此外，文章采用一致的段落结构和重复性的总结语句，这会提高自动化写作特征。",
        encoding="utf-8",
    )

    monkeypatch.setattr(ProcessingEngine, "_run_algo_package", lambda self, *_args, **_kwargs: None)

    engine = ProcessingEngine(db_session)
    result = engine.process(TaskType.AIGC_DETECT, "cnki", source_path, output_path, task_id=2)

    assert output_path.exists()
    assert result.result_json["type"] == "aigc_detect"
    assert "summary" in result.result_json
    assert "risk_band" in result.result_json
    assert result.result_json["simulation_profile"] == "cnki_like"
    assert result.result_json["provider_label"] == "知网AIGC检测仿真"
    assert result.result_json["source_stats"]["char_count"] > 0
    assert len(result.result_json["risk_paragraphs"]) >= 1
    assert len(result.result_json["paragraph_details"]) >= 1
    assert "distribution" in result.result_json
    assert "fragment_distribution" in result.result_json
    assert "document_metrics" in result.result_json
    assert "decision_basis" in result.result_json
    assert "document_outline" in result.result_json
    assert "suspicious_segments" in result.result_json
    content = output_path.read_bytes()
    assert content.startswith(b"%PDF-")
    assert b"/STSong-Light" in content


def test_aigc_detect_platform_profiles_are_close_but_not_identical(
    tmp_path: Path, db_session: Session, monkeypatch
) -> None:
    source_path = tmp_path / "paper_platform.txt"
    source_path.write_text(
        "本研究基于教学管理数据，围绕课程评价机制展开分析。\n"
        "文章包含连续论证句、固定连接词和重复总结表达，用于模拟AIGC风险检测场景。\n"
        "在不同平台规则下，分值应保持相近，但因评分偏好不同会存在轻微差异。",
        encoding="utf-8",
    )
    monkeypatch.setattr(ProcessingEngine, "_run_algo_package", lambda self, *_args, **_kwargs: None)

    engine = ProcessingEngine(db_session)
    results = {}
    for platform in ("cnki", "vip"):
        output_path = tmp_path / f"{platform}.pdf"
        result = engine.process(TaskType.AIGC_DETECT, platform, source_path, output_path, task_id=100)
        results[platform] = float(result.result_json["score_pct"])
        assert output_path.exists()

    assert len(set(round(value, 2) for value in results.values())) >= 2
    assert max(results.values()) - min(results.values()) <= 15


def test_rewrite_process_accepts_nested_algo_text_fields(tmp_path: Path, db_session: Session, monkeypatch) -> None:
    source_path = tmp_path / "rewrite.txt"
    output_path = tmp_path / "rewrite_out.txt"
    source_path.write_text("原始文本", encoding="utf-8")

    monkeypatch.setattr(ProcessingEngine, "_run_llm", lambda self, *_args, **_kwargs: None)
    monkeypatch.setattr(
        ProcessingEngine,
        "_run_algo_package",
        lambda self, *_args, **_kwargs: {"result": {"content": "算法包输出正文"}},
    )

    engine = ProcessingEngine(db_session)
    result = engine.process(TaskType.REWRITE, "cnki", source_path, output_path, task_id=3)

    assert output_path.exists()
    assert output_path.read_text(encoding="utf-8") == "算法包输出正文"
    assert result.result_json["type"] == "rewrite"
    assert result.result_json["output_stats"]["char_count"] > 0


def test_aigc_detect_accepts_nested_score_and_chinese_label(tmp_path: Path, db_session: Session, monkeypatch) -> None:
    source_path = tmp_path / "detect.txt"
    output_path = tmp_path / "detect.pdf"
    source_path.write_text("用于检测的正文内容。", encoding="utf-8")

    monkeypatch.setattr(ProcessingEngine, "_run_llm", lambda self, *_args, **_kwargs: None)
    monkeypatch.setattr(
        ProcessingEngine,
        "_run_algo_package",
        lambda self, *_args, **_kwargs: {"data": {"risk_score": "63%", "risk_level": "高风险"}},
    )

    engine = ProcessingEngine(db_session)
    result = engine.process(TaskType.AIGC_DETECT, "cnki", source_path, output_path, task_id=4)

    assert output_path.exists()
    assert result.result_json["label"] == "high"
    assert result.result_json["score_pct"] > 0
    assert result.result_json["score_breakdown"].get("algo_package_score") == 0.63
    assert "algo_package_score" in result.result_json["score_breakdown"]
    assert "distribution" in result.result_json
    assert "fragment_distribution" in result.result_json
    assert "document_metrics" in result.result_json
    assert "decision_basis" in result.result_json


def test_aigc_detect_full_text_pdf_report_is_parseable(tmp_path: Path, db_session: Session, monkeypatch) -> None:
    source_path = tmp_path / "full_text.txt"
    output_path = tmp_path / "full_text_report.pdf"
    paragraphs = [
        f"第{i}段：本研究围绕教学治理展开分析，研究表明该路径具备较强复制性，因此可以看出其表达具有模板化倾向，同时在多个场景中重复使用统一结论。"
        for i in range(1, 19)
    ]
    source_path.write_text("\n".join(paragraphs), encoding="utf-8")

    monkeypatch.setattr(ProcessingEngine, "_run_algo_package", lambda self, *_args, **_kwargs: None)

    engine = ProcessingEngine(db_session)
    result = engine.process(TaskType.AIGC_DETECT, "vip", source_path, output_path, task_id=8)

    assert output_path.exists()
    assert len(result.result_json["paragraph_details"]) == 18
    assert result.result_json["fragment_distribution"]["fragment_count"] > 0
    assert result.result_json["fragment_distribution"]["severe_fragment_count"] >= 0
    assert result.result_json["document_metrics"]["paragraph_count"] == 18
    reader = PdfReader(str(output_path))
    assert len(reader.pages) >= 2


def test_aigc_detect_pdf_uses_single_full_report_layout(tmp_path: Path, db_session: Session, monkeypatch) -> None:
    source_path = tmp_path / "layout_text.txt"
    output_path = tmp_path / "layout_report.pdf"
    paragraphs = [
        "Academic writing quality review sample title",
        "Abstract",
    ] + [
        "This report layout validation paragraph keeps a stable academic tone and repeats enough structured "
        "phrasing to trigger the full text report rendering path."
        for _ in range(10)
    ]
    source_path.write_text("\n".join(paragraphs), encoding="utf-8")

    monkeypatch.setattr(ProcessingEngine, "_run_algo_package", lambda self, *_args, **_kwargs: None)

    engine = ProcessingEngine(db_session)
    engine.process(TaskType.AIGC_DETECT, "cnki", source_path, output_path, task_id=9)

    reader = PdfReader(str(output_path))
    extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "AIGC检测" in extracted
    assert "全文报告单" in extracted
    assert "全文检测结果" in extracted
    assert "AIGC片段分布图" in extracted
    assert "片段指标列表" in extracted
    assert "原文内容" in extracted
    assert "说明" in extracted
    assert len(reader.pages) >= 2


def test_transform_text_combined_mode_runs_algo_then_llm(db_session: Session, monkeypatch) -> None:
    engine = ProcessingEngine(db_session)
    engine._effective_mode = "LLM_PLUS_ALGO"

    call_order: list[tuple[str, str]] = []

    def _fake_algo(self, _platform: str, _task_type: TaskType, text: str):
        call_order.append(("algo", text))
        self._pipeline_usage["algo_package_used"] = True
        return {"text": f"algo::{text}"}

    def _fake_llm(self, _task_type: TaskType, text: str):
        call_order.append(("llm", text))
        self._pipeline_usage["llm_used"] = True
        return f"llm::{text}"

    monkeypatch.setattr(ProcessingEngine, "_run_algo_package", _fake_algo)
    monkeypatch.setattr(ProcessingEngine, "_run_llm", _fake_llm)

    output = engine._transform_text("source text", TaskType.REWRITE, "cnki", {})

    assert output == "llm::algo::source text"
    assert call_order[0][0] == "algo"
    assert call_order[1][0] == "llm"
    assert call_order[1][1] == "algo::source text"


def test_transform_text_combined_mode_falls_back_to_algo_when_llm_empty(db_session: Session, monkeypatch) -> None:
    engine = ProcessingEngine(db_session)
    engine._effective_mode = "LLM_PLUS_ALGO"

    call_order: list[str] = []

    def _fake_algo(self, _platform: str, _task_type: TaskType, text: str):
        call_order.append("algo")
        self._pipeline_usage["algo_package_used"] = True
        return {"text": f"algo::{text}"}

    def _fake_llm(self, _task_type: TaskType, _text: str):
        call_order.append("llm")
        return None

    monkeypatch.setattr(ProcessingEngine, "_run_algo_package", _fake_algo)
    monkeypatch.setattr(ProcessingEngine, "_run_llm", _fake_llm)

    output = engine._transform_text("source text", TaskType.DEDUP, "cnki", {})

    assert output == "algo::source text"
    assert call_order == ["algo", "llm"]


def test_split_detect_paragraphs_merges_wrapped_lines(db_session: Session) -> None:
    engine = ProcessingEngine(db_session)
    text = "\n".join(
        [
            "第一章 绪论",
            "本研究围绕数智教学改革展开分析，系统梳理平台治理、课程设计与组织协同三方面问题，",
            "研究表明该路径具备较强复制性，并且在多个应用场景中形成稳定的实施框架，",
            "同时能够通过统一表达快速生成结构完整的段落内容。",
            "此外，本研究进一步从资源统筹角度提出建议，",
            "强调通过过程监督与结果复核提升治理质量。",
        ]
    )

    paragraphs = engine._split_detect_paragraphs(text)

    assert paragraphs[0] == "第一章 绪论"
    assert len(paragraphs) == 3
    assert paragraphs[1].startswith("本研究围绕数智教学改革展开分析")
    assert paragraphs[2].startswith("此外，本研究进一步从资源统筹角度提出建议")


def test_detect_label_supports_clean_band(db_session: Session) -> None:
    engine = ProcessingEngine(db_session)
    profile = engine._platform_detect_profile("cnki")

    assert engine._score_to_detect_label(0.12, profile) == "clean"
    assert engine._score_to_detect_label(0.24, profile) == "low"
    assert engine._score_to_detect_label(0.50, profile) == "medium"


def test_detect_label_prefers_higher_risk_between_algo_and_score(db_session: Session) -> None:
    engine = ProcessingEngine(db_session)

    assert engine._prefer_higher_risk_detect_label("clean", "low") == "low"
    assert engine._prefer_higher_risk_detect_label("low", "medium") == "medium"
    assert engine._prefer_higher_risk_detect_label("high", "low") == "high"


def test_cnki_borderline_paragraph_is_not_kept_clean(db_session: Session, monkeypatch) -> None:
    engine = ProcessingEngine(db_session)
    profile = engine._platform_detect_profile("cnki")

    monkeypatch.setattr(ProcessingEngine, "_extract_algo_paragraphs", lambda self, _algo: [])
    monkeypatch.setattr(ProcessingEngine, "_local_suspicious_segments_v2", lambda self, _paragraph, _platform, _profile: [])
    monkeypatch.setattr(
        ProcessingEngine,
        "_simulate_platform_detect_score",
        lambda self, _platform, _text, _base: (
            0.155,
            profile,
            {
                "template_signal": 0.0,
                "repeat_signal": 0.0,
                "context_signal": 0.0,
                "opening_signal": 0.0,
                "artifact_signal": 0.0,
                "english_abstract_signal": 0.0,
                "citation_relief": 0.0,
                "evidence_relief": 0.0,
                "style_signal": 0.0,
                "template_hits": [],
            },
        ),
    )

    rows = engine._build_detect_paragraph_details(
        "这是一段足够长的正文内容，用于验证知网正文段落在边界分数附近不会继续被压成 clean 标签，而是至少进入 low 标签。",
        "cnki",
        profile,
        None,
    )

    assert rows[0]["label"] == "low"


def test_cnki_short_doc_heading_inherits_following_risk(db_session: Session, monkeypatch) -> None:
    engine = ProcessingEngine(db_session)
    profile = engine._platform_detect_profile("cnki")

    monkeypatch.setattr(ProcessingEngine, "_extract_algo_paragraphs", lambda self, _algo: [])
    monkeypatch.setattr(ProcessingEngine, "_local_suspicious_segments_v2", lambda self, _paragraph, _platform, _profile: [])

    score_map = {
        "（三）课程融合：在一日生活中埋下种子": 0.11,
        "第一段正文用于模拟连续风险内容，这里保持较长文本以便进入边界判断。": 0.24,
        "第二段正文继续承接上一段，维持明显的疑似风险分数，用于让标题继承低风险标签。": 0.19,
    }

    def _fake_simulate(self, _platform: str, text: str, _base: float):
        return (
            score_map[text],
            profile,
            {
                "template_signal": 0.0,
                "repeat_signal": 0.0,
                "context_signal": 0.0,
                "opening_signal": 0.0,
                "artifact_signal": 0.0,
                "english_abstract_signal": 0.0,
                "citation_relief": 0.0,
                "evidence_relief": 0.0,
                "style_signal": 0.0,
                "template_hits": [],
            },
        )

    monkeypatch.setattr(ProcessingEngine, "_simulate_platform_detect_score", _fake_simulate)

    rows = engine._build_detect_paragraph_details(
        "\n".join(score_map.keys()),
        "cnki",
        profile,
        None,
    )

    assert rows[0]["label"] == "low"
    assert rows[0]["suspicious_segments"][0]["label"] == "low"
    assert rows[0]["suspicious_segments"][0]["reason"] == "风险区标题延续"


def test_cnki_risky_segment_uses_high_label_when_doc_not_clean(db_session: Session, monkeypatch) -> None:
    engine = ProcessingEngine(db_session)
    profile = engine._platform_detect_profile("cnki")

    monkeypatch.setattr(
        ProcessingEngine,
        "_extract_algo_paragraphs",
        lambda self, _algo: [
            {
                "index": 1,
                "label": "low",
                "score_ratio": 0.26,
                "segments": [{"text": "可疑句段", "score": 35.0, "reason": "测试"}],
            }
        ],
    )
    monkeypatch.setattr(ProcessingEngine, "_local_suspicious_segments_v2", lambda self, _paragraph, _platform, _profile: [])
    monkeypatch.setattr(ProcessingEngine, "_extract_algo_label", lambda self, _algo: "low")
    monkeypatch.setattr(ProcessingEngine, "_extract_algo_score", lambda self, _algo: 0.2)
    monkeypatch.setattr(
        ProcessingEngine,
        "_simulate_platform_detect_score",
        lambda self, _platform, _text, _base: (
            0.26,
            profile,
            {
                "template_signal": 0.0,
                "repeat_signal": 0.0,
                "context_signal": 0.0,
                "opening_signal": 0.0,
                "artifact_signal": 0.0,
                "english_abstract_signal": 0.0,
                "citation_relief": 0.0,
                "evidence_relief": 0.0,
                "style_signal": 0.0,
                "template_hits": [],
            },
        ),
    )

    rows = engine._build_detect_paragraph_details(
        "这是一段用于测试片段标签升级的正文内容，长度足够，且应该被识别为可疑。",
        "cnki",
        profile,
        {"label": "low", "ai_score": 0.2},
    )

    assert rows[0]["suspicious_segments"][0]["label"] == "high"


def test_local_suspicious_segments_v2_skips_weak_sentences(db_session: Session, monkeypatch) -> None:
    engine = ProcessingEngine(db_session)
    profile = engine._platform_detect_profile("cnki")

    def _fake_simulate(self, _platform: str, _text: str, _base_score: float):
        return (
            0.39,
            profile,
            {
                "template_signal": 0.05,
                "repeat_signal": 0.08,
                "context_signal": 0.10,
                "opening_signal": 0.02,
                "artifact_signal": 0.0,
                "english_abstract_signal": 0.0,
                "citation_relief": 0.0,
                "evidence_relief": 0.0,
                "template_hits": [],
            },
        )

    monkeypatch.setattr(ProcessingEngine, "_simulate_platform_detect_score", _fake_simulate)

    segments = engine._local_suspicious_segments_v2("这是一个正常句子。这里继续补充说明。", "cnki", profile)

    assert segments == []


def test_local_suspicious_segments_v2_skips_cnki_summary_wrapup_sentences(db_session: Session) -> None:
    engine = ProcessingEngine(db_session)
    profile = engine._platform_detect_profile("cnki")

    segments = engine._local_suspicious_segments_v2(
        "这一模式的可迁移性体现在两个层面，最核心的教育逻辑在于形成系列化的家园共育体系。",
        "cnki",
        profile,
    )

    assert segments == []


def test_is_no_ai_fragment_filters_thesis_front_matter(db_session: Session) -> None:
    engine = ProcessingEngine(db_session)

    assert engine._is_no_ai_fragment("学 位 论 文 独 创 性 说 明")
    assert engine._is_no_ai_fragment("本人郑重声明：所呈交的学位论文是我个人在导师指导下进行的研究工作。")


def test_human_case_relief_signal_prefers_practice_paragraphs(db_session: Session) -> None:
    engine = ProcessingEngine(db_session)
    text = (
        "在日常观察中发现，幼儿对“爱家人”这件事不是没有感情，而是缺少一种看得见、摸得着的表达渠道。"
        "正是立足这一现实，本园设计并推行“爱的存折”家园共育项目，尝试把孝亲教育转变为可记录、可反馈的生活实践。"
    )

    assert engine._human_case_relief_signal(text) >= 0.12
