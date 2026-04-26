from __future__ import annotations

from app.models import TaskType
from app.services.cnki_pipeline_shared import (
    CnkiPipelineRunResult,
    CnkiTextRunResult,
    execute_cnki_paragraph_pipeline,
    execute_cnki_text_pipeline,
)
from app.services.dedup_strategies.config import get_dedup_prompt_template
from app.services.vip_dedup_prompt import build_vip_dedup_prompt_from_template


def execute_vip_dedup(db, *, task_type: TaskType, paragraphs: list[str]) -> CnkiPipelineRunResult:
    template = get_dedup_prompt_template(db, platform="vip")
    return execute_cnki_paragraph_pipeline(
        db,
        task_type=task_type,
        paragraphs=paragraphs,
        prompt_builder=lambda paragraph: build_vip_dedup_prompt_from_template(template, paragraph),
        pipeline_label="维普降重复",
        empty_message="维普降重复无可改写正文",
    )


def execute_vip_dedup_text(db, *, task_type: TaskType, source_text: str) -> CnkiTextRunResult:
    template = get_dedup_prompt_template(db, platform="vip")
    return execute_cnki_text_pipeline(
        db,
        task_type=task_type,
        source_text=source_text,
        prompt_builder=lambda paragraph: build_vip_dedup_prompt_from_template(template, paragraph),
        pipeline_label="维普降重复",
        empty_message="维普降重复无可改写正文",
    )
