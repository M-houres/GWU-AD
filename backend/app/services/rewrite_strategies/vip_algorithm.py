from __future__ import annotations
from dataclasses import replace

from app.models import Task
from app.services.rewrite_strategies.assets import VIP_ASSETS
from app.services.rewrite_strategies.config import get_rewrite_runtime_config
from app.services.rewrite_strategies.rule_engine import apply_platform_rules
from app.services.rewrite_strategies.validators import adjust_to_target_length

def rewrite(db, *, task: Task | None, text: str, report_summary: dict | None = None) -> dict:
    runtime = get_rewrite_runtime_config(db, platform="vip")
    runtime_assets = replace(
        VIP_ASSETS,
        chunk_min_chars=int(runtime.get("chunk_min_chars", VIP_ASSETS.chunk_min_chars)),
        chunk_max_chars=int(runtime.get("chunk_max_chars", VIP_ASSETS.chunk_max_chars)),
        chunk_max_changes=int(runtime.get("algorithm_chunk_max_changes", VIP_ASSETS.chunk_max_changes)),
    )
    output, rule_trace = apply_platform_rules(
        db,
        text=text,
        assets=runtime_assets,
        report_summary=report_summary or {},
    )
    adjusted_output = adjust_to_target_length(
        output,
        source_text=text,
        platform="vip",
        allow_soft_expansion=False,
    )
    if adjusted_output != output:
        applied_rules = list(rule_trace.get("applied_rules") or [])
        applied_rules.append("length_adjust:target_window")
        rule_trace = {
            **rule_trace,
            "applied_rules": applied_rules,
        }
    output = adjusted_output
    rule_trace = {
        **rule_trace,
        "runtime": runtime,
    }
    return {"text": output, "rule_trace": rule_trace}
