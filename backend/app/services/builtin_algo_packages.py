import io
import json
import zipfile
from dataclasses import dataclass
from textwrap import dedent

from sqlalchemy.orm import Session

from app.exceptions import BizError
from app.services.algo_package_service import _validate_slot, install_algorithm_package


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


BUILTIN_PACKAGE_SPECS = _upgrade_builtin_specs()


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
