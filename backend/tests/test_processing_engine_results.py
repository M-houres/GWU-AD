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
    for platform in ("cnki", "vip", "paperpass"):
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
    result = engine.process(TaskType.AIGC_DETECT, "paperpass", source_path, output_path, task_id=8)

    assert output_path.exists()
    assert len(result.result_json["paragraph_details"]) == 18
    assert result.result_json["fragment_distribution"]["fragment_count"] > 0
    assert result.result_json["fragment_distribution"]["severe_fragment_count"] >= 0
    assert result.result_json["document_metrics"]["paragraph_count"] == 18
    reader = PdfReader(str(output_path))
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
