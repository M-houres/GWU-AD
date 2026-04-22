from pathlib import Path

from docx import Document
from pypdf import PdfReader
import pytest
from sqlalchemy.orm import Session

from app.models import SystemConfig
from app.models import TaskType
from app.services.rewrite_strategies.assets import CNKI_ASSETS, VIP_ASSETS
from app.services.rewrite_strategies.rule_engine import apply_platform_rules
from app.services.dedup_strategies.executor import execute_dedup_strategy
from app.services.dedup_strategies.assets import CNKI_DEDUP_ASSETS, VIP_DEDUP_ASSETS
from app.services.dedup_strategies.rule_engine import apply_dedup_rules
from app.services.dedup_strategies.cnki_llm import _prompt as cnki_dedup_prompt
from app.services.dedup_strategies.vip_llm import _prompt as vip_dedup_prompt
from app.services.dedup_strategies.validators import validate_dedup_output
from app.services.processing_engine import ProcessingEngine
from app.services.rewrite_strategies.cnki_llm import _prompt as cnki_rewrite_prompt
from app.services.rewrite_strategies.vip_llm import _prompt as vip_rewrite_prompt
from app.services.rewrite_strategies.validators import validate_rewrite_output


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

    engine = ProcessingEngine(db_session)
    result = engine.process(TaskType.AIGC_DETECT, "cnki", source_path, output_path, task_id=2)

    assert output_path.exists()
    assert result.result_json["type"] == "aigc_detect"
    assert "summary" in result.result_json
    assert "risk_band" in result.result_json
    assert result.result_json["simulation_profile"] == "cnki_internal"
    assert result.result_json["provider_label"] == "知网AIGC检测仿真"
    assert result.result_json["source_stats"]["char_count"] > 0
    assert len(result.result_json["paragraph_details"]) >= 1
    assert "distribution" in result.result_json
    assert "fragment_distribution" in result.result_json
    assert "document_metrics" in result.result_json
    assert "decision_basis" in result.result_json
    assert result.result_json["llm_used"] is False
    assert "algo_package_used" not in result.result_json
    assert result.result_json["score_breakdown"]["strategy"] == "algorithm"
    assert "llm_score" not in result.result_json["score_breakdown"]
    assert "algo_package_score" not in result.result_json["score_breakdown"]
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
    engine = ProcessingEngine(db_session)
    results = {}
    for platform in ("cnki", "vip"):
        output_path = tmp_path / f"{platform}.pdf"
        result = engine.process(TaskType.AIGC_DETECT, platform, source_path, output_path, task_id=100)
        results[platform] = float(result.result_json["score_pct"])
        assert output_path.exists()

    assert len(set(round(value, 2) for value in results.values())) >= 2
    assert max(results.values()) - min(results.values()) <= 15


def test_rewrite_process_for_common_platform_uses_internal_heuristic_fallback(
    tmp_path: Path, db_session: Session, monkeypatch
) -> None:
    source_path = tmp_path / "rewrite.txt"
    output_path = tmp_path / "rewrite_out.txt"
    source_path.write_text("研究表明，因此需要持续优化。", encoding="utf-8")

    monkeypatch.setattr(ProcessingEngine, "_run_llm", lambda self, *_args, **_kwargs: None)

    engine = ProcessingEngine(db_session)
    result = engine.process(TaskType.REWRITE, "paperpass", source_path, output_path, task_id=3)

    assert output_path.exists()
    assert output_path.read_text(encoding="utf-8")
    assert result.result_json["type"] == "rewrite"
    assert result.result_json["output_stats"]["char_count"] > 0


def test_aigc_detect_uses_internal_strategy_chain_without_external_scores(tmp_path: Path, db_session: Session) -> None:
    source_path = tmp_path / "detect.txt"
    output_path = tmp_path / "detect.pdf"
    source_path.write_text(
        "研究表明，该路径在多个学院中具有较强复制性，并通过统一模板组织论证结构，因此可以快速迁移到不同课程场景。",
        encoding="utf-8",
    )

    engine = ProcessingEngine(db_session)
    result = engine.process(TaskType.AIGC_DETECT, "cnki", source_path, output_path, task_id=4)

    assert output_path.exists()
    assert result.result_json["label"] in {"low", "medium", "high", "clean"}
    assert result.result_json["score_pct"] > 0
    assert result.result_json["llm_used"] is False
    assert "algo_package_used" not in result.result_json
    assert result.result_json["aigc_detect_strategy"]["strategy"] == "algorithm"
    assert result.result_json["aigc_detect_strategy"]["platform"] == "cnki"
    assert "algo_package_score" not in result.result_json["score_breakdown"]
    assert "llm_score" not in result.result_json["score_breakdown"]
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

    engine = ProcessingEngine(db_session)
    engine.process(TaskType.AIGC_DETECT, "cnki", source_path, output_path, task_id=9)

    reader = PdfReader(str(output_path))
    extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "AIGC检测" in extracted
    assert "全文报告单" in extracted
    assert "全文检测结果" in extracted
    assert "AIGC片段分布图" in extracted
    assert "分段检测结果" in extracted
    assert "AI特征字符数 / 章节(部分)字符数" in extracted
    assert "原文内容" in extracted
    assert "说明" in extracted
    assert len(reader.pages) >= 2


def test_processing_engine_wrap_pdf_line_accepts_legacy_width_kwarg(db_session: Session) -> None:
    engine = ProcessingEngine(db_session)

    lines = engine._wrap_pdf_line("这是一个用于兼容 width 参数的 PDF 换行测试。", width=10)

    assert lines
    assert all(isinstance(item, str) for item in lines)


def test_transform_text_combined_mode_runs_llm_then_heuristic_fallback(db_session: Session, monkeypatch) -> None:
    engine = ProcessingEngine(db_session)
    engine._effective_mode = "LLM_PLUS_ALGO"

    call_order: list[tuple[str, str]] = []

    def _fake_llm(self, _task_type: TaskType, text: str):
        call_order.append(("llm", text))
        self._pipeline_usage["llm_used"] = True
        return f"llm::{text}"

    monkeypatch.setattr(ProcessingEngine, "_run_llm", _fake_llm)

    output = engine._transform_text("source text", TaskType.DEDUP, "wanfang", {})

    assert output == "llm::source text"
    assert call_order == [("llm", "source text")]


def test_rewrite_cnki_uses_configured_llm_strategy(tmp_path: Path, db_session: Session, monkeypatch) -> None:
    source_path = tmp_path / "rewrite_cnki.txt"
    output_path = tmp_path / "rewrite_cnki_out.txt"
    source_path.write_text("核心素养导向下的教学设计需要兼顾活动组织与过程反馈。", encoding="utf-8")

    db_session.add(
        SystemConfig(
            category="system",
            config_key="rewrite_strategy",
            config_value={
                "cnki": {"rewrite": {"enabled": True, "active_strategy": "llm"}},
                "vip": {"rewrite": {"enabled": True, "active_strategy": "algorithm"}},
            },
            updated_by=1,
        )
    )
    db_session.commit()

    monkeypatch.setattr(
        "app.services.rewrite_strategies.cnki_llm.generate_with_llm",
        lambda *_args, **_kwargs: "核心素养导向下的教学设计需要兼顾活动组织、过程反馈与实施节奏，以保持原有论证脉络。",
    )

    engine = ProcessingEngine(db_session)
    result = engine.process(TaskType.REWRITE, "cnki", source_path, output_path, task_id=11)

    assert output_path.exists()
    assert result.result_json["rewrite_strategy"]["strategy"] == "llm"
    assert result.result_json["rewrite_strategy"]["platform"] == "cnki"
    assert result.result_json["llm_used"] is True
    assert "algo_package_used" not in result.result_json


def test_rewrite_vip_uses_configured_algorithm_strategy(tmp_path: Path, db_session: Session) -> None:
    source_path = tmp_path / "rewrite_vip.txt"
    output_path = tmp_path / "rewrite_vip_out.txt"
    source_path.write_text("课程评价机制的优化需要兼顾反馈时效与教学组织的可执行性。", encoding="utf-8")

    db_session.add(
        SystemConfig(
            category="system",
            config_key="rewrite_strategy",
            config_value={
                "cnki": {"rewrite": {"enabled": True, "active_strategy": "llm"}},
                "vip": {"rewrite": {"enabled": True, "active_strategy": "algorithm"}},
            },
            updated_by=1,
        )
    )
    db_session.commit()

    engine = ProcessingEngine(db_session)
    result = engine.process(TaskType.REWRITE, "vip", source_path, output_path, task_id=12)

    assert output_path.exists()
    assert result.result_json["rewrite_strategy"]["strategy"] == "algorithm"
    assert result.result_json["rewrite_strategy"]["platform"] == "vip"
    assert result.result_json["llm_used"] is False
    assert "algo_package_used" not in result.result_json
    assert output_path.read_text(encoding="utf-8")


def test_rewrite_cnki_broken_term_output_uses_internal_fallback(tmp_path: Path, db_session: Session, monkeypatch) -> None:
    source_path = tmp_path / "rewrite_broken_term.txt"
    output_path = tmp_path / "rewrite_broken_term_out.txt"
    source_path.write_text("研究强调可视化表达在课堂反馈中的支撑作用。", encoding="utf-8")

    db_session.add(
        SystemConfig(
            category="system",
            config_key="rewrite_strategy",
            config_value={
                "cnki": {"rewrite": {"enabled": True, "active_strategy": "llm"}},
                "vip": {"rewrite": {"enabled": True, "active_strategy": "algorithm"}},
            },
            updated_by=1,
        )
    )
    db_session.commit()

    monkeypatch.setattr(
        "app.services.rewrite_strategies.cnki_llm.generate_with_llm",
        lambda *_args, **_kwargs: "研究强调可以视化表达在课堂反馈中的支撑作用，并进一步保持原有论证脉络。",
    )

    engine = ProcessingEngine(db_session)
    result = engine.process(TaskType.REWRITE, "cnki", source_path, output_path, task_id=13)

    content = output_path.read_text(encoding="utf-8")
    strategy = result.result_json["rewrite_strategy"]
    assert output_path.exists()
    assert content
    assert "可视化表达" in content
    assert strategy["rule_trace"]["mode"] == "rewrite_rule_engine"
    assert strategy["rule_trace"]["llm_fallback"] is True


def test_rewrite_cnki_algorithm_keeps_protected_terms_and_records_rule_trace(
    tmp_path: Path, db_session: Session
) -> None:
    source_path = tmp_path / "rewrite_cnki_assets.txt"
    output_path = tmp_path / "rewrite_cnki_assets_out.txt"
    source_path.write_text(
        "研究表明，核心素养导向下的可视化学习任务需要依托学情诊断结果进行统筹设计。",
        encoding="utf-8",
    )

    db_session.add(
        SystemConfig(
            category="system",
            config_key="rewrite_strategy",
            config_value={
                "cnki": {"rewrite": {"enabled": True, "active_strategy": "algorithm"}},
                "vip": {"rewrite": {"enabled": True, "active_strategy": "algorithm"}},
            },
            updated_by=1,
        )
    )
    db_session.commit()

    engine = ProcessingEngine(db_session)
    result = engine.process(TaskType.REWRITE, "cnki", source_path, output_path, task_id=14)

    content = output_path.read_text(encoding="utf-8")
    trace = result.result_json["rewrite_strategy"]["rule_trace"]
    assert "核心素养" in content
    assert "可视化" in content
    assert "学情诊断" in content
    assert trace["protected_hits"]
    assert any(
        item.startswith("synonym:")
        or item.startswith("sentence_shape:")
        or item.startswith("sentence_opening:")
        or item.startswith("cnki_reframe:")
        or item.startswith("structural:")
        for item in trace["applied_rules"]
    )


def test_rewrite_cnki_algorithm_applies_safe_sentence_reframe(tmp_path: Path, db_session: Session) -> None:
    source_path = tmp_path / "rewrite_cnki_reframe.txt"
    output_path = tmp_path / "rewrite_cnki_reframe_out.txt"
    source_path.write_text(
        "从理论层面来看，本研究认为其核心在于教师共同体建设，这意味着课程实施需要系统协同。",
        encoding="utf-8",
    )

    db_session.add(
        SystemConfig(
            category="system",
            config_key="rewrite_strategy",
            config_value={
                "cnki": {"rewrite": {"enabled": True, "active_strategy": "algorithm"}},
                "vip": {"rewrite": {"enabled": True, "active_strategy": "algorithm"}},
            },
            updated_by=1,
        )
    )
    db_session.commit()

    engine = ProcessingEngine(db_session)
    result = engine.process(TaskType.REWRITE, "cnki", source_path, output_path, task_id=43)

    content = output_path.read_text(encoding="utf-8")
    trace = result.result_json["rewrite_strategy"]["rule_trace"]
    assert "从理论层面看" in content
    assert "研究指出" in content
    assert "关键在于" in content or "核心在于" in content
    assert any(
        item.startswith("cnki_reframe:") or item.startswith("structural:")
        for item in trace["applied_rules"]
    )


def test_rewrite_vip_algorithm_uses_structural_rules_and_rule_trace(
    tmp_path: Path, db_session: Session
) -> None:
    source_path = tmp_path / "rewrite_vip_assets.txt"
    output_path = tmp_path / "rewrite_vip_assets_out.txt"
    source_path.write_text(
        "将图书管理与阅读活动结合，能够提升校园阅读生态的整体质量，并形成更加稳定的实施机制。",
        encoding="utf-8",
    )

    db_session.add(
        SystemConfig(
            category="system",
            config_key="rewrite_strategy",
            config_value={
                "cnki": {"rewrite": {"enabled": True, "active_strategy": "algorithm"}},
                "vip": {"rewrite": {"enabled": True, "active_strategy": "algorithm"}},
            },
            updated_by=1,
        )
    )
    db_session.commit()

    engine = ProcessingEngine(db_session)
    result = engine.process(TaskType.REWRITE, "vip", source_path, output_path, task_id=15)

    content = output_path.read_text(encoding="utf-8")
    trace = result.result_json["rewrite_strategy"]["rule_trace"]
    assert content
    assert content != "将图书管理与阅读活动结合，能够提升校园阅读生态的整体质量，并形成更加稳定的实施机制。"
    assert "将把" not in content
    assert "能够可以" not in content
    assert any(
        item.startswith("synonym:")
        or item.startswith("sentence_shape:")
        or item.startswith("postprocess:")
        or item.startswith("nominalization:")
        or item.startswith("structural:")
        or item.startswith("length_adjust:")
        for item in trace["applied_rules"]
    )


def test_rewrite_cnki_algorithm_applies_structural_parallel_operator(
    tmp_path: Path, db_session: Session
) -> None:
    source_path = tmp_path / "rewrite_cnki_structural.txt"
    output_path = tmp_path / "rewrite_cnki_structural_out.txt"
    source_path.write_text(
        "为了提升课程治理质量，需要优化实施节奏，并保持评价反馈的稳定衔接。",
        encoding="utf-8",
    )

    db_session.add(
        SystemConfig(
            category="system",
            config_key="rewrite_strategy",
            config_value={
                "cnki": {"rewrite": {"enabled": True, "active_strategy": "algorithm"}},
                "vip": {"rewrite": {"enabled": True, "active_strategy": "algorithm"}},
            },
            updated_by=1,
        )
    )
    db_session.commit()

    engine = ProcessingEngine(db_session)
    result = engine.process(TaskType.REWRITE, "cnki", source_path, output_path, task_id=109)

    content = output_path.read_text(encoding="utf-8")
    trace = result.result_json["rewrite_strategy"]["rule_trace"]
    assert "既要" in content or "一方面要" in content or "若要" in content
    assert any(item.startswith("structural:") for item in trace["applied_rules"])


def test_dedup_cnki_algorithm_uses_independent_platform_strategy(tmp_path: Path, db_session: Session) -> None:
    source_path = tmp_path / "dedup_cnki.txt"
    output_path = tmp_path / "dedup_cnki_out.txt"
    source_path.write_text(
        "研究表明，核心素养导向下的可视化学习任务需要依托学情诊断结果进行统筹设计，因此需要进一步优化实施路径。",
        encoding="utf-8",
    )

    db_session.add(
        SystemConfig(
            category="system",
            config_key="dedup_strategy",
            config_value={
                "cnki": {"dedup": {"enabled": True, "active_strategy": "algorithm"}},
                "vip": {"dedup": {"enabled": True, "active_strategy": "algorithm"}},
            },
            updated_by=1,
        )
    )
    db_session.commit()

    engine = ProcessingEngine(db_session)
    result = engine.process(TaskType.DEDUP, "cnki", source_path, output_path, task_id=31)

    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    strategy = result.result_json["dedup_strategy"]
    assert strategy["strategy"] == "algorithm"
    assert strategy["platform"] == "cnki"
    assert "核心素养" in content
    assert "可视化" in content
    assert "学情诊断" in content
    assert result.result_json["rewrite_strategy"] is None
    assert any(
        item.startswith("synonym:") or item.startswith("dedup_sentence_shape:")
        or item.startswith("dedup_structural:")
        for item in strategy["rule_trace"]["applied_rules"]
    )


def test_dedup_vip_algorithm_uses_structural_rewrite_rules(tmp_path: Path, db_session: Session) -> None:
    source_path = tmp_path / "dedup_vip.txt"
    output_path = tmp_path / "dedup_vip_out.txt"
    source_path.write_text(
        "将图书管理与阅读活动结合，能够提升校园阅读生态的整体质量，并形成更加稳定的实施机制。",
        encoding="utf-8",
    )

    db_session.add(
        SystemConfig(
            category="system",
            config_key="dedup_strategy",
            config_value={
                "cnki": {"dedup": {"enabled": True, "active_strategy": "algorithm"}},
                "vip": {"dedup": {"enabled": True, "active_strategy": "algorithm"}},
            },
            updated_by=1,
        )
    )
    db_session.commit()

    engine = ProcessingEngine(db_session)
    result = engine.process(TaskType.DEDUP, "vip", source_path, output_path, task_id=32)

    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    strategy = result.result_json["dedup_strategy"]
    assert strategy["strategy"] == "algorithm"
    assert strategy["platform"] == "vip"
    assert content
    assert content != "将图书管理与阅读活动结合，能够提升校园阅读生态的整体质量，并形成更加稳定的实施机制。"
    assert "将把" not in content
    assert "能够可以" not in content
    assert "可以进一步" not in content
    assert any(
        item.startswith("synonym:")
        or item.startswith("dedup_structure:")
        or item.startswith("dedup_structural:")
        or item.startswith("dedup_sentence_shape:")
        or item.startswith("postprocess:")
        for item in strategy["rule_trace"]["applied_rules"]
    )


def test_dedup_vip_algorithm_applies_compact_structural_operator(
    tmp_path: Path, db_session: Session
) -> None:
    source_path = tmp_path / "dedup_vip_structural.txt"
    output_path = tmp_path / "dedup_vip_structural_out.txt"
    source_path.write_text(
        "将图书管理与阅读活动结合，能够提升校园阅读生态的整体质量，并形成更加稳定的实施机制。",
        encoding="utf-8",
    )

    db_session.add(
        SystemConfig(
            category="system",
            config_key="dedup_strategy",
            config_value={
                "cnki": {"dedup": {"enabled": True, "active_strategy": "algorithm"}},
                "vip": {"dedup": {"enabled": True, "active_strategy": "algorithm"}},
            },
            updated_by=1,
        )
    )
    db_session.commit()

    engine = ProcessingEngine(db_session)
    result = engine.process(TaskType.DEDUP, "vip", source_path, output_path, task_id=110)

    content = output_path.read_text(encoding="utf-8")
    trace = result.result_json["dedup_strategy"]["rule_trace"]
    assert "既能" in content or "也能" in content
    assert any(item.startswith("dedup_structural:") for item in trace["applied_rules"])


def test_dedup_cnki_llm_strategy_uses_platform_prompt_and_keeps_dedup_meta(
    tmp_path: Path, db_session: Session, monkeypatch
) -> None:
    source_path = tmp_path / "dedup_cnki_llm.txt"
    output_path = tmp_path / "dedup_cnki_llm_out.txt"
    source_path.write_text(
        "核心素养导向下的教学设计需要兼顾活动组织与过程反馈，因此需要持续优化课堂实施路径。",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "app.services.dedup_strategies.cnki_llm.generate_with_llm",
        lambda *_args, **_kwargs: "核心素养导向下的教学设计需要兼顾活动组织、过程反馈与课堂推进节奏，由此可进一步优化实施路径。",
    )
    db_session.add(
        SystemConfig(
            category="system",
            config_key="dedup_strategy",
            config_value={
                "cnki": {"dedup": {"enabled": True, "active_strategy": "llm"}},
                "vip": {"dedup": {"enabled": True, "active_strategy": "algorithm"}},
            },
            updated_by=1,
        )
    )
    db_session.add(
        SystemConfig(
            category="system",
            config_key="llm",
            config_value={"enabled": True, "provider": "local_mock", "model": "local-mock-v1", "api_key": "", "base_url": ""},
            updated_by=1,
        )
    )
    db_session.commit()

    engine = ProcessingEngine(db_session)
    result = engine.process(TaskType.DEDUP, "cnki", source_path, output_path, task_id=33)

    assert output_path.exists()
    strategy = result.result_json["dedup_strategy"]
    assert strategy["strategy"] == "llm"
    assert strategy["platform"] == "cnki"
    assert result.result_json["llm_used"] is True
    assert "algo_package_used" not in result.result_json
    assert strategy["quality_flags"]["protected_content_ok"] is True


def test_dedup_vip_llm_strategy_falls_back_to_algorithm_when_llm_fails(
    tmp_path: Path, db_session: Session, monkeypatch
) -> None:
    source_path = tmp_path / "dedup_vip_llm.txt"
    output_path = tmp_path / "dedup_vip_llm_out.txt"
    source_path.write_text(
        "将图书管理与阅读活动结合，能够提升校园阅读生态的整体质量，并形成更加稳定的实施机制。",
        encoding="utf-8",
    )

    def _boom(*_args, **_kwargs):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr("app.services.dedup_strategies.vip_llm.generate_with_llm", _boom)
    db_session.add(
        SystemConfig(
            category="system",
            config_key="dedup_strategy",
            config_value={
                "cnki": {"dedup": {"enabled": True, "active_strategy": "algorithm"}},
                "vip": {"dedup": {"enabled": True, "active_strategy": "llm"}},
            },
            updated_by=1,
        )
    )
    db_session.add(
        SystemConfig(
            category="system",
            config_key="llm",
            config_value={"enabled": True, "provider": "local_mock", "model": "local-mock-v1", "api_key": "", "base_url": ""},
            updated_by=1,
        )
    )
    db_session.commit()

    engine = ProcessingEngine(db_session)
    result = engine.process(TaskType.DEDUP, "vip", source_path, output_path, task_id=34)

    assert output_path.exists()
    strategy = result.result_json["dedup_strategy"]
    assert strategy["strategy"] == "llm"
    assert strategy["platform"] == "vip"
    assert result.result_json["llm_used"] is True
    assert strategy["rule_trace"]["mode"] == "dedup_rule_engine"
    assert strategy["rule_trace"]["llm_fallback"] is True


def test_dedup_algorithm_empty_output_uses_fallback_and_does_not_fail(
    tmp_path: Path, db_session: Session, monkeypatch
) -> None:
    source_path = tmp_path / "dedup_empty.txt"
    output_path = tmp_path / "dedup_empty_out.txt"
    source_path.write_text(
        "因此需要围绕课程实施路径进行优化，同时保持核心素养导向下的教学组织逻辑。",
        encoding="utf-8",
    )

    db_session.add(
        SystemConfig(
            category="system",
            config_key="dedup_strategy",
            config_value={
                "cnki": {"dedup": {"enabled": True, "active_strategy": "algorithm"}},
                "vip": {"dedup": {"enabled": True, "active_strategy": "algorithm"}},
            },
            updated_by=1,
        )
    )
    db_session.commit()

    monkeypatch.setattr(
        "app.services.dedup_strategies.cnki_algorithm.rewrite",
        lambda *_args, **_kwargs: {"text": "", "rule_trace": {"mode": "dedup_rule_engine", "applied_rules": []}},
    )

    engine = ProcessingEngine(db_session)
    result = engine.process(TaskType.DEDUP, "cnki", source_path, output_path, task_id=35)

    content = output_path.read_text(encoding="utf-8")
    strategy = result.result_json["dedup_strategy"]
    assert output_path.exists()
    assert content
    assert "由此可见" in content or "本文进一步指出" in content or "有必要" in content
    assert "降重复率策略空输出，已切换兜底改写" in strategy["warnings"]
    assert strategy["rule_trace"]["fallback_applied"] is True
    assert strategy["rule_trace"]["fallback_reason"] == "empty_strategy_output"


def test_dedup_validation_rejects_bad_sample_artifacts() -> None:
    source_text = "小学数学可视化教学需要保持术语准确与表达自然，并兼顾论证连贯。" * 3
    rewritten_text = "小学数学作为属于核心课程，相关研究蕴含包括着丰富经验，并形成路径方式。"

    with pytest.raises(Exception) as exc_info:
        validate_dedup_output(
            platform="vip",
            source_text=source_text,
            rewritten_text=rewritten_text,
            rule_trace={"mode": "test"},
        )

    assert "明显异常表达" in str(exc_info.value)


def test_dedup_cnki_validation_rejects_known_bad_sample_patterns() -> None:
    source_text = "派驻监督研究需要兼顾制度逻辑、组织运行和履职约束，并保持论证表达自然。" * 3
    rewritten_text = "由此可见，这说明其属于制度推进路径，同时，进一步看，在此基础上提出结论。"

    with pytest.raises(Exception) as exc_info:
        validate_dedup_output(
            platform="cnki",
            source_text=source_text,
            rewritten_text=rewritten_text,
            rule_trace={"mode": "test"},
        )

    assert "明显异常表达" in str(exc_info.value)


def test_dedup_cnki_validation_rejects_mechanical_connective_cascade() -> None:
    source_text = "派驻监督研究需要兼顾制度逻辑、组织运行和实践约束，并保持论证表达自然。" * 3
    rewritten_text = (
        "派驻监督研究需要兼顾制度逻辑与组织运行。"
        "同时，梳理履职现状。"
        "此外，归纳监督主体结构。"
        "进一步看，分析制度运行原因。"
        "在此基础上，提出优化建议。"
    )

    with pytest.raises(Exception) as exc_info:
        validate_dedup_output(
            platform="cnki",
            source_text=source_text,
            rewritten_text=rewritten_text,
            rule_trace={"mode": "test"},
        )

    assert "机械连接词堆叠" in str(exc_info.value)


def test_dedup_algorithm_protects_dynamic_cross_domain_terms(tmp_path: Path, db_session: Session) -> None:
    source_path = tmp_path / "dedup_dynamic_terms.txt"
    output_path = tmp_path / "dedup_dynamic_terms_out.txt"
    source_path.write_text(
        "研究表明，Transformer 模型在 AUC 提升 5.2% 的同时保持 p < 0.05，相关结果见图 2 和文献[12]。",
        encoding="utf-8",
    )

    db_session.add(
        SystemConfig(
            category="system",
            config_key="dedup_strategy",
            config_value={
                "cnki": {"dedup": {"enabled": True, "active_strategy": "algorithm"}},
                "vip": {"dedup": {"enabled": True, "active_strategy": "algorithm"}},
            },
            updated_by=1,
        )
    )
    db_session.commit()

    engine = ProcessingEngine(db_session)
    result = engine.process(TaskType.DEDUP, "vip", source_path, output_path, task_id=42)

    content = output_path.read_text(encoding="utf-8")
    trace = result.result_json["dedup_strategy"]["rule_trace"]
    assert "Transformer" in content
    assert "AUC" in content
    assert "5.2%" in content
    assert "[12]" in content
    assert any(token in trace["protected_hits"] for token in ("Transformer", "AUC", "5.2%", "[12]"))


def test_dedup_algorithm_protects_dynamic_chinese_cross_domain_terms(tmp_path: Path, db_session: Session) -> None:
    source_path = tmp_path / "dedup_cross_domain_terms.txt"
    output_path = tmp_path / "dedup_cross_domain_terms_out.txt"
    source_path.write_text(
        "构建现金流风险预警机制能够提升企业财务稳健性，并形成更加稳定的治理结构。",
        encoding="utf-8",
    )

    db_session.add(
        SystemConfig(
            category="system",
            config_key="dedup_strategy",
            config_value={
                "cnki": {"dedup": {"enabled": True, "active_strategy": "algorithm"}},
                "vip": {"dedup": {"enabled": True, "active_strategy": "algorithm"}},
            },
            updated_by=1,
        )
    )
    db_session.commit()

    engine = ProcessingEngine(db_session)
    result = engine.process(TaskType.DEDUP, "vip", source_path, output_path, task_id=95)

    content = output_path.read_text(encoding="utf-8")
    trace = result.result_json["dedup_strategy"]["rule_trace"]
    assert "现金流风险预警" in content
    assert "财务稳健性" in content
    assert "治理结构" in content
    assert any(token in trace["protected_hits"] for token in ("现金流风险预警", "财务稳健性", "治理结构"))


def test_dedup_cnki_algorithm_avoids_sample_like_connective_cascade(
    tmp_path: Path, db_session: Session
) -> None:
    source_path = tmp_path / "dedup_cnki_connectives.txt"
    output_path = tmp_path / "dedup_cnki_connectives_out.txt"
    source_path.write_text(
        (
            "本文将以创新的视角，运用文献归纳法和案例分析法，从监管方法论、制度演进轨迹、相关法规修订进程等方面，"
            "围绕派驻监督职能特点和履职现状，剖析存在问题和深层原因，总结相关监督体制研究，提出优化建议。"
        ),
        encoding="utf-8",
    )

    db_session.add(
        SystemConfig(
            category="system",
            config_key="dedup_strategy",
            config_value={
                "cnki": {"dedup": {"enabled": True, "active_strategy": "algorithm"}},
                "vip": {"dedup": {"enabled": True, "active_strategy": "algorithm"}},
            },
            updated_by=1,
        )
    )
    db_session.commit()

    engine = ProcessingEngine(db_session)
    result = engine.process(TaskType.DEDUP, "cnki", source_path, output_path, task_id=87)

    content = output_path.read_text(encoding="utf-8")
    strategy = result.result_json["dedup_strategy"]
    connective_hits = sum(content.count(prefix) for prefix in ("同时，", "此外，", "进一步看，", "在此基础上，", "由此可见，"))

    assert content
    assert connective_hits <= 1
    assert "这说明其属于" not in content
    assert "。此外，" not in content
    assert "。进一步看，" not in content
    assert "。在此基础上，" not in content
    assert any(
        item.startswith("synonym:")
        or item.startswith("dedup_sentence_shape:")
        or item.startswith("sentence_opening:")
        for item in strategy["rule_trace"]["applied_rules"]
    )


def test_rewrite_validation_accepts_borderline_ratio_with_warning() -> None:
    source_text = "研究表明该方案在多个教学场景中具有较强的可执行性与复制价值。" * 3
    rewritten_text = source_text + "同时，研究过程保持既有论证结构。"

    result = validate_rewrite_output(
        platform="cnki",
        source_text=source_text,
        rewritten_text=rewritten_text,
        rule_trace={"mode": "test"},
        strict_length=False,
    )

    assert result.text == rewritten_text
    assert result.quality_flags["length_ok"] is False
    assert any("3%~10%" in item for item in result.warnings)


def test_rewrite_validation_warns_on_soft_mechanical_prefix_usage() -> None:
    source_text = "派驻监督研究需要兼顾制度逻辑、组织运行和实践约束，并保持论证表达自然。" * 3
    rewritten_text = (
        "派驻监督研究需要兼顾制度逻辑、组织运行和实践约束。"
        "同时，围绕履职现状展开分析。"
        "此外，对制度运行影响因素进行归纳。"
    )

    result = validate_rewrite_output(
        platform="cnki",
        source_text=source_text,
        rewritten_text=rewritten_text,
        rule_trace={"mode": "test"},
        strict_length=False,
    )

    assert result.quality_flags["structure_natural_ok"] is False
    assert any("衔接表达偏机械" in item for item in result.warnings)


def test_rewrite_validation_marks_shallow_rewrite_risk() -> None:
    source_text = (
        "数字化治理研究需要同时兼顾制度逻辑、组织协同、流程重构与技术支撑，并在此基础上保持论证路径完整。"
        * 3
    )
    rewritten_text = (
        "数字化治理研究需要同时兼顾制度逻辑、组织协同、流程优化与技术支撑，并在此基础上保持论证路径完整。"
        * 3
    )

    result = validate_rewrite_output(
        platform="cnki",
        source_text=source_text,
        rewritten_text=rewritten_text,
        rule_trace={"mode": "test"},
        strict_length=False,
    )

    assert result.quality_flags["shallow_rewrite_ok"] is False
    assert any("改写幅度偏浅" in item for item in result.warnings)
    assert result.quality_score < 0.9


def test_rewrite_validation_marks_style_alignment_gap_for_fragmented_vip_text() -> None:
    source_text = (
        "书香校园建设需要整合家庭、社区和学校资源，形成稳定的阅读支持体系，同时通过活动设计和平台联动提升学生参与度。"
        * 2
    )
    rewritten_text = (
        "书香校园建设需要整合资源。学校要组织活动。家长要参与阅读。社区要提供支持。平台也要跟进。"
    )

    result = validate_rewrite_output(
        platform="vip",
        source_text=source_text,
        rewritten_text=rewritten_text,
        rule_trace={"mode": "test"},
        strict_length=False,
    )

    assert result.quality_flags["style_profile_available"] is True
    assert result.quality_flags["style_alignment_ok"] is False
    assert any("高质量改写样本" in item for item in result.warnings)


def test_dedup_validation_marks_repetitive_sentence_pattern_risk() -> None:
    source_text = (
        "企业治理研究需要把采购协同、库存效率、资金节奏与监督反馈统筹起来，以保持论证表达稳定且具备专业可信度。"
        * 2
    )
    rewritten_text = "企业要统筹采购。企业要统筹库存。企业要统筹资金。企业要统筹监督。"

    result = validate_dedup_output(
        platform="vip",
        source_text=source_text,
        rewritten_text=rewritten_text,
        rule_trace={"mode": "test"},
    )

    assert result.quality_flags["discourse_diversity_ok"] is False
    assert any("句式重复度偏高" in item for item in result.warnings)
    assert result.quality_score < 0.9


def test_dedup_validation_marks_style_alignment_gap_for_fragmented_vip_text() -> None:
    source_text = (
        "企业存货管理优化需要统筹采购节奏、库存结构、周转效率和监督机制，同时保持论证表达紧凑并与经营情境对应。"
        * 2
    )
    rewritten_text = (
        "企业要管理存货。采购要安排。库存要控制。周转要提升。监督也要跟上。"
    )

    result = validate_dedup_output(
        platform="vip",
        source_text=source_text,
        rewritten_text=rewritten_text,
        rule_trace={"mode": "test"},
    )

    assert result.quality_flags["style_profile_available"] is True
    assert result.quality_flags["style_alignment_ok"] is False
    assert any("高质量降重样本" in item for item in result.warnings)


def test_dedup_executor_style_normalizes_fragmented_algorithm_output(db_session: Session, monkeypatch) -> None:
    source_text = (
        "企业存货管理优化需要统筹采购节奏、库存结构、周转效率和监督机制，同时保持论证表达紧凑并与经营情境对应。"
        * 2
    )

    monkeypatch.setattr(
        "app.services.dedup_strategies.vip_algorithm.rewrite",
        lambda *_args, **_kwargs: {
            "text": "企业要管理存货。同时，采购要安排。此外，库存要控制。周转要提升。监督也要跟上。",
            "rule_trace": {"mode": "dedup_rule_engine", "applied_rules": ["test:fragmented"]},
        },
    )

    result = execute_dedup_strategy(
        db_session,
        task=None,
        platform="vip",
        text=source_text,
        report_summary={},
        strategy="algorithm",
    )

    assert result["quality_flags"]["style_profile_available"] is True
    assert result["quality_flags"]["style_alignment_ok"] is True
    assert "此外，" not in result["rewritten_text"]
    assert "采购要安排，库存要控制" in result["rewritten_text"] or "采购要安排。库存要控制" not in result["rewritten_text"]
    assert any(item.startswith("style_normalize:") for item in result["rule_trace"]["applied_rules"])


def test_rewrite_llm_low_quality_output_falls_back_to_rule_engine(
    tmp_path: Path, db_session: Session, monkeypatch
) -> None:
    source_path = tmp_path / "rewrite_llm_low_quality.txt"
    output_path = tmp_path / "rewrite_llm_low_quality_out.txt"
    source_path.write_text(
        "数字化转型背景下的课程治理研究需要兼顾制度逻辑、组织协同、流程优化与评价反馈，并保持段落论证自然展开。"
        * 2,
        encoding="utf-8",
    )

    db_session.add(
        SystemConfig(
            category="system",
            config_key="rewrite_strategy",
            config_value={
                "cnki": {"rewrite": {"enabled": True, "active_strategy": "llm"}},
                "vip": {"rewrite": {"enabled": True, "active_strategy": "algorithm"}},
            },
            updated_by=1,
        )
    )
    db_session.commit()

    monkeypatch.setattr(
        "app.services.rewrite_strategies.cnki_llm.generate_with_llm",
        lambda *_args, **_kwargs: "课程治理需要研究。课程治理需要分析。课程治理需要优化。课程治理需要总结。",
    )

    engine = ProcessingEngine(db_session)
    result = engine.process(TaskType.REWRITE, "cnki", source_path, output_path, task_id=108)

    strategy = result.result_json["rewrite_strategy"]
    content = output_path.read_text(encoding="utf-8")
    assert output_path.exists()
    assert content
    assert strategy["strategy"] == "llm"
    assert strategy["rule_trace"]["mode"] == "rewrite_rule_engine"
    assert strategy["rule_trace"]["llm_fallback"] is True
    assert content != "课程治理需要研究。课程治理需要分析。课程治理需要优化。课程治理需要总结。"
    assert strategy["quality_flags"]["discourse_diversity_ok"] is True
    assert strategy["quality_score"] >= 0.7


def test_dedup_rule_engine_cnki_applies_style_shaping_rules() -> None:
    text = (
        "研究表明，课堂治理路径具有重要价值。"
        "同时，需要进一步优化实施机制。"
        "此外，需要持续优化反馈环节。"
        "进一步看，需要梳理协同条件。"
    )

    output, trace = apply_dedup_rules(None, text=text, assets=CNKI_DEDUP_ASSETS, report_summary={})

    assert "此外，" not in output
    assert "进一步看，" not in output
    assert "仍需优化" in output
    assert any(item.startswith("dedup_style:cnki_") for item in trace["applied_rules"])
    assert any(item.startswith("cnki_dedup_reframe:") for item in trace["applied_rules"])


def test_dedup_rule_engine_vip_applies_style_shaping_rules() -> None:
    text = (
        "企业要管理存货。"
        "同时，采购要安排。"
        "此外，库存要控制。"
        "周转要提升。"
        "监督也要跟上。"
    )

    output, trace = apply_dedup_rules(None, text=text, assets=VIP_DEDUP_ASSETS, report_summary={})

    assert "此外，" not in output
    assert "采购要安排，库存要控制" in output or "库存要控制，周转要提升" in output
    assert any(item.startswith("dedup_style:vip_") for item in trace["applied_rules"])


def test_rewrite_validation_still_rejects_extreme_length_ratio() -> None:
    source_text = "研究表明该方案在多个教学场景中具有较强的可执行性与复制价值。" * 3
    rewritten_text = source_text[:20]

    with pytest.raises(Exception) as exc_info:
        validate_rewrite_output(
            platform="cnki",
            source_text=source_text,
            rewritten_text=rewritten_text,
            rule_trace={"mode": "test"},
        )

    assert "超出可处理范围" in str(exc_info.value)


def test_rewrite_validation_rejects_bad_sample_artifacts() -> None:
    source_text = "小学数学可视化教学需要保持术语准确与表达自然。" * 3
    rewritten_text = "小学数学作为属于核心课程，相关研究蕴含包括着丰富经验，并形成路径方式。"

    with pytest.raises(Exception) as exc_info:
        validate_rewrite_output(
            platform="vip",
            source_text=source_text,
            rewritten_text=rewritten_text,
            rule_trace={"mode": "test"},
        )

    assert "明显异常表达" in str(exc_info.value)


def test_rewrite_cnki_validation_rejects_known_bad_sample_patterns() -> None:
    source_text = "可视化教学模型需要兼顾图像呈现、动态演示与智能理解三个层次。" * 3
    rewritten_text = "由此可见，这说明其属于图像表现出层，并进一步保持原有论证脉络。"

    with pytest.raises(Exception) as exc_info:
        validate_rewrite_output(
            platform="cnki",
            source_text=source_text,
            rewritten_text=rewritten_text,
            rule_trace={"mode": "test"},
        )

    assert "明显异常表达" in str(exc_info.value)


def test_rewrite_validation_rejects_cross_domain_term_weakening() -> None:
    source_text = "边缘计算架构需要兼顾实时推理、带宽约束和设备异构条件下的任务调度。" * 3
    rewritten_text = "边缘进行计算的架构需要兼顾实时性的推理、带宽方面的约束以及设备异构条件下面的任务调度过程。"

    with pytest.raises(Exception) as exc_info:
        validate_rewrite_output(
            platform="cnki",
            source_text=source_text,
            rewritten_text=rewritten_text,
            rule_trace={"mode": "test"},
        )

    assert "明显异常表达" in str(exc_info.value)


def test_rewrite_cnki_validation_rejects_mechanical_connective_cascade() -> None:
    source_text = "派驻监督研究需要兼顾制度逻辑、组织运行和实践约束，并保持论证表达自然。" * 3
    rewritten_text = (
        "摘要：派驻监督研究需要兼顾制度逻辑、组织运行和实践约束。"
        "同时，围绕履职现状展开分析。"
        "此外，归纳监督主体的结构特点。"
        "进一步看，梳理制度运行中的深层原因。"
        "在此基础上，提出优化建议。"
    )

    with pytest.raises(Exception) as exc_info:
        validate_rewrite_output(
            platform="cnki",
            source_text=source_text,
            rewritten_text=rewritten_text,
            rule_trace={"mode": "test"},
        )

    assert "机械连接词堆叠" in str(exc_info.value)


def test_rewrite_cnki_algorithm_avoids_sample_like_connective_cascade(
    tmp_path: Path, db_session: Session
) -> None:
    source_path = tmp_path / "rewrite_cnki_connectives.txt"
    output_path = tmp_path / "rewrite_cnki_connectives_out.txt"
    source_path.write_text(
        (
            "本文将以创新的视角，运用文献归纳法、实证研究法等研究方法，从监管方法论、监管体制发展轨迹、"
            "监管相关法律法规修订进程等方面，围绕纪检监察派驻机构职能特点和履职现状，剖析存在问题和深层次原因，"
            "总结国内外有关监督体制的经典论述，提出可行性、可发展性的研究对策，构建优化监督体系。"
        ),
        encoding="utf-8",
    )

    db_session.add(
        SystemConfig(
            category="system",
            config_key="rewrite_strategy",
            config_value={
                "cnki": {"rewrite": {"enabled": True, "active_strategy": "algorithm"}},
                "vip": {"rewrite": {"enabled": True, "active_strategy": "algorithm"}},
            },
            updated_by=1,
        )
    )
    db_session.commit()

    engine = ProcessingEngine(db_session)
    result = engine.process(TaskType.REWRITE, "cnki", source_path, output_path, task_id=86)

    content = output_path.read_text(encoding="utf-8")
    trace = result.result_json["rewrite_strategy"]["rule_trace"]
    connective_hits = sum(content.count(prefix) for prefix in ("同时，", "此外，", "进一步看，", "在此基础上，"))

    assert content
    assert connective_hits <= 1
    assert "。此外，" not in content
    assert "。进一步看，" not in content
    assert "。在此基础上，" not in content
    assert any(
        item.startswith("sentence_opening:") or item.startswith("sentence_shape:")
        for item in trace["applied_rules"]
    )


def test_rewrite_algorithm_protects_dynamic_cross_domain_terms(tmp_path: Path, db_session: Session) -> None:
    source_path = tmp_path / "rewrite_dynamic_terms.txt"
    output_path = tmp_path / "rewrite_dynamic_terms_out.txt"
    source_path.write_text(
        "研究表明，Transformer 模型在 AUC 提升 5.2% 的同时保持 p < 0.05，相关结果见图 2 和文献[12]。",
        encoding="utf-8",
    )

    db_session.add(
        SystemConfig(
            category="system",
            config_key="rewrite_strategy",
            config_value={
                "cnki": {"rewrite": {"enabled": True, "active_strategy": "algorithm"}},
                "vip": {"rewrite": {"enabled": True, "active_strategy": "algorithm"}},
            },
            updated_by=1,
        )
    )
    db_session.commit()

    engine = ProcessingEngine(db_session)
    result = engine.process(TaskType.REWRITE, "cnki", source_path, output_path, task_id=41)

    content = output_path.read_text(encoding="utf-8")
    trace = result.result_json["rewrite_strategy"]["rule_trace"]
    assert "Transformer" in content
    assert "AUC" in content
    assert "5.2%" in content
    assert "[12]" in content
    assert any(token in trace["protected_hits"] for token in ("Transformer", "AUC", "5.2%", "[12]"))


def test_rewrite_algorithm_protects_dynamic_chinese_cross_domain_terms(tmp_path: Path, db_session: Session) -> None:
    source_path = tmp_path / "rewrite_cross_domain_terms.txt"
    output_path = tmp_path / "rewrite_cross_domain_terms_out.txt"
    source_path.write_text(
        "研究表明，临床路径优化需要统筹诊疗规范、资源配置与患者体验，同时兼顾长期随访与用药依从性。",
        encoding="utf-8",
    )

    db_session.add(
        SystemConfig(
            category="system",
            config_key="rewrite_strategy",
            config_value={
                "cnki": {"rewrite": {"enabled": True, "active_strategy": "algorithm"}},
                "vip": {"rewrite": {"enabled": True, "active_strategy": "algorithm"}},
            },
            updated_by=1,
        )
    )
    db_session.commit()

    engine = ProcessingEngine(db_session)
    result = engine.process(TaskType.REWRITE, "cnki", source_path, output_path, task_id=96)

    content = output_path.read_text(encoding="utf-8")
    trace = result.result_json["rewrite_strategy"]["rule_trace"]
    assert "临床路径" in content
    assert "诊疗规范" in content
    assert "长期随访" in content
    assert "用药依从性" in content
    assert any(token in trace["protected_hits"] for token in ("临床路径", "诊疗规范", "长期随访", "用药依从性"))


def test_rewrite_rule_engine_cnki_applies_style_shaping_rules() -> None:
    text = (
        "本研究认为，该路径具有重要价值。"
        "同时，这意味着需要进一步优化实施机制。"
        "此外，在课堂治理过程中需要持续完善反馈链条。"
        "进一步看，这意味着需要协调资源支持。"
    )

    output, trace = apply_platform_rules(None, text=text, assets=CNKI_ASSETS, report_summary={})

    assert "此外，" not in output
    assert "进一步看，" not in output
    assert any(item.startswith("rewrite_style:cnki_") for item in trace["applied_rules"])
    assert any(item.startswith("cnki_reframe:") for item in trace["applied_rules"])


def test_rewrite_rule_engine_cnki_reframes_theory_and_practice_openings() -> None:
    text = "本研究的理论贡献在于：构建了客户体验评价体系。实践价值在于：提出营销优化方案。"

    output, trace = apply_platform_rules(None, text=text, assets=CNKI_ASSETS, report_summary={})

    assert "从理论层面看" in output
    assert "就实践层面而言" in output
    assert any(item.startswith("cnki_reframe:") for item in trace["applied_rules"])


def test_rewrite_rule_engine_vip_applies_style_shaping_rules() -> None:
    text = (
        "图书管理要统筹资源。"
        "同时，阅读活动要组织。"
        "此外，家校协同要跟进。"
        "平台支持也要到位。"
        "反馈机制也要完善。"
    )

    output, trace = apply_platform_rules(None, text=text, assets=VIP_ASSETS, report_summary={})

    assert "此外，" not in output
    assert "阅读活动要组织，家校" in output or "家校" in output and "平台支持也要到位" in output
    assert any(item.startswith("rewrite_style:vip_") for item in trace["applied_rules"])


def test_rewrite_rule_engine_vip_reframes_overall_assessment_opening() -> None:
    text = "总体来看，派驻监督职能履行仍存在一定问题，需要继续优化整改路径。"

    output, trace = apply_platform_rules(None, text=text, assets=VIP_ASSETS, report_summary={})

    assert "就整体情况而言" in output
    assert any(item.startswith("vip_flow:") for item in trace["applied_rules"])


def test_rewrite_vip_algorithm_does_not_expand_with_mechanical_connectors(
    tmp_path: Path, db_session: Session
) -> None:
    source_path = tmp_path / "rewrite_vip_no_soft_expand.txt"
    output_path = tmp_path / "rewrite_vip_no_soft_expand_out.txt"
    source_path.write_text(
        (
            "摘要：小学图书馆作为校园文化的重要载体，其功能定位经历着深刻变革。传统图书管理以藏书保管为核心，"
            "重视馆藏数量与完整性，却疏于发挥图书的教育价值。随着基础教育改革深入推进，图书馆管理理念亟需从静态保管"
            "转向动态服务，从被动等待转向主动引导。"
        ),
        encoding="utf-8",
    )

    db_session.add(
        SystemConfig(
            category="system",
            config_key="rewrite_strategy",
            config_value={
                "cnki": {"rewrite": {"enabled": True, "active_strategy": "algorithm"}},
                "vip": {"rewrite": {"enabled": True, "active_strategy": "algorithm"}},
            },
            updated_by=1,
        )
    )
    db_session.commit()

    engine = ProcessingEngine(db_session)
    result = engine.process(TaskType.REWRITE, "vip", source_path, output_path, task_id=107)

    content = output_path.read_text(encoding="utf-8")
    strategy = result.result_json["rewrite_strategy"]
    prefix_hits = sum(content.count(prefix) for prefix in ("同时，", "此外，", "进一步看，", "在此基础上，"))

    assert strategy["strategy"] == "algorithm"
    assert prefix_hits <= 1
    assert strategy["quality_flags"]["structure_natural_ok"] is True
    assert strategy["quality_flags"]["style_alignment_ok"] is True


def test_dedup_validation_rejects_cross_domain_term_weakening() -> None:
    source_text = "现金流风险预警是企业财务稳健性分析的重要环节。" * 3
    rewritten_text = "现金流方面的风险情况预警是企业财务稳健性分析中的关键环节和重要形式。"

    with pytest.raises(Exception) as exc_info:
        validate_dedup_output(
            platform="vip",
            source_text=source_text,
            rewritten_text=rewritten_text,
            rule_trace={"mode": "test"},
        )

    assert "明显异常表达" in str(exc_info.value)


def test_dedup_validation_marks_cross_domain_terms_missing_without_hard_fail() -> None:
    source_text = "社区记忆的建构既受地方叙事影响，也与代际传播机制和公共空间实践相关。" * 2
    rewritten_text = "相关记忆的建构受地方叙事影响，也与代际传播和空间实践相关。"

    result = validate_dedup_output(
        platform="vip",
        source_text=source_text,
        rewritten_text=rewritten_text,
        rule_trace={"mode": "test"},
    )

    assert result.quality_flags["cross_domain_terms_ok"] is False
    assert result.quality_flags["protected_content_ok"] is False
    assert any("保护术语缺失" in item for item in result.warnings)


def test_llm_prompts_include_cross_discipline_constraints() -> None:
    source = "测试文本"

    assert "优先参考以下正向改写风格示例" in cnki_rewrite_prompt(source)
    assert "高质量样本风格基线" in cnki_rewrite_prompt(source)
    assert "教育、医学、法学/政策、财经管理、工程/计算机、人文社科" in cnki_rewrite_prompt(source)
    assert "不要只把“本文/本研究”换成“该研究”就结束" in cnki_rewrite_prompt(source)
    assert "临床路径" in vip_rewrite_prompt(source)
    assert "高质量样本风格基线" in vip_rewrite_prompt(source)
    assert "不要只做局部替词或只把“本文/本研究”替换成“该研究”" in vip_rewrite_prompt(source)
    assert "行政复议程序" in cnki_dedup_prompt(source)
    assert "高质量降重样本风格基线" in cnki_dedup_prompt(source)
    assert "不要只替换单个动词、句首主语或连接词" in cnki_dedup_prompt(source)
    assert "社区记忆" in vip_dedup_prompt(source)
    assert "高质量降重样本风格基线" in vip_dedup_prompt(source)
    assert "不要只替换个别动词或把句首连接词换一种说法" in vip_dedup_prompt(source)
    assert "禁止模仿以下坏写法示例" in cnki_rewrite_prompt(source)
    assert "禁止模仿以下坏写法示例" in vip_dedup_prompt(source)
    assert "优先参考以下正向改写风格示例" in vip_dedup_prompt(source)


def test_transform_docx_skips_blank_runs_for_dedup(tmp_path: Path, db_session: Session) -> None:
    source_path = tmp_path / "dedup_blank_runs.docx"
    output_path = tmp_path / "dedup_blank_runs_out.docx"
    doc = Document()
    paragraph = doc.add_paragraph()
    paragraph.add_run("   ")
    paragraph.add_run("因此需要进一步优化课堂组织路径。")
    paragraph.add_run("\n")
    doc.save(source_path)

    db_session.add(
        SystemConfig(
            category="system",
            config_key="dedup_strategy",
            config_value={
                "cnki": {"dedup": {"enabled": True, "active_strategy": "algorithm"}},
                "vip": {"dedup": {"enabled": True, "active_strategy": "algorithm"}},
            },
            updated_by=1,
        )
    )
    db_session.commit()

    engine = ProcessingEngine(db_session)
    result = engine.process(TaskType.DEDUP, "cnki", source_path, output_path, task_id=36)

    output_doc = Document(str(output_path))
    output_text = "\n".join(paragraph.text for paragraph in output_doc.paragraphs)
    assert output_path.exists()
    assert result.result_json["type"] == "dedup"
    assert "由此可见" in output_text or "有必要" in output_text or "优化" in output_text


def test_transform_text_combined_mode_falls_back_to_heuristic_when_llm_empty(
    db_session: Session, monkeypatch
) -> None:
    engine = ProcessingEngine(db_session)
    engine._effective_mode = "LLM_PLUS_ALGO"

    call_order: list[str] = []

    def _fake_llm(self, _task_type: TaskType, _text: str):
        call_order.append("llm")
        return None

    monkeypatch.setattr(ProcessingEngine, "_run_llm", _fake_llm)

    output = engine._transform_text("因此需要优化", TaskType.DEDUP, "wanfang", {})

    assert output
    assert output != "algo::因此需要优化"
    assert call_order == ["llm"]


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
    )

    assert rows[0]["label"] == "low"


def test_cnki_short_doc_heading_inherits_following_risk(db_session: Session, monkeypatch) -> None:
    engine = ProcessingEngine(db_session)
    profile = engine._platform_detect_profile("cnki")

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
    )

    assert rows[0]["label"] == "low"
    assert rows[0]["suspicious_segments"][0]["label"] == "low"
    assert rows[0]["suspicious_segments"][0]["reason"] == "风险区标题延续"


def test_cnki_risky_segment_uses_internal_low_label_without_external_package(
    db_session: Session, monkeypatch
) -> None:
    engine = ProcessingEngine(db_session)
    profile = engine._platform_detect_profile("cnki")

    monkeypatch.setattr(
        ProcessingEngine,
        "_local_suspicious_segments_v2",
        lambda self, _paragraph, _platform, _profile: [{"text": "可疑句段", "score": 35.0, "reason": "测试"}],
    )
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
    )

    assert rows[0]["suspicious_segments"][0]["label"] == "low"


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
