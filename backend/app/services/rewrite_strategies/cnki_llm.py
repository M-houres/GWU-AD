from __future__ import annotations

from app.models import Task, TaskType
from app.services.llm_service import generate_with_llm
from app.services.strategy_prompt_assets import build_slot_positive_examples, build_slot_prompt_examples
from app.services.strategy_style_profiles import build_rewrite_style_guidance
from app.services.rewrite_strategies.cnki_algorithm import rewrite as algorithm_rewrite
from app.services.rewrite_strategies.validators import adjust_to_target_length


def _prompt(text: str) -> str:
    positive_examples = build_slot_positive_examples("cnki.rewrite.llm")
    negative_examples = build_slot_prompt_examples("cnki.rewrite.llm")
    style_guidance = build_rewrite_style_guidance("cnki")
    return (
        "你是一名专业中文学术文本润色师。请对以下文本执行知网降AIGC率改写。\n"
        "硬性要求：只做语言表层重构，不改变主旨、事实、数据、论点和格式；中文字符数优先控制在增加 5% 到 8%；"
        "必须完整保留复合术语、政策表述、专业缩写、引文和数字，严禁把“可视化”改成“可以视化”或“能够视化”。\n"
        "必须兼容教育、医学、法学/政策、财经管理、工程/计算机、人文社科等论文场景；"
        "像“血糖管理”“行政复议程序”“现金流风险预警”“边缘计算架构”“区域社会韧性”这类专业名词应原样保留，不得弱化成空泛说法。\n"
        f"{style_guidance}\n"
        "请按段落和完整语义块改写，优先使用句首重写、判断句改写、短句重排和局部学术表达替换，不要做词级硬替换。"
        "核心判断句、理论贡献/实践价值句、总体评价句至少做一次句法骨架替换，不要只把“本文/本研究”换成“该研究”就结束。"
        "不要把一个长句机械拆成多个由“同时”“此外”“进一步看”“在此基础上”领起的短句，不要连续堆叠这些连接词。"
        "不要输出“这说明其属于”“并进一步保持原有论证脉络”等模板句，不要产生“作为属于”“蕴含包括着”“融结合”“路径方式”这类拼接异常。\n"
        f"{positive_examples}\n"
        f"{negative_examples}\n"
        "只输出改写后的完整文本，不要解释。\n\n"
        f"原文：\n{text}"
    )


def rewrite(db, *, task: Task | None, text: str, report_summary: dict | None = None) -> dict:
    try:
        output = generate_with_llm(db, task_type=TaskType.REWRITE, text=_prompt(text))
        rule_trace = {"mode": "llm_prompt", "applied_rules": ["llm:cnki_prompt"], "protected_hits": []}
    except Exception:
        return algorithm_rewrite(db, task=task, text=text, report_summary=report_summary)
    output = adjust_to_target_length(output, source_text=text, platform="cnki")
    return {"text": output, "rule_trace": rule_trace}
