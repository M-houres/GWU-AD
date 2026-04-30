from __future__ import annotations

import math
import re
import statistics
from dataclasses import dataclass
from typing import Any

from app.utils import count_billable_chars


AI_VERBS = {
    "赋能",
    "激活",
    "构建",
    "打造",
    "助力",
    "聚焦",
    "深化",
    "优化",
    "拓展",
    "提升",
    "培育",
    "营造",
    "催生",
    "孕育",
    "跃迁",
    "重塑",
    "重构",
    "革新",
    "迭代",
    "渗透",
    "彰显",
    "凸显",
    "驱动",
    "引领",
    "锚定",
    "承载",
    "回应",
    "推动",
    "促进",
    "实现",
    "完善",
    "加强",
    "强化",
    "推进",
    "落实",
    "健全",
}

AI_NOUNS = {
    "机理",
    "路径",
    "范式",
    "态势",
    "维度",
    "格局",
    "生态",
    "场域",
    "旨归",
    "内核",
    "内涵",
    "外延",
    "表征",
    "样态",
    "图景",
    "底色",
    "肌理",
    "脉络",
    "意涵",
    "语境",
    "谱系",
    "动能",
    "势能",
    "韧性",
    "耦合",
    "机制",
    "体系",
    "逻辑",
    "价值",
}

CONNECTORS = {
    "首先",
    "其次",
    "再次",
    "最后",
    "此外",
    "同时",
    "因此",
    "由此可见",
    "综上所述",
    "总而言之",
    "值得注意的是",
    "需要指出的是",
    "基于此",
    "在此基础上",
    "从整体上看",
    "另一方面",
}

DOMAIN_TERMS = {
    "核心素养",
    "课程标准",
    "学情",
    "教研",
    "少先队",
    "辅导员",
    "临床",
    "病理",
    "预后",
    "法益",
    "请求权",
    "构成要件",
    "边际",
    "均衡",
    "阈值",
    "鲁棒",
    "吞吐量",
}

CONCRETE_HINTS = {
    "课堂",
    "学生",
    "教师",
    "学校",
    "社区",
    "访谈",
    "问卷",
    "样本",
    "案例",
    "实验",
    "数据",
    "图表",
    "地点",
    "时间",
}

TEMPLATE_PATTERNS = [
    r"研究表明",
    r"本文.{0,12}(研究|探讨|分析)",
    r"本研究以.{0,30}为(个)?案",
    r"随着.{0,20}(深入)?推进",
    r"在.{0,20}背景下",
    r"立足.{0,20}实际",
    r"亟需|亟待",
    r"不容忽视",
    r"有机(统一|结合)",
    r"必然(选择|趋势|要求)",
    r"核心(要义|议题|内核)",
    r"关键环节",
    r"重要(载体|使命|途径|抓手)",
    r"值得关注的是",
    r"需要指出的是",
]

PARALLEL_PATTERNS = [
    r"从[^，,。；;]{2,18}(转向|到|走向)[^，,。；;]{2,18}[，,、]\s*从[^，,。；;]{2,18}(转向|到|走向)[^，,。；;]{2,18}",
    r"(通过|经由|借助)[^，,。；;]{2,18}[，,、]\s*(通过|经由|借助)[^，,。；;]{2,18}",
    r"既.{2,20}(又|也).{2,20}",
    r"不(仅|单|但).{2,30}(更|而且|还).{2,30}",
    r"[\u4e00-\u9fa5]{2,6}、[\u4e00-\u9fa5]{2,6}、[\u4e00-\u9fa5]{2,6}",
]

PHILOSOPHY_TAIL_PATTERNS = [
    r"本质上是.{2,30}",
    r"实质(是|在于).{2,30}",
    r"每一次.{2,20}都.{2,30}",
    r"这既是.{2,30}也是.{2,30}",
    r"成为.{2,20}的必然.{0,10}",
]


@dataclass(slots=True)
class ParagraphFeatures:
    char_count: int
    sentence_count: int
    sent_len_mean: float
    sent_len_cv: float
    burstiness: float
    punct_regularity: float
    ai_verb_ratio: float
    ai_noun_ratio: float
    conn_density: float
    fourch_density: float
    ttr: float
    tmpl_hit: float
    parallel_hit: float
    phil_hit_tail: float
    entity_density: float
    num_density: float
    domain_term_density: float
    dup_ngram_ratio: float
    concrete_density: float
    quote_density: float
    definition_rate: float
    template_hits: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "char_count": self.char_count,
            "sentence_count": self.sentence_count,
            "sent_len_mean": round(self.sent_len_mean, 4),
            "sent_len_cv": round(self.sent_len_cv, 4),
            "burstiness": round(self.burstiness, 4),
            "punct_regularity": round(self.punct_regularity, 4),
            "ai_verb_ratio": round(self.ai_verb_ratio, 4),
            "ai_noun_ratio": round(self.ai_noun_ratio, 4),
            "conn_density": round(self.conn_density, 4),
            "fourch_density": round(self.fourch_density, 4),
            "ttr": round(self.ttr, 4),
            "tmpl_hit": round(self.tmpl_hit, 4),
            "parallel_hit": round(self.parallel_hit, 4),
            "phil_hit_tail": round(self.phil_hit_tail, 4),
            "entity_density": round(self.entity_density, 4),
            "num_density": round(self.num_density, 4),
            "domain_term_density": round(self.domain_term_density, 4),
            "dup_ngram_ratio": round(self.dup_ngram_ratio, 4),
            "concrete_density": round(self.concrete_density, 4),
            "quote_density": round(self.quote_density, 4),
            "definition_rate": round(self.definition_rate, 4),
            "template_hits": list(self.template_hits[:6]),
        }


def clamp(value: float, min_value: float = 0.0, max_value: float = 1.0) -> float:
    return max(min_value, min(max_value, float(value)))


def normalize_text(text: str) -> str:
    output = str(text or "").replace("\u3000", " ")
    output = re.sub(r"[ \t]+", " ", output)
    output = re.sub(r"\n{3,}", "\n\n", output)
    return output.strip()


def split_sentences(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"[。！？!?；;\n]+", str(text or "")) if item.strip()]


def _compact_text(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "")).strip()


def _is_front_heading(text: str) -> bool:
    compact = _compact_text(text)
    lowered = compact.lower()
    if not compact:
        return False
    if lowered in {
        "摘要",
        "摘要:",
        "摘要：",
        "中文摘要",
        "英文摘要",
        "关键词",
        "关键词:",
        "关键词：",
        "关键字",
        "关键字:",
        "关键字：",
        "【关键词】",
        "【关键字】",
        "abstract",
        "abstract:",
        "abstract：",
        "keywords",
        "keywords:",
        "keywords：",
        "引言",
        "引言:",
        "引言：",
        "绪论",
        "绪论:",
        "绪论：",
        "前言",
        "前言:",
        "前言：",
        "导论",
        "导论:",
        "导论：",
        "结论",
        "结论:",
        "结论：",
        "结语",
        "结语:",
        "结语：",
        "参考文献",
        "参考文献:",
        "参考文献：",
        "附录",
        "附录:",
        "附录：",
        "致谢",
        "致谢:",
        "致谢：",
    }:
        return True
    if len(compact) <= 12:
        for prefix in ("摘要", "关键词", "关键字", "引言", "绪论", "前言", "结论", "结语", "参考文献", "附录", "致谢"):
            if compact.startswith(prefix):
                return True
    return False


def _is_outline_heading(text: str) -> bool:
    compact = _compact_text(text)
    if not compact or len(compact) > 40:
        return False
    if re.match(r"^\d+(?:\.\d+){0,3}[、.．]?", compact):
        return True
    if re.match(r"^第[一二三四五六七八九十百零0-9]+[章节部分篇]", compact):
        return True
    if re.match(r"^[一二三四五六七八九十百零]+[、.．]", compact):
        return True
    if re.match(r"^[（(][一二三四五六七八九十百零0-9]+[)）]", compact):
        return True
    return False


def _is_title_like(text: str, *, nonempty_index: int) -> bool:
    content = str(text or "").strip()
    if nonempty_index != 1 or not content:
        return False
    if len(content) > 64:
        return False
    return not re.search(r"[。！？；;]", content)


def _is_subtitle_like(text: str, *, nonempty_index: int, previous_kind: str) -> bool:
    content = str(text or "").strip()
    if not content or nonempty_index > 3:
        return False
    if previous_kind not in {"title", "subtitle"}:
        return False
    if content.startswith(("——", "—", "--", "-", "副标题")):
        return True
    return len(content) <= 48 and not re.search(r"[。！？；;]", content)


def _is_keyword_body(text: str, *, previous_kind: str) -> bool:
    content = str(text or "").strip()
    if previous_kind != "keyword_heading" or not content:
        return False
    if len(content) > 120:
        return False
    return any(token in content for token in ("；", ";", "、", "，"))


def _classify_part(text: str, *, nonempty_index: int, previous_kind: str) -> str:
    content = str(text or "").strip()
    if not content:
        return "blank"
    if _is_title_like(content, nonempty_index=nonempty_index):
        return "title"
    if _is_subtitle_like(content, nonempty_index=nonempty_index, previous_kind=previous_kind):
        return "subtitle"
    if _is_front_heading(content):
        compact = _compact_text(content).lower()
        if compact.startswith(("关键词", "关键字")) or compact.startswith("keywords"):
            return "keyword_heading"
        return "front_heading"
    if _is_keyword_body(content, previous_kind=previous_kind):
        return "keyword_body"
    if _is_outline_heading(content):
        return "outline_heading"
    return "body"


def _join_split_parts(left: str, right: str) -> str:
    left_text = str(left or "").strip()
    right_text = str(right or "").strip()
    if not left_text:
        return right_text
    if not right_text:
        return left_text
    if re.search(r"[\u4e00-\u9fff（([“‘]$", left_text) or re.match(r"^[\u4e00-\u9fff，。；：！？、）】》」]", right_text):
        return f"{left_text}{right_text}"
    return f"{left_text} {right_text}".strip()


def split_paragraphs(text: str) -> list[str]:
    clean = normalize_text(text)
    if not clean:
        return []
    raw_parts = [part.strip() for part in re.split(r"\n{1,}", clean) if part.strip()]
    if len(raw_parts) <= 1:
        raw_parts = [part.strip() for part in re.split(r"(?<=[。！？!?])\s*", clean) if part.strip()]
    paragraphs: list[str] = []
    paragraph_kinds: list[str] = []
    buffer = ""
    buffer_kind = "body"
    previous_kind = "blank"
    nonempty_index = 0
    for part in raw_parts:
        nonempty_index += 1
        part_kind = _classify_part(part, nonempty_index=nonempty_index, previous_kind=previous_kind)
        if part_kind != "body":
            if buffer:
                paragraphs.append(buffer)
                paragraph_kinds.append(buffer_kind)
                buffer = ""
                buffer_kind = "body"
            paragraphs.append(part)
            paragraph_kinds.append(part_kind)
            previous_kind = part_kind
            continue
        candidate = _join_split_parts(buffer, part) if buffer else part
        if count_billable_chars(candidate) < 40:
            buffer = candidate
            buffer_kind = "body"
            previous_kind = part_kind
            continue
        paragraphs.append(candidate)
        paragraph_kinds.append("body")
        buffer = ""
        buffer_kind = "body"
        previous_kind = part_kind
    if buffer:
        last_kind = paragraph_kinds[-1] if paragraph_kinds else ""
        if paragraphs and count_billable_chars(buffer) < 30 and buffer_kind == "body" and last_kind == "body":
            paragraphs[-1] = _join_split_parts(paragraphs[-1], buffer)
        else:
            paragraphs.append(buffer)
            paragraph_kinds.append(buffer_kind)
    return paragraphs or [clean]


def clip_text(text: str, limit: int) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit].rstrip()}..."


def token_count(text: str, words: set[str]) -> int:
    return sum(str(text or "").count(word) for word in words)


def pattern_hits(text: str, patterns: list[str]) -> list[str]:
    hits: list[str] = []
    for pattern in patterns:
        if re.search(pattern, text):
            hits.append(pattern)
    return hits


def repeated_ngram_ratio(text: str, n: int = 4) -> float:
    compact = re.sub(r"\s+", "", str(text or ""))
    if len(compact) <= n:
        return 0.0
    grams = [compact[index : index + n] for index in range(0, len(compact) - n + 1)]
    if not grams:
        return 0.0
    return clamp((len(grams) - len(set(grams))) / len(grams))


def four_char_density(text: str, char_count: int) -> float:
    matches = re.findall(r"[\u4e00-\u9fa5]{4}", str(text or ""))
    filtered = [item for item in matches if item not in DOMAIN_TERMS]
    return len(filtered) / max(char_count / 100.0, 1.0)


def entity_density(text: str, char_count: int) -> float:
    patterns = [
        r"[《][^》]{2,30}[》]",
        r"\d{4}年",
        r"\d+(?:\.\d+)?%",
        r"\d+(?:余)?(名|人|处|项|篇|次|册|所|个)",
        r"[\u4e00-\u9fa5]{2,8}(省|市|县|区|镇|乡|村|学校|学院|大学|公司|医院)",
    ]
    hits = 0
    for pattern in patterns:
        hits += len(re.findall(pattern, str(text or "")))
    return hits / max(char_count / 100.0, 1.0)


def extract_features(paragraph: str) -> ParagraphFeatures:
    text = normalize_text(paragraph)
    char_count = count_billable_chars(text)
    sentences = split_sentences(text)
    sentence_lengths = [count_billable_chars(item) for item in sentences if item.strip()]
    sent_len_mean = statistics.mean(sentence_lengths) if sentence_lengths else 0.0
    sent_len_std = statistics.pstdev(sentence_lengths) if len(sentence_lengths) > 1 else 0.0
    sent_len_cv = sent_len_std / max(sent_len_mean, 1.0)
    burstiness = (sent_len_std - sent_len_mean) / max(sent_len_std + sent_len_mean, 1.0)
    punct_count = len(re.findall(r"[，,。！？!?；;：:]", text))
    punct_regularity = 1.0 - clamp((sent_len_cv - 0.18) / 0.8)
    template_hits = pattern_hits(text, TEMPLATE_PATTERNS)
    parallel_hits = pattern_hits(text, PARALLEL_PATTERNS)
    tail = text[-90:]
    phil_hits = pattern_hits(tail, PHILOSOPHY_TAIL_PATTERNS)
    unique_chars = len(set(re.sub(r"\s+", "", text)))
    total_chars = max(char_count, 1)
    definition_count = len(re.findall(r"(是指|是对|定义为|可以理解为|本质上是|意味着)", text))
    quote_count = len(re.findall(r"[“”\"『』]", text))
    return ParagraphFeatures(
        char_count=char_count,
        sentence_count=len(sentences),
        sent_len_mean=sent_len_mean,
        sent_len_cv=sent_len_cv,
        burstiness=burstiness,
        punct_regularity=clamp(punct_regularity),
        ai_verb_ratio=token_count(text, AI_VERBS) / max(len(sentences), 1),
        ai_noun_ratio=token_count(text, AI_NOUNS) / max(len(sentences), 1),
        conn_density=token_count(text, CONNECTORS) / max(total_chars / 100.0, 1.0),
        fourch_density=four_char_density(text, total_chars),
        ttr=unique_chars / total_chars,
        tmpl_hit=clamp(len(template_hits) / 4.0),
        parallel_hit=clamp(len(parallel_hits) / 2.0),
        phil_hit_tail=clamp(len(phil_hits) / 2.0),
        entity_density=entity_density(text, total_chars),
        num_density=len(re.findall(r"\d+", text)) / max(total_chars / 100.0, 1.0),
        domain_term_density=token_count(text, DOMAIN_TERMS) / max(total_chars / 100.0, 1.0),
        dup_ngram_ratio=repeated_ngram_ratio(text),
        concrete_density=token_count(text, CONCRETE_HINTS) / max(total_chars / 100.0, 1.0),
        quote_density=quote_count / max(total_chars / 100.0, 1.0),
        definition_rate=definition_count / max(len(sentences), 1),
        template_hits=template_hits + parallel_hits + phil_hits,
    )


def sigmoid(value: float) -> float:
    try:
        return 1.0 / (1.0 + math.exp(-value))
    except OverflowError:
        return 0.0 if value < 0 else 1.0


def label_from_score(score: float, *, high: float, medium: float, low: float) -> str:
    if score >= high:
        return "high"
    if score >= medium:
        return "medium"
    if score >= low:
        return "low"
    return "clean"


def risk_band(label: str) -> str:
    return {
        "high": "高风险",
        "medium": "中风险",
        "low": "低风险",
        "clean": "低风险",
    }.get(label, "低风险")


def reason_tags(features: ParagraphFeatures, label: str) -> list[str]:
    if label == "clean":
        return []
    tags: list[str] = []
    if features.tmpl_hit >= 0.25:
        tags.append("模板套语命中")
    if features.parallel_hit >= 0.25:
        tags.append("并列排比结构明显")
    if features.conn_density >= 1.2:
        tags.append("连接词密度偏高")
    if features.fourch_density >= 2.0:
        tags.append("四字结构偏密")
    if features.sent_len_mean >= 34 and features.sent_len_cv <= 0.45:
        tags.append("句长规整")
    if features.ai_noun_ratio + features.ai_verb_ratio >= 1.2:
        tags.append("抽象词簇集中")
    if features.dup_ngram_ratio >= 0.08:
        tags.append("重复片段偏多")
    if not tags:
        tags.append("综合特征偏高")
    return tags[:3]


def paragraph_segments(paragraph: str, score: float, label: str, features: ParagraphFeatures) -> list[dict[str, Any]]:
    if label == "clean":
        return []
    segments: list[dict[str, Any]] = []
    threshold = 0.48 if label == "low" else 0.38
    for sentence in split_sentences(paragraph):
        sentence_features = extract_features(sentence)
        local_signal = clamp(
            sentence_features.tmpl_hit * 0.28
            + sentence_features.parallel_hit * 0.24
            + clamp(sentence_features.ai_noun_ratio / 2.5) * 0.18
            + clamp(sentence_features.conn_density / 3.0) * 0.14
            + clamp(sentence_features.fourch_density / 5.0) * 0.10
            + sentence_features.dup_ngram_ratio * 0.06
        )
        if local_signal < threshold and len(sentence) < 28:
            continue
        segments.append(
            {
                "text": clip_text(sentence, 90),
                "score": round(max(score * 100.0, local_signal * 100.0), 2),
                "reason": "、".join(reason_tags(sentence_features, label)[:2]) or "综合特征偏高",
                "label": label if label in {"high", "medium"} else "low",
            }
        )
    if not segments and features.template_hits:
        segments.append(
            {
                "text": clip_text(paragraph, 90),
                "score": round(score * 100.0, 2),
                "reason": "模板套语命中",
                "label": label if label in {"high", "medium"} else "low",
            }
        )
    return sorted(segments, key=lambda item: item["score"], reverse=True)[:3]


def text_stats(text: str) -> dict[str, Any]:
    clean = normalize_text(text)
    sentences = split_sentences(clean)
    paragraphs = split_paragraphs(clean)
    avg_sentence_length = round(
        sum(count_billable_chars(item) for item in sentences) / len(sentences), 2
    ) if sentences else 0
    return {
        "char_count": count_billable_chars(clean),
        "paragraph_count": len(paragraphs),
        "sentence_count": len(sentences),
        "avg_sentence_length": avg_sentence_length,
    }
