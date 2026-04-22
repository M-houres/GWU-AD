from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal


Platform = Literal["cnki", "vip"]


CROSS_DOMAIN_PROTECTED_TERM_STRINGS: tuple[str, ...] = (
    "血糖管理",
    "并发症风险",
    "用药依从性",
    "长期随访",
    "临床路径",
    "诊疗规范",
    "公共卫生",
    "行政复议程序",
    "程序合法性",
    "法律适用",
    "证据链完整性",
    "事实认定",
    "现金流风险预警",
    "财务稳健性",
    "并购整合",
    "治理结构",
    "边缘计算",
    "边缘计算架构",
    "任务调度",
    "多传感器协同校准机制",
    "定位稳定性",
    "响应效率",
    "社区记忆",
    "地方志",
    "区域社会韧性",
    "代际传播机制",
    "公共空间实践",
)

DYNAMIC_DOMAIN_TERM_PATTERNS: tuple[str, ...] = (
    r"[\u4e00-\u9fffA-Za-z0-9]{2,20}(?:复议程序|证据链完整性|现金流风险预警|财务稳健性|并购整合|治理结构)",
    r"[\u4e00-\u9fffA-Za-z0-9]{2,20}(?:边缘计算架构|边缘计算|任务调度|多传感器协同校准机制|定位稳定性|响应效率)",
    r"[\u4e00-\u9fffA-Za-z0-9]{2,20}(?:血糖管理|并发症风险|用药依从性|长期随访|临床路径|诊疗规范|公共卫生)",
    r"[\u4e00-\u9fffA-Za-z0-9]{2,20}(?:社区记忆|地方志|区域社会韧性|代际传播机制|公共空间实践)",
)

DOMAIN_TERM_STOP_TOKENS: tuple[str, ...] = (
    "需要",
    "同时",
    "能够",
    "并形成",
    "并兼顾",
    "提升",
    "统筹",
    "保持",
    "展开",
    "分析",
    "研究表明",
    "构建",
)


@dataclass(frozen=True)
class SynonymRule:
    source: str
    targets: tuple[str, ...]
    category: str
    priority: int = 50
    length_delta: int = 0
    risk_level: str = "low"
    protected_if_contains: tuple[str, ...] = ()
    forbidden_contexts: tuple[str, ...] = ()


@dataclass(frozen=True)
class TemplateRule:
    id: str
    pattern: str
    replacement: str
    category: str
    priority: int = 50
    length_delta: int = 0
    risk_level: str = "medium"


@dataclass(frozen=True)
class CohesionRule:
    trigger: tuple[str, ...]
    connector: str
    relation: str
    priority: int = 50


@dataclass(frozen=True)
class ProtectedTerm:
    term: str
    source: str
    level: str = "strong"
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class BadPattern:
    pattern: str
    message: str
    platform: str = "all"
    regex: bool = False


@dataclass(frozen=True)
class PlatformAssets:
    platform: Platform
    synonyms: tuple[SynonymRule, ...] = field(default_factory=tuple)
    templates: tuple[TemplateRule, ...] = field(default_factory=tuple)
    protected_terms: tuple[ProtectedTerm, ...] = field(default_factory=tuple)
    cohesion_rules: tuple[CohesionRule, ...] = field(default_factory=tuple)
    bad_patterns: tuple[BadPattern, ...] = field(default_factory=tuple)


def extract_dynamic_domain_terms(text: str) -> tuple[str, ...]:
    content = str(text or "")
    hits: list[str] = []
    seen: set[str] = set()
    for term in CROSS_DOMAIN_PROTECTED_TERM_STRINGS:
        if term in content and term not in seen:
            hits.append(term)
            seen.add(term)
    for pattern in DYNAMIC_DOMAIN_TERM_PATTERNS:
        for match in re.findall(pattern, content):
            token = str(match or "").strip()
            if len(token) < 3 or token in seen:
                continue
            if any(stop in token for stop in DOMAIN_TERM_STOP_TOKENS):
                continue
            hits.append(token)
            seen.add(token)
    return tuple(sorted(hits, key=len, reverse=True))


COMMON_PROTECTED_TERMS: tuple[ProtectedTerm, ...] = (
    ProtectedTerm("AIGC", "common_abbreviation"),
    ProtectedTerm("AI", "common_abbreviation"),
    ProtectedTerm("STEM", "common_abbreviation"),
    ProtectedTerm("STEAM", "common_abbreviation"),
    ProtectedTerm("PBL", "common_abbreviation"),
    ProtectedTerm("OBE", "common_abbreviation"),
    ProtectedTerm("ChatGPT", "common_abbreviation"),
    ProtectedTerm("核心素养", "education_term"),
    ProtectedTerm("学情诊断", "education_term"),
    ProtectedTerm("跨学科", "education_term"),
    ProtectedTerm("项目化学习", "education_term"),
    ProtectedTerm("大单元教学", "education_term"),
    ProtectedTerm("义务教育课程方案", "policy_term"),
    ProtectedTerm("义务教育课程标准", "policy_term"),
    ProtectedTerm("立德树人", "policy_term"),
    ProtectedTerm("生态文明", "policy_term"),
    *(ProtectedTerm(term, "cross_domain_term") for term in CROSS_DOMAIN_PROTECTED_TERM_STRINGS),
)


CNKI_PROTECTED_TERMS: tuple[ProtectedTerm, ...] = COMMON_PROTECTED_TERMS + (
    ProtectedTerm("可视化", "compound_term"),
    ProtectedTerm("数字化", "compound_term"),
    ProtectedTerm("智能化", "compound_term"),
    ProtectedTerm("信息化", "compound_term"),
    ProtectedTerm("图像化", "compound_term"),
    ProtectedTerm("具象化", "compound_term"),
    ProtectedTerm("常态化", "compound_term"),
    ProtectedTerm("体系化", "compound_term"),
    ProtectedTerm("结构化", "compound_term"),
    ProtectedTerm("生成式人工智能", "technical_term"),
    ProtectedTerm("人工智能", "technical_term"),
    ProtectedTerm("教育数字化", "policy_term"),
)


VIP_PROTECTED_TERMS: tuple[ProtectedTerm, ...] = COMMON_PROTECTED_TERMS + (
    ProtectedTerm("少先队", "education_term"),
    ProtectedTerm("地方红色资源", "education_term"),
    ProtectedTerm("图书管理", "education_term"),
    ProtectedTerm("信息科技", "education_term"),
    ProtectedTerm("渡江战役", "proper_noun"),
    ProtectedTerm("蚌埠", "proper_noun"),
)


COMMON_BAD_PATTERNS: tuple[BadPattern, ...] = (
    BadPattern("进行进行", "重复动词"),
    BadPattern("了了", "重复助词"),
    BadPattern("的的", "重复助词"),
    BadPattern("，，", "重复标点"),
    BadPattern("。。", "重复标点"),
    BadPattern("作为属于", "词级替换拼接异常"),
    BadPattern("蕴含包括", "词级替换拼接异常"),
    BadPattern("融结合", "词级替换拼接异常"),
    BadPattern("将把", "重复处置结构"),
    BadPattern("能够可以", "重复情态词"),
    BadPattern("可以能够", "重复情态词"),
    BadPattern("应当需要", "重复情态词"),
    BadPattern("路径方式", "名词拼接异常"),
    BadPattern("模型式", "名词拼接异常"),
    BadPattern("改变革", "词级替换拼接异常"),
    BadPattern("关键稳定性", "固定搭配异常"),
    BadPattern("关键环节和重要形式", "定义句近义堆叠异常"),
    BadPattern("方面的风险情况", "专业术语被空泛扩写"),
    BadPattern("依从性表现", "医学术语被空泛扩写"),
    BadPattern("跟踪随访安排", "医学术语被空泛扩写"),
    BadPattern("边缘进行计算", "工程术语被拆坏"),
    BadPattern(r"在很多方面进行更加(?:全面|系统|持续|深入)", "空泛扩写堆叠", regex=True),
    BadPattern("[local-mock-llm-refined]", "本地模拟标记泄漏"),
)


CNKI_BAD_PATTERNS: tuple[BadPattern, ...] = (
    BadPattern(r"(可以|能够|能)视化", "复合术语可视化被拆坏", platform="cnki", regex=True),
    BadPattern(r"(可以|能够|能)数字化", "复合术语数字化被拆坏", platform="cnki", regex=True),
    BadPattern(r"(可以|能够|能)智能化", "复合术语智能化被拆坏", platform="cnki", regex=True),
    BadPattern(r"(可以|能够|能)信息化", "复合术语信息化被拆坏", platform="cnki", regex=True),
    BadPattern("这说明其属于", "判断句模板化坏句", platform="cnki"),
    BadPattern("图像表现出", "知网坏样本表达异常", platform="cnki"),
    BadPattern("通用表现出", "知网坏样本表达异常", platform="cnki"),
    BadPattern("表现出层", "知网坏样本表达异常", platform="cnki"),
    BadPattern("至关关键", "知网坏样本搭配异常", platform="cnki"),
    BadPattern("探索与探索", "知网坏样本重复搭配", platform="cnki"),
    BadPattern("达成立德树人", "政策表述搭配异常", platform="cnki"),
    BadPattern("完成生态文明", "政策表述搭配异常", platform="cnki"),
)


CNKI_SYNONYMS: tuple[SynonymRule, ...] = (
    SynonymRule("依托", ("基于", "借助"), "formal_demotion", priority=90),
    SynonymRule("落实", ("推进",), "formal_demotion", priority=82, forbidden_contexts=("立德树人",)),
    SynonymRule("研究表明", ("研究显示", "研究发现"), "academic_softening", priority=84),
    SynonymRule("可以看出", ("据此可见",), "cohesion_softening", priority=76),
    SynonymRule("我们发现", ("研究发现", "本文发现"), "academic_softening", priority=78),
    SynonymRule("非常", ("较为",), "evaluation_demotion", priority=74),
    SynonymRule(
        "重要",
        ("关键",),
        "evaluation_demotion",
        priority=72,
        forbidden_contexts=("重要参考", "重要力量", "重要组成部分", "重要意义", "至关重要"),
    ),
    SynonymRule("很多", ("较多", "不少"), "evaluation_demotion", priority=68),
    SynonymRule("具备", ("具有",), "formal_demotion", priority=60),
    SynonymRule("促进", ("推动",), "formal_demotion", priority=58),
    SynonymRule("揭示", ("说明",), "formal_demotion", priority=52),
)


VIP_SYNONYMS: tuple[SynonymRule, ...] = (
    SynonymRule("蕴含", ("包含",), "term_weakening", priority=88),
    SynonymRule("承载", ("承载着", "承担"), "term_weakening", priority=82),
    SynonymRule("构建", ("建立", "形成"), "term_weakening", priority=86),
    SynonymRule("依赖", ("借助", "依托"), "term_weakening", priority=82),
    SynonymRule("深刻", ("显著",), "evaluation_demotion", priority=80),
    SynonymRule("极高", ("较高",), "evaluation_demotion", priority=78),
    SynonymRule("两张皮", ("脱节",), "colloquial_normalization", priority=90),
    SynonymRule("统摄", ("统领",), "term_weakening", priority=74),
    SynonymRule("贯通", ("打通",), "term_weakening", priority=74),
    SynonymRule("耦合", ("结合",), "term_weakening", priority=72),
    SynonymRule("嵌入", ("融入",), "term_weakening", priority=70),
    SynonymRule("协同", ("协作",), "term_weakening", priority=70),
    SynonymRule("赋能", ("支持",), "term_weakening", priority=70),
    SynonymRule("首先", ("第一",), "sequence_rewrite", priority=64),
    SynonymRule("其次", ("第二",), "sequence_rewrite", priority=64),
    SynonymRule("但是", ("然而",), "cohesion_rewrite", priority=60),
    SynonymRule("开展研究", ("研究",), "nominalization_shift", priority=66),
    SynonymRule("进行分析", ("分析",), "nominalization_shift", priority=66),
    SynonymRule("作出解释", ("解释",), "nominalization_shift", priority=62),
    SynonymRule("实现转化", ("实现转变",), "nominalization_shift", priority=62),
)


CNKI_TEMPLATES: tuple[TemplateRule, ...] = ()


VIP_TEMPLATES: tuple[TemplateRule, ...] = ()


CNKI_COHESION_RULES: tuple[CohesionRule, ...] = ()


VIP_COHESION_RULES: tuple[CohesionRule, ...] = ()


CNKI_ASSETS = PlatformAssets(
    platform="cnki",
    synonyms=CNKI_SYNONYMS,
    templates=CNKI_TEMPLATES,
    protected_terms=CNKI_PROTECTED_TERMS,
    cohesion_rules=CNKI_COHESION_RULES,
    bad_patterns=COMMON_BAD_PATTERNS + CNKI_BAD_PATTERNS,
)


VIP_ASSETS = PlatformAssets(
    platform="vip",
    synonyms=VIP_SYNONYMS,
    templates=VIP_TEMPLATES,
    protected_terms=VIP_PROTECTED_TERMS,
    cohesion_rules=VIP_COHESION_RULES,
    bad_patterns=COMMON_BAD_PATTERNS,
)


def platform_assets(platform: str) -> PlatformAssets:
    key = str(platform or "").strip().lower()
    if key == "vip":
        return VIP_ASSETS
    return CNKI_ASSETS


def protected_terms_for(platform: str) -> tuple[str, ...]:
    return tuple(item.term for item in platform_assets(platform).protected_terms)


def bad_patterns_for(platform: str) -> tuple[BadPattern, ...]:
    return platform_assets(platform).bad_patterns
