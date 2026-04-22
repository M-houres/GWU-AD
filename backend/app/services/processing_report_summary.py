import re

from app.models import TaskType


def extract_percent(text: str, keywords: list[str]) -> float | None:
    for keyword in keywords:
        pattern = rf"{re.escape(keyword)}[^0-9]{{0,12}}(\d+(?:\.\d+)?)\s*%"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return round(float(match.group(1)), 2)
    return None


def extract_report_summary(task_type: TaskType, report_text: str) -> dict:
    content = " ".join((report_text or "").split())
    summary = {
        "available": bool(content),
        "metrics": [],
        "highlights": [],
        "recommended_actions": [],
        "pressure": "low",
    }
    if not content:
        summary["recommended_actions"] = ["未上传辅助报告，本次按正文通用策略处理。"]
        return summary

    if task_type == TaskType.DEDUP:
        total_ratio = extract_percent(content, ["总文字复制比", "全文总重复率", "重复率", "总复制比"])
        quote_ratio = extract_percent(content, ["去除引用复制比"])
        self_ratio = extract_percent(content, ["去除本人已发表文献复制比"])
        for label, value in (
            ("总文字复制比", total_ratio),
            ("去除引用复制比", quote_ratio),
            ("去除本人已发表文献复制比", self_ratio),
        ):
            if value is not None:
                summary["metrics"].append({"label": label, "value": value, "unit": "%"})
        summary["highlights"] = [word for word in ["全文", "检测报告", "总文字复制比", "去除引用复制比"] if word in content][
            :4
        ]
        if total_ratio is not None and total_ratio >= 25:
            summary["recommended_actions"].append("重复率偏高，优先处理定义、综述和结论性长句。")
            summary["pressure"] = "high"
        elif total_ratio is not None and total_ratio >= 15:
            summary["recommended_actions"].append("重复率中等，优先改写高频连接词和段首句。")
            summary["pressure"] = "medium"
        if quote_ratio is not None and quote_ratio >= 10:
            summary["recommended_actions"].append("检查引用说明是否过少，必要时补充规范引文表达。")
        if self_ratio is not None and self_ratio >= 10:
            summary["recommended_actions"].append("留意与本人历史文本重合的定义和结论段。")
    else:
        ai_ratio = extract_percent(content, ["AIGC总体风险", "总体风险", "AIGC疑似度", "AI生成疑似度", "疑似AI生成"])
        high_ratio = extract_percent(content, ["高风险占比", "高风险段落占比"])
        for label, value in (
            ("总体风险", ai_ratio),
            ("高风险占比", high_ratio),
        ):
            if value is not None:
                summary["metrics"].append({"label": label, "value": value, "unit": "%"})
        summary["highlights"] = [word for word in ["AIGC", "疑似AI", "高风险段落", "全文"] if word.lower() in content.lower()][:4]
        if ai_ratio is not None and ai_ratio >= 50:
            summary["recommended_actions"].append("AIGC 风险偏高，优先拆分长句并弱化模板化连接词。")
            summary["pressure"] = "high"
        elif ai_ratio is not None and ai_ratio >= 30:
            summary["recommended_actions"].append("AIGC 风险中等，建议提升句式变化和论证层次。")
            summary["pressure"] = "medium"
        if high_ratio is not None and high_ratio >= 20:
            summary["recommended_actions"].append("重点复核高风险段落，尤其是定义句和总结句。")

    if not summary["recommended_actions"]:
        if task_type == TaskType.DEDUP:
            summary["recommended_actions"].append("建议重点复核连续长句、定义表述和文献综述段落。")
        else:
            summary["recommended_actions"].append("建议优先调整摘要、结论和高频模板化表达。")
    return summary
