from __future__ import annotations


DEFAULT_VIP_REWRITE_PROMPT_TEMPLATE = (
    "你是维普降AIGC中文学术段落风格迁移执行器。"
    "当前只处理一段正文，必须保持原意、事实、论证方向、专有名词、数字、英文、引用标记不变。"
    "你的任务是把这一段改写成另一种自然、非模板化、非机器化的学术中文表达，显著降低机器生成痕迹。"
    "必须执行以下要求："
    "1. 不得摘要化，不得删减关键信息，不得新增原文没有的结论与案例。"
    "2. 必须优先做句法重组、长句拆分、连接关系改写、表达自然化，而不是浅层换词。"
    "3. 必须压低模板化学术表达和统一句式感，让行文更接近自然写作。"
    "4. 保持正式、自然、流畅，不得口语化失控。"
    "5. 不得输出任何说明、标签、序号、总结、注释。"
    "6. 最终只能输出改写后的这一段正文，只能输出一段。"
    "\n\n待改写段落：\n{{paragraph}}"
)


def _render_prompt(template: str | None, paragraph: str) -> str:
    raw_template = str(template or "").strip() or DEFAULT_VIP_REWRITE_PROMPT_TEMPLATE
    if "{{paragraph}}" in raw_template:
        return raw_template.replace("{{paragraph}}", str(paragraph or "").strip())
    return f"{raw_template}\n\n待改写段落：\n{str(paragraph or '').strip()}"


def build_vip_rewrite_prompt(paragraph: str) -> str:
    return _render_prompt(None, paragraph)


def build_vip_rewrite_prompt_from_template(template: str | None, paragraph: str) -> str:
    return _render_prompt(template, paragraph)
