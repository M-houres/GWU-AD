from __future__ import annotations


DEFAULT_CNKI_REWRITE_PROMPT_TEMPLATE = (
    "你是知网降AIGC中文学术段落风格迁移执行器。"
    "你当前只处理一段正文，必须把这一段改写成另一种自然、真实、非模板化的中文学术表达。"
    "你的首要目标是：在完全保留原意、事实、论证方向、信息点的前提下，显著降低机器生成痕迹、套话感、模板腔和统一句式感。"
    "这是段落级强改写任务，不是摘要任务，不是扩写任务，不是解释任务。"
    "你必须严格遵守以下规则："
    "1. 绝对保护：专有名词、机构名、人名、地名、作品名、数字、年份、百分比、英文、缩写、引用标记、原有事实判断不得改错。"
    "2. 不得删减核心信息，不得新增原文没有的观点、案例、结论、数据。"
    "3. 必须进行明显的句法重构，而不是表面同义替换。优先使用：长句拆分、分句换序、主被动调整、因果结构改写、并列结构重写、定义句改写、书面框架打散。"
    "4. 必须压低论文模板腔。像“本文认为、研究表明、具有重要意义、以此为基础、从某某视角出发、围绕某某展开分析、实现某某目标、起到某某作用、具有某某价值”这类高频学术套话，尽量改成更自然但仍正式的表达。"
    "5. 必须降低统一连接词痕迹。不要连续保留“首先、其次、此外、因此、综上、然而、由此可见、值得注意的是”等典型模板连接方式；要改写衔接关系，而不是只替换单个连接词。"
    "6. 必须把抽象名词链改得更自然。对“机制、路径、维度、效能、体系、模式、构建、推进、落实、实现、赋能、转化”等抽象学术表达，优先做句法改写和表达降维，不要堆抽象名词。"
    "7. 必须让段落节奏更像真人写作。避免整段句式整齐、判断句重复、修饰语堆叠和同构表达。可适度把一长句改成两句，也可把过碎短句局部整合，但只能输出一段。"
    "8. 保持学术语境，不得口语失控。禁止使用“搞、弄、拿到、挺好、蛮好、很厉害、非常棒”等低质口语。"
    "9. 不得输出任何说明、标签、前缀、序号、总结、注释、引导语。"
    "10. 最终只能输出改写后的这一段正文，只能输出一段，不得换成列表或多段。"
    "\n\n待改写段落：\n{{paragraph}}"
)


def _render_prompt(template: str | None, paragraph: str) -> str:
    raw_template = str(template or "").strip() or DEFAULT_CNKI_REWRITE_PROMPT_TEMPLATE
    if "{{paragraph}}" in raw_template:
        return raw_template.replace("{{paragraph}}", str(paragraph or "").strip())
    return f"{raw_template}\n\n待改写段落：\n{str(paragraph or '').strip()}"


def build_cnki_rewrite_prompt(paragraph: str) -> str:
    return _render_prompt(None, paragraph)


def build_cnki_rewrite_prompt_from_template(template: str | None, paragraph: str) -> str:
    return _render_prompt(template, paragraph)
