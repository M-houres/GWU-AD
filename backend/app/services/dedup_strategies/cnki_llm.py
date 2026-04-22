from __future__ import annotations

from app.models import Task, TaskType
from app.services.dedup_strategies.cnki_algorithm import rewrite as algorithm_rewrite
from app.services.llm_service import generate_with_llm
from app.services.strategy_prompt_assets import build_slot_positive_examples, build_slot_prompt_examples
from app.services.strategy_style_profiles import build_dedup_style_guidance


def _prompt(text: str) -> str:
    positive_examples = build_slot_positive_examples("cnki.dedup.llm")
    negative_examples = build_slot_prompt_examples("cnki.dedup.llm")
    style_guidance = build_dedup_style_guidance("cnki")
    return (
        "你是一名中文论文知网查重降重编辑。请在不改变事实、数据、引用、术语和段落顺序的前提下，"
        "降低连续相似片段和定义句、综述句的重复风险。要求偏保守：保留专业术语，轻度调整句式、连接词和表达顺序；"
        "必须兼容教育、医学、法学/政策、财经管理、工程/计算机、人文社科等领域，"
        "像“血糖管理”“行政复议程序”“现金流风险预警”“边缘计算架构”“区域社会韧性”等专业名词不得改散、改虚或拆坏；"
        "优先改写定义句、判断句和结论句的句法骨架，不要只替换单个动词、句首主语或连接词；"
        "不要按降AIGC率目标强制扩写，不要把一个长句机械拆成多个由“同时”“此外”“进一步看”“在此基础上”“由此可见”领起的短句，"
        "不要输出“这说明其属于”这类模板化判断句。\n"
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
        rule_trace = {"mode": "dedup_llm_prompt", "applied_rules": ["dedup_llm:cnki_prompt"], "protected_hits": []}
    except Exception:
        rule_trace = dict(base.get("rule_trace") or {})
        rule_trace["llm_fallback"] = True
        return {"text": base_text, "rule_trace": rule_trace}
    return {"text": output, "rule_trace": rule_trace}
