from __future__ import annotations

from app.models import Task, TaskType
from app.services.llm_service import generate_with_llm
from app.services.strategy_prompt_assets import build_slot_positive_examples, build_slot_prompt_examples
from app.services.strategy_style_profiles import build_rewrite_style_guidance
from app.services.rewrite_strategies.validators import adjust_to_target_length
from app.services.rewrite_strategies.vip_algorithm import rewrite as algorithm_rewrite


def _prompt(text: str) -> str:
    positive_examples = build_slot_positive_examples("vip.rewrite.llm")
    negative_examples = build_slot_prompt_examples("vip.rewrite.llm")
    style_guidance = build_rewrite_style_guidance("vip")
    return (
        "你是一名专业中文文本改写师。请对以下文本执行维普降AIGC率改写。\n"
        "综合运用句式重组、句序微调、长短句调节和段落级顺滑，不要依赖词级硬替换。"
        "保持标题、段落、表格、引文、数据、术语和主旨不变；中文字符数优先控制在增加 5% 到 8%。\n"
        "需要兼容教育、医学、法学/政策、财经管理、工程/计算机、人文社科等不同专业论文，"
        "必须保留“临床路径”“证据链完整性”“并购整合”“边缘计算架构”“社区记忆”等专业名词的完整表达。\n"
        f"{style_guidance}\n"
        "需要优先改写核心判断句和总结句的句法骨架，不要只做局部替词或只把“本文/本研究”替换成“该研究”。"
        "禁止输出“作为属于”“蕴含包括着”“将把”“能够可以”“可以能够”“路径方式”“模型式”等低质量拼接表达。"
        "需要兼容不同专业论文，优先保证自然度、完整术语和论证连贯性。\n"
        f"{positive_examples}\n"
        f"{negative_examples}\n"
        "只输出改写后的完整文本，不要解释。\n\n"
        f"原文：\n{text}"
    )


def rewrite(db, *, task: Task | None, text: str, report_summary: dict | None = None) -> dict:
    try:
        output = generate_with_llm(db, task_type=TaskType.REWRITE, text=_prompt(text))
        rule_trace = {"mode": "llm_prompt", "applied_rules": ["llm:vip_prompt"], "protected_hits": []}
    except Exception:
        output = algorithm_rewrite(db, task=task, text=text, report_summary=report_summary)
        return output
    output = adjust_to_target_length(output, source_text=text, platform="vip")
    return {"text": output, "rule_trace": rule_trace}
