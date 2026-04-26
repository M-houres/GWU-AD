from __future__ import annotations

from difflib import SequenceMatcher

from app.exceptions import BizError
from app.models import Task
from app.services.process_strategy_service import build_strategy_reset_message, is_strategy_reset_pending
from app.utils import count_billable_chars


STRATEGY_LLM = "llm"


def execute_dedup_strategy(
    db,
    *,
    task: Task | None,
    platform: str,
    text: str,
    report_summary: dict | None = None,
    strategy: str = STRATEGY_LLM,
) -> dict:
    normalized_platform = str(platform or "").strip().lower()
    if normalized_platform not in {"cnki", "vip"}:
        raise BizError(code=4116, message="不支持的平台")
    if is_strategy_reset_pending("dedup", normalized_platform):
        raise BizError(
            code=4120,
            message=build_strategy_reset_message(task_type="dedup", platform=normalized_platform),
        )
    if normalized_platform == "cnki":
        from app.services.dedup_strategies.cnki_llm import rewrite

        rewrite_result = rewrite(db, task=task, text=text, report_summary=report_summary or {})
        output = str(rewrite_result.get("text") or "") if isinstance(rewrite_result, dict) else str(rewrite_result or "")
        rule_trace = rewrite_result.get("rule_trace") if isinstance(rewrite_result, dict) else {}
        if not output.strip():
            raise BizError(code=4621, message="知网降重复输出为空")
        length_before = count_billable_chars(str(text or ""))
        length_after = count_billable_chars(output)
        similarity_ratio = SequenceMatcher(None, str(text or "")[:4000], output[:4000]).ratio()
        return {
            "rewritten_text": output,
            "strategy": STRATEGY_LLM,
            "platform": normalized_platform,
            "task_type": "dedup",
            "length_before": length_before,
            "length_after": length_after,
            "length_delta_ratio": round(((length_after - length_before) / max(length_before, 1)), 4),
            "similarity_ratio": round(similarity_ratio, 4),
            "change_ratio": round((1 - similarity_ratio) * 100, 2),
            "quality_score": 1.0,
            "quality_flags": {"cnki_dedup_pipeline_applied": True},
            "warnings": [],
            "rule_trace": dict(rule_trace or {}),
        }
    if normalized_platform == "vip":
        from app.services.dedup_strategies.vip_llm import rewrite

        rewrite_result = rewrite(db, task=task, text=text, report_summary=report_summary or {})
        output = str(rewrite_result.get("text") or "") if isinstance(rewrite_result, dict) else str(rewrite_result or "")
        rule_trace = rewrite_result.get("rule_trace") if isinstance(rewrite_result, dict) else {}
        if not output.strip():
            raise BizError(code=4621, message="维普降重复输出为空")
        length_before = count_billable_chars(str(text or ""))
        length_after = count_billable_chars(output)
        similarity_ratio = SequenceMatcher(None, str(text or "")[:4000], output[:4000]).ratio()
        return {
            "rewritten_text": output,
            "strategy": STRATEGY_LLM,
            "platform": normalized_platform,
            "task_type": "dedup",
            "length_before": length_before,
            "length_after": length_after,
            "length_delta_ratio": round(((length_after - length_before) / max(length_before, 1)), 4),
            "similarity_ratio": round(similarity_ratio, 4),
            "change_ratio": round((1 - similarity_ratio) * 100, 2),
            "quality_score": 1.0,
            "quality_flags": {"vip_dedup_pipeline_applied": True},
            "warnings": [],
            "rule_trace": dict(rule_trace or {}),
        }
    raise BizError(code=4120, message="降重复率新策略尚未接入")
