from __future__ import annotations

from app.exceptions import BizError
from app.models import Task
from app.services.process_strategy_service import build_strategy_reset_message, is_strategy_reset_pending
from app.utils import count_billable_chars


def execute_rewrite_strategy(
    db,
    *,
    task: Task | None,
    platform: str,
    text: str,
    report_summary: dict | None = None,
) -> dict:
    normalized_platform = str(platform or "").strip().lower()
    if normalized_platform not in {"cnki", "vip"}:
        raise BizError(code=4116, message="不支持的平台")
    if is_strategy_reset_pending("rewrite", normalized_platform):
        raise BizError(
            code=4119,
            message=build_strategy_reset_message(task_type="rewrite", platform=normalized_platform),
        )
    if normalized_platform == "cnki":
        from app.services.rewrite_strategies.cnki_llm import rewrite

        rewrite_result = rewrite(db, task=task, text=text, report_summary=report_summary or {})
        output = str(rewrite_result.get("text") or "") if isinstance(rewrite_result, dict) else str(rewrite_result or "")
        rule_trace = rewrite_result.get("rule_trace") if isinstance(rewrite_result, dict) else {}
        if not output.strip():
            raise BizError(code=4611, message="知网降AIGC率 V20 输出为空")
        length_before = count_billable_chars(str(text or ""))
        length_after = count_billable_chars(output)
        return {
            "rewritten_text": output,
            "strategy": "llm",
            "platform": normalized_platform,
            "task_type": "rewrite",
            "length_before": length_before,
            "length_after": length_after,
            "change_ratio": round(((length_after - length_before) / max(length_before, 1)), 4),
            "quality_score": 1.0,
            "quality_flags": {"strict_cnki_v20_passed": True},
            "warnings": [],
            "rule_trace": dict(rule_trace or {}),
        }
    if normalized_platform == "vip":
        from app.services.rewrite_strategies.vip_llm import rewrite

        rewrite_result = rewrite(db, task=task, text=text, report_summary=report_summary or {})
        output = str(rewrite_result.get("text") or "") if isinstance(rewrite_result, dict) else str(rewrite_result or "")
        rule_trace = rewrite_result.get("rule_trace") if isinstance(rewrite_result, dict) else {}
        if not output.strip():
            raise BizError(code=4611, message="维普降AIGC率 W4 输出为空")
        length_before = count_billable_chars(str(text or ""))
        length_after = count_billable_chars(output)
        return {
            "rewritten_text": output,
            "strategy": "llm",
            "platform": normalized_platform,
            "task_type": "rewrite",
            "length_before": length_before,
            "length_after": length_after,
            "change_ratio": round(((length_after - length_before) / max(length_before, 1)), 4),
            "quality_score": 1.0,
            "quality_flags": {"strict_vip_w4_passed": True},
            "warnings": [],
            "rule_trace": dict(rule_trace or {}),
        }
    raise BizError(code=4119, message="降AIGC率新策略尚未接入")
