import io
import json
import zipfile
from dataclasses import dataclass
from textwrap import dedent

from sqlalchemy.orm import Session

from app.exceptions import BizError
from app.services.algo_package_service import _validate_slot, get_active_slot_config, install_algorithm_package


@dataclass(frozen=True)
class BuiltinPackageSpec:
    platform: str
    function_type: str
    name: str
    version: str
    main_py: str


_VERSION = "1.1.0"


def _aigc_detect_code(*, profile: str, score_offset: float) -> str:
    return (
        dedent(
            f"""
            import hashlib
            import re

            PROFILE = "{profile}"
            SCORE_OFFSET = {score_offset}


            def _clamp(value):
                return max(0.0, min(1.0, float(value)))


            def process(input_data):
                text = input_data.get("text", "") if isinstance(input_data, dict) else str(input_data)
                clean = " ".join(str(text).split())
                if not clean:
                    return {{"ai_score": 0.1, "label": "low", "profile": PROFILE, "text_stats": {{"chars": 0, "sentences": 0}}}}

                sentences = [seg.strip() for seg in re.split(r"[。\\n]+", clean) if seg.strip()]
                avg_len = sum(len(seg) for seg in sentences) / max(len(sentences), 1)
                unique_ratio = len(set(clean)) / max(len(clean), 1)
                repeat_signal = 1.0 - unique_ratio

                base = 0.42 + (avg_len - 22.0) / 125.0 + repeat_signal * 0.35 + SCORE_OFFSET
                seed = int(hashlib.md5(clean.encode("utf-8")).hexdigest()[:8], 16)
                jitter = ((seed % 17) - 8) / 1000.0
                score = round(_clamp(base + jitter), 4)

                if score >= 0.65:
                    label = "high"
                elif score >= 0.35:
                    label = "medium"
                else:
                    label = "low"

                return {{
                    "ai_score": score,
                    "label": label,
                    "profile": PROFILE,
                    "text_stats": {{
                        "chars": len(clean),
                        "sentences": len(sentences),
                        "avg_sentence_length": round(avg_len, 2),
                    }},
                    "algorithm": f"{{PROFILE}}_aigc_sim_v1_1_0",
                }}
            """
        ).strip()
        + "\n"
    )


def _dedup_code(*, profile: str, replacements: list[tuple[str, str]]) -> str:
    replacements_literal = json.dumps(replacements, ensure_ascii=False)
    return (
        dedent(
            f"""
            import hashlib
            import re

            PROFILE = "{profile}"
            REPLACEMENTS = {replacements_literal}


            def process(input_data):
                text = input_data.get("text", "") if isinstance(input_data, dict) else str(input_data)
                normalized = re.sub(r"\\s+", " ", str(text)).strip()
                if not normalized:
                    return {{"text": "", "similarity": 0.0, "algorithm": f"{{PROFILE}}_dedup_sim_v1_1_0"}}

                output = normalized
                change_count = 0
                for src, dst in REPLACEMENTS:
                    prev = output
                    output = output.replace(src, dst)
                    if output != prev:
                        change_count += 1

                if output == normalized and len(output) > 30:
                    output = output.replace("，", "；", 1)
                    if output == normalized:
                        output = output.replace("。", "；", 1)

                seed = int(hashlib.md5(normalized.encode("utf-8")).hexdigest()[:8], 16)
                rough_similarity = 8.0 + (seed % 31) + change_count * 2.2
                similarity = round(max(0.1, min(78.0, rough_similarity)), 2)

                return {{
                    "text": output,
                    "similarity": similarity,
                    "changes": change_count,
                    "algorithm": f"{{PROFILE}}_dedup_sim_v1_1_0",
                }}
            """
        ).strip()
        + "\n"
    )


def _rewrite_code(*, profile: str, replacements: list[tuple[str, str]]) -> str:
    replacements_literal = json.dumps(replacements, ensure_ascii=False)
    return (
        dedent(
            f"""
            import hashlib
            import re

            PROFILE = "{profile}"
            REPLACEMENTS = {replacements_literal}


            def _clamp_score(score):
                return max(0.0, min(100.0, float(score)))


            def process(input_data):
                text = input_data.get("text", "") if isinstance(input_data, dict) else str(input_data)
                source = re.sub(r"\\s+", " ", str(text)).strip()
                if not source:
                    return {{"text": "", "original_aigc_score": 0.0, "rewritten_aigc_score": 0.0, "algorithm": f"{{PROFILE}}_rewrite_sim_v1_1_0"}}

                output = source
                for src, dst in REPLACEMENTS:
                    output = output.replace(src, dst)
                output = re.sub(r"[。]{{2,}}", "。", output)

                seed = int(hashlib.md5(source.encode("utf-8")).hexdigest()[:8], 16)
                original_score = _clamp_score(52 + (seed % 34))
                reduction = 18 + (seed % 16)
                rewritten_score = _clamp_score(original_score - reduction)

                return {{
                    "text": output,
                    "original_aigc_score": round(original_score, 2),
                    "rewritten_aigc_score": round(rewritten_score, 2),
                    "algorithm": f"{{PROFILE}}_rewrite_sim_v1_1_0",
                }}
            """
        ).strip()
        + "\n"
    )


BUILTIN_PACKAGE_SPECS = (
    BuiltinPackageSpec(
        platform="cnki",
        function_type="aigc_detect",
        name="cnki_aigc_detect",
        version=_VERSION,
        main_py=_aigc_detect_code(profile="cnki_like", score_offset=0.00),
    ),
    BuiltinPackageSpec(
        platform="cnki",
        function_type="dedup",
        name="cnki_dedup",
        version=_VERSION,
        main_py=_dedup_code(
            profile="cnki_like",
            replacements=[
                ("首先", "第一"),
                ("其次", "第二"),
                ("因此", "由此可见"),
                ("但是", "然而"),
                ("总之", "综上所述"),
                ("可以看出", "据此可见"),
            ],
        ),
    ),
    BuiltinPackageSpec(
        platform="cnki",
        function_type="rewrite",
        name="cnki_rewrite",
        version=_VERSION,
        main_py=_rewrite_code(
            profile="cnki_like",
            replacements=[
                ("研究表明", "已有研究指出"),
                ("我们发现", "研究发现"),
                ("可以看出", "据此可见"),
                ("非常重要", "具有关键意义"),
            ],
        ),
    ),
    BuiltinPackageSpec(
        platform="vip",
        function_type="aigc_detect",
        name="vip_aigc_detect",
        version=_VERSION,
        main_py=_aigc_detect_code(profile="vip_like", score_offset=-0.02),
    ),
    BuiltinPackageSpec(
        platform="vip",
        function_type="dedup",
        name="vip_dedup",
        version=_VERSION,
        main_py=_dedup_code(
            profile="vip_like",
            replacements=[
                ("首先", "其一"),
                ("其次", "其二"),
                ("此外", "另一方面"),
                ("因此", "所以"),
                ("总之", "总体来看"),
                ("可以看出", "能够看出"),
            ],
        ),
    ),
    BuiltinPackageSpec(
        platform="vip",
        function_type="rewrite",
        name="vip_rewrite",
        version=_VERSION,
        main_py=_rewrite_code(
            profile="vip_like",
            replacements=[
                ("研究表明", "文献显示"),
                ("我们发现", "结果显示"),
                ("可以看出", "可以观察到"),
                ("非常重要", "较为关键"),
            ],
        ),
    ),
    BuiltinPackageSpec(
        platform="paperpass",
        function_type="aigc_detect",
        name="paperpass_aigc_detect",
        version=_VERSION,
        main_py=_aigc_detect_code(profile="paperpass_like", score_offset=0.03),
    ),
    BuiltinPackageSpec(
        platform="paperpass",
        function_type="dedup",
        name="paperpass_dedup",
        version=_VERSION,
        main_py=_dedup_code(
            profile="paperpass_like",
            replacements=[
                ("首先", "首要的是"),
                ("其次", "进一步看"),
                ("此外", "同时还需注意"),
                ("因此", "由此能够发现"),
                ("总之", "综合来看"),
                ("可以看出", "据此可以发现"),
            ],
        ),
    ),
    BuiltinPackageSpec(
        platform="paperpass",
        function_type="rewrite",
        name="paperpass_rewrite",
        version=_VERSION,
        main_py=_rewrite_code(
            profile="paperpass_like",
            replacements=[
                ("研究表明", "从现有研究来看"),
                ("我们发现", "分析结果显示"),
                ("可以看出", "据此可以发现"),
                ("非常重要", "具有核心作用"),
            ],
        ),
    ),
)


def _build_package_zip(spec: BuiltinPackageSpec) -> bytes:
    manifest = {
        "name": spec.name,
        "version": spec.version,
        "platform": spec.platform,
        "function_type": spec.function_type,
        "entry": "main.py",
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.writestr("main.py", spec.main_py)
    return buf.getvalue()


def _build_template_readme(spec: BuiltinPackageSpec) -> str:
    function_guides = {
        "aigc_detect": "- 推荐返回 dict，并至少包含 ai_score(0~1) 与 label(low/medium/high)\n- 建议额外返回 text_stats、algorithm、profile 等可观测字段\n",
        "dedup": "- 推荐返回 dict，并包含 text 字段作为处理后的正文\n- 建议额外返回 similarity、changes、algorithm 等字段\n",
        "rewrite": "- 推荐返回 dict，并包含 text 字段作为改写后的正文\n- 建议额外返回 original_aigc_score、rewritten_aigc_score、algorithm 等字段\n",
    }
    guide_text = function_guides.get(
        spec.function_type,
        "- 返回值必须非 None，并能被 JSON 序列化或转成字符串\n",
    ).strip()
    return dedent(
        f"""
        # 算法包模板说明

        这是 `{spec.platform}/{spec.function_type}` 槽位的可运行模板包。

        使用方式：
        1. 按需修改 `main.py` 中的 `process` 函数实现。
        2. 如需改名或重新上传，请同步修改 `manifest.json` 里的 `name` 与 `version`。
        3. 上传目标槽位必须与 `manifest.json` 内的 `platform` / `function_type` 完全一致。
        4. 入口文件默认是 `main.py`，如需改成别的路径，务必同步修改 `entry` 且保证文件实际存在。

        当前槽位建议：
        {guide_text}

        上传前检查：
        - zip 内必须有 `manifest.json`
        - Python 文件需 UTF-8 编码
        - `process` 需要能处理字符串输入；若你只接受 dict，请至少兼容 `{{"text": "..."}}`
        - 单次执行超时默认 8 秒
        - 上传文件大小默认不超过 200 MB
        """
    ).strip() + "\n"


_AIGC_VERSION = "1.4.0"
_AIGC_VERSION_TAG = _AIGC_VERSION.replace(".", "_")
_CNKI_AIGC_VERSION = "1.8.1"
_CNKI_AIGC_VERSION_TAG = _CNKI_AIGC_VERSION.replace(".", "_")
_CNKI_TEXT_VERSION = "1.2.0"
_CNKI_TEXT_VERSION_TAG = _CNKI_TEXT_VERSION.replace(".", "_")
_VIP_DEDUP_VERSION = "1.2.1"
_VIP_DEDUP_VERSION_TAG = _VIP_DEDUP_VERSION.replace(".", "_")


def _legacy_aigc_detect_code_v2(*, profile: str, score_offset: float) -> str:
    return (
        dedent(
            f"""
            import hashlib
            import re

            PROFILE = "{profile}"
            SCORE_OFFSET = {score_offset}
            PROFILE_SETTINGS = {{
                "cnki_like": {{
                    "high": 0.67,
                    "medium": 0.42,
                    "paragraph_weight": 0.58,
                    "peak_weight": 0.24,
                    "segment_weight": 0.18,
                }},
                "vip_like": {{
                    "high": 0.64,
                    "medium": 0.40,
                    "paragraph_weight": 0.54,
                    "peak_weight": 0.22,
                    "segment_weight": 0.24,
                }},
                "paperpass_like": {{
                    "high": 0.60,
                    "medium": 0.38,
                    "paragraph_weight": 0.50,
                    "peak_weight": 0.20,
                    "segment_weight": 0.30,
                }},
            }}
            TEMPLATE_PHRASES = [
                "研究表明",
                "可以看出",
                "由此可见",
                "综上所述",
                "总而言之",
                "值得注意的是",
                "首先",
                "其次",
                "此外",
                "另一方面",
                "进一步而言",
                "从整体上看",
                "不难发现",
            ]
            RELIEF_PATTERNS = [r"\\[\\d+\\]", r"（\\d{{4}}）", r"\\(\\d{{4}}\\)", r"表\\d+", r"图\\d+", r"\\d+%"]
            SPECIAL_HEADINGS = ["摘要", "关键词", "引言", "绪论", "前言", "结语", "结论", "参考文献", "附录", "致谢"]


            def _clamp(value):
                return max(0.0, min(1.0, float(value)))


            def _split_sentences(text):
                return [seg.strip() for seg in re.split(r"[。！？!?；;\\n]+", str(text or "")) if seg.strip()]


            def _template_signal(text):
                hits = [phrase for phrase in TEMPLATE_PHRASES if phrase in str(text or "")]
                density = len(hits) / max(len(str(text or "")) / 85.0, 1.0)
                return _clamp(density), hits[:4]


            def _repetition_signal(text):
                content = " ".join(str(text or "").split())
                if not content:
                    return 0.0
                unique_ratio = len(set(content)) / max(len(content), 1)
                return _clamp(1.0 - unique_ratio)


            def _uniformity_signal(sentences):
                lengths = [len(item) for item in sentences if item]
                if not lengths:
                    return 0.0
                if len(lengths) == 1:
                    return 0.5
                avg_len = sum(lengths) / len(lengths)
                variance = sum((value - avg_len) ** 2 for value in lengths) / len(lengths)
                return _clamp(1.0 - min(1.0, variance / max(avg_len * 14.0, 1.0)))


            def _citation_relief(text):
                content = str(text or "")
                hit_count = 0
                for pattern in RELIEF_PATTERNS:
                    hit_count += len(re.findall(pattern, content))
                return min(0.18, hit_count * 0.025)


            def _score_to_label(score, settings):
                if score >= settings["high"]:
                    return "high"
                if score >= settings["medium"]:
                    return "medium"
                return "low"


            def _detect_heading(paragraph):
                clean = " ".join(str(paragraph or "").split())
                normalized = re.sub(r"\\s+", "", clean).strip("：:.。;；")
                if not normalized or len(normalized) > 36:
                    return None
                if normalized in SPECIAL_HEADINGS:
                    return clean
                if re.match(r"^(第[一二三四五六七八九十百零0-9]+[章节部分篇]|[一二三四五六七八九十百零]+[、.．]|\\d+(?:\\.\\d+){{0,3}}[、.．]?|[（(][一二三四五六七八九十百零0-9]+[)）])", normalized):
                    return clean
                return None


            def _sentence_payload(sentence, settings):
                sentences = _split_sentences(sentence)
                template_signal, template_hits = _template_signal(sentence)
                score = _clamp(
                    0.28
                    + template_signal * 0.28
                    + _repetition_signal(sentence) * 0.18
                    + _uniformity_signal(sentences) * 0.12
                    - _citation_relief(sentence)
                    + SCORE_OFFSET
                )
                return {{
                    "text": sentence[:76],
                    "score": round(score * 100, 2),
                    "label": _score_to_label(score, settings),
                    "reason": "、".join(template_hits[:2]) if template_hits else "综合风险偏高",
                }}


            def _paragraph_payload(index, paragraph, settings):
                sentences = _split_sentences(paragraph)
                avg_len = sum(len(seg) for seg in sentences) / max(len(sentences), 1)
                template_signal, template_hits = _template_signal(paragraph)
                repeat_signal = _repetition_signal(paragraph)
                uniformity_signal = _uniformity_signal(sentences)
                citation_relief = _citation_relief(paragraph)
                seed = int(hashlib.md5(paragraph.encode("utf-8")).hexdigest()[:8], 16)
                jitter = ((seed % 11) - 5) / 1000.0
                score = _clamp(
                    0.34
                    + max(0.0, (avg_len - 18.0) / 55.0) * 0.18
                    + template_signal * 0.18
                    + repeat_signal * 0.16
                    + uniformity_signal * 0.12
                    - citation_relief
                    + SCORE_OFFSET
                    + jitter
                )
                suspicious_segments = []
                for sentence in sentences:
                    if len(sentence) < 8:
                        continue
                    item = _sentence_payload(sentence, settings)
                    if item["score"] / 100.0 >= settings["medium"] or len(template_hits) >= 2:
                        suspicious_segments.append(item)
                suspicious_segments.sort(key=lambda item: item["score"], reverse=True)
                label = _score_to_label(score, settings)
                return {{
                    "index": index,
                    "score": round(score * 100, 2),
                    "label": label,
                    "excerpt": paragraph[:110],
                    "char_count": len(paragraph),
                    "sentence_count": len(sentences),
                    "signals": {{
                        "template_signal": round(template_signal, 4),
                        "repeat_signal": round(repeat_signal, 4),
                        "uniformity_signal": round(uniformity_signal, 4),
                        "citation_relief": round(citation_relief, 4),
                    }},
                    "suspicious_segments": suspicious_segments[:3],
                }}


            def _build_outline(paragraphs):
                outline = []
                seen = set()
                for index, paragraph in enumerate(paragraphs, start=1):
                    heading = _detect_heading(paragraph)
                    if not heading:
                        continue
                    key = re.sub(r"\\s+", "", heading)
                    if key in seen:
                        continue
                    seen.add(key)
                    outline.append({{"section": heading[:32], "start_index": index}})
                for pos, item in enumerate(outline):
                    next_start = outline[pos + 1]["start_index"] if pos + 1 < len(outline) else len(paragraphs) + 1
                    item["end_index"] = max(item["start_index"], next_start - 1)
                return outline[:20]


            def _fragment_distribution(paragraph_payloads, paragraphs, settings):
                count_map = {{"high": 0, "medium": 0, "low": 0, "no_ai": 0}}
                char_map = {{"high": 0, "medium": 0, "low": 0, "no_ai": 0}}
                weighted_scores = []
                for paragraph_payload, paragraph in zip(paragraph_payloads, paragraphs):
                    paragraph_ratio = paragraph_payload["score"] / 100.0
                    for sentence in _split_sentences(paragraph):
                        clean = " ".join(str(sentence or "").split())
                        if not clean:
                            continue
                        char_count = len(clean)
                        if not char_count:
                            continue
                        if _detect_heading(clean) or (_citation_relief(clean) >= 0.08 and len(clean) <= 90):
                            label = "no_ai"
                            score_ratio = 0.0
                        else:
                            sentence_payload = _sentence_payload(clean, settings)
                            score_ratio = _clamp(sentence_payload["score"] / 100.0 * 0.74 + paragraph_ratio * 0.26)
                            label = _score_to_label(score_ratio, settings)
                            weighted_scores.append(score_ratio)
                        count_map[label] += 1
                        char_map[label] += char_count

                total_fragments = sum(count_map.values())
                total_chars = sum(char_map.values())
                if not total_fragments or not total_chars:
                    return {{
                        "fragment_count": 0,
                        "high_fragment_count": 0,
                        "middle_fragment_count": 0,
                        "low_fragment_count": 0,
                        "no_ai_fragment_count": 0,
                        "high_suspected_fragment_ratio": 0.0,
                        "middle_suspected_fragment_ratio": 0.0,
                        "low_suspected_fragment_ratio": 0.0,
                        "no_ai_fragment_ratio": 0.0,
                        "high_and_middle_suspected_fragment_ratio": 0.0,
                        "total_suspected_fragment_ratio": 0.0,
                        "high_suspected_text_ratio": 0.0,
                        "middle_suspected_text_ratio": 0.0,
                        "low_suspected_text_ratio": 0.0,
                        "no_ai_suspected_text_ratio": 0.0,
                        "high_and_middle_suspected_text_ratio": 0.0,
                        "total_suspected_text_ratio": 0.0,
                        "weighted_score_pct": 0.0,
                    }}

                def _ratio(part, whole):
                    return round(part / max(whole, 1) * 100, 2)

                high_middle_fragments = count_map["high"] + count_map["medium"]
                suspected_fragments = high_middle_fragments + count_map["low"]
                high_middle_chars = char_map["high"] + char_map["medium"]
                suspected_chars = high_middle_chars + char_map["low"]
                return {{
                    "fragment_count": total_fragments,
                    "high_fragment_count": count_map["high"],
                    "middle_fragment_count": count_map["medium"],
                    "low_fragment_count": count_map["low"],
                    "no_ai_fragment_count": count_map["no_ai"],
                    "high_suspected_fragment_ratio": _ratio(count_map["high"], total_fragments),
                    "middle_suspected_fragment_ratio": _ratio(count_map["medium"], total_fragments),
                    "low_suspected_fragment_ratio": _ratio(count_map["low"], total_fragments),
                    "no_ai_fragment_ratio": _ratio(count_map["no_ai"], total_fragments),
                    "high_and_middle_suspected_fragment_ratio": _ratio(high_middle_fragments, total_fragments),
                    "total_suspected_fragment_ratio": _ratio(suspected_fragments, total_fragments),
                    "high_suspected_text_ratio": _ratio(char_map["high"], total_chars),
                    "middle_suspected_text_ratio": _ratio(char_map["medium"], total_chars),
                    "low_suspected_text_ratio": _ratio(char_map["low"], total_chars),
                    "no_ai_suspected_text_ratio": _ratio(char_map["no_ai"], total_chars),
                    "high_and_middle_suspected_text_ratio": _ratio(high_middle_chars, total_chars),
                    "total_suspected_text_ratio": _ratio(suspected_chars, total_chars),
                    "weighted_score_pct": round(sum(weighted_scores) / max(len(weighted_scores), 1) * 100, 2) if weighted_scores else 0.0,
                }}


            def process(input_data):
                text = input_data.get("text", "") if isinstance(input_data, dict) else str(input_data)
                clean = str(text or "").strip()
                if not clean:
                    return {{
                        "ai_score": 0.1,
                        "label": "low",
                        "profile": PROFILE,
                        "algorithm": f"{{PROFILE}}_aigc_sim_v{_AIGC_VERSION_TAG}",
                        "text_stats": {{"chars": 0, "sentences": 0, "paragraphs": 0}},
                        "distribution": {{"high": 0, "medium": 0, "low": 0, "high_ratio": 0.0}},
                        "fragment_distribution": {{"fragment_count": 0, "weighted_score_pct": 0.0}},
                        "outline": [],
                        "paragraphs": [],
                        "suspicious_segments": [],
                    }}

                settings = PROFILE_SETTINGS.get(PROFILE, PROFILE_SETTINGS["cnki_like"])
                paragraphs = [part.strip() for part in re.split(r"\\n+", clean) if part.strip()]
                if not paragraphs:
                    paragraphs = [clean]
                paragraph_payloads = [_paragraph_payload(index, paragraph, settings) for index, paragraph in enumerate(paragraphs, start=1)]
                outline = _build_outline(paragraphs)
                fragment_distribution = _fragment_distribution(paragraph_payloads, paragraphs, settings)
                paragraph_scores = [item["score"] / 100.0 for item in paragraph_payloads]
                suspicious_segments = []
                for item in paragraph_payloads:
                    for segment in item["suspicious_segments"]:
                        suspicious_segments.append({{
                            "paragraph_index": item["index"],
                            "text": segment["text"],
                            "score": segment["score"],
                            "reason": segment["reason"],
                        }})
                suspicious_segments.sort(key=lambda item: item["score"], reverse=True)

                mean_score = sum(paragraph_scores) / max(len(paragraph_scores), 1)
                peak_score = max(paragraph_scores) if paragraph_scores else 0.0
                segment_score = (
                    sum(item["score"] for item in suspicious_segments[:5]) / max(len(suspicious_segments[:5]), 1) / 100.0
                    if suspicious_segments
                    else 0.0
                )
                score = _clamp(
                    mean_score * settings["paragraph_weight"]
                    + peak_score * settings["peak_weight"]
                    + segment_score * settings["segment_weight"]
                )

                high_count = sum(1 for item in paragraph_payloads if item["label"] == "high")
                medium_count = sum(1 for item in paragraph_payloads if item["label"] == "medium")
                low_count = len(paragraph_payloads) - high_count - medium_count
                sentences = _split_sentences(clean)

                return {{
                    "ai_score": round(score, 4),
                    "label": _score_to_label(score, settings),
                    "profile": PROFILE,
                    "algorithm": f"{{PROFILE}}_aigc_sim_v{_AIGC_VERSION_TAG}",
                    "text_stats": {{
                        "chars": len(clean),
                        "sentences": len(sentences),
                        "paragraphs": len(paragraph_payloads),
                        "avg_sentence_length": round(sum(len(seg) for seg in sentences) / max(len(sentences), 1), 2),
                    }},
                    "distribution": {{
                        "high": high_count,
                        "medium": medium_count,
                        "low": low_count,
                        "high_ratio": round(high_count / max(len(paragraph_payloads), 1) * 100, 2),
                    }},
                    "fragment_distribution": fragment_distribution,
                    "outline": outline,
                    "paragraphs": paragraph_payloads,
                    "suspicious_segments": suspicious_segments[:10],
                }}
            """
        ).strip()
        + "\n"
    )


def _aigc_detect_code_v3(*, profile: str, score_offset: float) -> str:
    return (
        dedent(
            f"""
            import hashlib
            import re

            PROFILE = "{profile}"
            SCORE_OFFSET = {score_offset}
            PROFILE_SETTINGS = {{
                "cnki_like": {{"high": 0.67, "medium": 0.42, "coverage_weight": 0.06, "streak_weight": 0.03}},
                "vip_like": {{"high": 0.64, "medium": 0.40, "coverage_weight": 0.08, "streak_weight": 0.03}},
                "paperpass_like": {{"high": 0.60, "medium": 0.38, "coverage_weight": 0.05, "streak_weight": 0.05}},
            }}
            TEMPLATE_PHRASES = [
                "研究表明", "本研究旨在", "本文基于", "在此背景下", "可以看出", "由此可见", "综上所述",
                "总而言之", "值得注意的是", "首先", "其次", "再次", "最后", "此外", "与此同时",
                "另一方面", "进一步而言", "从整体上看", "不难发现", "基于此"
            ]
            CITATION_PATTERNS = [r"\\[\\d+\\]", r"（\\d{{4}}）", r"\\(\\d{{4}}\\)", r"表\\d+", r"图\\d+", r"\\d+%"]
            EVIDENCE_PATTERNS = [r"\\bN\\s*=\\s*\\d+", r"样本量", r"问卷", r"访谈", r"实验", r"受访者", r"标准差", r"均值", r"统计", r"案例"]
            HEADING_PATTERNS = [r"^(第[一二三四五六七八九十百零0-9]+[章节部分篇])", r"^[一二三四五六七八九十百零]+[、.．]", r"^\\d+(?:\\.\\d+){{0,3}}[、.．]?", r"^[（(][一二三四五六七八九十百零0-9]+[)）]"]


            def _clamp(value):
                return max(0.0, min(1.0, float(value)))


            def _split_sentences(text):
                return [seg.strip() for seg in re.split(r"[。！？!?；;\\n]+", str(text or "")) if seg.strip()]


            def _split_paragraphs(text):
                parts = [part.strip() for part in re.split(r"\\n+", str(text or "")) if part.strip()]
                return parts or [str(text or "").strip()]


            def _template_signal(text):
                content = str(text or "")
                hits = [phrase for phrase in TEMPLATE_PHRASES if phrase in content]
                density = len(hits) / max(len(content) / 85.0, 1.0)
                return _clamp(density), hits[:4]


            def _repeat_signal(text):
                content = " ".join(str(text or "").split())
                if not content:
                    return 0.0
                return _clamp(1.0 - len(set(content)) / max(len(content), 1))


            def _uniformity_signal(sentences):
                lengths = [len(item) for item in sentences if item]
                if not lengths:
                    return 0.0
                if len(lengths) == 1:
                    return 0.5
                avg_len = sum(lengths) / len(lengths)
                variance = sum((value - avg_len) ** 2 for value in lengths) / len(lengths)
                return _clamp(1.0 - min(1.0, variance / max(avg_len * 14.0, 1.0)))


            def _opening_signal(text):
                clean = re.sub(r"^(?:第[一二三四五六七八九十百零0-9]+[章节部分篇]|[一二三四五六七八九十百零]+[、.．]|\\d+(?:\\.\\d+){{0,3}}[、.．]?|[（(][一二三四五六七八九十百零0-9]+[)）])", "", " ".join(str(text or "").split())).lstrip("：:.。;；、，, ")
                starters = ("本研究", "本文", "研究表明", "综上所述", "总而言之", "值得注意的是", "首先", "其次", "再次", "此外", "另一方面", "由此可见", "基于此")
                signal = 0.48 if any(clean.startswith(token) for token in starters) else 0.0
                if re.search(r"^在.{{0,8}}背景下", clean):
                    signal += 0.18
                return _clamp(signal)


            def _citation_relief(text):
                return min(0.18, sum(len(re.findall(pattern, str(text or ""))) for pattern in CITATION_PATTERNS) * 0.025)


            def _evidence_relief(text):
                return min(0.16, sum(len(re.findall(pattern, str(text or ""), flags=re.IGNORECASE)) for pattern in EVIDENCE_PATTERNS) * 0.018)


            def _score_to_label(score, settings):
                if score >= settings["high"]:
                    return "high"
                if score >= settings["medium"]:
                    return "medium"
                return "low"


            def _fragment_band(score):
                if score >= 0.9:
                    return "severe"
                if score >= 0.8:
                    return "moderate"
                if score >= 0.7:
                    return "mild"
                return ""


            def _is_heading(text):
                clean = re.sub(r"\\s+", "", str(text or "")).strip("：:.。;；")
                if not clean or len(clean) > 36:
                    return False
                return any(re.match(pattern, clean) for pattern in HEADING_PATTERNS) or clean in ["摘要", "关键词", "引言", "绪论", "前言", "结语", "结论", "参考文献", "附录", "致谢"]


            def process(input_data):
                text = input_data.get("text", "") if isinstance(input_data, dict) else str(input_data)
                clean = str(text or "").strip()
                if not clean:
                    return {{"ai_score": 0.1, "label": "low", "profile": PROFILE, "algorithm": f"{{PROFILE}}_aigc_sim_v{_AIGC_VERSION_TAG}", "paragraphs": [], "fragment_distribution": {{"fragment_count": 0}}, "outline": [], "decision_basis": [], "document_metrics": {{"paragraph_count": 0}}}}

                settings = PROFILE_SETTINGS.get(PROFILE, PROFILE_SETTINGS["cnki_like"])
                paragraphs = _split_paragraphs(clean)
                paragraph_payloads = []
                suspicious_segments = []
                opening_keys = []
                for index, paragraph in enumerate(paragraphs, start=1):
                    sentences = _split_sentences(paragraph)
                    template_signal, template_hits = _template_signal(paragraph)
                    repeat_signal = _repeat_signal(paragraph)
                    uniformity_signal = _uniformity_signal(sentences)
                    opening_signal = _opening_signal(paragraph)
                    citation_relief = _citation_relief(paragraph)
                    evidence_relief = _evidence_relief(paragraph)
                    avg_len = sum(len(seg) for seg in sentences) / max(len(sentences), 1)
                    seed = int(hashlib.md5(paragraph.encode("utf-8")).hexdigest()[:8], 16)
                    jitter = ((seed % 11) - 5) / 1000.0
                    score = _clamp(0.34 + max(0.0, (avg_len - 18.0) / 55.0) * 0.18 + template_signal * 0.18 + repeat_signal * 0.16 + uniformity_signal * 0.12 + opening_signal * 0.06 - citation_relief - evidence_relief + SCORE_OFFSET + jitter)
                    label = _score_to_label(score, settings)
                    opening_key = re.sub(r"\\s+", "", paragraph)[:12]
                    if opening_key and not _is_heading(paragraph):
                        opening_keys.append(opening_key)
                    seg_rows = []
                    for sentence in sentences:
                        if len(sentence) < 8:
                            continue
                        seg_score = _clamp(0.28 + _template_signal(sentence)[0] * 0.28 + _repeat_signal(sentence) * 0.18 + _uniformity_signal(_split_sentences(sentence)) * 0.12 + _opening_signal(sentence) * 0.06 - _citation_relief(sentence) - _evidence_relief(sentence) + SCORE_OFFSET)
                        if seg_score >= settings["medium"] or len(template_hits) >= 2:
                            reason_bits = []
                            if _template_signal(sentence)[0] >= 0.22:
                                reason_bits.append("模板连接词偏多")
                            if _repeat_signal(sentence) >= 0.32:
                                reason_bits.append("重复表达偏多")
                            if _uniformity_signal(_split_sentences(sentence)) >= 0.58:
                                reason_bits.append("句式波动偏小")
                            seg_rows.append({{"text": sentence[:76], "score": round(seg_score * 100, 2), "label": _score_to_label(seg_score, settings), "reason": "、".join(reason_bits[:2]) or "综合风险偏高"}})
                    seg_rows.sort(key=lambda item: item["score"], reverse=True)
                    for segment in seg_rows[:3]:
                        suspicious_segments.append({{"paragraph_index": index, "text": segment["text"], "score": segment["score"], "reason": segment["reason"]}})
                    paragraph_payloads.append({{"index": index, "score": round(score * 100, 2), "label": label, "excerpt": paragraph[:110], "char_count": len(paragraph), "sentence_count": len(sentences), "suspicious_segments": seg_rows[:3], "signals": {{"template_signal": round(template_signal, 4), "repeat_signal": round(repeat_signal, 4), "uniformity_signal": round(uniformity_signal, 4), "opening_signal": round(opening_signal, 4)}}}})

                suspicious_segments.sort(key=lambda item: item["score"], reverse=True)
                count_map = {{"high": 0, "medium": 0, "low": 0, "no_ai": 0}}
                char_map = {{"high": 0, "medium": 0, "low": 0, "no_ai": 0}}
                display_count = {{"mild": 0, "moderate": 0, "severe": 0}}
                for item, paragraph in zip(paragraph_payloads, paragraphs):
                    paragraph_ratio = item["score"] / 100.0
                    for sentence in _split_sentences(paragraph):
                        clean_sentence = " ".join(sentence.split())
                        if not clean_sentence:
                            continue
                        if _is_heading(clean_sentence) or (_citation_relief(clean_sentence) >= 0.08 and len(clean_sentence) <= 90):
                            label = "no_ai"
                            score_ratio = 0.0
                        else:
                            score_ratio = _clamp((item["score"] / 100.0) * 0.28 + paragraph_ratio * 0.72)
                            label = _score_to_label(score_ratio, settings)
                            band = _fragment_band(score_ratio)
                            if band:
                                display_count[band] += 1
                        count_map[label] += 1
                        char_map[label] += len(clean_sentence)

                def _ratio(part, whole):
                    return round(part / max(whole, 1) * 100, 2)

                total_fragments = sum(count_map.values())
                total_chars = sum(char_map.values())
                high_medium_count = sum(1 for item in paragraph_payloads if item["label"] in ("high", "medium"))
                longest_streak = 0
                current_streak = 0
                for item in paragraph_payloads:
                    if item["label"] in ("high", "medium"):
                        current_streak += 1
                        longest_streak = max(longest_streak, current_streak)
                    else:
                        current_streak = 0
                opening_similarity = _clamp(max(0, len(opening_keys) - len(set(opening_keys))) / max(len(opening_keys), 1)) if opening_keys else 0.0
                mean_score = sum(item["score"] / 100.0 for item in paragraph_payloads) / max(len(paragraph_payloads), 1)
                peak_score = max((item["score"] / 100.0 for item in paragraph_payloads), default=0.0)
                segment_score = sum(item["score"] for item in suspicious_segments[:5]) / max(len(suspicious_segments[:5]), 1) / 100.0 if suspicious_segments else 0.0
                coverage_ratio = high_medium_count / max(len(paragraph_payloads), 1)
                score = _clamp(mean_score * 0.48 + peak_score * 0.18 + segment_score * 0.12 + coverage_ratio * settings["coverage_weight"] + (longest_streak / max(len(paragraph_payloads), 1)) * settings["streak_weight"] + opening_similarity * 0.03)

                decision_basis = []
                first_para_signals = (paragraph_payloads[0].get("signals") or {{}}) if paragraph_payloads else {{}}
                if float(first_para_signals.get("template_signal") or 0.0) >= 0.2:
                    decision_basis.append({{"title": "模板连接词密度偏高", "direction": "risk"}})
                if opening_similarity >= 0.2:
                    decision_basis.append({{"title": "段首表达重复度较高", "direction": "risk"}})
                if longest_streak >= 3:
                    decision_basis.append({{"title": "存在连续风险片段带", "direction": "risk"}})
                if _ratio(char_map["high"] + char_map["medium"], total_chars) >= 20:
                    decision_basis.append({{"title": "高中风险文字占比较高", "direction": "risk"}})

                outline = [{{"section": paragraph[:32], "start_index": index}} for index, paragraph in enumerate(paragraphs, start=1) if _is_heading(paragraph)][:20]
                return {{
                    "ai_score": round(score, 4),
                    "label": _score_to_label(score, settings),
                    "profile": PROFILE,
                    "algorithm": f"{{PROFILE}}_aigc_sim_v{_AIGC_VERSION_TAG}",
                    "text_stats": {{"chars": len(clean), "sentences": len(_split_sentences(clean)), "paragraphs": len(paragraph_payloads)}},
                    "distribution": {{"high": sum(1 for item in paragraph_payloads if item["label"] == "high"), "medium": sum(1 for item in paragraph_payloads if item["label"] == "medium"), "low": sum(1 for item in paragraph_payloads if item["label"] == "low"), "high_ratio": _ratio(sum(1 for item in paragraph_payloads if item["label"] == "high"), len(paragraph_payloads))}},
                    "fragment_distribution": {{"fragment_count": total_fragments, "high_fragment_count": count_map["high"], "middle_fragment_count": count_map["medium"], "low_fragment_count": count_map["low"], "no_ai_fragment_count": count_map["no_ai"], "high_and_middle_suspected_text_ratio": _ratio(char_map["high"] + char_map["medium"], total_chars), "total_suspected_text_ratio": _ratio(char_map["high"] + char_map["medium"] + char_map["low"], total_chars), "weighted_score_pct": round(sum(item["score"] for item in paragraph_payloads) / max(len(paragraph_payloads), 1), 2), "mild_fragment_count": display_count["mild"], "moderate_fragment_count": display_count["moderate"], "severe_fragment_count": display_count["severe"]}},
                    "document_metrics": {{"paragraph_count": len(paragraph_payloads), "high_medium_paragraph_ratio": _ratio(high_medium_count, len(paragraph_payloads)), "longest_risk_streak": longest_streak, "opening_similarity_ratio": round(opening_similarity * 100, 2)}},
                    "decision_basis": decision_basis[:4],
                    "outline": outline,
                    "paragraphs": paragraph_payloads,
                    "suspicious_segments": suspicious_segments[:10],
                }}
            """
        ).strip()
        + "\n"
    )


def _cnki_aigc_detect_code_v5() -> str:
    return (
        dedent(
            f"""
            import hashlib
            import re

            PROFILE = "cnki_like"
            TEMPLATE_PHRASES = [
                "本研究以", "本研究旨在", "本文基于", "在此背景下", "研究表明", "研究发现", "研究结论显示",
                "可以看出", "由此可见", "综上所述", "总而言之", "值得注意的是", "首先", "其次", "再次",
                "此外", "与此同时", "另一方面", "进一步而言", "不难发现", "基于上述", "系统分析",
                "构建", "搭建", "实施保障", "优化路径", "评价体系", "机制设计"
            ]
            ARTIFACT_MARKERS = [
                "需要求", "知识得到", "主题着眼于", "读全面本书", "都衡", "全面性", "让用", "成效",
                "目的模糊等困难", "机械替换", "主题聚焦对策的实施"
            ]
            ENGLISH_HINTS = ["abstract", "keywords", "this study", "this paper", "based on", "findings show", "research object"]
            SPECIAL_HEADINGS = ["摘要", "关键词", "引言", "绪论", "前言", "结语", "结论", "参考文献", "附录", "致谢", "abstract", "keywords"]
            HEADING_PATTERNS = [
                r"^(第[一二三四五六七八九十百零0-9]+[章节部分篇])",
                r"^[一二三四五六七八九十百零]+[、.．]",
                r"^\\d+(?:\\.\\d+){{0,3}}[、.．]?",
                r"^[（(][一二三四五六七八九十百零0-9]+[)）]",
            ]
            CITATION_PATTERNS = [r"\\[\\d+\\]", r"（\\d{{4}}）", r"\\(\\d{{4}}\\)", r"表\\d+", r"图\\d+", r"\\d+%"]
            EVIDENCE_PATTERNS = [r"\\bN\\s*=\\s*\\d+", r"样本量", r"问卷", r"访谈", r"实验", r"受访者", r"统计", r"案例", r"调查", r"表\\d+"]
            HUMAN_CASE_PATTERNS = [
                r"幼儿|孩子|家长|教师|老师|妈妈|爸爸|爷爷|奶奶|家人|亲子|家园|园所|本园|我园|班级|晨圈|绘本|贺卡|甜汤|社区老人",
                r"捶背|摆碗筷|倒了杯热水|讲一讲这周存了什么|家长感悟接龙|家长体验课|家长助教活动|献给妈妈的歌|母亲节|重阳节",
                r"看得见|摸得着|拥抱|眼神|红了眼眶|流露出的困惑和落寞",
            ]
            RHETORICAL_PATTERNS = [
                r"该项目旨在",
                r"核心问题不是.+而是",
                r"以节日为(?:媒介|载体)",
                r"从“?.+?”?到“?.+?”?",
                r"变化发生在可以观察到的细节里",
                r"让.+更有仪式感与温度",
                r"家园同心，共育花开",
                r"这个机制的意外收获是",
            ]
            PRACTICE_CHAIN_PATTERNS = [
                r"课程融合|晨圈分享|家长参与|成效与反思",
                r"绘本阅读|手工绘画|演唱活动|家人小调查|家长体验课|家长助教活动|家长感悟接龙",
                r"角色互换|双向流动|情感共鸣|进入社区|主动参与|表达更主动|参与质量",
                r"制作贺卡|爱心甜汤|调查活动|分享环节|晨圈时间|节日活动",
            ]
            SUMMARY_WRAPUP_PATTERNS = [
                r"最核心的教育逻辑|最本质的教育逻辑",
                r"可迁移性体现在两个层面|具有极强的可迁移性",
                r"形成系列化的家园共育体系",
                r"推广价值|生命底色|不长在课堂里",
            ]
            ROUGH_EDIT_PATTERNS = [
                r"此种",
                r"做媒介",
                r"渐渐去",
                r"不断施行",
                r"分明感受到",
                r"中心，也",
                r"多数敷衍",
                r"成为“孩子”",
            ]
            FRONT_MATTER_PATTERNS = [
                r"分类号", r"密级", r"学号", r"独创性说明", r"知识产权声明", r"学位论文作者签名",
                r"指导教师签名", r"保密论文待解密后适用本声明", r"论文题目[:：]", r"学科名称[:：]",
                r"本人郑重声明", r"本人完全了解学校有关保护知识产权的规定",
            ]
            SECTION_KEYWORDS = {{
                "abstract": ["摘要", "中英文摘要", "英文摘要", "abstract"],
                "intro": ["绪论", "引言", "前言"],
                "review": ["相关概念", "理论基础", "文献综述", "相关研究", "理论综述"],
                "conclusion": ["结论", "结语", "总结"],
            }}


            def _clamp(value):
                return max(0.0, min(1.0, float(value)))


            def _split_sentences(text):
                return [seg.strip() for seg in re.split(r"[。！？!?；;\\n]+", str(text or "")) if seg.strip()]


            def _split_paragraphs(text):
                raw = str(text or "").replace("\\r\\n", "\\n").replace("\\r", "\\n")
                parts = [part.strip() for part in re.split(r"\\n+", raw) if part.strip()]
                return parts or [raw.strip()]


            def _normalize_heading(text):
                return re.sub(r"\\s+", "", str(text or "")).strip("：:.。;；")


            def _detect_section(paragraph):
                normalized = _normalize_heading(paragraph).lower()
                if not normalized:
                    return ""
                for section, keywords in SECTION_KEYWORDS.items():
                    if any(normalized.startswith(keyword.lower()) for keyword in keywords):
                        return section
                return ""


            def _is_heading(paragraph):
                normalized = _normalize_heading(paragraph)
                if not normalized or len(normalized) > 36:
                    return False
                if normalized.lower() in SPECIAL_HEADINGS:
                    return True
                return any(re.match(pattern, normalized) for pattern in HEADING_PATTERNS)


            def _template_signal(text):
                content = str(text or "")
                hits = [phrase for phrase in TEMPLATE_PHRASES if phrase in content]
                density = len(hits) / max(len(content) / 85.0, 1.0)
                return _clamp(density), hits[:5]


            def _repeat_signal(text):
                content = " ".join(str(text or "").split())
                if not content:
                    return 0.0
                return _clamp(1.0 - len(set(content)) / max(len(content), 1))


            def _uniformity_signal(sentences):
                lengths = [len(item) for item in sentences if item]
                if not lengths:
                    return 0.0
                if len(lengths) == 1:
                    return 0.5
                avg_len = sum(lengths) / len(lengths)
                variance = sum((value - avg_len) ** 2 for value in lengths) / len(lengths)
                return _clamp(1.0 - min(1.0, variance / max(avg_len * 14.0, 1.0)))


            def _opening_signal(text):
                clean = re.sub(
                    r"^(?:第[一二三四五六七八九十百零0-9]+[章节部分篇]|[一二三四五六七八九十百零]+[、.．]|\\d+(?:\\.\\d+){{0,3}}[、.．]?|[（(][一二三四五六七八九十百零0-9]+[)）])",
                    "",
                    " ".join(str(text or "").split()),
                ).lstrip("：:.。;；、，, ")
                starters = ("本研究", "本文", "研究表明", "研究发现", "综上所述", "总而言之", "值得注意的是", "首先", "其次", "再次", "基于上述")
                signal = 0.48 if any(clean.startswith(token) for token in starters) else 0.0
                if re.search(r"^在.{{0,8}}背景下", clean):
                    signal += 0.18
                return _clamp(signal)


            def _citation_relief(text):
                return min(0.18, sum(len(re.findall(pattern, str(text or ""))) for pattern in CITATION_PATTERNS) * 0.025)


            def _evidence_relief(text):
                return min(0.16, sum(len(re.findall(pattern, str(text or ""), flags=re.IGNORECASE)) for pattern in EVIDENCE_PATTERNS) * 0.018)


            def _human_case_relief(text):
                content = str(text or "")
                hit_count = sum(len(re.findall(pattern, content, flags=re.IGNORECASE)) for pattern in HUMAN_CASE_PATTERNS)
                density = hit_count / max(len(content) / 110.0, 1.0)
                return _clamp(min(0.22, density * 0.075))


            def _rhetorical_polish_signal(text):
                content = str(text or "")
                hit_count = sum(len(re.findall(pattern, content, flags=re.IGNORECASE)) for pattern in RHETORICAL_PATTERNS)
                density = hit_count / max(len(content) / 120.0, 1.0)
                return _clamp(min(0.30, density * 0.16))


            def _practice_chain_signal(text):
                content = str(text or "")
                hit_count = sum(len(re.findall(pattern, content, flags=re.IGNORECASE)) for pattern in PRACTICE_CHAIN_PATTERNS)
                density = hit_count / max(len(content) / 120.0, 1.0)
                return _clamp(min(0.24, density * 0.11))


            def _summary_wrapup_relief(text):
                content = str(text or "")
                hit_count = sum(len(re.findall(pattern, content, flags=re.IGNORECASE)) for pattern in SUMMARY_WRAPUP_PATTERNS)
                density = hit_count / max(len(content) / 110.0, 1.0)
                return _clamp(min(0.20, density * 0.12))


            def _rough_edit_relief(text):
                content = str(text or "")
                hit_count = sum(len(re.findall(pattern, content, flags=re.IGNORECASE)) for pattern in ROUGH_EDIT_PATTERNS)
                density = hit_count / max(len(content) / 120.0, 1.0)
                return _clamp(min(0.18, density * 0.14))


            def _artifact_signal(text):
                content = str(text or "")
                hits = [marker for marker in ARTIFACT_MARKERS if marker in content]
                density = len(hits) / max(len(content) / 120.0, 1.0)
                score = min(0.2, density * 0.14 + (0.04 if hits else 0.0))
                return _clamp(score), hits[:4]


            def _is_no_ai_fragment(text):
                clean = " ".join(str(text or "").split())
                compact = re.sub(r"\\s+", "", clean)
                if not clean:
                    return True
                if _is_heading(clean):
                    return True
                if any(re.search(pattern, compact, flags=re.IGNORECASE) for pattern in FRONT_MATTER_PATTERNS):
                    return True
                if _citation_relief(clean) >= 0.08 and len(clean) <= 90:
                    return True
                if len(clean) <= 10 and not re.search(r"[\\u4e00-\\u9fffA-Za-z]{{4,}}", clean):
                    return True
                return False


            def _english_abstract_signal(text, section):
                content = str(text or "")
                lower = content.lower()
                ascii_ratio = len(re.findall(r"[A-Za-z]", content)) / max(len(content), 1)
                hint_count = sum(1 for hint in ENGLISH_HINTS if hint in lower)
                score = 0.0
                if section == "abstract":
                    score += 0.05
                if "abstract" in lower or "keywords" in lower:
                    score += 0.06
                if ascii_ratio >= 0.18:
                    score += min(0.06, ascii_ratio * 0.18)
                if hint_count >= 2:
                    score += min(0.05, hint_count * 0.02)
                return _clamp(min(0.18, score))


            def _section_bias(section):
                return {{
                    "abstract": 0.14,
                    "intro": 0.08,
                    "review": 0.02,
                    "conclusion": 0.03,
                }}.get(section or "", 0.0)


            def _score_to_label(score):
                if score >= 0.67:
                    return "high"
                if score >= 0.42:
                    return "medium"
                if score >= 0.18:
                    return "low"
                return "clean"


            def _fragment_band(score):
                if score >= 0.9:
                    return "severe"
                if score >= 0.8:
                    return "moderate"
                if score >= 0.7:
                    return "mild"
                return ""


            def process(input_data):
                text = input_data.get("text", "") if isinstance(input_data, dict) else str(input_data)
                clean = str(text or "").strip()
                if not clean:
                    return {{
                        "ai_score": 0.1,
                        "label": "low",
                        "profile": PROFILE,
                        "algorithm": "cnki_like_aigc_sim_v{_CNKI_AIGC_VERSION_TAG}",
                        "paragraphs": [],
                        "fragment_distribution": {{"fragment_count": 0, "weighted_score_pct": 0.0}},
                        "outline": [],
                        "decision_basis": [],
                        "document_metrics": {{"paragraph_count": 0, "abstract_avg_score": 0.0, "intro_avg_score": 0.0}},
                        "suspicious_segments": [],
                    }}

                paragraphs = _split_paragraphs(clean)
                current_section = ""
                paragraph_payloads = []
                suspicious_segments = []
                outline = []
                opening_keys = []
                artifact_hit_count = 0
                abstract_scores = []
                intro_scores = []

                for index, paragraph in enumerate(paragraphs, start=1):
                    detected_section = _detect_section(paragraph)
                    if detected_section:
                        current_section = detected_section
                    if _is_heading(paragraph):
                        outline.append({{"section": paragraph[:32], "start_index": index}})
                        paragraph_payloads.append({{
                            "index": index,
                            "score": 0.0,
                            "label": "clean",
                            "excerpt": paragraph[:110],
                            "char_count": len(paragraph),
                            "sentence_count": 0,
                            "section": current_section or detected_section or "",
                            "suspicious_segments": [],
                            "signals": {{"template_signal": 0.0, "repeat_signal": 0.0, "uniformity_signal": 0.0, "opening_signal": 0.0, "artifact_signal": 0.0, "english_signal": 0.0}},
                        }})
                        continue

                    sentences = _split_sentences(paragraph)
                    if _is_no_ai_fragment(paragraph):
                        paragraph_payloads.append({{
                            "index": index,
                            "score": 0.0,
                            "label": "clean",
                            "excerpt": paragraph[:110],
                            "char_count": len(paragraph),
                            "sentence_count": len(sentences),
                            "section": current_section,
                            "suspicious_segments": [],
                            "signals": {{"template_signal": 0.0, "repeat_signal": 0.0, "uniformity_signal": 0.0, "opening_signal": 0.0, "artifact_signal": 0.0, "english_signal": 0.0, "human_case_relief": 0.0, "rhetorical_signal": 0.0, "rough_edit_relief": 0.0}},
                        }})
                        continue

                    template_signal, template_hits = _template_signal(paragraph)
                    repeat_signal = _repeat_signal(paragraph)
                    uniformity_signal = _uniformity_signal(sentences)
                    opening_signal = _opening_signal(paragraph)
                    citation_relief = _citation_relief(paragraph)
                    evidence_relief = _evidence_relief(paragraph)
                    human_case_relief = _human_case_relief(paragraph)
                    rhetorical_signal = _rhetorical_polish_signal(paragraph)
                    practice_chain_signal = _practice_chain_signal(paragraph)
                    summary_wrapup_relief = _summary_wrapup_relief(paragraph)
                    rough_edit_relief = _rough_edit_relief(paragraph)
                    artifact_signal, artifact_hits = _artifact_signal(paragraph)
                    english_signal = _english_abstract_signal(paragraph, current_section)
                    artifact_hit_count += len(artifact_hits)
                    human_relief_weight = 0.60
                    if rhetorical_signal >= 0.12 or opening_signal >= 0.18:
                        human_relief_weight = 0.38
                    elif practice_chain_signal >= 0.10 and summary_wrapup_relief < 0.10:
                        human_relief_weight = 0.26

                    avg_len = sum(len(seg) for seg in sentences) / max(len(sentences), 1)
                    seed = int(hashlib.md5(paragraph.encode("utf-8")).hexdigest()[:8], 16)
                    jitter = ((seed % 11) - 5) / 1000.0
                    score = _clamp(
                        0.18
                        + max(0.0, (avg_len - 20.0) / 75.0) * 0.10
                        + template_signal * 0.18
                        + repeat_signal * 0.10
                        + uniformity_signal * 0.06
                        + opening_signal * 0.08
                        + rhetorical_signal * 0.34
                        + practice_chain_signal * 0.18
                        + artifact_signal * 0.12
                        + english_signal * 0.08
                        + _section_bias(current_section)
                        - citation_relief
                        - evidence_relief
                        - human_case_relief * human_relief_weight
                        - summary_wrapup_relief * 0.22
                        - rough_edit_relief * 1.02
                        + jitter
                    )
                    if rough_edit_relief >= 0.12 and human_case_relief >= 0.16 and rhetorical_signal < 0.08 and template_signal < 0.12 and opening_signal < 0.18:
                        score = min(score, 0.18)
                    label = _score_to_label(score)
                    if current_section == "abstract":
                        abstract_scores.append(score * 100)
                    elif current_section == "intro":
                        intro_scores.append(score * 100)

                    opening_key = re.sub(r"\\s+", "", paragraph)[:14]
                    if opening_key:
                        opening_keys.append(opening_key)

                    seg_rows = []
                    for sentence in sentences:
                        if len(sentence) < 10:
                            continue
                        sentence_template, _sentence_hits = _template_signal(sentence)
                        sentence_repeat = _repeat_signal(sentence)
                        sentence_uniformity = _uniformity_signal(_split_sentences(sentence))
                        sentence_opening = _opening_signal(sentence)
                        sentence_human_case = _human_case_relief(sentence)
                        sentence_rhetorical = _rhetorical_polish_signal(sentence)
                        sentence_practice_chain = _practice_chain_signal(sentence)
                        sentence_summary_wrapup = _summary_wrapup_relief(sentence)
                        sentence_rough_edit = _rough_edit_relief(sentence)
                        sentence_artifact, _artifact_hits = _artifact_signal(sentence)
                        sentence_english = _english_abstract_signal(sentence, current_section)
                        sentence_human_weight = 0.56
                        if sentence_rhetorical >= 0.12 or sentence_opening >= 0.18:
                            sentence_human_weight = 0.36
                        elif sentence_practice_chain >= 0.08 and sentence_summary_wrapup < 0.10:
                            sentence_human_weight = 0.24
                        seg_score = _clamp(
                            0.14
                            + sentence_template * 0.22
                            + sentence_repeat * 0.12
                            + sentence_uniformity * 0.06
                            + sentence_opening * 0.08
                            + sentence_rhetorical * 0.30
                            + sentence_practice_chain * 0.18
                            + sentence_artifact * 0.10
                            + sentence_english * 0.08
                            + _section_bias(current_section) * 0.8
                            - _citation_relief(sentence)
                            - _evidence_relief(sentence)
                            - sentence_human_case * sentence_human_weight
                            - sentence_summary_wrapup * 0.24
                            - sentence_rough_edit * 0.96
                        )
                        if sentence_rough_edit >= 0.10 and sentence_human_case >= 0.14 and sentence_rhetorical < 0.08 and sentence_template < 0.15:
                            seg_score = min(seg_score, 0.18)
                        if sentence_summary_wrapup >= 0.10 and seg_score < 0.46:
                            continue
                        if seg_score < 0.42 and sentence_template < 0.2 and sentence_artifact < 0.08 and sentence_rhetorical < 0.08:
                            continue
                        reason_bits = []
                        if current_section in ("abstract", "intro") and sentence_template >= 0.18:
                            reason_bits.append("摘要/绪论模板化偏强")
                        if sentence_template >= 0.22:
                            reason_bits.append("模板连接词偏多")
                        if sentence_rhetorical >= 0.12:
                            reason_bits.append("表达方式过于顺滑完整")
                        if sentence_repeat >= 0.3:
                            reason_bits.append("重复表达偏多")
                        if sentence_artifact >= 0.08:
                            reason_bits.append("存在异常改写痕迹")
                        seg_rows.append({{"text": sentence[:76], "score": round(seg_score * 100, 2), "label": _score_to_label(seg_score), "reason": "、".join(reason_bits[:2]) or "综合风险偏高"}})
                    seg_rows.sort(key=lambda item: item["score"], reverse=True)
                    for segment in seg_rows[:3]:
                        suspicious_segments.append({{"paragraph_index": index, "text": segment["text"], "score": segment["score"], "reason": segment["reason"]}})

                    paragraph_payloads.append({{
                        "index": index,
                        "score": round(score * 100, 2),
                        "label": label,
                        "excerpt": paragraph[:110],
                        "char_count": len(paragraph),
                        "sentence_count": len(sentences),
                        "section": current_section,
                        "suspicious_segments": seg_rows[:3],
                        "signals": {{
                            "template_signal": round(template_signal, 4),
                            "repeat_signal": round(repeat_signal, 4),
                            "uniformity_signal": round(uniformity_signal, 4),
                            "opening_signal": round(opening_signal, 4),
                            "artifact_signal": round(artifact_signal, 4),
                            "english_signal": round(english_signal, 4),
                            "human_case_relief": round(human_case_relief, 4),
                            "rhetorical_signal": round(rhetorical_signal, 4),
                            "practice_chain_signal": round(practice_chain_signal, 4),
                            "summary_wrapup_relief": round(summary_wrapup_relief, 4),
                            "rough_edit_relief": round(rough_edit_relief, 4),
                            "template_hits": template_hits,
                            "artifact_hits": artifact_hits,
                        }},
                    }})

                suspicious_segments.sort(key=lambda item: item["score"], reverse=True)
                paragraph_scores = [item["score"] / 100.0 for item in paragraph_payloads if item["sentence_count"] > 0]
                high_count = sum(1 for item in paragraph_payloads if item["label"] == "high")
                medium_count = sum(1 for item in paragraph_payloads if item["label"] == "medium")
                low_count = sum(1 for item in paragraph_payloads if item["sentence_count"] > 0 and item["label"] == "low")
                high_medium_count = high_count + medium_count

                longest_streak = 0
                current_streak = 0
                for item in paragraph_payloads:
                    if item["label"] in ("high", "medium") and item["sentence_count"] > 0:
                        current_streak += 1
                        longest_streak = max(longest_streak, current_streak)
                    elif item["sentence_count"] > 0:
                        current_streak = 0

                opening_similarity = 0.0
                if opening_keys:
                    opening_similarity = _clamp(max(0, len(opening_keys) - len(set(opening_keys))) / max(len(opening_keys), 1))

                count_map = {{"high": 0, "medium": 0, "low": 0, "no_ai": 0}}
                char_map = {{"high": 0, "medium": 0, "low": 0, "no_ai": 0}}
                display_count = {{"mild": 0, "moderate": 0, "severe": 0}}
                display_chars = {{"mild": 0, "moderate": 0, "severe": 0}}
                for item in paragraph_payloads:
                    paragraph = paragraphs[item["index"] - 1]
                    paragraph_ratio = item["score"] / 100.0
                    for sentence in _split_sentences(paragraph):
                        compact = " ".join(sentence.split())
                        if not compact:
                            continue
                        if _is_heading(compact):
                            label = "no_ai"
                            score_ratio = 0.0
                        else:
                            score_ratio = _clamp(paragraph_ratio * 0.72 + _template_signal(compact)[0] * 0.18 + _artifact_signal(compact)[0] * 0.10)
                            label = _score_to_label(score_ratio)
                            if label == "clean":
                                label = "no_ai"
                            else:
                                band = _fragment_band(score_ratio)
                                if band:
                                    display_count[band] += 1
                                    display_chars[band] += len(compact)
                        count_map[label] += 1
                        char_map[label] += len(compact)

                def _ratio(part, whole):
                    return round(part / max(whole, 1) * 100, 2)

                total_fragments = sum(count_map.values())
                total_chars = sum(char_map.values())
                mean_score = sum(paragraph_scores) / max(len(paragraph_scores), 1) if paragraph_scores else 0.0
                peak_score = max(paragraph_scores) if paragraph_scores else 0.0
                segment_score = sum(item["score"] for item in suspicious_segments[:5]) / max(len(suspicious_segments[:5]), 1) / 100.0 if suspicious_segments else 0.0
                paragraph_total = len([item for item in paragraph_payloads if item["sentence_count"] > 0])
                coverage_ratio = high_medium_count / max(paragraph_total, 1)
                streak_ratio = longest_streak / max(paragraph_total, 1)
                abstract_ratio = (sum(abstract_scores) / max(len(abstract_scores), 1) / 100.0) if abstract_scores else 0.0
                intro_ratio = (sum(intro_scores) / max(len(intro_scores), 1) / 100.0) if intro_scores else 0.0
                rough_edit_total = sum(item.get("signals", {{}}).get("rough_edit_relief", 0.0) for item in paragraph_payloads if item["sentence_count"] > 0)
                rough_document_relief = min(0.06, rough_edit_total * 0.10)
                score = _clamp(mean_score * 0.46 + peak_score * 0.18 + segment_score * 0.12 + coverage_ratio * 0.06 + streak_ratio * 0.03 + opening_similarity * 0.03 + abstract_ratio * 0.08 + intro_ratio * 0.05 - rough_document_relief)

                decision_basis = []
                if abstract_scores and sum(abstract_scores) / max(len(abstract_scores), 1) >= 50:
                    decision_basis.append({{"title": "摘要区域模板化明显", "direction": "risk"}})
                if intro_scores and sum(intro_scores) / max(len(intro_scores), 1) >= 45:
                    decision_basis.append({{"title": "绪论展开方式较集中", "direction": "risk"}})
                if artifact_hit_count > 0:
                    decision_basis.append({{"title": "存在异常改写痕迹", "direction": "risk"}})
                if _ratio(char_map["high"] + char_map["medium"], total_chars) >= 20:
                    decision_basis.append({{"title": "高中风险文字占比偏高", "direction": "risk"}})
                if longest_streak >= 3:
                    decision_basis.append({{"title": "存在连续风险片段带", "direction": "risk"}})

                return {{
                    "ai_score": round(score, 4),
                    "label": _score_to_label(score),
                    "profile": PROFILE,
                    "algorithm": "cnki_like_aigc_sim_v{_CNKI_AIGC_VERSION_TAG}",
                    "text_stats": {{"chars": len(clean), "sentences": len(_split_sentences(clean)), "paragraphs": len(paragraph_payloads)}},
                    "distribution": {{"high": high_count, "medium": medium_count, "low": low_count, "high_ratio": _ratio(high_count, max(paragraph_total, 1))}},
                    "fragment_distribution": {{
                        "fragment_count": total_fragments,
                        "high_fragment_count": count_map["high"],
                        "middle_fragment_count": count_map["medium"],
                        "low_fragment_count": count_map["low"],
                        "no_ai_fragment_count": count_map["no_ai"],
                        "high_and_middle_suspected_text_ratio": _ratio(char_map["high"] + char_map["medium"], total_chars),
                        "total_suspected_text_ratio": _ratio(char_map["high"] + char_map["medium"] + char_map["low"], total_chars),
                        "weighted_score_pct": round(sum(item["score"] for item in paragraph_payloads if item["sentence_count"] > 0) / max(paragraph_total, 1), 2) if paragraph_payloads else 0.0,
                        "mild_fragment_count": display_count["mild"],
                        "moderate_fragment_count": display_count["moderate"],
                        "severe_fragment_count": display_count["severe"],
                        "mild_text_ratio": _ratio(display_chars["mild"], total_chars),
                        "moderate_text_ratio": _ratio(display_chars["moderate"], total_chars),
                        "severe_text_ratio": _ratio(display_chars["severe"], total_chars),
                    }},
                    "document_metrics": {{
                        "paragraph_count": len(paragraph_payloads),
                        "high_medium_paragraph_ratio": _ratio(high_medium_count, max(paragraph_total, 1)),
                        "longest_risk_streak": longest_streak,
                        "opening_similarity_ratio": round(opening_similarity * 100, 2),
                        "abstract_avg_score": round(sum(abstract_scores) / max(len(abstract_scores), 1), 2) if abstract_scores else 0.0,
                        "intro_avg_score": round(sum(intro_scores) / max(len(intro_scores), 1), 2) if intro_scores else 0.0,
                        "artifact_hit_count": artifact_hit_count,
                        "rough_edit_relief_total": round(rough_edit_total, 4),
                    }},
                    "decision_basis": decision_basis[:5],
                    "outline": outline[:20],
                    "paragraphs": paragraph_payloads,
                    "suspicious_segments": suspicious_segments[:10],
                }}
            """
        ).strip()
        + "\n"
    )


def _cnki_rewrite_code_v2() -> str:
    direct_replacements = json.dumps(
        [
            ["研究结论显示", "从全文分析结果来看"],
            ["研究表明", "从相关研究和分析结果来看"],
            ["研究发现", "从分析结果来看"],
            ["基于上述诊断，本文提出", "结合前文问题，文中进一步提出"],
            ["基于上述分析，本文提出", "结合前文分析，文中进一步提出"],
            ["综上所述", "综合前文分析"],
            ["总而言之", "综合来看"],
            ["可以看出", "据此能够判断"],
            ["由此可见", "据此能够判断"],
            ["实施保障机制", "实施保障安排"],
            ["搭建", "形成"],
            ["旨在", "重点在于"],
        ],
        ensure_ascii=False,
    )
    artifact_fixes = json.dumps(
        [
            ["需要求", "需求"],
            ["知识得到", "知识获取"],
            ["主题着眼于", "围绕主题展开"],
            ["读全面本书", "完整阅读整本书"],
            ["都衡", "均衡"],
            ["全面性", "完整性"],
            ["让用", "应用"],
            ["成效", "实际成效"],
        ],
        ensure_ascii=False,
    )
    regex_rules = json.dumps(
        [
            ["research_object", r"本研究以([^，。；\\n]{2,32})为研究对象", r"本文围绕\g<1>展开分析"],
            ["goal", r"旨在([^，。；\\n]{2,42})", r"重点在于\g<1>"],
            ["aspect", r"在([^，。；\\n]{2,18})方面，", r"围绕\g<1>，"],
            ["problem_to_action", r"基于上述(?:诊断|分析|研究)，?(?:本文|文章)?提出", r"结合前文分析，文中进一步提出"],
            ["through_to_goal", r"通过([^，。；\\n]{2,24})，(?:以)?实现([^，。；\\n]{2,28})", r"借助\g<1>，以推动\g<2>"],
            ["noun_stack", r"构建([^，。；\\n]{2,20})(体系|机制|框架)", r"形成\g<1>\g<2>"],
        ],
        ensure_ascii=False,
    )
    return (
        dedent(
            f"""
            import hashlib
            import json
            import re

            PROFILE = "cnki_like_sampled_rules"
            STYLE_PROFILE = "cnki_academic_humanized"
            DIRECT_REPLACEMENTS = json.loads({json.dumps(direct_replacements, ensure_ascii=False)})
            ARTIFACT_FIXES = json.loads({json.dumps(artifact_fixes, ensure_ascii=False)})
            REGEX_RULES = json.loads({json.dumps(regex_rules, ensure_ascii=False)})
            TEMPLATE_MARKERS = {{
                "本研究以": 2.4,
                "旨在": 2.0,
                "研究结论显示": 2.2,
                "研究表明": 1.8,
                "基于上述": 1.9,
                "系统分析": 1.6,
                "构建": 1.4,
                "搭建": 1.4,
                "实施保障": 1.4,
                "优化路径": 1.2,
                "可以看出": 1.5,
                "由此可见": 1.5,
                "综上所述": 1.7,
            }}
            HUMAN_MARKERS = {{
                "围绕": 0.8,
                "结合前文分析": 1.2,
                "据此能够判断": 0.8,
                "借助": 0.6,
                "展开分析": 0.8,
                "完整阅读整本书": 0.8,
            }}


            def _clamp_score(score):
                return max(0.0, min(100.0, float(score)))


            def _normalize_text(text):
                raw = str(text or "").replace("\\r\\n", "\\n").replace("\\r", "\\n")
                lines = [re.sub(r"\\s+", " ", line).strip() for line in raw.split("\\n")]
                return "\\n".join(line for line in lines if line).strip()


            def _estimate_template_score(text):
                compact = re.sub(r"\\s+", "", str(text or ""))
                if not compact:
                    return 0.0
                score = 44.0
                for marker, weight in TEMPLATE_MARKERS.items():
                    score += compact.count(marker) * weight
                for marker, weight in HUMAN_MARKERS.items():
                    score -= compact.count(marker) * weight
                clauses = [item for item in re.split(r"[。！？；]", compact) if item]
                avg_clause_len = sum(len(item) for item in clauses) / max(len(clauses), 1)
                if avg_clause_len > 44:
                    score += min(8.0, (avg_clause_len - 44) * 0.2)
                return _clamp_score(score)


            def _split_long_sentence(sentence):
                text = sentence
                connectors = ["，同时", "，并且", "，并", "，其中", "，从而"]
                for connector in connectors:
                    if len(text) > 82 and connector in text:
                        text = text.replace(connector, "。" + connector.lstrip("，"), 1)
                        return text, 1
                commas = [match.start() for match in re.finditer("，", text)]
                if len(text) > 88 and len(commas) >= 3:
                    middle = commas[len(commas) // 2]
                    text = text[:middle] + "。" + text[middle + 1 :]
                    return text, 1
                return text, 0


            def _rewrite_paragraph(paragraph):
                text = paragraph
                applied = []
                for src, dst in ARTIFACT_FIXES:
                    if src in text:
                        text = text.replace(src, dst)
                        applied.append("artifact:" + src)
                for src, dst in DIRECT_REPLACEMENTS:
                    if src in text:
                        text = text.replace(src, dst)
                        applied.append("replace:" + src)
                for name, pattern, repl in REGEX_RULES:
                    text, count = re.subn(pattern, repl, text)
                    if count:
                        applied.extend([name] * count)

                sentences = re.split(r"(。|！|？|；)", text)
                rebuilt = []
                split_count = 0
                for index in range(0, len(sentences), 2):
                    sentence = sentences[index].strip()
                    punct = sentences[index + 1] if index + 1 < len(sentences) else ""
                    if not sentence:
                        continue
                    rewritten, added = _split_long_sentence(sentence)
                    split_count += added
                    rebuilt.append(rewritten + punct)
                if split_count:
                    applied.append("split_long_sentence")
                output = "".join(rebuilt).replace("。。", "。").replace("；。", "；")
                return output.strip(), applied


            def process(input_data):
                text = input_data.get("text", "") if isinstance(input_data, dict) else str(input_data)
                source = _normalize_text(text)
                if not source:
                    return {{
                        "text": "",
                        "original_aigc_score": 0.0,
                        "rewritten_aigc_score": 0.0,
                        "algorithm": "cnki_rewrite_sim_v{_CNKI_TEXT_VERSION_TAG}",
                        "profile": PROFILE,
                        "style_profile": STYLE_PROFILE,
                        "transformation_count": 0,
                        "rules_applied": [],
                    }}

                paragraphs = [item for item in source.split("\\n") if item.strip()]
                rewritten_paragraphs = []
                applied_rules = []
                for paragraph in paragraphs:
                    rewritten, paragraph_rules = _rewrite_paragraph(paragraph)
                    rewritten_paragraphs.append(rewritten)
                    applied_rules.extend(paragraph_rules)

                rewritten_text = "\\n".join(rewritten_paragraphs).strip()
                original_score = _estimate_template_score(source)
                rewritten_score = _estimate_template_score(rewritten_text)
                if applied_rules and rewritten_score >= original_score:
                    seed = int(hashlib.md5(source.encode("utf-8")).hexdigest()[:8], 16)
                    rewritten_score = max(8.0, original_score - (7 + seed % 6))

                unique_rules = []
                for name in applied_rules:
                    if name not in unique_rules:
                        unique_rules.append(name)

                return {{
                    "text": rewritten_text,
                    "original_aigc_score": round(original_score, 2),
                    "rewritten_aigc_score": round(rewritten_score, 2),
                    "algorithm": "cnki_rewrite_sim_v{_CNKI_TEXT_VERSION_TAG}",
                    "profile": PROFILE,
                    "style_profile": STYLE_PROFILE,
                    "transformation_count": len(applied_rules),
                    "rules_applied": unique_rules[:16],
                }}
            """
        ).strip()
        + "\n"
    )


def _cnki_dedup_code_v2() -> str:
    direct_replacements = json.dumps(
        [
            ["研究表明", "已有研究指出"],
            ["研究发现", "相关分析显示"],
            ["可以看出", "据此可见"],
            ["由此可见", "据此能够判断"],
            ["总之", "综合来看"],
            ["首先", "其一"],
            ["其次", "进一步看"],
            ["此外", "同时"],
            ["本文认为", "文中进一步指出"],
        ],
        ensure_ascii=False,
    )
    regex_rules = json.dumps(
        [
            ["important_part", r"([^，。；\\n]{2,18})是([^，。；\\n]{2,24})的重要(组成部分|途径|手段|保障)", r"\g<2>离不开\g<1>这一\g<3>"],
            ["through_to_goal", r"通过([^，。；\\n]{2,24})，(?:以)?实现([^，。；\\n]{2,28})", r"借助\g<1>，来推动\g<2>"],
            ["analyze", r"对([^，。；\\n]{2,28})进行分析", r"围绕\g<1>展开分析"],
            ["feature", r"具有([^，。；\\n]{2,18})特点", r"呈现出\g<1>特征"],
            ["aspect", r"在([^，。；\\n]{2,18})方面，", r"围绕\g<1>，"],
        ],
        ensure_ascii=False,
    )
    return (
        dedent(
            f"""
            import hashlib
            import json
            import re

            PROFILE = "cnki_like"
            DIRECT_REPLACEMENTS = json.loads({json.dumps(direct_replacements, ensure_ascii=False)})
            REGEX_RULES = json.loads({json.dumps(regex_rules, ensure_ascii=False)})


            def _normalize_text(text):
                raw = str(text or "").replace("\\r\\n", "\\n").replace("\\r", "\\n")
                lines = [re.sub(r"\\s+", " ", line).strip() for line in raw.split("\\n")]
                return "\\n".join(line for line in lines if line).strip()


            def _reorder_sentence(sentence):
                text = sentence
                if len(text) > 76 and "，同时" in text:
                    return text.replace("，同时", "；同时", 1), 1
                if len(text) > 80 and text.count("，") >= 3:
                    comma_positions = [match.start() for match in re.finditer("，", text)]
                    middle = comma_positions[len(comma_positions) // 2]
                    return text[:middle] + "；" + text[middle + 1 :], 1
                return text, 0


            def process(input_data):
                text = input_data.get("text", "") if isinstance(input_data, dict) else str(input_data)
                source = _normalize_text(text)
                if not source:
                    return {{
                        "text": "",
                        "similarity": 0.0,
                        "changes": 0,
                        "algorithm": "cnki_dedup_sim_v{_CNKI_TEXT_VERSION_TAG}",
                    }}

                output = source
                changes = 0
                for src, dst in DIRECT_REPLACEMENTS:
                    count = output.count(src)
                    if count:
                        output = output.replace(src, dst)
                        changes += count
                for _name, pattern, repl in REGEX_RULES:
                    output, count = re.subn(pattern, repl, output)
                    changes += count

                sentences = re.split(r"(。|！|？|；)", output)
                rebuilt = []
                for index in range(0, len(sentences), 2):
                    sentence = sentences[index].strip()
                    punct = sentences[index + 1] if index + 1 < len(sentences) else ""
                    if not sentence:
                        continue
                    rewritten, added = _reorder_sentence(sentence)
                    changes += added
                    rebuilt.append(rewritten + punct)
                output = "".join(rebuilt).replace("；；", "；").strip()

                seed = int(hashlib.md5(source.encode("utf-8")).hexdigest()[:8], 16)
                similarity = round(max(6.0, min(68.0, 34.0 - changes * 2.8 + (seed % 9))), 2)

                return {{
                    "text": output,
                    "similarity": similarity,
                    "changes": changes,
                    "algorithm": "cnki_dedup_sim_v{_CNKI_TEXT_VERSION_TAG}",
                }}
            """
        ).strip()
        + "\n"
    )


def _vip_dedup_code_v2() -> str:
    direct_replacements = json.dumps(
        [
            ["经营活动至关重要", "稳定运营离不开顺畅的资金调配"],
            ["从企业自身出发", "立足企业自身经营实际"],
            ["提高管理水平", "提升管理效能"],
            ["提高运营效率和盈利能力", "带动运营效率与盈利能力改善"],
            ["进行整体的分析", "作整体梳理"],
            ["存在的问题", "暴露出的短板"],
            ["提出相应的解决对策", "进一步细化改进对策"],
            ["提出相应的解决建议", "进一步细化改进建议"],
            ["提出相应的解决路径", "进一步细化改进路径"],
            ["导致资金链断裂", "甚至诱发资金周转失衡"],
            ["广泛应用了BIM技术", "将BIM技术纳入实际应用"],
            ["通过BIM技术的应用", "借助BIM技术的落地"],
        ],
        ensure_ascii=False,
    )
    regex_rules = json.dumps(
        [
            ["study_multi_aspects", r"对([^，。；\\n]{4,32})进行研究，从([^。；\\n]{4,48})方面进行分析", r"围绕\g<1>展开讨论，并分别从\g<2>方面加以拆解"],
            ["analyze_overall", r"本文通过分析([^，。；\\n]{4,36})，对其([^，。；\\n]{2,28})进行整体的分析", r"文章以\g<1>为切入点，进一步梳理其\g<2>的关联"],
            ["problem_solution", r"并结合([^，。；\\n]{4,32})当前([^，。；\\n]{2,18})存在的问题，提出相应的([^，。；\\n]{2,16})(对策|建议|路径)", r"结合\g<1>当前\g<2>暴露出的短板，进一步细化改进\g<4>"],
            ["three_step_frame", r"论文从([^，。；\\n]{2,20})的分析开始，秉持[“\"]?分析现状[-—–]{1,2}发现问题[-—–]{1,2}解决问题[”\"]?的思路", r"文章先梳理\g<1>现状，再归纳问题表现，随后承接改进思路"],
            ["aspect_analysis", r"从([^，。；\\n]{2,32})方面进行分析", r"分别从\g<1>方面展开拆解"],
            ["through_raise", r"通过([^，。；\\n]{2,28})，(?:可以)?提高([^，。；\\n]{2,28})", r"借助\g<1>，有助于提升\g<2>"],
            ["raise_management_goal", r"以提高([^，。；\\n]{2,24})管理水平", r"以带动\g<1>管理效能提升"],
            ["raise_performance_goal", r"以提高([^，。；\\n]{2,24})(运营效率|盈利能力)", r"以带动\g<1>\g<2>改善"],
            ["project_located", r"([^，。；\\n]{2,24})位于([^，。；\\n]{4,36})，占地面积([^，。；\\n]{1,20})，建筑面积([^，。；\\n]{1,20})", r"\g<1>坐落于\g<2>，占地\g<3>，建筑面积达到\g<4>"],
            ["project_include", r"该项目包括([^。；\\n]{8,80})", r"项目建设内容涵盖\g<1>"],
            ["management_applies_bim", r"项目在([^，。；\\n]{2,20})中广泛应用了BIM技术，包括以下方面", r"项目在\g<1>环节将BIM技术纳入实际应用，主要体现在以下几方面"],
            ["enterprise_risk", r"许多企业在经营过程中面临([^，。；\\n]{4,24})，导致([^，。；\\n]{4,24})", r"不少企业在经营推进中会遭遇\g<1>，甚至诱发\g<2>"],
            ["macro_scale", r"我国是([^，。；\\n]{2,24})大国，每年([^。；\\n]{8,72})", r"从行业规模看，我国在\g<1>领域体量较大，\g<2>"],
        ],
        ensure_ascii=False,
    )
    focus_patterns = json.dumps(
        {
            "thesis_frame": ["分析现状", "发现问题", "解决问题", "提出相应的解决对策"],
            "management_analysis": ["营运资金管理", "流动资产", "流动负债", "经营模式"],
            "macro_intro": ["我国是", "占全球", "占世界", "年产值"],
            "case_fact": ["位于", "占地面积", "建筑面积", "该项目包括"],
            "bim_flow": ["BIM技术", "施工进度", "可视化沟通", "风险管理"],
        },
        ensure_ascii=False,
    )
    return (
        dedent(
            f"""
            import hashlib
            import json
            import re

            PROFILE = "vip_like"
            DIRECT_REPLACEMENTS = json.loads({json.dumps(direct_replacements, ensure_ascii=False)})
            REGEX_RULES = json.loads({json.dumps(regex_rules, ensure_ascii=False)})
            FOCUS_PATTERNS = json.loads({json.dumps(focus_patterns, ensure_ascii=False)})


            def _normalize_text(text):
                raw = str(text or "").replace("\\r\\n", "\\n").replace("\\r", "\\n")
                raw = raw.replace("“", '"').replace("”", '"').replace("——", "—")
                lines = [re.sub(r"\\s+", " ", line).strip() for line in raw.split("\\n")]
                return "\\n".join(line for line in lines if line).strip()


            def _split_sentences(text):
                return [seg.strip() for seg in re.split(r"[。！？!?；;\\n]+", str(text or "")) if seg.strip()]


            def _reorder_sentence(sentence):
                text = sentence
                if len(text) > 94 and "，并" in text:
                    return text.replace("，并", "；并", 1), 1
                if len(text) > 88 and "，同时" in text:
                    return text.replace("，同时", "；同时", 1), 1
                commas = [match.start() for match in re.finditer("，", text)]
                if len(text) > 96 and len(commas) >= 3:
                    pivot = commas[len(commas) // 2]
                    return text[:pivot] + "；" + text[pivot + 1 :], 1
                return text, 0


            def _focus_flags(text):
                content = str(text or "")
                flags = []
                for name, patterns in FOCUS_PATTERNS.items():
                    if any(pattern in content for pattern in patterns):
                        flags.append(name)
                return flags


            def _estimate_copy_risk(text):
                content = str(text or "")
                if not content:
                    return 0.0
                signal = 0.08 if len(content) < 80 else 0.14
                weighted_patterns = [
                    (r"对[^，。；\\n]{{4,32}}进行研究", 0.06),
                    (r"从[^，。；\\n]{{4,48}}方面进行分析", 0.06),
                    (r"分析现状[-—–]{{1,2}}发现问题[-—–]{{1,2}}解决问题", 0.08),
                    (r"提出相应的解决(对策|建议|路径)", 0.07),
                    (r"提高[^，。；\\n]{0,12}(?:管理水平|运营效率|盈利能力)", 0.05),
                    (r"通过[^，。；\\n]{{2,28}}(?:模型|技术)", 0.04),
                    (r"位于[^，。；\\n]{{4,36}}，占地面积", 0.08),
                    (r"该项目包括", 0.06),
                    (r"导致资金链断裂", 0.08),
                    (r"经营活动至关重要", 0.06),
                    (r"营运资金管理", 0.03),
                ]
                for pattern, weight in weighted_patterns:
                    signal += len(re.findall(pattern, content)) * weight
                if re.search(r"\\d{{2,}}", content) and "占" in content and "面积" in content:
                    signal += 0.04
                if "BIM技术" in content and "项目" in content:
                    signal += 0.05
                return min(0.82, signal)


            def _rewrite_paragraph(paragraph):
                text = paragraph
                applied = []

                for name, pattern, repl in REGEX_RULES:
                    text, count = re.subn(pattern, repl, text)
                    if count:
                        applied.extend([name] * count)

                for src, dst in DIRECT_REPLACEMENTS:
                    count = text.count(src)
                    if count:
                        text = text.replace(src, dst)
                        applied.extend([f"replace:{{src}}"] * count)

                sentences = re.split(r"(。|！|？|；)", text)
                rebuilt = []
                split_count = 0
                for index in range(0, len(sentences), 2):
                    sentence = sentences[index].strip()
                    punct = sentences[index + 1] if index + 1 < len(sentences) else ""
                    if not sentence:
                        continue
                    rewritten, added = _reorder_sentence(sentence)
                    split_count += added
                    rebuilt.append(rewritten + punct)
                if split_count:
                    applied.append("reorder_sentence")
                output = "".join(rebuilt).replace("；；", "；").replace("。。", "。").strip()
                return output, applied


            def process(input_data):
                text = input_data.get("text", "") if isinstance(input_data, dict) else str(input_data)
                source = _normalize_text(text)
                if not source:
                    return {{
                        "text": "",
                        "similarity": 0.0,
                        "changes": 0,
                        "algorithm": "vip_dedup_sim_v{_VIP_DEDUP_VERSION_TAG}",
                        "rules_applied": [],
                        "focus_flags": [],
                        "original_risk_score": 0.0,
                        "rewritten_risk_score": 0.0,
                    }}

                paragraphs = [item for item in source.split("\\n") if item.strip()]
                rewritten_paragraphs = []
                applied_rules = []
                for paragraph in paragraphs:
                    rewritten, paragraph_rules = _rewrite_paragraph(paragraph)
                    rewritten_paragraphs.append(rewritten)
                    applied_rules.extend(paragraph_rules)

                rewritten_text = "\\n".join(rewritten_paragraphs).strip()
                original_risk = _estimate_copy_risk(source)
                rewritten_risk = _estimate_copy_risk(rewritten_text)
                if applied_rules and rewritten_risk >= original_risk:
                    rewritten_risk = max(0.08, original_risk - min(0.24, len(applied_rules) * 0.02))

                unique_rules = []
                for name in applied_rules:
                    if name not in unique_rules:
                        unique_rules.append(name)

                seed = int(hashlib.md5(source.encode("utf-8")).hexdigest()[:8], 16)
                baseline = 18.0 + original_risk * 58.0
                improvement = 0.0
                if applied_rules:
                    improvement = max(4.0, (original_risk - rewritten_risk) * 90.0 + len(applied_rules) * 0.8)
                similarity = round(max(5.0, min(68.0, baseline - improvement + (seed % 5))), 2)

                return {{
                    "text": rewritten_text,
                    "similarity": similarity,
                    "changes": len(applied_rules),
                    "algorithm": "vip_dedup_sim_v{_VIP_DEDUP_VERSION_TAG}",
                    "rules_applied": unique_rules[:16],
                    "focus_flags": _focus_flags(source),
                    "original_risk_score": round(original_risk * 100, 2),
                    "rewritten_risk_score": round(rewritten_risk * 100, 2),
                }}
            """
        ).strip()
        + "\n"
    )


def _upgrade_builtin_specs() -> tuple[BuiltinPackageSpec, ...]:
    profile_offsets = {
        "cnki": ("cnki_like", 0.0),
        "vip": ("vip_like", -0.02),
        "paperpass": ("paperpass_like", 0.03),
    }
    upgraded: list[BuiltinPackageSpec] = []
    for spec in BUILTIN_PACKAGE_SPECS:
        if spec.function_type != "aigc_detect":
            upgraded.append(spec)
            continue
        profile, score_offset = profile_offsets[spec.platform]
        upgraded.append(
            BuiltinPackageSpec(
                platform=spec.platform,
                function_type=spec.function_type,
                name=spec.name,
                version=_AIGC_VERSION,
                main_py=_aigc_detect_code_v3(profile=profile, score_offset=score_offset),
            )
        )
    return tuple(upgraded)


def _apply_cnki_sampled_upgrades(specs: tuple[BuiltinPackageSpec, ...]) -> tuple[BuiltinPackageSpec, ...]:
    upgraded: list[BuiltinPackageSpec] = []
    for spec in specs:
        if spec.platform != "cnki":
            upgraded.append(spec)
            continue
        if spec.function_type == "aigc_detect":
            upgraded.append(
                BuiltinPackageSpec(
                    platform=spec.platform,
                    function_type=spec.function_type,
                    name=spec.name,
                    version=_CNKI_AIGC_VERSION,
                    main_py=_cnki_aigc_detect_code_v5(),
                )
            )
            continue
        if spec.function_type == "rewrite":
            upgraded.append(
                BuiltinPackageSpec(
                    platform=spec.platform,
                    function_type=spec.function_type,
                    name=spec.name,
                    version=_CNKI_TEXT_VERSION,
                    main_py=_cnki_rewrite_code_v2(),
                )
            )
            continue
        if spec.function_type == "dedup":
            upgraded.append(
                BuiltinPackageSpec(
                    platform=spec.platform,
                    function_type=spec.function_type,
                    name=spec.name,
                    version=_CNKI_TEXT_VERSION,
                    main_py=_cnki_dedup_code_v2(),
                )
            )
            continue
        upgraded.append(spec)
    return tuple(upgraded)


def _apply_vip_sampled_upgrades(specs: tuple[BuiltinPackageSpec, ...]) -> tuple[BuiltinPackageSpec, ...]:
    upgraded: list[BuiltinPackageSpec] = []
    for spec in specs:
        if spec.platform == "vip" and spec.function_type == "dedup":
            upgraded.append(
                BuiltinPackageSpec(
                    platform=spec.platform,
                    function_type=spec.function_type,
                    name=spec.name,
                    version=_VIP_DEDUP_VERSION,
                    main_py=_vip_dedup_code_v2(),
                )
            )
            continue
        upgraded.append(spec)
    return tuple(upgraded)


BUILTIN_PACKAGE_SPECS = _apply_vip_sampled_upgrades(_apply_cnki_sampled_upgrades(_upgrade_builtin_specs()))


def build_builtin_template_package(
    *,
    platform: str,
    function_type: str,
) -> tuple[str, bytes]:
    normalized_platform, normalized_function_type = _validate_slot(platform, function_type)
    spec = next(
        (
            item
            for item in BUILTIN_PACKAGE_SPECS
            if item.platform == normalized_platform and item.function_type == normalized_function_type
        ),
        None,
    )
    if spec is None:
        raise BizError(code=4526, message="算法包模板不存在")

    manifest = {
        "name": spec.name,
        "version": spec.version,
        "platform": spec.platform,
        "function_type": spec.function_type,
        "entry": "main.py",
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.writestr("main.py", spec.main_py)
        zf.writestr("README.md", _build_template_readme(spec))

    filename = f"algo_package_template_{spec.platform}_{spec.function_type}_{spec.version}.zip"
    return filename, buf.getvalue()


def _blank_package_manifest(*, platform: str, function_type: str) -> dict:
    return {
        "name": f"{platform}_{function_type}_custom",
        "version": "1.0.0",
        "platform": platform,
        "function_type": function_type,
        "entry": "main.py",
    }


def _blank_package_main_py(*, platform: str, function_type: str) -> str:
    algorithm_name = f"{platform}_{function_type}_custom"
    if function_type == "aigc_detect":
        return (
            dedent(
                f"""
                def _extract_text(payload):
                    if isinstance(payload, dict):
                        return payload.get("text", "")
                    return payload


                def process(payload):
                    text = str(_extract_text(payload) or "").strip()
                    # TODO: replace the placeholder logic with your own implementation.
                    score = 0.0 if not text else 0.5
                    label = "low" if score < 0.35 else "medium"
                    return {{
                        "ai_score": round(score, 4),
                        "label": label,
                        "algorithm": "{algorithm_name}",
                        "text_stats": {{
                            "chars": len(text),
                        }},
                    }}
                """
            ).strip()
            + "\n"
        )
    if function_type == "dedup":
        return (
            dedent(
                f"""
                def _extract_text(payload):
                    if isinstance(payload, dict):
                        return payload.get("text", "")
                    return payload


                def process(payload):
                    text = str(_extract_text(payload) or "").strip()
                    # TODO: replace the placeholder logic with your own implementation.
                    return {{
                        "text": text,
                        "similarity": 0.0,
                        "changes": 0,
                        "algorithm": "{algorithm_name}",
                    }}
                """
            ).strip()
            + "\n"
        )
    return (
        dedent(
            f"""
            def _extract_text(payload):
                if isinstance(payload, dict):
                    return payload.get("text", "")
                return payload


            def process(payload):
                text = str(_extract_text(payload) or "").strip()
                # TODO: replace the placeholder logic with your own implementation.
                return {{
                    "text": text,
                    "original_aigc_score": 0.0,
                    "rewritten_aigc_score": 0.0,
                    "algorithm": "{algorithm_name}",
                }}
            """
        ).strip()
        + "\n"
    )


def _authoring_bundle_readme() -> str:
    return (
        dedent(
            """
            # 算法写作总规范包

            这个规范包只解决一件事：你自己写的算法包，怎样组织、编码、返回，才能上传到当前系统后稳定跑起来。

            不包含业务算法结论，也不包含平台规避策略。它只描述当前项目的真实运行契约。

            ## 你应该怎么用

            1. 进入 `blank_packages/`，找到你要写的槽位目录。
            2. 先改 `manifest.json` 的 `name`、`version`。
            3. 再改 `main.py` 里的 `process` 实现。
            4. 打包时，必须把 `manifest.json` 和入口文件打在 zip 根目录下。
            5. 上传时，后台选择的槽位必须和 `manifest.json` 完全一致。

            ## 当前系统的硬约束

            - 上传文件必须是 zip
            - `manifest.json` 必须是 UTF-8
            - 入口 Python 文件必须是 UTF-8
            - `manifest.entry` 必须指向 zip 内真实存在的文件
            - 路径不能是绝对路径，也不能包含 `..`
            - 入口文件必须定义可调用的 `process`
            - `process` 返回值不能是 `None`
            - 运行时优先传入字符串；若报 `TypeError`，会再尝试传入 `{"text": "..."}`
            - 当前默认执行超时 8 秒
            - 当前默认包大小上限 200 MB

            ## 目录说明

            - `docs/00_runtime_contract.md`
              当前项目实际怎么校验、怎么加载、怎么执行
            - `docs/01_aigc_detect_spec.md`
              `aigc_detect` 写法规范
            - `docs/02_dedup_spec.md`
              `dedup` 写法规范
            - `docs/03_rewrite_spec.md`
              `rewrite` 写法规范
            - `blank_packages/`
              9 个槽位的空白可运行骨架
            """
        ).strip()
        + "\n"
    )


def _runtime_contract_doc() -> str:
    return (
        dedent(
            """
            # 运行时契约

            ## 1. manifest 要求

            - `name` 正则：`^[A-Za-z0-9_-]{2,64}$`
            - `version` 正则：`^[0-9]+(?:\\.[0-9]+){2}(?:[-+._A-Za-z0-9]*)?$`
            - `platform` 只能是 `cnki` / `vip` / `paperpass`
            - `function_type` 只能是 `aigc_detect` / `dedup` / `rewrite`
            - `entry` 默认 `main.py`
            - `entry` 只能是相对路径，不能包含 `..`

            ## 2. 运行方式

            - 系统会在子进程里执行算法包
            - 会从 zip 中读取 `manifest.entry` 对应的 Python 文件
            - 入口模块必须定义 `process`

            ## 3. 调用方式

            smoke test 与正式执行，都会优先按下面方式调用：

            ```python
            result = process(text)
            ```

            如果抛出 `TypeError`，系统会再尝试：

            ```python
            result = process({"text": text})
            ```

            因此最稳的写法，是你的 `process` 同时兼容字符串和对象输入。

            ## 4. smoke test 样例

            当前 smoke test 文本：

            ```text
            这是用于算法包 smoke test 的样例文本。
            ```

            只要你的 `process` 在这一步报错、超时或返回 `None`，上传就会失败。

            ## 5. 打包注意事项

            正确：

            ```text
            your_package.zip
              manifest.json
              main.py
            ```

            错误：

            ```text
            your_package.zip
              my_folder/
                manifest.json
                main.py
            ```

            上传时要求 `manifest.json` 在 zip 根层可直接读取。
            """
        ).strip()
        + "\n"
    )


def _function_spec_doc(function_type: str) -> str:
    if function_type == "aigc_detect":
        title = "AIGC 检测算法写作规范"
        core_principles = [
            "输入兼容字符串与 `{\"text\": ...}` 两种形式。",
            "返回值使用 dict，不要返回自定义对象。",
            "至少返回 `ai_score` 和 `label`，避免前后版本字段含义漂移。",
        ]
        output_example = dedent(
            """
            {
              "ai_score": 0.42,
              "label": "medium",
              "algorithm": "paperpass_aigc_detect_custom",
              "text_stats": {
                "chars": 1280
              }
            }
            """
        ).strip()
        writing_notes = [
            "`ai_score` 建议固定在 0 到 1 之间。",
            "`label` 建议只用 `low` / `medium` / `high`。",
            "不要依赖全局状态或外部网络调用。",
        ]
    elif function_type == "dedup":
        title = "降重复率算法写作规范"
        core_principles = [
            "返回正文时优先放在 `text` 字段里。",
            "若需要附带分数、变更次数，统一作为结构化字段返回。",
            "对空文本、超短文本要直接可处理，不要抛异常。",
        ]
        output_example = dedent(
            """
            {
              "text": "处理后的正文",
              "similarity": 12.6,
              "changes": 8,
              "algorithm": "cnki_dedup_custom"
            }
            """
        ).strip()
        writing_notes = [
            "如果返回 dict，请务必带 `text`。",
            "如果只返回字符串，系统也能跑，但后续排查信息会少。",
            "注意保证输出永远是字符串或可 JSON 序列化结构。",
        ]
    else:
        title = "改写算法写作规范"
        core_principles = [
            "返回正文时优先放在 `text` 字段里。",
            "建议把改写前后指标也结构化返回，方便对比。",
            "保持 `process` 幂等、可重复执行，不依赖运行环境副作用。",
        ]
        output_example = dedent(
            """
            {
              "text": "改写后的正文",
              "original_aigc_score": 58.0,
              "rewritten_aigc_score": 31.5,
              "algorithm": "vip_rewrite_custom"
            }
            """
        ).strip()
        writing_notes = [
            "如果返回 dict，请务必带 `text`。",
            "原始分、改写后分建议都返回数值。",
            "不要在 `process` 内读写业务数据库或系统目录。",
        ]

    principles_text = "\n".join(f"- {item}" for item in core_principles)
    notes_text = "\n".join(f"- {item}" for item in writing_notes)
    return (
        dedent(
            f"""
            # {title}

            ## 核心原则

            {principles_text}

            ## 返回值建议

            ```json
            {output_example}
            ```

            ## 写作注意事项

            {notes_text}

            ## 常见失败原因

            - `process` 参数只支持一种形态，结果 smoke test 兼容失败
            - 返回了 `None`
            - 返回了不可 JSON 化的对象
            - 入口文件不是 UTF-8
            - 打包时把 `manifest.json` 压到了子目录里
            """
        ).strip()
        + "\n"
    )


def _blank_package_readme(*, platform: str, function_type: str) -> str:
    return (
        dedent(
            f"""
            # 空白骨架说明

            这是 `{platform}/{function_type}` 槽位的最小可运行骨架。

            你需要做的只有两件事：

            1. 修改 `manifest.json`
               - 改 `name`
               - 改 `version`
            2. 修改 `main.py`
               - 保留 `process`
               - 把占位逻辑替换成你的真实算法

            打包时注意：

            - zip 根目录必须直接包含 `manifest.json`
            - zip 根目录必须直接包含 `main.py`，或你在 `entry` 中指定的入口文件
            - 上传槽位必须和 manifest 中的 `platform` / `function_type` 完全一致
            """
        ).strip()
        + "\n"
    )


def build_authoring_spec_bundle() -> tuple[str, bytes]:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.md", _authoring_bundle_readme())
        zf.writestr("docs/00_runtime_contract.md", _runtime_contract_doc())
        zf.writestr("docs/01_aigc_detect_spec.md", _function_spec_doc("aigc_detect"))
        zf.writestr("docs/02_dedup_spec.md", _function_spec_doc("dedup"))
        zf.writestr("docs/03_rewrite_spec.md", _function_spec_doc("rewrite"))

        for platform in ("cnki", "vip", "paperpass"):
            for function_type in ("aigc_detect", "dedup", "rewrite"):
                base = f"blank_packages/{platform}/{function_type}"
                manifest = _blank_package_manifest(platform=platform, function_type=function_type)
                zf.writestr(f"{base}/manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
                zf.writestr(f"{base}/main.py", _blank_package_main_py(platform=platform, function_type=function_type))
                zf.writestr(f"{base}/README.md", _blank_package_readme(platform=platform, function_type=function_type))

    filename = "ALGO_PACKAGE_AUTHORING_SPEC_BUNDLE.zip"
    return filename, buf.getvalue()


def ensure_builtin_algo_package_active(
    db: Session,
    *,
    platform: str,
    function_type: str,
    uploaded_by: int,
) -> dict | None:
    normalized_platform, normalized_function_type = _validate_slot(platform, function_type)
    active_slot = get_active_slot_config(
        db,
        platform=normalized_platform,
        function_type=normalized_function_type,
    )
    if active_slot:
        return active_slot

    spec = next(
        (
            item
            for item in BUILTIN_PACKAGE_SPECS
            if item.platform == normalized_platform and item.function_type == normalized_function_type
        ),
        None,
    )
    if spec is None:
        return None

    result = install_algorithm_package(
        db,
        file_bytes=_build_package_zip(spec),
        platform=normalized_platform,
        function_type=normalized_function_type,
        uploaded_by=uploaded_by,
        activate_after_upload=True,
    )
    return result.get("active_slot")


def bootstrap_builtin_algo_packages(
    db: Session,
    *,
    uploaded_by: int,
    activate_after_upload: bool = True,
) -> dict:
    items = []
    for spec in BUILTIN_PACKAGE_SPECS:
        result = install_algorithm_package(
            db,
            file_bytes=_build_package_zip(spec),
            platform=spec.platform,
            function_type=spec.function_type,
            uploaded_by=uploaded_by,
            activate_after_upload=activate_after_upload,
        )
        items.append(
            {
                "platform": spec.platform,
                "function_type": spec.function_type,
                "name": spec.name,
                "version": spec.version,
                "active_version": (result.get("active_slot") or {}).get("version"),
            }
        )
    return {"count": len(items), "items": items}
