from pathlib import Path

from app.services.cnki_aigc_report_parser import parse_distribution_20pct, parse_metadata, parse_section_rows


def test_parse_distribution_20pct_extracts_front_middle_back() -> None:
    lines = [
        "AIGC片段分布图",
        "前部20%",
        "中部60%",
        "后部20%",
        "AI特征值：18.1%",
        "AI特征字符数：11494",
        "AI特征值：61.6%",
        "AI特征字符数：7816",
        "AI特征值：7.1%",
        "AI特征字符数：2694",
        "AI特征值：7.8%",
        "AI特征字符数：984",
    ]

    result = parse_distribution_20pct(lines)

    assert result == {
        "front": {"score_pct": 61.6, "ai_chars": 7816},
        "middle": {"score_pct": 7.1, "ai_chars": 2694},
        "back": {"score_pct": 7.8, "ai_chars": 984},
    }


def test_parse_section_rows_handles_wrapped_cnki_section_names() -> None:
    lines = [
        "分段检测结果",
        "序号 AI特征值 AI特征字符数 / 章节(部分)字符数 章节(部分)名称",
        "1 78.0% 2703 / 3464 中英文摘要等",
        "2 53.9% 5113 / 9493 1 绪论",
        "3 5.9% 338 / 5765",
        "3 X餐饮连锁公司发展概况与营销策略现状及其问题诊断4 0.0% 0 / 9143",
        "_第1部分",
        "5 0.0% 0 / 3388 3 X餐饮连锁公司发展概况与营销策略现状及其问题诊断_第2部分",
        "6 14.0% 1383 / 9865 4 X餐饮连锁公司营销环境分析",
        "1. 中英文摘要等",
    ]

    rows = parse_section_rows(lines)

    assert rows[:3] == [
        {"row_no": 1, "score_pct": 78.0, "ai_chars": 2703, "section_chars": 3464, "section_name": "中英文摘要等"},
        {"row_no": 2, "score_pct": 53.9, "ai_chars": 5113, "section_chars": 9493, "section_name": "1 绪论"},
        {
            "row_no": 3,
            "score_pct": 5.9,
            "ai_chars": 338,
            "section_chars": 5765,
            "section_name": "3 X餐饮连锁公司发展概况与营销策略现状及其问题诊断",
        },
    ]
    assert rows[3]["row_no"] == 4
    assert rows[3]["section_name"] == "3 X餐饮连锁公司发展概况与营销策略现状及其问题诊断_第1部分"
    assert rows[5]["section_name"] == "4 X餐饮连锁公司营销环境分析"


def test_parse_metadata_identifies_report_kind_and_score() -> None:
    pdf_path = Path("AIGC全文报告_信息技术支持下的小学英语互动课堂构建研究.pdf")
    lines = [
        "AIGC检测 · 全文报告单",
        "NO:CNKIAIGC2026FG_202604122391627 检测时间：2026-04-05 18:08:42",
        "篇名： 信息技术支持下的小学英语互动课堂构建研究",
        "作者： XXX",
        "文件名：信息技术支持下的小学英语互动课堂构建研究.docx",
        "全文检测结果  知网AIGC检测  https://cx.cnki.net",
        "17.1%",
        "AI特征值：17.1%",
        "AI特征字符数：646",
        "总字符数：3783",
        "分段检测结果",
    ]

    metadata = parse_metadata(lines, pdf_path)

    assert metadata["report_kind"] == "full"
    assert metadata["report_no"] == "CNKIAIGC2026FG_202604122391627"
    assert metadata["title"] == "信息技术支持下的小学英语互动课堂构建研究"
    assert metadata["total_score_pct"] == 17.1
    assert metadata["ai_chars"] == 646
    assert metadata["total_chars"] == 3783
