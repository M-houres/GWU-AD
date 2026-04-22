from __future__ import annotations

from app.models import Task
from app.services.dedup_strategies.assets import CNKI_DEDUP_ASSETS
from app.services.dedup_strategies.rule_engine import apply_dedup_rules


def rewrite(db, *, task: Task | None, text: str, report_summary: dict | None = None) -> dict:
    output, rule_trace = apply_dedup_rules(
        db,
        text=text,
        assets=CNKI_DEDUP_ASSETS,
        report_summary=report_summary or {},
    )
    return {"text": output, "rule_trace": rule_trace}
