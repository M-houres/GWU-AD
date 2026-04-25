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
    layer: str = "L2"
    quality_tier: str = "A"


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
    active_quality_tiers: tuple[str, ...] = ("S", "A")
    layer_change_limits: tuple[tuple[str, int], ...] = ()
    chunk_min_chars: int = 180
    chunk_max_chars: int = 260
    chunk_max_changes: int = 6


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

VIP_WP2_ALLOWED_BAD_PATTERN_STRINGS: frozenset[str] = frozenset(
    {
        "作为属于",
        "将把",
        "能够可以",
        "可以能够",
        "路径方式",
        "改变革",
    }
)

VIP_COMMON_BAD_PATTERNS: tuple[BadPattern, ...] = tuple(
    item for item in COMMON_BAD_PATTERNS if item.pattern not in VIP_WP2_ALLOWED_BAD_PATTERN_STRINGS
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


CNKI_RULE_LAYER_QUOTAS: dict[str, int] = {
    "L1": 180,
    "L2": 420,
    "L3": 280,
    "L5": 120,
}

CNKI_ACTIVE_LAYER_QUOTAS: dict[str, int] = {
    "L1": 70,
    "L2": 150,
    "L3": 95,
    "L5": 45,
}

_CNKI_L1_SEEDS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("然而", ("不过", "但", "可是"), "connector_shift"),
    ("但是", ("然而", "不过", "可是"), "connector_shift"),
    ("尽管", ("虽然", "即便", "虽说"), "connector_shift"),
    ("虽然", ("尽管", "虽说", "即便"), "connector_shift"),
    ("此外", ("除此之外", "另外", "与此同时"), "connector_shift"),
    ("与此同时", ("同时", "并且", "同一时间"), "connector_shift"),
    ("因此", ("从而", "由此", "为此"), "causal_shift"),
    ("从而", ("进而", "因此", "由此"), "causal_shift"),
    ("即便", ("就算", "虽然", "哪怕"), "connector_shift"),
    ("哪怕", ("即便", "就算", "纵然"), "connector_shift"),
    ("基于此", ("有鉴于此", "为此", "据此"), "causal_shift"),
    ("鉴于此", ("基于此", "有鉴于此", "据此"), "causal_shift"),
    ("为此", ("基于此", "鉴于此", "因此"), "causal_shift"),
    ("不仅", ("不单", "不只", "不光"), "parallel_shift"),
    ("而且", ("并且", "同时", "还"), "parallel_shift"),
    ("不仅如此", ("除此外", "不止于此", "除此之外"), "parallel_shift"),
    ("首先", ("第一", "其一", "一是"), "sequence_shift"),
    ("其次", ("第二", "其二", "二是"), "sequence_shift"),
    ("再次", ("第三", "其三", "三是"), "sequence_shift"),
    ("最后", ("最终", "最终来看", "其四"), "sequence_shift"),
    ("然后", ("随后", "继而", "接着"), "sequence_shift"),
    ("总体", ("整体", "综合来看", "总体而言"), "summary_shift"),
    ("综上", ("总的来看", "整体而言", "综上所述"), "summary_shift"),
    ("由于", ("因为", "鉴于", "考虑到"), "causal_shift"),
    ("对此", ("针对此", "就此", "围绕这一点"), "topic_shift"),
    ("同时", ("与此同时", "并且", "而且"), "connector_shift"),
    ("并且", ("同时", "而且", "还"), "connector_shift"),
    ("进而", ("从而", "进一步", "继而"), "causal_shift"),
    ("于是", ("因此", "从而", "随后"), "causal_shift"),
    ("另外", ("此外", "除此之外", "同时"), "connector_shift"),
    ("总之", ("总的来说", "综合而言", "总体上"), "summary_shift"),
    ("换言之", ("也就是说", "即", "换句话说"), "summary_shift"),
    ("具体来说", ("具体而言", "具体地", "细化来看"), "topic_shift"),
    ("总的来说", ("总体而言", "综上所述", "总体上看"), "summary_shift"),
    ("正因如此", ("有鉴于此", "正是因此", "因此"), "causal_shift"),
    ("事实上", ("实际上", "实际情况是", "客观上看"), "topic_shift"),
    ("可见", ("由此可见", "据此可见", "由此看来"), "summary_shift"),
    ("另一方面", ("另一层面上", "从另一角度看", "与此同时"), "parallel_shift"),
    ("相较之下", ("相比之下", "比较而言", "对照来看"), "topic_shift"),
    ("在此基础上", ("基于这一点", "据此", "由此进一步"), "causal_shift"),
    ("相应地", ("对应地", "由此", "因此"), "connector_shift"),
    ("进一步看", ("继续来看", "从这一点看", "进一步而言"), "connector_shift"),
    ("进一步而言", ("进一步看", "继续来看", "从这一角度看"), "connector_shift"),
    ("总体来看", ("从整体看", "综合来看", "整体而言"), "summary_shift"),
    ("由此可见", ("据此可见", "由此看来", "可见"), "summary_shift"),
    ("据此可见", ("由此可见", "由此看来", "可见"), "summary_shift"),
    ("归根结底", ("从根本上看", "归结起来", "总体上看"), "summary_shift"),
    ("值得注意的是", ("需要注意的是", "应当注意的是", "需强调的是"), "topic_shift"),
    ("需要说明的是", ("有必要说明的是", "需指出的是", "应当说明的是"), "topic_shift"),
    ("与此同时还", ("同时还", "并且还", "另外还"), "parallel_shift"),
    ("由此看来", ("由此可见", "据此可见", "可见"), "summary_shift"),
    ("在这种情况下", ("在此情形下", "在这一背景下", "在该情境下"), "topic_shift"),
    ("在此情形下", ("在这种情况下", "在这一背景下", "在该条件下"), "topic_shift"),
    ("就此而言", ("从这一点看", "围绕这一点", "由此来看"), "topic_shift"),
    ("从这一角度看", ("从这一点看", "由此来看", "就此而言"), "topic_shift"),
    ("从这一点看", ("从这一角度看", "由此来看", "就此而言"), "topic_shift"),
    ("由此进一步", ("在此基础上", "进而", "进一步而言"), "causal_shift"),
    ("围绕这一点", ("就此", "针对此", "从这一点看"), "topic_shift"),
    ("综合而言", ("总体而言", "总的来看", "综合来看"), "summary_shift"),
)

_CNKI_L2_SEEDS: tuple[tuple[str, tuple[str, ...], str, tuple[str, ...]], ...] = (
    ("推动", ("促进", "促使", "带动"), "verb_shift", ()),
    ("促进", ("推动", "推进", "加快"), "verb_shift", ()),
    ("提升", ("提高", "增强", "改善"), "verb_shift", ()),
    ("提高", ("提升", "增强", "改善"), "verb_shift", ()),
    ("降低", ("减少", "减弱", "削减"), "verb_shift", ()),
    ("减少", ("降低", "减弱", "压缩"), "verb_shift", ()),
    ("缺乏", ("欠缺", "不足", "缺少"), "verb_shift", ()),
    ("欠缺", ("缺乏", "不足", "缺少"), "verb_shift", ()),
    ("构建", ("建立", "搭建", "形成"), "verb_shift", ()),
    ("建立", ("构建", "搭建", "创建"), "verb_shift", ()),
    ("完善", ("健全", "优化", "改进"), "verb_shift", ()),
    ("优化", ("改进", "完善", "提升"), "verb_shift", ()),
    ("改进", ("优化", "完善", "提升"), "verb_shift", ()),
    ("实现", ("达成", "完成", "取得"), "verb_shift", ()),
    ("达成", ("实现", "完成", "获取"), "verb_shift", ()),
    ("建设", ("打造", "建立", "发展"), "verb_shift", ()),
    ("打造", ("建设", "建立", "创建"), "verb_shift", ()),
    ("开展", ("进行", "推行", "实施"), "verb_shift", ()),
    ("推行", ("实施", "落实", "执行"), "verb_shift", ()),
    ("推进", ("深化", "加快", "推动"), "verb_shift", ()),
    ("认为", ("指出", "认识到", "觉得"), "verb_shift", ()),
    ("指出", ("强调", "表明", "提出"), "verb_shift", ()),
    ("强调", ("指出", "表明", "着重指出"), "verb_shift", ()),
    ("表明", ("显示", "说明", "揭示"), "verb_shift", ()),
    ("揭示", ("表明", "显示", "说明"), "verb_shift", ()),
    ("分析", ("考察", "研究", "探究"), "verb_shift", ()),
    ("探讨", ("研究", "考察", "分析"), "verb_shift", ()),
    ("研究", ("探讨", "考察", "分析"), "verb_shift", ("本研究", "该研究", "本文研究", "研究表明")),
    ("影响", ("作用于", "制约", "干预"), "verb_shift", ()),
    ("制约", ("限制", "阻碍", "影响"), "verb_shift", ()),
    ("限制", ("制约", "阻碍", "约束"), "verb_shift", ()),
    ("依赖", ("依靠", "借助", "凭借"), "verb_shift", ()),
    ("依靠", ("依赖", "借助", "凭借"), "verb_shift", ()),
    ("导致", ("造成", "引发", "使得"), "verb_shift", ()),
    ("造成", ("导致", "引发", "带来"), "verb_shift", ()),
    ("引发", ("导致", "造成", "引起"), "verb_shift", ()),
    ("获得", ("取得", "得到", "获取"), "verb_shift", ()),
    ("取得", ("获得", "得到", "获取"), "verb_shift", ()),
    ("聚焦", ("关注", "围绕", "专注"), "verb_shift", ()),
    ("关注", ("聚焦", "重视", "注重"), "verb_shift", ()),
    ("体现", ("反映", "呈现", "表现"), "verb_shift", ()),
    ("涵盖", ("包括", "涉及", "包含"), "verb_shift", ()),
    ("涉及", ("涵盖", "包含", "覆盖"), "verb_shift", ()),
    ("引入", ("引进", "纳入", "融入"), "verb_shift", ()),
    ("纳入", ("引入", "加入", "并入"), "verb_shift", ()),
    ("明确", ("厘清", "确立", "界定"), "verb_shift", ()),
    ("确立", ("明确", "建立", "确定"), "verb_shift", ()),
    ("保障", ("确保", "保证", "维护"), "verb_shift", ()),
    ("整合", ("融合", "协同", "统筹"), "verb_shift", ()),
    ("形成", ("产生", "构成", "发展为"), "verb_shift", ()),
    ("凸显", ("彰显", "突出", "体现"), "verb_shift", ()),
    ("兼顾", ("统筹", "平衡", "综合"), "verb_shift", ()),
    ("落实", ("执行", "贯彻", "推进"), "verb_shift", ("立德树人",)),
    ("提出", ("给出", "提供", "拿出"), "verb_shift", ()),
    ("扩大", ("拓展", "增加", "延伸"), "verb_shift", ()),
    ("加强", ("强化", "增强", "深化"), "verb_shift", ()),
    ("解决", ("处理", "化解", "应对"), "verb_shift", ()),
    ("探索", ("寻找", "尝试", "摸索"), "verb_shift", ()),
    ("遵循", ("按照", "依据", "秉承"), "verb_shift", ()),
    ("应对", ("处理", "回应", "解决"), "verb_shift", ()),
    ("阐释", ("解释", "说明", "论述"), "verb_shift", ()),
    ("归纳", ("总结", "概括", "提炼"), "verb_shift", ()),
    ("检验", ("验证", "核验", "测验"), "verb_shift", ()),
    ("比较", ("对比", "比照", "参照"), "verb_shift", ()),
    ("识别", ("辨识", "判别", "甄别"), "verb_shift", ()),
    ("评估", ("评价", "测评", "评判"), "verb_shift", ()),
    ("拓宽", ("拓展", "扩大", "延展"), "verb_shift", ()),
    ("衔接", ("连接", "贯通", "联结"), "verb_shift", ()),
    ("协同", ("协作", "配合", "联动"), "verb_shift", ()),
    ("强化", ("加强", "增强", "加固"), "verb_shift", ()),
)

_CNKI_L3_SEEDS: tuple[tuple[str, tuple[str, ...], str] | tuple[str, tuple[str, ...], str, tuple[str, ...]], ...] = (
    ("层面", ("方面", "维度", "领域"), "noun_shift", ("从理论层面", "理论层面", "实践层面", "就实践层面而言")),
    ("方面", ("层面", "维度", "角度"), "noun_shift"),
    ("维度", ("方面", "层面", "角度"), "noun_shift"),
    ("路径", ("途径", "方式", "方向"), "noun_shift"),
    ("途径", ("路径", "方式", "方向"), "noun_shift"),
    ("体系", ("框架", "模式", "系统"), "noun_shift"),
    ("框架", ("体系", "模式", "结构"), "noun_shift"),
    ("模式", ("方式", "体系", "方法"), "noun_shift"),
    ("机制", ("制度", "方式", "模式"), "noun_shift"),
    ("制度", ("机制", "规范", "体系"), "noun_shift"),
    ("策略", ("方案", "办法", "举措"), "noun_shift"),
    ("举措", ("措施", "做法", "行动"), "noun_shift"),
    ("措施", ("举措", "方案", "做法"), "noun_shift"),
    ("困境", ("难题", "挑战", "难点"), "noun_shift"),
    ("难题", ("困境", "挑战", "问题"), "noun_shift"),
    ("挑战", ("困境", "难题", "难点"), "noun_shift"),
    ("现状", ("情况", "状况", "实际"), "noun_shift"),
    ("状况", ("现状", "情况", "实际"), "noun_shift"),
    ("效果", ("成效", "结果", "成果"), "noun_shift"),
    ("成效", ("效果", "结果", "成果"), "noun_shift"),
    ("理念", ("观念", "思路", "思想"), "noun_shift"),
    ("观念", ("理念", "思想", "认识"), "noun_shift"),
    ("基础", ("根基", "前提", "基石"), "noun_shift"),
    ("根基", ("基础", "基石", "前提"), "noun_shift"),
    ("目标", ("方向", "目的", "宗旨"), "noun_shift"),
    ("目的", ("目标", "宗旨", "方向"), "noun_shift"),
    ("资源", ("条件", "要素", "支撑"), "noun_shift"),
    ("条件", ("资源", "要素", "基础"), "noun_shift"),
    ("平台", ("载体", "渠道", "空间"), "noun_shift"),
    ("载体", ("平台", "媒介", "渠道"), "noun_shift"),
    ("前提", ("基础", "条件", "先决条件"), "noun_shift"),
    ("特征", ("特点", "特性", "属性"), "noun_shift"),
    ("属性", ("特性", "性质", "特征"), "noun_shift"),
    ("优势", ("长处", "特点", "强项"), "noun_shift"),
    ("价值", ("意义", "作用", "功能"), "noun_shift"),
    ("能力", ("水平", "素养", "实力"), "noun_shift"),
    ("作用", ("功能", "价值", "意义"), "noun_shift"),
    ("领域", ("范畴", "行业", "方向"), "noun_shift"),
    ("结构", ("组织", "架构", "体系"), "noun_shift"),
    ("功能", ("作用", "价值", "用途"), "noun_shift"),
    ("方向", ("路径", "目标", "定向"), "noun_shift"),
    ("重点", ("核心", "关键", "焦点"), "noun_shift"),
    ("成果", ("结果", "产出", "效果"), "noun_shift"),
    ("背景", ("情境", "环境", "语境"), "noun_shift"),
    ("需求", ("需要", "要求", "诉求"), "noun_shift"),
    ("保障", ("支撑", "支持", "托底"), "noun_shift"),
    ("内容", ("要素", "方面", "组成"), "noun_shift"),
    ("核心", ("关键", "重点", "中心"), "noun_shift"),
    ("关键", ("核心", "重点", "要点"), "noun_shift"),
    ("语境", ("情境", "背景", "场域"), "noun_shift"),
    ("场景", ("情境", "场域", "环境"), "noun_shift"),
    ("范式", ("模式", "路径", "框架"), "noun_shift"),
    ("链路", ("路径", "流程", "环节"), "noun_shift"),
    ("环节", ("步骤", "流程", "节点"), "noun_shift"),
    ("节点", ("环节", "关键点", "节点位"), "noun_shift"),
    ("流程", ("链路", "路径", "步骤"), "noun_shift"),
    ("范畴", ("领域", "范围", "方向"), "noun_shift"),
    ("语料", ("文本材料", "材料", "样本"), "noun_shift"),
)

_CNKI_L5_SEEDS: tuple[tuple[str, tuple[str, ...], str, tuple[str, ...]], ...] = (
    ("有效", ("切实", "积极", "充分"), "degree_shift", ()),
    ("进一步", ("持续", "不断", "更加"), "degree_shift", ()),
    ("系统", ("全面", "整体", "综合"), "degree_shift", ("系统工程", "系统架构")),
    ("深入", ("细致", "充分", "全面"), "degree_shift", ()),
    ("普遍", ("广泛", "常见", "大量"), "degree_shift", ()),
    ("重要", ("关键", "核心", "必要"), "degree_shift", ("重要参考", "重要组成部分", "至关重要")),
    ("充分", ("充足", "足够", "完全"), "degree_shift", ()),
    ("广泛", ("大量", "多方面", "全面"), "degree_shift", ()),
    ("持续", ("不断", "长期", "稳定"), "degree_shift", ()),
    ("积极", ("主动", "努力", "切实"), "degree_shift", ()),
    ("严重", ("突出", "显著", "明显"), "degree_shift", ()),
    ("显著", ("明显", "突出", "明确"), "degree_shift", ()),
    ("全面", ("系统", "整体", "综合"), "degree_shift", ("全面建设",)),
    ("合理", ("科学", "恰当", "适当"), "degree_shift", ()),
    ("明显", ("显著", "突出", "清晰"), "degree_shift", ()),
    ("必要", ("重要", "关键", "不可或缺"), "degree_shift", ()),
    ("根本", ("核心", "关键", "本质"), "degree_shift", ()),
    ("实质", ("本质", "核心", "根本"), "degree_shift", ()),
    ("客观", ("实际", "真实", "公正"), "degree_shift", ()),
    ("直接", ("直观", "明确", "即时"), "degree_shift", ()),
    ("及时", ("迅速", "快速", "尽快"), "degree_shift", ()),
    ("真实", ("实际", "客观", "准确"), "degree_shift", ()),
    ("整体", ("全面", "系统", "综合"), "degree_shift", ()),
    ("不断", ("持续", "持续不断", "逐步"), "degree_shift", ()),
)

_CNKI_LAYER_WRAPPERS: dict[str, tuple[tuple[str, str], ...]] = {
    "L1": (("", ""),),
    "L2": (("", ""), ("持续", ""), ("进一步", "")),
    "L3": (("", ""), ("整体", ""), ("核心", "")),
    "L5": (("", ""), ("较为", ""), ("相对", "")),
}


def _tier_by_index(index: int, *, active_quota: int) -> str:
    if index < active_quota:
        return "S" if index % 3 == 0 else "A"
    return "B" if index % 2 == 0 else "C"


def _priority_by_layer(layer: str, *, wrapper_level: int, offset: int) -> int:
    base = {"L1": 96, "L2": 88, "L3": 76, "L5": 64}.get(layer, 60)
    return max(1, base - wrapper_level * 10 - (offset % 12))


def _build_cnki_layer_rules(
    *,
    layer: str,
    quota: int,
    active_quota: int,
    wrappers: tuple[tuple[str, str], ...],
    seeds: tuple[tuple[str, tuple[str, ...], str], ...] | tuple[tuple[str, tuple[str, ...], str, tuple[str, ...]], ...],
) -> tuple[SynonymRule, ...]:
    generated: list[SynonymRule] = []
    seen: set[tuple[str, str]] = set()
    for wrapper_level, (prefix, suffix) in enumerate(wrappers):
        for seed_index, seed in enumerate(seeds):
            if len(seed) == 4:
                source, targets, category, forbidden_contexts = seed  # type: ignore[misc]
            else:
                source, targets, category = seed  # type: ignore[misc]
                forbidden_contexts = ()
            for target in targets:
                wrapped_source = f"{prefix}{source}{suffix}"
                wrapped_target = f"{prefix}{target}{suffix}"
                if layer == "L1":
                    wrapped_source = source
                    wrapped_target = target
                key = (wrapped_source, wrapped_target)
                if wrapped_source == wrapped_target or key in seen:
                    continue
                seen.add(key)
                generated.append(
                    SynonymRule(
                        source=wrapped_source,
                        targets=(wrapped_target,),
                        category=category,
                        priority=_priority_by_layer(layer, wrapper_level=wrapper_level, offset=seed_index),
                        risk_level="low" if layer in {"L1", "L2"} else "medium",
                        forbidden_contexts=tuple(forbidden_contexts),
                        layer=layer,
                        quality_tier="C",
                    )
                )
                if len(generated) >= quota:
                    break
            if len(generated) >= quota:
                break
        if len(generated) >= quota:
            break

    if len(generated) < quota:
        # 兜底补齐规则位，保持可扩展空间；默认为低质量灰度规则，不参与默认触发。
        filler_index = 0
        while len(generated) < quota:
            filler_index += 1
            generated.append(
                SynonymRule(
                    source=f"扩展占位词{layer}{filler_index}",
                    targets=(f"扩展占位替换{layer}{filler_index}",),
                    category="reserved_pool",
                    priority=1,
                    risk_level="high",
                    layer=layer,
                    quality_tier="C",
                )
            )

    finalized: list[SynonymRule] = []
    for index, item in enumerate(generated[:quota]):
        finalized.append(
            SynonymRule(
                source=item.source,
                targets=item.targets,
                category=item.category,
                priority=item.priority,
                length_delta=item.length_delta,
                risk_level=item.risk_level,
                protected_if_contains=item.protected_if_contains,
                forbidden_contexts=item.forbidden_contexts,
                layer=item.layer,
                quality_tier=_tier_by_index(index, active_quota=active_quota),
            )
        )
    return tuple(finalized)


def _build_cnki_synonym_rules() -> tuple[SynonymRule, ...]:
    l1 = _build_cnki_layer_rules(
        layer="L1",
        quota=CNKI_RULE_LAYER_QUOTAS["L1"],
        active_quota=CNKI_ACTIVE_LAYER_QUOTAS["L1"],
        wrappers=_CNKI_LAYER_WRAPPERS["L1"],
        seeds=_CNKI_L1_SEEDS,
    )
    l2 = _build_cnki_layer_rules(
        layer="L2",
        quota=CNKI_RULE_LAYER_QUOTAS["L2"],
        active_quota=CNKI_ACTIVE_LAYER_QUOTAS["L2"],
        wrappers=_CNKI_LAYER_WRAPPERS["L2"],
        seeds=_CNKI_L2_SEEDS,
    )
    l3 = _build_cnki_layer_rules(
        layer="L3",
        quota=CNKI_RULE_LAYER_QUOTAS["L3"],
        active_quota=CNKI_ACTIVE_LAYER_QUOTAS["L3"],
        wrappers=_CNKI_LAYER_WRAPPERS["L3"],
        seeds=_CNKI_L3_SEEDS,
    )
    l5 = _build_cnki_layer_rules(
        layer="L5",
        quota=CNKI_RULE_LAYER_QUOTAS["L5"],
        active_quota=CNKI_ACTIVE_LAYER_QUOTAS["L5"],
        wrappers=_CNKI_LAYER_WRAPPERS["L5"],
        seeds=_CNKI_L5_SEEDS,
    )
    return tuple([*l1, *l2, *l3, *l5])


CNKI_SYNONYMS: tuple[SynonymRule, ...] = _build_cnki_synonym_rules()


VIP_SYNONYMS: tuple[SynonymRule, ...] = (
    SynonymRule("蕴含", ("包含",), "term_weakening", priority=88, layer="L2", quality_tier="A"),
    SynonymRule("承载", ("承载着", "承担"), "term_weakening", priority=82, layer="L2", quality_tier="A"),
    SynonymRule("构建", ("建立", "形成"), "term_weakening", priority=86, layer="L2", quality_tier="A"),
    SynonymRule("依赖", ("借助", "依托"), "term_weakening", priority=82, layer="L2", quality_tier="A"),
    SynonymRule("深刻", ("显著",), "evaluation_demotion", priority=80, layer="L5", quality_tier="A"),
    SynonymRule("极高", ("较高",), "evaluation_demotion", priority=78, layer="L5", quality_tier="A"),
    SynonymRule("两张皮", ("脱节",), "colloquial_normalization", priority=90, layer="L3", quality_tier="S"),
    SynonymRule("统摄", ("统领",), "term_weakening", priority=74, layer="L2", quality_tier="A"),
    SynonymRule("贯通", ("打通",), "term_weakening", priority=74, layer="L2", quality_tier="A"),
    SynonymRule("耦合", ("结合",), "term_weakening", priority=72, layer="L2", quality_tier="A"),
    SynonymRule("嵌入", ("融入",), "term_weakening", priority=70, layer="L2", quality_tier="A"),
    SynonymRule("协同", ("协作",), "term_weakening", priority=70, layer="L2", quality_tier="A"),
    SynonymRule("赋能", ("支持",), "term_weakening", priority=70, layer="L2", quality_tier="A"),
    SynonymRule("首先", ("第一",), "sequence_rewrite", priority=64, layer="L1", quality_tier="A"),
    SynonymRule("其次", ("第二",), "sequence_rewrite", priority=64, layer="L1", quality_tier="A"),
    SynonymRule("但是", ("然而",), "cohesion_rewrite", priority=60, layer="L1", quality_tier="A"),
    SynonymRule("开展研究", ("研究",), "nominalization_shift", priority=66, layer="L2", quality_tier="A"),
    SynonymRule("进行分析", ("分析",), "nominalization_shift", priority=66, layer="L2", quality_tier="A"),
    SynonymRule("作出解释", ("解释",), "nominalization_shift", priority=62, layer="L2", quality_tier="A"),
    SynonymRule("实现转化", ("实现转变",), "nominalization_shift", priority=62, layer="L2", quality_tier="A"),
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
    active_quality_tiers=("S", "A"),
    layer_change_limits=(("L1", 2), ("L2", 2), ("L3", 1), ("L5", 1)),
    chunk_min_chars=180,
    chunk_max_chars=260,
    chunk_max_changes=6,
)


VIP_ASSETS = PlatformAssets(
    platform="vip",
    synonyms=VIP_SYNONYMS,
    templates=VIP_TEMPLATES,
    protected_terms=VIP_PROTECTED_TERMS,
    cohesion_rules=VIP_COHESION_RULES,
    bad_patterns=VIP_COMMON_BAD_PATTERNS,
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
