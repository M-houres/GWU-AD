from __future__ import annotations

from app.models import Task, TaskType
from app.services.dedup_strategies.vip_algorithm import rewrite as algorithm_rewrite
from app.services.llm_service import generate_with_llm
from app.services.strategy_prompt_assets import build_slot_positive_examples, build_slot_prompt_examples
from app.services.strategy_style_profiles import build_dedup_style_guidance


def _prompt(text: str) -> str:
    positive_examples = build_slot_positive_examples("vip.dedup.llm")
    negative_examples = build_slot_prompt_examples("vip.dedup.llm")
    style_guidance = build_dedup_style_guidance("vip")
    return (
        "你是一名中文论文维普查重降重编辑。请降低文字、语序、近义表达和段落逻辑结构相似风险。"
        "允许比知网策略更明显地调整句式，包括主被动转换、长短句调节、分句重排和连接词重组；"
        "必须兼容教育、医学、法学/政策、财经管理、工程/计算机、人文社科等领域，"
        "必须完整保留“临床路径”“证据链完整性”“并购整合”“边缘计算架构”“社区记忆”等跨学科术语表达；"
        "优先对定义句、综述句和收束句做句法骨架重组，不要只替换个别动词或把句首连接词换一种说法；"
        "但必须按完整语义块改写，不要做词级硬替换，不要输出“这说明其属于”“借助X这一方式”“把A和B进行结合”这类模板。"
        "必须保留事实、数据、引用、术语、英文缩写和原有论点，禁止出现“作为属于”“蕴含包括着”“融结合”“将把”“能够可以”“可以进一步”这类拼接痕迹。"
        f"{style_guidance}\n"
        f"{positive_examples}\n"
        f"{negative_examples}\n"
        "不要解释，只输出改写后的完整文本。\n\n"
        f"原文：\n{text}"
    )


def rewrite(db, *, task: Task | None, text: str, report_summary: dict | None = None) -> dict:
    base = algorithm_rewrite(db, task=task, text=text, report_summary=report_summary)
    base_text = str(base.get("text") or text)
    try:
        output = generate_with_llm(db, task_type=TaskType.DEDUP, text=_prompt(base_text))
        rule_trace = {"mode": "dedup_llm_prompt", "applied_rules": ["dedup_llm:vip_prompt"], "protected_hits": []}
    except Exception:
        rule_trace = dict(base.get("rule_trace") or {})
        rule_trace["llm_fallback"] = True
        return {"text": base_text, "rule_trace": rule_trace}
    return {"text": output, "rule_trace": rule_trace}
