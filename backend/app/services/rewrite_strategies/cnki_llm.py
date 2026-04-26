from __future__ import annotations

from app.models import TaskType
from app.models import Task
from app.services.cnki_rewrite_runtime import execute_cnki_rewrite_text


def rewrite(db, *, task: Task | None, text: str, report_summary: dict | None = None) -> dict:
    result = execute_cnki_rewrite_text(
        db,
        task_type=task.task_type if task is not None else TaskType.REWRITE,
        source_text=text,
    )
    return {
        "text": result.text,
        "rule_trace": {
            "mode": "cnki_rewrite_style_transfer",
            "applied_rules": ["llm:cnki:rewrite:paragraph_style_transfer"],
            "protected_hits": [],
            "strategy_version": "cnki_rewrite_v1",
            "paragraph_count": result.run.paragraph_count,
            "total_chars": result.run.total_chars,
            "llm_provider": result.run.llm_provider,
            "llm_model": result.run.llm_model,
        },
    }
