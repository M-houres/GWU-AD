from __future__ import annotations

from app.services.rewrite_strategies.assets import (
    BadPattern,
    CohesionRule,
    PlatformAssets,
    ProtectedTerm,
    SynonymRule,
    TemplateRule,
    COMMON_BAD_PATTERNS,
    COMMON_PROTECTED_TERMS,
)


CNKI_DEDUP_PROTECTED_TERMS: tuple[ProtectedTerm, ...] = COMMON_PROTECTED_TERMS + (
    ProtectedTerm("可视化", "compound_term"),
    ProtectedTerm("数字化", "compound_term"),
    ProtectedTerm("智能化", "compound_term"),
    ProtectedTerm("信息化", "compound_term"),
    ProtectedTerm("生成式人工智能", "technical_term"),
    ProtectedTerm("教育数字化", "policy_term"),
)

VIP_DEDUP_PROTECTED_TERMS: tuple[ProtectedTerm, ...] = COMMON_PROTECTED_TERMS + (
    ProtectedTerm("少先队", "education_term"),
    ProtectedTerm("地方红色资源", "education_term"),
    ProtectedTerm("图书管理", "education_term"),
    ProtectedTerm("信息科技", "education_term"),
    ProtectedTerm("渡江战役", "proper_noun"),
    ProtectedTerm("蚌埠", "proper_noun"),
)

CNKI_DEDUP_SYNONYMS: tuple[SynonymRule, ...] = (
    SynonymRule("依托", ("借助", "依靠"), "cnki_stable_synonym", priority=90),
    SynonymRule("研究表明", ("相关研究显示", "已有研究指出"), "cnki_intro_rewrite", priority=88),
    SynonymRule("可以看出", ("据此可见", "由此能够看出"), "cnki_connector_rewrite", priority=86),
    SynonymRule("因此", ("据此可见", "所以"), "cnki_connector_rewrite", priority=82),
    SynonymRule("但是", ("然而", "不过"), "cnki_connector_rewrite", priority=80),
    SynonymRule("首先", ("第一", "一方面"), "cnki_sequence_rewrite", priority=78),
    SynonymRule("其次", ("第二", "另一方面"), "cnki_sequence_rewrite", priority=76),
    SynonymRule(
        "重要",
        ("关键", "较为重要"),
        "cnki_evaluation_rewrite",
        priority=70,
        forbidden_contexts=("重要参考", "重要力量", "重要组成部分", "重要意义", "至关重要"),
    ),
    SynonymRule("很多", ("较多", "大量"), "cnki_evaluation_rewrite", priority=68),
    SynonymRule("促进", ("推动", "带动"), "cnki_verb_rewrite", priority=66),
)

VIP_DEDUP_SYNONYMS: tuple[SynonymRule, ...] = (
    SynonymRule("构建", ("建立", "形成"), "vip_term_shift", priority=90),
    SynonymRule("依赖", ("借助", "依托"), "vip_term_shift", priority=88),
    SynonymRule("协同", ("协作",), "vip_term_shift", priority=86),
    SynonymRule("赋能", ("支持",), "vip_term_shift", priority=84),
    SynonymRule("首先", ("第一",), "vip_sequence_rewrite", priority=82),
    SynonymRule("其次", ("第二",), "vip_sequence_rewrite", priority=80),
    SynonymRule("但是", ("然而",), "vip_connector_rewrite", priority=76),
    SynonymRule("进行分析", ("分析",), "vip_nominalization", priority=74),
    SynonymRule("开展研究", ("研究",), "vip_nominalization", priority=72),
)

CNKI_DEDUP_TEMPLATES: tuple[TemplateRule, ...] = (
    TemplateRule(
        "cnki_dedup_through_to_by",
        r"通过([^。！？；;，,]{2,24})，([^。！？；;]{6,48})",
        r"借助\1这一方式，\2",
        "cnki_light_sentence_rewrite",
        priority=86,
    ),
)

VIP_DEDUP_TEMPLATES: tuple[TemplateRule, ...] = ()

CNKI_DEDUP_COHESION_RULES: tuple[CohesionRule, ...] = ()

VIP_DEDUP_COHESION_RULES: tuple[CohesionRule, ...] = ()

CNKI_DEDUP_BAD_PATTERNS: tuple[BadPattern, ...] = (
    BadPattern(r"(可以|能够|能)视化", "复合术语可视化被拆坏", platform="cnki", regex=True),
    BadPattern(r"(可以|能够|能)数字化", "复合术语数字化被拆坏", platform="cnki", regex=True),
    BadPattern(r"(可以|能够|能)智能化", "复合术语智能化被拆坏", platform="cnki", regex=True),
    BadPattern(r"(可以|能够|能)信息化", "复合术语信息化被拆坏", platform="cnki", regex=True),
    BadPattern("这说明其属于", "判断句模板化坏句", platform="cnki"),
    BadPattern("至关关键", "知网降重搭配异常", platform="cnki"),
    BadPattern("探索与探索", "知网降重重复搭配", platform="cnki"),
)

CNKI_DEDUP_ASSETS = PlatformAssets(
    platform="cnki",
    synonyms=CNKI_DEDUP_SYNONYMS,
    templates=CNKI_DEDUP_TEMPLATES,
    protected_terms=CNKI_DEDUP_PROTECTED_TERMS,
    cohesion_rules=CNKI_DEDUP_COHESION_RULES,
    bad_patterns=COMMON_BAD_PATTERNS + CNKI_DEDUP_BAD_PATTERNS,
)

VIP_DEDUP_ASSETS = PlatformAssets(
    platform="vip",
    synonyms=VIP_DEDUP_SYNONYMS,
    templates=VIP_DEDUP_TEMPLATES,
    protected_terms=VIP_DEDUP_PROTECTED_TERMS,
    cohesion_rules=VIP_DEDUP_COHESION_RULES,
    bad_patterns=COMMON_BAD_PATTERNS,
)


def dedup_assets(platform: str) -> PlatformAssets:
    key = str(platform or "").strip().lower()
    if key == "vip":
        return VIP_DEDUP_ASSETS
    return CNKI_DEDUP_ASSETS
