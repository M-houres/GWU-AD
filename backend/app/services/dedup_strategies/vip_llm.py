from __future__ import annotations

from app.exceptions import BizError
from app.models import Task, TaskType
from app.services.llm_service import generate_with_llm, load_llm_config
from app.services.vip_wp2_prompt import build_vip_dedup_prompt, build_vip_dedup_validation_prompt
from app.services.vip_wp2_runtime import (
    generate_json_payload,
    validate_wp2_prompt_b_payload,
    wp2_prompt_b_passed,
)


def _prompt(text: str, *, chunk_index: int = 1, chunk_total: int = 1) -> str:
    return build_vip_dedup_prompt(text, chunk_index=chunk_index, chunk_total=chunk_total)


def _run_prompt_b_validation(db, *, source_text: str, rewritten_text: str) -> dict:
    payload = generate_json_payload(
        db,
        task_type=TaskType.DEDUP,
        prompt=build_vip_dedup_validation_prompt(source_text, rewritten_text),
        error_code=4634,
        error_message="维普降重复率校验阶段未返回有效JSON",
    )
    return validate_wp2_prompt_b_payload(payload, error_code=4634, stage_label="维普降重复率校验阶段")


def rewrite(db, *, task: Task | None, text: str, report_summary: dict | None = None) -> dict:
    llm_cfg = load_llm_config(db)
    content = str(text or "")

    try:
        output = str(
            generate_with_llm(
                db,
                task_type=TaskType.DEDUP,
                text=_prompt(content, chunk_index=1, chunk_total=1),
            )
            or ""
        ).strip()
        if not output:
            raise BizError(code=4624, message="维普降重复率大模型改写失败: Prompt A 输出为空")
        prompt_b = _run_prompt_b_validation(db, source_text=text, rewritten_text=output)
        if not wp2_prompt_b_passed(prompt_b):
            issues = prompt_b.get("issues") if isinstance(prompt_b.get("issues"), list) else []
            issue_text = "；".join(str(item.get("detail") or "").strip() for item in issues[:3] if isinstance(item, dict))
            raise BizError(code=4635, message=f"维普降重复率 A/B 校验未通过{f'：{issue_text}' if issue_text else ''}")
        rule_trace = {
            "mode": "dedup_llm_prompt_ab_strict_wp2_global",
            "applied_rules": [
                "dedup_llm:vip_wp2_prompt_a:strict_wp2_global",
                "dedup_llm:vip_wp2_prompt_b:validation",
            ],
            "protected_hits": [],
            "strategy_version": "vip_wp2_dedup_llm_ab_strict",
            "chunk_count": 1,
            "technical_chunking": False,
            "prompt_b_validation": prompt_b,
            "llm_provider": str(llm_cfg.get("provider") or ""),
            "llm_model": str(llm_cfg.get("model") or ""),
        }
    except Exception as exc:
        raise BizError(code=4624, message=f"维普降重复率大模型改写失败: {exc}") from exc

    if output.strip():
        return {"text": output, "rule_trace": rule_trace}

    raise BizError(code=4636, message="维普降重复率大模型结果为空")
