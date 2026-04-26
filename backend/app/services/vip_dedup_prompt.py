from __future__ import annotations


DEFAULT_VIP_DEDUP_PROMPT_TEMPLATE = (
    "你是维普降重复中文学术段落深度重述执行器。"
    "当前只处理一段正文，必须保持原意、事实、论证方向、结论、专有名词、数字、英文、引用标记不变。"
    "你的任务是在内容等值的前提下，显著拉开这一段与原文在词面、句法、表达路径和行文组织上的差异。"
    "必须执行以下要求："
    "1. 不得删减主体信息，不得摘要化，不得新增原文没有的观点与数据。"
    "2. 必须优先做深层结构改写，包括句式重构、顺序改写、因果链改写、并列结构改写、定义表达重述。"
    "3. 不要保留原句骨架，不要停留在表面同义替换。"
    "4. 保持中文自然、正式、通顺，避免机械感、拼接感和无效废话。"
    "5. 不得输出任何说明、标签、序号、总结、注释。"
    "6. 最终只能输出改写后的这一段正文，只能输出一段。"
    "\n\n待改写段落：\n{{paragraph}}"
)


def _render_prompt(template: str | None, paragraph: str) -> str:
    raw_template = str(template or "").strip() or DEFAULT_VIP_DEDUP_PROMPT_TEMPLATE
    if "{{paragraph}}" in raw_template:
        return raw_template.replace("{{paragraph}}", str(paragraph or "").strip())
    return f"{raw_template}\n\n待改写段落：\n{str(paragraph or '').strip()}"


def build_vip_dedup_prompt(paragraph: str) -> str:
    return _render_prompt(None, paragraph)


def build_vip_dedup_prompt_from_template(template: str | None, paragraph: str) -> str:
    return _render_prompt(template, paragraph)
