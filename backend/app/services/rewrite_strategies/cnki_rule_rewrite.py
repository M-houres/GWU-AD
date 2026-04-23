from __future__ import annotations
from dataclasses import replace

from app.models import Task
from app.services.rewrite_strategies.assets import CNKI_ASSETS
from app.services.rewrite_strategies.config import get_rewrite_runtime_config
from app.services.rewrite_strategies.rule_engine import apply_platform_rules
from app.services.rewrite_strategies.validators import adjust_to_target_length


def rewrite(db, *, task: Task | None, text: str, report_summary: dict | None = None) -> dict:
    runtime = get_rewrite_runtime_config(db, platform="cnki")
    runtime_assets = replace(
        CNKI_ASSETS,
        chunk_min_chars=int(runtime.get("chunk_min_chars", CNKI_ASSETS.chunk_min_chars)),
        chunk_max_chars=int(runtime.get("chunk_max_chars", CNKI_ASSETS.chunk_max_chars)),
        chunk_max_changes=int(runtime.get("algorithm_chunk_max_changes", CNKI_ASSETS.chunk_max_changes)),
    )
    output, rule_trace = apply_platform_rules(
        db,
        text=text,
        assets=runtime_assets,
        report_summary=report_summary or {},
    )
    adjusted_output = adjust_to_target_length(output, source_text=text, platform="cnki")
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
        "mode": "rewrite_rule_engine",
        "strategy_version": "cnki_v5_rule_engine",
        "rule_pool_size": len(CNKI_ASSETS.synonyms),
        "template_library_size": len(CNKI_ASSETS.templates),
        "runtime": runtime,
    }
    return {"text": output, "rule_trace": rule_trace}
