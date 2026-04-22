from difflib import SequenceMatcher

from app.models import TaskType


def build_transform_result(
    *,
    task_type: TaskType,
    platform: str,
    mode: str,
    source_text: str,
    output_text: str,
    report_summary: dict,
    text_stats,
    clip_text,
    pipeline_usage: dict,
    rewrite_strategy_meta: dict | None,
    dedup_strategy_meta: dict | None,
) -> dict:
    source_stats = text_stats(source_text)
    output_stats = text_stats(output_text)
    sample_before = source_text[:4000]
    sample_after = output_text[:4000]
    similarity = SequenceMatcher(None, sample_before, sample_after).ratio() if sample_before or sample_after else 1.0
    change_ratio = round((1 - similarity) * 100, 2)
    task_label = "降重" if task_type == TaskType.DEDUP else "学术润色"
    review_points = list(report_summary.get("recommended_actions") or [])
    review_points.append("建议下载结果文档后结合原文进行人工终审。")
    review_points.append("重点检查摘要、结论、数据表述和引用位置。")
    deduped_points = list(dict.fromkeys(review_points))
    rewrite_strategy = dict(rewrite_strategy_meta or {}) if task_type == TaskType.REWRITE else None
    dedup_strategy = dict(dedup_strategy_meta or {}) if task_type == TaskType.DEDUP else None
    return {
        "type": task_type.value,
        "platform": platform,
        "mode": mode,
        "llm_used": bool(pipeline_usage.get("llm_used")),
        "summary": f"{task_label}任务已完成，本次结果已结合正文与辅助报告生成处理摘要。",
        "source_stats": source_stats,
        "output_stats": output_stats,
        "change_ratio": change_ratio,
        "report_summary": report_summary,
        "review_points": deduped_points[:4],
        "output_preview": clip_text(output_text, 220),
        "rewrite_strategy": rewrite_strategy,
        "dedup_strategy": dedup_strategy,
    }
