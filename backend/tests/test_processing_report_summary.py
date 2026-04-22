from app.models import TaskType
from app.services.processing_report_summary import extract_percent, extract_report_summary


def test_extract_percent_matches_first_keyword_value() -> None:
    text = "检测报告：全文总重复率 18.5%，去除引用复制比 11%。"

    assert extract_percent(text, ["总文字复制比", "全文总重复率"]) == 18.5
    assert extract_percent(text, ["不存在字段"]) is None


def test_extract_report_summary_returns_default_when_report_missing() -> None:
    summary = extract_report_summary(TaskType.DEDUP, "")

    assert summary["available"] is False
    assert summary["pressure"] == "low"
    assert summary["metrics"] == []
    assert summary["recommended_actions"] == ["未上传辅助报告，本次按正文通用策略处理。"]


def test_extract_report_summary_parses_dedup_pressure_and_actions() -> None:
    summary = extract_report_summary(
        TaskType.DEDUP,
        "全文检测报告 总文字复制比 27.3% 去除引用复制比 12% 去除本人已发表文献复制比 10.5%",
    )

    assert summary["available"] is True
    assert summary["pressure"] == "high"
    assert {"label": "总文字复制比", "value": 27.3, "unit": "%"} in summary["metrics"]
    assert {"label": "去除引用复制比", "value": 12.0, "unit": "%"} in summary["metrics"]
    assert "全文" in summary["highlights"]
    assert "重复率偏高，优先处理定义、综述和结论性长句。" in summary["recommended_actions"]
    assert "检查引用说明是否过少，必要时补充规范引文表达。" in summary["recommended_actions"]


def test_extract_report_summary_parses_aigc_pressure_and_actions() -> None:
    summary = extract_report_summary(
        TaskType.REWRITE,
        "全文AIGC检测报告 总体风险 52% 高风险段落占比 24%",
    )

    assert summary["available"] is True
    assert summary["pressure"] == "high"
    assert {"label": "总体风险", "value": 52.0, "unit": "%"} in summary["metrics"]
    assert {"label": "高风险占比", "value": 24.0, "unit": "%"} in summary["metrics"]
    assert "AIGC" in summary["highlights"]
    assert "AIGC 风险偏高，优先拆分长句并弱化模板化连接词。" in summary["recommended_actions"]
    assert "重点复核高风险段落，尤其是定义句和总结句。" in summary["recommended_actions"]


def test_extract_report_summary_adds_fallback_actions_when_metrics_are_weak() -> None:
    dedup_summary = extract_report_summary(TaskType.DEDUP, "全文检测报告 总文字复制比 8%")
    aigc_summary = extract_report_summary(TaskType.AIGC_DETECT, "AIGC检测报告 总体风险 10%")

    assert dedup_summary["pressure"] == "low"
    assert dedup_summary["recommended_actions"] == ["建议重点复核连续长句、定义表述和文献综述段落。"]
    assert aigc_summary["pressure"] == "low"
    assert aigc_summary["recommended_actions"] == ["建议优先调整摘要、结论和高频模板化表达。"]
