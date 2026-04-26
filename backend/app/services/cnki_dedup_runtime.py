from __future__ import annotations

from app.models import TaskType
from app.services.cnki_dedup_prompt import build_cnki_dedup_prompt_from_template
from app.services.cnki_pipeline_shared import (
    CnkiPipelineRunResult,
    CnkiTextRunResult,
    execute_cnki_paragraph_pipeline,
    execute_cnki_text_pipeline,
)
from app.services.dedup_strategies.config import get_dedup_prompt_template


def execute_cnki_dedup(db, *, task_type: TaskType, paragraphs: list[str]) -> CnkiPipelineRunResult:
    template = get_dedup_prompt_template(db, platform="cnki")
    return execute_cnki_paragraph_pipeline(
        db,
        task_type=task_type,
        paragraphs=paragraphs,
        prompt_builder=lambda paragraph: build_cnki_dedup_prompt_from_template(template, paragraph),
        pipeline_label="知网降重复",
        empty_message="知网降重复无可改写正文",
    )


def execute_cnki_dedup_text(db, *, task_type: TaskType, source_text: str) -> CnkiTextRunResult:
    template = get_dedup_prompt_template(db, platform="cnki")
    return execute_cnki_text_pipeline(
        db,
        task_type=task_type,
        source_text=source_text,
        prompt_builder=lambda paragraph: build_cnki_dedup_prompt_from_template(template, paragraph),
        pipeline_label="知网降重复",
        empty_message="知网降重复无可改写正文",
    )
