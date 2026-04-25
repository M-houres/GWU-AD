from __future__ import annotations

from app.models import TaskType
from app.models import Task
from app.services.vip_w4_runtime import execute_vip_w4_text


def rewrite(db, *, task: Task | None, text: str, report_summary: dict | None = None) -> dict:
    result = execute_vip_w4_text(
        db,
        task_type=task.task_type if task is not None else TaskType.REWRITE,
        source_text=text,
    )
    return {
        "text": result.text,
        "rule_trace": {
            "mode": "vip_w4_strict_runtime",
            "applied_rules": ["llm:vip_w4:full_text_runtime"],
            "protected_hits": [],
            "strategy_version": "vip_w4",
            "chunk_count": 1,
            "technical_chunking": False,
            "reported_total_rewrites": result.run.reported_total_rewrites,
            "plan": {
                "total_chars": result.run.plan.total_chars,
                "total_quota": result.run.plan.total_quota,
                "paragraph_count": result.run.plan.paragraph_count,
                "paragraph_quotas": [
                    {"index": item.index, "char_count": item.char_count, "quota": item.quota}
                    for item in result.run.plan.paragraphs
                ],
            },
            "llm_provider": result.run.llm_provider,
            "llm_model": result.run.llm_model,
        },
    }
