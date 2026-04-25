from __future__ import annotations

import json
import re

from app.exceptions import BizError
from app.models import Task, TaskType
from app.services.cnki_rewrite_prompt import (
    build_cnki_dedup_precheck_prompt,
    build_cnki_dedup_prompt,
    build_cnki_dedup_validation_prompt,
)
from app.services.llm_service import generate_with_llm, load_llm_config


def _prompt(
    text: str,
    *,
    chunk_index: int = 1,
    chunk_total: int = 1,
    analysis: dict | None = None,
) -> str:
    return build_cnki_dedup_prompt(
        text,
        chunk_index=chunk_index,
        chunk_total=chunk_total,
    )


def _extract_json_payload(raw: str) -> dict | None:
    text = str(raw or "").strip()
    if not text:
        return None
    candidates = [text]
    fenced = re.findall(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
    if fenced:
        candidates = [item.strip() for item in fenced if str(item).strip()] + candidates
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        candidates.insert(0, match.group(0))
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except Exception:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _is_string_list(value) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _is_json_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_preanalysis_payload(payload: dict) -> dict:
    required_keys = {
        "ambient_formality",
        "p1_candidates",
        "p2_candidates",
        "p3_candidates",
        "p4_candidates",
        "frozen_terms",
        "high_freq_targets",
        "avg_n_per_sentence",
        "needs_sentence_ops",
    }
    if set(payload.keys()) != required_keys:
        raise BizError(code=4628, message="知网降重复率预分析阶段JSON字段不符合V14")
    if str(payload.get("ambient_formality") or "").strip() not in {"高度书面", "中等书面", "偏口语"}:
        raise BizError(code=4628, message="知网降重复率预分析阶段环境正式度不符合V14")
    for key in ("p1_candidates", "p2_candidates", "p3_candidates", "p4_candidates", "frozen_terms", "high_freq_targets"):
        if not _is_string_list(payload.get(key)):
            raise BizError(code=4628, message=f"知网降重复率预分析阶段字段 {key} 不符合V14")
    if not _is_json_number(payload.get("avg_n_per_sentence")):
        raise BizError(code=4628, message="知网降重复率预分析阶段 avg_n_per_sentence 不符合V14")
    if not isinstance(payload.get("needs_sentence_ops"), bool):
        raise BizError(code=4628, message="知网降重复率预分析阶段 needs_sentence_ops 不符合V14")
    return payload


def _validate_prompt_b_payload(payload: dict) -> dict:
    required_keys = {
        "semantic_ok",
        "grammar_ok",
        "formality_maintained",
        "avg_changes_per_sentence",
        "char_change",
        "diversity_ok",
        "issues",
        "verdict",
    }
    if set(payload.keys()) != required_keys:
        raise BizError(code=4629, message="知网降重复率校验阶段JSON字段不符合V14")
    for key in ("semantic_ok", "grammar_ok", "formality_maintained", "diversity_ok"):
        if not isinstance(payload.get(key), bool):
            raise BizError(code=4629, message=f"知网降重复率校验阶段字段 {key} 不符合V14")
    if not _is_json_number(payload.get("avg_changes_per_sentence")):
        raise BizError(code=4629, message="知网降重复率校验阶段 avg_changes_per_sentence 不符合V14")
    if not isinstance(payload.get("char_change"), str):
        raise BizError(code=4629, message="知网降重复率校验阶段 char_change 不符合V14")
    issues = payload.get("issues")
    if not isinstance(issues, list):
        raise BizError(code=4629, message="知网降重复率校验阶段 issues 不符合V14")
    for item in issues:
        if not isinstance(item, dict):
            raise BizError(code=4629, message="知网降重复率校验阶段 issues 项不符合V14")
        if set(item.keys()) != {"location", "type", "detail"}:
            raise BizError(code=4629, message="知网降重复率校验阶段 issues 字段不符合V14")
    if str(payload.get("verdict") or "").strip().lower() not in {"pass", "fail"}:
        raise BizError(code=4629, message="知网降重复率校验阶段 verdict 不符合V14")
    return payload


def _generate_json_payload(db, *, prompt: str, task_type: TaskType, error_code: int, error_message: str) -> dict:
    raw = generate_with_llm(db, task_type=task_type, text=prompt)
    last_raw = str(raw or "").strip()
    payload = _extract_json_payload(last_raw)
    if isinstance(payload, dict):
        return payload
    preview = re.sub(r"\s+", " ", last_raw)[:160]
    raise BizError(code=error_code, message=f"{error_message}，响应片段：{preview or 'empty'}")


def _run_preanalysis(db, *, text: str) -> dict:
    payload = _generate_json_payload(
        db,
        task_type=TaskType.DEDUP,
        prompt=build_cnki_dedup_precheck_prompt(text),
        error_code=4628,
        error_message="知网降重复率预分析阶段未返回有效JSON",
    )
    return _validate_preanalysis_payload(payload)


def _run_prompt_b_validation(db, *, source_text: str, rewritten_text: str) -> dict:
    payload = _generate_json_payload(
        db,
        task_type=TaskType.DEDUP,
        prompt=build_cnki_dedup_validation_prompt(source_text, rewritten_text),
        error_code=4629,
        error_message="知网降重复率校验阶段未返回有效JSON",
    )
    return _validate_prompt_b_payload(payload)


def _prompt_b_passed(payload: dict) -> bool:
    verdict = str(payload.get("verdict") or "").strip().lower()
    semantic_ok = bool(payload.get("semantic_ok", False))
    grammar_ok = bool(payload.get("grammar_ok", False))
    formality_maintained = bool(payload.get("formality_maintained", False))
    diversity_ok = bool(payload.get("diversity_ok", False))
    return verdict == "pass" and semantic_ok and grammar_ok and formality_maintained and diversity_ok


def rewrite(db, *, task: Task | None, text: str, report_summary: dict | None = None) -> dict:
    llm_cfg = load_llm_config(db)
    content = str(text or "")

    try:
        preanalysis = _run_preanalysis(db, text=content)
        output = str(
            generate_with_llm(
                db,
                task_type=TaskType.DEDUP,
                text=_prompt(
                    content,
                    chunk_index=1,
                    chunk_total=1,
                    analysis=preanalysis,
                ),
            )
            or ""
        ).strip()
        if not output:
            raise BizError(code=4624, message="知网降重复率大模型改写失败: Prompt A 输出为空")
        prompt_b = _run_prompt_b_validation(db, source_text=text, rewritten_text=output)
        if not _prompt_b_passed(prompt_b):
            issues = prompt_b.get("issues") if isinstance(prompt_b.get("issues"), list) else []
            issue_text = "；".join(str(item.get("detail") or "").strip() for item in issues[:3] if isinstance(item, dict))
            raise BizError(code=4630, message=f"知网降重复率三段式校验未通过{f'：{issue_text}' if issue_text else ''}")
        rule_trace = {
            "mode": "dedup_llm_prompt_pab_strict_v14_global",
            "applied_rules": [
                "dedup_llm:cnki_prompt_p:preanalysis",
                "dedup_llm:cnki_prompt_a:strict_v14_global",
                "dedup_llm:cnki_prompt_b:validation",
            ],
            "protected_hits": [],
            "strategy_version": "cnki_v14_dedup_llm_pab_strict",
            "chunk_count": 1,
            "technical_chunking": False,
            "preanalysis": preanalysis,
            "prompt_b_validation": prompt_b,
            "llm_provider": str(llm_cfg.get("provider") or ""),
            "llm_model": str(llm_cfg.get("model") or ""),
        }
    except Exception as exc:
        raise BizError(code=4624, message=f"知网降重复率大模型改写失败: {exc}") from exc

    if output.strip():
        return {"text": output, "rule_trace": rule_trace}

    raise BizError(code=4625, message="知网降重复率大模型结果为空")
