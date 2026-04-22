from __future__ import annotations

from typing import Any

from app.exceptions import BizError
from app.models import Task
from app.services.aigc_detect_strategies.config import ensure_aigc_detect_enabled
from app.services.aigc_detect_strategies.report_builder import build_report_payload


def execute_aigc_detect_strategy(
    db,
    *,
    task: Task | None,
    platform: str,
    text: str,
    report_summary: dict | None = None,
    mode: str = "ALGO_ONLY",
) -> dict[str, Any]:
    normalized_platform = str(platform or "").strip().lower()
    ensure_aigc_detect_enabled(db, platform=normalized_platform)
    if normalized_platform == "cnki":
        from app.services.aigc_detect_strategies.cnki import detect
    elif normalized_platform == "vip":
        from app.services.aigc_detect_strategies.vip import detect
    else:
        raise BizError(code=4116, message="不支持的平台")

    detect_output = detect(text)
    return build_report_payload(
        text=text,
        platform=normalized_platform,
        detect_output=detect_output,
        report_summary=report_summary or {},
        mode=mode,
        task_id=getattr(task, "id", None),
    )
