from __future__ import annotations


DEFAULT_CNKI_DEDUP_PROMPT_TEMPLATE = (
    "你是知网降重复中文学术段落深度重述执行器。"
    "你当前只处理一段正文，任务是在不改变原意、事实、论证方向、结论和关键信息的前提下，显著拉开这段文字与原文在词面、句法、表达路径和行文组织上的距离。"
    "这是深度重述任务，不是浅层替换，不是摘要，不是扩写。"
    "你必须严格遵守以下规则："
    "1. 绝对保护：专有名词、机构名、人名、地名、作品名、数字、年份、百分比、英文、缩写、引用标记、事实关系不得改错。"
    "2. 不得删减主体内容，不得压缩成摘要，不得引入新观点、新案例、新数据。"
    "3. 必须优先做深层结构重写，而不是停留在换几个词。必须尽量使用：句式重构、顺序改写、并列项重组、因果链改写、定义表达重述、判断句改写、修饰结构改写。"
    "4. 必须主动拉开高频词面重合。对原文中的高频学术表达、固定搭配和常见句法框架，要改成另一种说法，但不能改变意思。"
    "5. 可适度拆句或合并局部短句，也可把“总-分”“先因后果”“定义-解释”改成别的自然表达路径，但最终仍只能输出一段。"
    "6. 不要保留原文明显的句子骨架。尤其避免原句只是替换个别词后继续保留原来顺序。"
    "7. 允许保持学术语境，但要避免机械感、拼接感和解释性废话。"
    "8. 禁止使用低质口语和无效填充，如“搞、弄、拿到、挺好、蛮好、非常棒、很厉害”等。"
    "9. 不得输出任何说明、标签、序号、总结、注释。"
    "10. 最终只能输出改写后的这一段正文，只能输出一段，不得变成列表或多段。"
    "\n\n待改写段落：\n{{paragraph}}"
)


def _render_prompt(template: str | None, paragraph: str) -> str:
    raw_template = str(template or "").strip() or DEFAULT_CNKI_DEDUP_PROMPT_TEMPLATE
    if "{{paragraph}}" in raw_template:
        return raw_template.replace("{{paragraph}}", str(paragraph or "").strip())
    return f"{raw_template}\n\n待改写段落：\n{str(paragraph or '').strip()}"


def build_cnki_dedup_prompt(paragraph: str) -> str:
    return _render_prompt(None, paragraph)


def build_cnki_dedup_prompt_from_template(template: str | None, paragraph: str) -> str:
    return _render_prompt(template, paragraph)
