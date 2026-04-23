from __future__ import annotations

from dataclasses import replace

from app.models import Task
from app.services.dedup_strategies.assets import CNKI_DEDUP_ASSETS
from app.services.dedup_strategies.config import get_dedup_runtime_config
from app.services.dedup_strategies.rule_engine import apply_dedup_rules


def rewrite(db, *, task: Task | None, text: str, report_summary: dict | None = None) -> dict:
    runtime = get_dedup_runtime_config(db, platform="cnki")
    runtime_assets = replace(
        CNKI_DEDUP_ASSETS,
        chunk_min_chars=int(runtime.get("chunk_min_chars", CNKI_DEDUP_ASSETS.chunk_min_chars)),
        chunk_max_chars=int(runtime.get("chunk_max_chars", CNKI_DEDUP_ASSETS.chunk_max_chars)),
        chunk_max_changes=int(runtime.get("algorithm_chunk_max_changes", CNKI_DEDUP_ASSETS.chunk_max_changes)),
    )
    output, rule_trace = apply_dedup_rules(
        db,
        text=text,
        assets=runtime_assets,
        report_summary=report_summary or {},
    )
    rule_trace = {
        **(rule_trace or {}),
        "mode": "dedup_rule_engine",
        "strategy_version": "cnki_v5_rule_engine",
        "rule_pool_size": len(CNKI_DEDUP_ASSETS.synonyms),
        "template_library_size": len(CNKI_DEDUP_ASSETS.templates),
        "runtime": runtime,
    }
    return {"text": output, "rule_trace": rule_trace}
