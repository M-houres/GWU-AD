import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

from docx import Document
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import LLMErrorLog, SwitchLog, SystemSwitch, TaskType
from app.services.algo_package_service import run_active_package
from app.services.llm_service import generate_with_llm, load_llm_config
from app.utils import count_billable_chars, extract_text_from_file

MODE_LLM_PLUS_ALGO = "LLM_PLUS_ALGO"
MODE_ALGO_ONLY = "ALGO_ONLY"
settings = get_settings()


@dataclass
class ProcessResult:
    output_path: str
    result_json: dict


class ProcessingEngine:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._current_switch: SystemSwitch | None = None
        self._current_task_id: int | None = None
        self._pipeline_usage = {"llm_used": False, "algo_package_used": False}
        self._effective_mode = MODE_ALGO_ONLY

    def _get_or_init_switch(self) -> SystemSwitch:
        switch = self.db.query(SystemSwitch).first()
        if switch:
            return switch
        switch = SystemSwitch(
            current_mode=MODE_LLM_PLUS_ALGO if settings.llm_enabled_default else MODE_ALGO_ONLY,
            llm_enabled=settings.llm_enabled_default,
            llm_fail_count=0,
            llm_fail_threshold=3,
        )
        self.db.add(switch)
        self.db.flush()
        return switch

    def _switch_mode(self, target_mode: str, reason: str) -> None:
        switch = self._get_or_init_switch()
        if switch.current_mode == target_mode:
            return
        self.db.add(SwitchLog(from_mode=switch.current_mode, to_mode=target_mode, reason=reason))
        switch.current_mode = target_mode
        self.db.flush()

    def _normalize_requested_mode(self, processing_mode: str | None) -> str | None:
        raw = str(processing_mode or "").strip()
        mode = raw.upper()
        if mode in {MODE_ALGO_ONLY, MODE_LLM_PLUS_ALGO}:
            return mode
        lowered = raw.lower()
        if lowered in {"algo_only", "algo"}:
            return MODE_ALGO_ONLY
        if lowered in {"algo_llm", "llm_plus_algo", "algo+llm"}:
            return MODE_LLM_PLUS_ALGO
        return None

    def _resolve_effective_mode(self, switch: SystemSwitch, requested_mode: str | None) -> str:
        if requested_mode == MODE_ALGO_ONLY:
            return MODE_ALGO_ONLY
        if requested_mode == MODE_LLM_PLUS_ALGO:
            if switch.llm_enabled and switch.current_mode == MODE_LLM_PLUS_ALGO:
                return MODE_LLM_PLUS_ALGO
            return MODE_ALGO_ONLY
        return switch.current_mode

    def process(
        self,
        task_type: TaskType,
        platform: str,
        input_path: Path,
        output_path: Path,
        task_id: int | None = None,
        report_path: Path | None = None,
        processing_mode: str | None = None,
    ) -> ProcessResult:
        switch = self._get_or_init_switch()
        self._current_switch = switch
        self._current_task_id = task_id
        self._pipeline_usage = {"llm_used": False, "algo_package_used": False}

        llm_cfg = load_llm_config(self.db)
        switch.llm_enabled = bool(llm_cfg.get("enabled", False))
        normalized_platform = (platform or "").strip().lower()
        if not switch.llm_enabled:
            self._switch_mode(MODE_ALGO_ONLY, "llm disabled")
        elif switch.current_mode != MODE_ALGO_ONLY or switch.llm_fail_count < switch.llm_fail_threshold:
            self._switch_mode(MODE_LLM_PLUS_ALGO, "llm healthy")
        requested_mode = self._normalize_requested_mode(processing_mode)
        self._effective_mode = self._resolve_effective_mode(switch, requested_mode)

        source_text = extract_text_from_file(input_path)
        report_text = self._load_optional_report(report_path)
        report_summary = self._extract_report_summary(task_type, report_text)

        if task_type == TaskType.AIGC_DETECT:
            algo_result = self._run_algo_package(normalized_platform, task_type, source_text)
            llm_detect_text = self._build_detect_llm_excerpt(source_text, normalized_platform)
            llm_detect_result = self._parse_llm_detect_result(self._run_llm(task_type, llm_detect_text))
            detect_result = self._build_detect_result(
                text=source_text,
                platform=normalized_platform,
                mode=self._effective_mode,
                report_summary=report_summary,
                algo_result=algo_result,
                llm_result=llm_detect_result,
            )
            detect_result.setdefault("score_breakdown", {})["llm_excerpt_chars"] = len(llm_detect_text)
            self._write_detect_report_pdf(output_path, detect_result)
            return ProcessResult(output_path=str(output_path), result_json=detect_result)

        if input_path.suffix.lower() == ".docx":
            self._transform_docx(input_path, output_path, task_type, normalized_platform, report_summary)
            output_text = extract_text_from_file(output_path)
        else:
            output_text = self._transform_text(source_text, task_type, normalized_platform, report_summary)
            output_path.write_text(output_text, encoding="utf-8")

        result_json = self._build_transform_result(
            task_type=task_type,
            platform=normalized_platform,
            mode=self._effective_mode,
            source_text=source_text,
            output_text=output_text,
            report_summary=report_summary,
        )
        return ProcessResult(output_path=str(output_path), result_json=result_json)

    def _load_optional_report(self, report_path: Path | None) -> str:
        if report_path is None or not report_path.exists():
            return ""
        try:
            return extract_text_from_file(report_path)
        except Exception:
            return ""

    def _heuristic_ai_score(self, text: str) -> float:
        clean = text.strip()
        if not clean:
            return 0.0
        normalized = clean.replace("。", ".").replace("！", ".").replace("？", ".")
        sentences = [seg.strip() for seg in normalized.split(".") if seg.strip()]
        if not sentences:
            return 0.0
        avg_len = sum(len(s) for s in sentences) / len(sentences)
        uniq_ratio = len(set(clean)) / max(len(clean), 1)
        score = min(1.0, max(0.0, (avg_len / 80.0) * 0.6 + (1 - uniq_ratio) * 0.4))
        return round(score, 4)

    def _iter_body_runs(self, doc: Document):
        for para in doc.paragraphs:
            for run in para.runs:
                yield run
        if settings.docx_process_table_text:
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        for para in cell.paragraphs:
                            for run in para.runs:
                                yield run

    def _transform_docx(
        self,
        input_path: Path,
        output_path: Path,
        task_type: TaskType,
        platform: str,
        report_summary: dict | None = None,
    ) -> None:
        doc = Document(str(input_path))
        summary = report_summary or {}
        for run in self._iter_body_runs(doc):
            if run.text:
                run.text = self._transform_text(run.text, task_type, platform, summary)
        doc.save(str(output_path))

    def _run_algo_package(self, platform: str, task_type: TaskType, text: str):
        try:
            result = run_active_package(
                self.db,
                platform=platform,
                function_type=task_type.value,
                text=text,
            )
        except Exception:
            return None
        if result is None:
            return None
        self._pipeline_usage["algo_package_used"] = True
        value, _meta = result
        return value

    def _run_llm(self, task_type: TaskType, text: str) -> str | None:
        switch = self._current_switch or self._get_or_init_switch()
        if self._effective_mode != MODE_LLM_PLUS_ALGO or not switch.llm_enabled:
            return None
        try:
            output = generate_with_llm(self.db, task_type=task_type, text=text)
            switch.llm_fail_count = 0
            self._pipeline_usage["llm_used"] = True
            self.db.flush()
            return output
        except Exception as exc:
            switch.llm_fail_count += 1
            should_downgrade = switch.llm_fail_count >= switch.llm_fail_threshold
            if should_downgrade:
                self._switch_mode(MODE_ALGO_ONLY, f"llm_fail:{str(exc)[:160]}")
            self.db.add(
                LLMErrorLog(
                    task_id=self._current_task_id,
                    error_type=exc.__class__.__name__,
                    error_detail=str(exc)[:500],
                    trigger_downgrade=should_downgrade,
                )
            )
            self.db.flush()
            return None

    def _parse_llm_detect_result(self, raw: str | None) -> dict | None:
        if not isinstance(raw, str) or not raw.strip():
            return None

        payload: dict | None = None
        text = raw.strip()
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                candidate = json.loads(match.group(0))
                if isinstance(candidate, dict):
                    payload = candidate
            except Exception:
                payload = None

        if payload is None:
            return self._parse_llm_detect_fallback(text)

        score = self._coerce_ratio(payload.get("ai_score"))
        if score is None:
            score = self._coerce_ratio(payload.get("score"))
        if score is None:
            return self._parse_llm_detect_fallback(text)

        label = self._normalize_detect_label(payload.get("label"))
        if not label:
            label = self._normalize_detect_label(payload.get("risk_level"))
        reason = payload.get("reason")
        return {
            "ai_score": score,
            "label": label,
            "reason": str(reason).strip()[:180] if isinstance(reason, str) else "",
        }

    def _parse_llm_detect_fallback(self, text: str) -> dict | None:
        percent_match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
        if percent_match:
            score = self._coerce_ratio(percent_match.group(1))
        else:
            score = self._coerce_ratio(self._first_numeric(text))
        if score is None:
            return None
        return {
            "ai_score": score,
            "label": self._normalize_detect_label(text),
            "reason": "",
        }

    def _first_numeric(self, text: str) -> str | None:
        match = re.search(r"(\d+(?:\.\d+)?)", text)
        if not match:
            return None
        return match.group(1)

    def _coerce_ratio(self, raw) -> float | None:
        if raw is None:
            return None
        if isinstance(raw, str):
            raw = raw.strip().replace("%", "")
        try:
            value = float(raw)
        except Exception:
            return None
        if value > 1:
            value = value / 100
        return round(self._clamp_score(value), 4)

    def _normalize_detect_label(self, raw) -> str:
        value = str(raw or "").strip().lower()
        if not value:
            return ""
        if "high" in value or "高" in value:
            return "high"
        if "medium" in value or "mid" in value or "中" in value:
            return "medium"
        if "low" in value or "低" in value:
            return "low"
        return ""

    def _iter_result_dicts(self, payload) -> list[dict]:
        if not isinstance(payload, dict):
            return []
        queue: list[tuple[dict, int]] = [(payload, 0)]
        visited: set[int] = set()
        items: list[dict] = []
        while queue:
            current, depth = queue.pop(0)
            marker = id(current)
            if marker in visited:
                continue
            visited.add(marker)
            items.append(current)
            if depth >= 2:
                continue
            for value in current.values():
                if isinstance(value, dict):
                    queue.append((value, depth + 1))
        return items

    def _extract_algo_score(self, algo_result) -> float | None:
        keys = (
            "ai_score",
            "aigc_score",
            "score",
            "risk_score",
            "probability",
            "ai_probability",
        )
        for current in self._iter_result_dicts(algo_result):
            for key in keys:
                if key not in current:
                    continue
                score = self._coerce_ratio(current.get(key))
                if score is not None:
                    return score
        return None

    def _extract_algo_label(self, algo_result) -> str:
        keys = (
            "label",
            "level",
            "risk_level",
            "risk",
            "grade",
        )
        for current in self._iter_result_dicts(algo_result):
            for key in keys:
                if key not in current:
                    continue
                label = self._normalize_detect_label(current.get(key))
                if label:
                    return label
        return ""

    def _extract_algo_text(self, algo_result) -> str | None:
        if isinstance(algo_result, str) and algo_result.strip():
            return algo_result
        keys = (
            "text",
            "rewritten_text",
            "rewrite_text",
            "output_text",
            "result_text",
            "content",
            "body",
            "output",
            "result",
        )
        for current in self._iter_result_dicts(algo_result):
            for key in keys:
                if key not in current:
                    continue
                value = current.get(key)
                if isinstance(value, str) and value.strip():
                    return value
        return None

    def _transform_text(self, text: str, task_type: TaskType, platform: str, report_summary: dict) -> str:
        normalized_input = self._normalize_text(text)

        # In combined mode, enforce algorithm package -> LLM chaining so both links
        # can contribute to dedup/rewrite when available.
        if self._effective_mode == MODE_LLM_PLUS_ALGO:
            algo_result = self._run_algo_package(platform, task_type, normalized_input)
            algo_text = self._extract_algo_text(algo_result)
            llm_input = algo_text or normalized_input
            llm_output = self._run_llm(task_type, llm_input)
            if isinstance(llm_output, str) and llm_output.strip():
                return llm_output
            if algo_text:
                return algo_text
            return self._heuristic_transform_text(
                text=normalized_input,
                task_type=task_type,
                report_summary=report_summary,
            )

        algo_result = self._run_algo_package(platform, task_type, normalized_input)
        algo_text = self._extract_algo_text(algo_result)
        if algo_text:
            return algo_text
        return self._heuristic_transform_text(
            text=normalized_input,
            task_type=task_type,
            report_summary=report_summary,
        )

    def _heuristic_transform_text(self, *, text: str, task_type: TaskType, report_summary: dict) -> str:
        pressure = report_summary.get("pressure", "low")
        if task_type == TaskType.DEDUP:
            replacements = {
                "因此": "由此可见",
                "但是": "然而",
                "首先": "第一",
                "其次": "第二",
                "总之": "综上所述",
                "可以看出": "据此可见",
                "本文认为": "本文进一步指出",
            }
            output = self._apply_replacements(text, replacements)
            output = self._split_long_sentences(output, 48 if pressure == "high" else 64)
            return output
        if task_type == TaskType.REWRITE:
            replacements = {
                "研究表明": "已有研究指出",
                "可以看出": "据此可见",
                "非常": "较为",
                "重要": "关键",
                "很多": "大量",
                "我们发现": "研究发现",
                "这个": "该",
            }
            output = self._apply_replacements(text, replacements)
            output = self._split_long_sentences(output, 54 if pressure == "high" else 72)
            return output
        return text
    def _normalize_text(self, text: str) -> str:
        output = re.sub(r"[ \t]+", " ", text)
        output = re.sub(r"\n{3,}", "\n\n", output)
        return output.strip()

    def _apply_replacements(self, text: str, replacements: dict[str, str]) -> str:
        output = text
        for src, target in replacements.items():
            output = output.replace(src, target)
        return output

    def _split_long_sentences(self, text: str, threshold: int) -> str:
        chunks = re.split(r"([。！？!?])", text)
        rebuilt: list[str] = []
        for index in range(0, len(chunks), 2):
            sentence = chunks[index].strip()
            punct = chunks[index + 1] if index + 1 < len(chunks) else ""
            if len(sentence) > threshold and "，" in sentence:
                parts = [part.strip() for part in sentence.split("，") if part.strip()]
                current: list[str] = []
                current_len = 0
                groups: list[str] = []
                for part in parts:
                    if current and current_len + len(part) > threshold:
                        groups.append("，".join(current))
                        current = [part]
                        current_len = len(part)
                    else:
                        current.append(part)
                        current_len += len(part)
                if current:
                    groups.append("，".join(current))
                rebuilt.append("。".join(groups) + punct)
            else:
                rebuilt.append(sentence + punct)
        return "".join(rebuilt).strip()

    def _text_stats(self, text: str) -> dict:
        clean = text.strip()
        sentences = [part.strip() for part in re.split(r"[。！？!?；;\n]+", clean) if part.strip()]
        paragraphs = [part.strip() for part in clean.splitlines() if part.strip()]
        sentence_count = len(sentences)
        avg_sentence_length = round(sum(len(item) for item in sentences) / sentence_count, 2) if sentence_count else 0
        return {
            "char_count": count_billable_chars(clean),
            "paragraph_count": len(paragraphs),
            "sentence_count": sentence_count,
            "avg_sentence_length": avg_sentence_length,
        }

    def _extract_report_summary(self, task_type: TaskType, report_text: str) -> dict:
        content = " ".join((report_text or "").split())
        summary = {
            "available": bool(content),
            "metrics": [],
            "highlights": [],
            "recommended_actions": [],
            "pressure": "low",
        }
        if not content:
            summary["recommended_actions"] = ["未上传辅助报告，本次按正文通用策略处理。"]
            return summary

        if task_type == TaskType.DEDUP:
            total_ratio = self._extract_percent(content, ["总文字复制比", "全文总重复率", "重复率", "总复制比"])
            quote_ratio = self._extract_percent(content, ["去除引用复制比"])
            self_ratio = self._extract_percent(content, ["去除本人已发表文献复制比"])
            for label, value in (
                ("总文字复制比", total_ratio),
                ("去除引用复制比", quote_ratio),
                ("去除本人已发表文献复制比", self_ratio),
            ):
                if value is not None:
                    summary["metrics"].append({"label": label, "value": value, "unit": "%"})
            summary["highlights"] = [word for word in ["全文", "检测报告", "总文字复制比", "去除引用复制比"] if word in content][:4]
            if total_ratio is not None and total_ratio >= 25:
                summary["recommended_actions"].append("重复率偏高，优先处理定义、综述和结论性长句。")
                summary["pressure"] = "high"
            elif total_ratio is not None and total_ratio >= 15:
                summary["recommended_actions"].append("重复率中等，优先改写高频连接词和段首句。")
                summary["pressure"] = "medium"
            if quote_ratio is not None and quote_ratio >= 10:
                summary["recommended_actions"].append("检查引用说明是否过少，必要时补充规范引文表达。")
            if self_ratio is not None and self_ratio >= 10:
                summary["recommended_actions"].append("留意与本人历史文本重合的定义和结论段。")
        else:
            ai_ratio = self._extract_percent(content, ["AIGC总体风险", "总体风险", "AIGC疑似度", "AI生成疑似度", "疑似AI生成"])
            high_ratio = self._extract_percent(content, ["高风险占比", "高风险段落占比"])
            for label, value in (
                ("总体风险", ai_ratio),
                ("高风险占比", high_ratio),
            ):
                if value is not None:
                    summary["metrics"].append({"label": label, "value": value, "unit": "%"})
            summary["highlights"] = [word for word in ["AIGC", "疑似AI", "高风险段落", "全文"] if word.lower() in content.lower()][:4]
            if ai_ratio is not None and ai_ratio >= 50:
                summary["recommended_actions"].append("AIGC 风险偏高，优先拆分长句并弱化模板化连接词。")
                summary["pressure"] = "high"
            elif ai_ratio is not None and ai_ratio >= 30:
                summary["recommended_actions"].append("AIGC 风险中等，建议提升句式变化和论证层次。")
                summary["pressure"] = "medium"
            if high_ratio is not None and high_ratio >= 20:
                summary["recommended_actions"].append("重点复核高风险段落，尤其是定义句和总结句。")

        if not summary["recommended_actions"]:
            if task_type == TaskType.DEDUP:
                summary["recommended_actions"].append("建议重点复核连续长句、定义表述和文献综述段落。")
            else:
                summary["recommended_actions"].append("建议优先调整摘要、结论和高频模板化表达。")
        return summary

    def _extract_percent(self, text: str, keywords: list[str]) -> float | None:
        for keyword in keywords:
            pattern = rf"{re.escape(keyword)}[^0-9]{{0,12}}(\d+(?:\.\d+)?)\s*%"
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return round(float(match.group(1)), 2)
        return None


    def _clamp_score(self, value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    def _legacy_platform_detect_profile_v000(self, platform: str) -> dict:
        key = (platform or "").strip().lower()
        profiles = {
            "cnki": {
                "name": "cnki_like",
                "baseline_weight": 0.7,
                "style_weight": 0.2,
                "repeat_weight": 0.1,
                "offset": 0.0,
                "high": 0.65,
                "medium": 0.35,
            },
            "vip": {
                "name": "vip_like",
                "baseline_weight": 0.64,
                "style_weight": 0.24,
                "repeat_weight": 0.12,
                "offset": -0.02,
                "high": 0.62,
                "medium": 0.33,
            },
            "paperpass": {
                "name": "paperpass_like",
                "baseline_weight": 0.66,
                "style_weight": 0.16,
                "repeat_weight": 0.18,
                "offset": 0.03,
                "high": 0.6,
                "medium": 0.32,
            },
        }
        return profiles.get(key, profiles["cnki"])

    def _legacy_simulate_platform_detect_score_v00(self, platform: str, text: str, base_score: float) -> tuple[float, dict, dict]:
        profile = self._platform_detect_profile(platform)
        stats = self._text_stats(text)
        clean = (text or "").strip()
        compact = " ".join(clean.split())
        unique_ratio = (len(set(compact)) / len(compact)) if compact else 1.0
        repeat_signal = self._clamp_score(1.0 - unique_ratio)
        avg_len = float(stats.get("avg_sentence_length") or 0.0)
        style_signal = self._clamp_score((avg_len - 18.0) / 55.0)

        weighted = (
            float(base_score) * profile["baseline_weight"]
            + style_signal * profile["style_weight"]
            + repeat_signal * profile["repeat_weight"]
            + profile["offset"]
        )
        score = round(self._clamp_score(weighted), 4)
        breakdown = {
            "base_score": round(float(base_score), 4),
            "style_signal": round(style_signal, 4),
            "repeat_signal": round(repeat_signal, 4),
            "weights": {
                "baseline": profile["baseline_weight"],
                "style": profile["style_weight"],
                "repeat": profile["repeat_weight"],
                "offset": profile["offset"],
            },
            "thresholds": {
                "high": profile["high"],
                "medium": profile["medium"],
            },
        }
        return score, profile, breakdown

    def _legacy_build_detect_result_v00(
        self,
        *,
        text: str,
        platform: str,
        mode: str,
        report_summary: dict,
        algo_result,
        llm_result: dict | None,
    ) -> dict:
        base_score = self._heuristic_ai_score(text)
        score, profile, breakdown = self._simulate_platform_detect_score(platform, text, base_score)
        label = "high" if score >= profile["high"] else "medium" if score >= profile["medium"] else "low"
        algo_has_label = False

        if isinstance(algo_result, dict):
            package_score = self._extract_algo_score(algo_result)
            if package_score is not None:
                score = round(self._clamp_score(score * 0.65 + package_score * 0.35), 4)
                breakdown["algo_package_score"] = round(package_score, 4)
                breakdown["blended"] = True
            else:
                breakdown["blended"] = False

            algo_label = self._extract_algo_label(algo_result)
            if algo_label:
                label = algo_label
                algo_has_label = True
        else:
            breakdown["blended"] = False

        if isinstance(llm_result, dict):
            llm_score = self._coerce_ratio(llm_result.get("ai_score"))
            if llm_score is not None:
                score = round(self._clamp_score(score * 0.8 + llm_score * 0.2), 4)
                breakdown["llm_score"] = round(llm_score, 4)
                breakdown["llm_blended"] = True
            else:
                breakdown["llm_blended"] = False

            llm_label = self._normalize_detect_label(llm_result.get("label"))
            if llm_label and not algo_has_label:
                label = llm_label

            reason = llm_result.get("reason")
            if isinstance(reason, str) and reason.strip():
                breakdown["llm_reason"] = reason.strip()[:180]
        else:
            breakdown["llm_blended"] = False

        band = self._risk_band(score, high=profile["high"], medium=profile["medium"])
        risk_paragraphs = self._top_risk_paragraphs(text, platform=platform)
        return {
            "type": TaskType.AIGC_DETECT.value,
            "platform": platform,
            "simulation_profile": profile["name"],
            "mode": mode,
            "llm_used": self._pipeline_usage["llm_used"],
            "algo_package_used": self._pipeline_usage["algo_package_used"],
            "ai_score": score,
            "score_pct": round(score * 100, 2),
            "label": label,
            "risk_band": band,
            "summary": f"AIGC detection completed. Current risk level: {band}.",
            "source_stats": self._text_stats(text),
            "report_summary": report_summary,
            "score_breakdown": breakdown,
            "risk_paragraphs": risk_paragraphs,
        }

    def _risk_band(self, score: float, *, high: float = 0.65, medium: float = 0.35) -> str:
        if score >= high:
            return "高风险"
        if score >= medium:
            return "中风险"
        return "低风险"

    def _legacy_top_risk_paragraphs_v00(self, text: str, platform: str = "cnki") -> list[dict]:
        paragraphs = [part.strip() for part in text.splitlines() if part.strip()]
        scored = []
        for index, paragraph in enumerate(paragraphs, start=1):
            if len(paragraph) < 20:
                continue
            base_score = self._heuristic_ai_score(paragraph)
            simulated_score, _profile, _breakdown = self._simulate_platform_detect_score(platform, paragraph, base_score)
            scored.append(
                {
                    "index": index,
                    "score": round(simulated_score * 100, 2),
                    "excerpt": self._clip_text(paragraph, 80),
                }
            )
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:3]


    def _wrap_pdf_line(self, text: str, width: int = 90) -> list[str]:
        compact = " ".join(str(text or "").split())
        if not compact:
            return [""]
        wrapped: list[str] = []
        remaining = compact
        while len(remaining) > width:
            cut = remaining.rfind(" ", 0, width + 1)
            if cut <= 0:
                cut = width
            wrapped.append(remaining[:cut].strip())
            remaining = remaining[cut:].strip()
        if remaining:
            wrapped.append(remaining)
        return wrapped

    def _pdf_safe_text(self, text: str) -> str:
        return str(text or "").encode("latin-1", "replace").decode("latin-1")

    def _pdf_escape(self, text: str) -> str:
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    def _render_pdf(self, lines: list[str]) -> bytes:
        page_width = 595
        page_height = 842
        margin_x = 46
        margin_top = 60
        margin_bottom = 52
        font_size = 11
        line_height = 15

        expanded_lines: list[str] = []
        for line in lines:
            wrapped = self._wrap_pdf_line(line, width=92)
            expanded_lines.extend(wrapped if wrapped else [""])
        if not expanded_lines:
            expanded_lines = [""]

        usable_height = page_height - margin_top - margin_bottom
        lines_per_page = max(1, int(usable_height // line_height))
        page_line_chunks = [
            expanded_lines[i : i + lines_per_page] for i in range(0, len(expanded_lines), lines_per_page)
        ]

        objects: list[tuple[int, bytes]] = [(1, b"<< /Type /Catalog /Pages 2 0 R >>")]
        page_refs: list[str] = []
        next_obj_id = 3
        font_obj_id = 2 + len(page_line_chunks) * 2 + 1

        for chunk in page_line_chunks:
            page_obj_id = next_obj_id
            content_obj_id = next_obj_id + 1
            next_obj_id += 2
            page_refs.append(f"{page_obj_id} 0 R")

            text_ops: list[str] = []
            for index, line in enumerate(chunk):
                y = page_height - margin_top - index * line_height
                safe_line = self._pdf_escape(self._pdf_safe_text(line))
                text_ops.append(f"BT /F1 {font_size} Tf 1 0 0 1 {margin_x} {y:.2f} Tm ({safe_line}) Tj ET")
            stream_text = "\n".join(text_ops)
            stream_bytes = stream_text.encode("latin-1", "replace")

            page_obj = (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] "
                f"/Resources << /Font << /F1 {font_obj_id} 0 R >> >> /Contents {content_obj_id} 0 R >>"
            ).encode("ascii")
            content_obj = (
                f"<< /Length {len(stream_bytes)} >>\nstream\n".encode("ascii")
                + stream_bytes
                + b"\nendstream"
            )
            objects.append((page_obj_id, page_obj))
            objects.append((content_obj_id, content_obj))

        pages_obj = f"<< /Type /Pages /Count {len(page_line_chunks)} /Kids [{' '.join(page_refs)}] >>".encode("ascii")
        objects.insert(1, (2, pages_obj))
        objects.append((font_obj_id, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"))

        objects.sort(key=lambda item: item[0])
        output = bytearray()
        output.extend(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets: dict[int, int] = {}

        for obj_id, obj_body in objects:
            offsets[obj_id] = len(output)
            output.extend(f"{obj_id} 0 obj\n".encode("ascii"))
            output.extend(obj_body)
            output.extend(b"\nendobj\n")

        xref_offset = len(output)
        max_obj_id = max(offsets)
        output.extend(f"xref\n0 {max_obj_id + 1}\n".encode("ascii"))
        output.extend(b"0000000000 65535 f \n")
        for obj_id in range(1, max_obj_id + 1):
            offset = offsets.get(obj_id, 0)
            output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
        output.extend(f"trailer\n<< /Size {max_obj_id + 1} /Root 1 0 R >>\n".encode("ascii"))
        output.extend(f"startxref\n{xref_offset}\n%%EOF".encode("ascii"))
        return bytes(output)
    def _legacy_platform_detect_profile_v0(self, platform: str) -> dict:
        key = (platform or "").strip().lower()
        profiles = {
            "cnki": {
                "name": "cnki_like",
                "provider_label": "知网AIGC检测仿真",
                "score_label": "AIGC值",
                "baseline_weight": 0.56,
                "style_weight": 0.14,
                "repeat_weight": 0.12,
                "template_weight": 0.10,
                "context_weight": 0.08,
                "offset": 0.0,
                "high": 0.67,
                "medium": 0.42,
                "overall_paragraph_weight": 0.56,
                "overall_peak_weight": 0.26,
                "overall_segment_weight": 0.18,
            },
            "vip": {
                "name": "vip_like",
                "provider_label": "维普AIGC检测仿真",
                "score_label": "AIGC疑似度",
                "baseline_weight": 0.52,
                "style_weight": 0.16,
                "repeat_weight": 0.12,
                "template_weight": 0.11,
                "context_weight": 0.09,
                "offset": -0.02,
                "high": 0.64,
                "medium": 0.40,
                "overall_paragraph_weight": 0.54,
                "overall_peak_weight": 0.24,
                "overall_segment_weight": 0.22,
            },
            "paperpass": {
                "name": "paperpass_like",
                "provider_label": "PaperPass AIGC检测仿真",
                "score_label": "AIGC风险值",
                "baseline_weight": 0.48,
                "style_weight": 0.14,
                "repeat_weight": 0.14,
                "template_weight": 0.10,
                "context_weight": 0.14,
                "offset": 0.03,
                "high": 0.60,
                "medium": 0.38,
                "overall_paragraph_weight": 0.50,
                "overall_peak_weight": 0.22,
                "overall_segment_weight": 0.28,
            },
        }
        return profiles.get(key, profiles["cnki"])

    def _legacy_template_signal_v1(self, text: str) -> tuple[float, list[str]]:
        hits: list[str] = []
        phrases = [
            "研究表明",
            "本研究旨在",
            "本文基于",
            "在此背景下",
            "可以看出",
            "由此可见",
            "综上所述",
            "总而言之",
            "值得注意的是",
            "首先",
            "其次",
            "再次",
            "最后",
            "此外",
            "与此同时",
            "另一方面",
            "进一步而言",
            "从整体上看",
            "不难发现",
            "基于此",
            "具有重要的理论意义和实践意义",
            "为此提供参考",
            "从而实现",
        ]
        content = str(text or "")
        for phrase in phrases:
            if phrase in content:
                hits.append(phrase)
        density = len(hits) / max(len(content) / 85.0, 1.0)
        return round(self._clamp_score(density), 4), hits[:4]

    def _legacy_opening_signal_v1(self, text: str) -> float:
        clean = " ".join(str(text or "").split())
        normalized = re.sub(
            r"^(?:第[一二三四五六七八九十百零0-9]+[章节部分篇]|[一二三四五六七八九十百零]+[、.．]|"
            r"\d+(?:\.\d+){0,3}[、.．]?|[（(][一二三四五六七八九十百零0-9]+[)）])",
            "",
            clean,
        ).lstrip("：:.。;；、，, ")
        if not normalized:
            return 0.0

        starters = (
            "本研究",
            "本文",
            "研究表明",
            "综上所述",
            "总而言之",
            "值得注意的是",
            "首先",
            "其次",
            "再次",
            "此外",
            "与此同时",
            "另一方面",
            "进一步",
            "从整体上看",
            "由此可见",
            "在此背景下",
            "基于此",
        )
        signal = 0.0
        if any(normalized.startswith(token) for token in starters):
            signal += 0.48
        order_hits = sum(1 for token in ("首先", "其次", "再次", "最后", "此外", "另一方面") if token in normalized[:24])
        signal += min(0.36, order_hits * 0.12)
        if re.search(r"^在.{0,8}背景下", normalized):
            signal += 0.18
        return round(self._clamp_score(signal), 4)

    def _legacy_citation_relief_signal_v1(self, text: str) -> float:
        content = str(text or "")
        patterns = [r"\[\d+\]", r"（\d{4}）", r"\(\d{4}\)", r"表\d+", r"图\d+", r"\d+%"]
        hit_count = 0
        for pattern in patterns:
            hit_count += len(re.findall(pattern, content))
        return round(min(0.18, hit_count * 0.025), 4)

    def _legacy_evidence_relief_signal_v1(self, text: str) -> float:
        content = str(text or "")
        patterns = [
            r"\bN\s*=\s*\d+",
            r"样本量",
            r"问卷",
            r"访谈",
            r"实验",
            r"受访者",
            r"标准差",
            r"均值",
            r"统计",
            r"案例",
            r"观察记录",
        ]
        hit_count = 0
        for pattern in patterns:
            hit_count += len(re.findall(pattern, content, flags=re.IGNORECASE))
        return round(min(0.16, hit_count * 0.018), 4)

    def _legacy_uniformity_signal_v1(self, sentences: list[str]) -> float:
        lengths = [len(item.strip()) for item in sentences if item.strip()]
        if not lengths:
            return 0.0
        if len(lengths) == 1:
            return 0.5
        avg_len = sum(lengths) / len(lengths)
        variance = sum((value - avg_len) ** 2 for value in lengths) / len(lengths)
        signal = 1.0 - min(1.0, variance / max(avg_len * 14.0, 1.0))
        return round(self._clamp_score(signal), 4)

    def _legacy_normalized_opening_key_v1(self, paragraph: str) -> str:
        clean = " ".join(str(paragraph or "").split())
        if not clean:
            return ""
        heading_level, _heading = self._detect_outline_heading(clean)
        if heading_level is not None:
            return ""
        normalized = re.sub(
            r"^(?:第[一二三四五六七八九十百零0-9]+[章节部分篇]|[一二三四五六七八九十百零]+[、.．]|"
            r"\d+(?:\.\d+){0,3}[、.．]?|[（(][一二三四五六七八九十百零0-9]+[)）])",
            "",
            clean,
        ).lstrip("：:.。;；、，, ")
        normalized = re.sub(r"\s+", "", normalized)
        return normalized[:12]

    def _legacy_paragraph_opening_similarity_v1(self, paragraphs: list[str]) -> float:
        keys: list[str] = []
        starter_counts: dict[str, int] = {}
        starters = (
            "本研究",
            "本文",
            "研究表明",
            "首先",
            "其次",
            "再次",
            "最后",
            "此外",
            "另一方面",
            "值得注意的是",
            "综上所述",
            "由此可见",
            "基于此",
        )
        for paragraph in paragraphs:
            key = self._normalized_opening_key(paragraph)
            if len(key) < 6:
                continue
            keys.append(key)
            for starter in starters:
                if key.startswith(starter):
                    starter_counts[starter] = starter_counts.get(starter, 0) + 1
                    break
        if not keys:
            return 0.0
        duplicate_ratio = max(0, len(keys) - len(set(keys))) / max(len(keys), 1)
        starter_repeat_ratio = sum(max(0, count - 1) for count in starter_counts.values()) / max(len(keys), 1)
        return round(self._clamp_score(duplicate_ratio * 0.68 + starter_repeat_ratio * 0.62), 4)

    def _legacy_fragment_display_band_v1(self, score: float, profile: dict) -> str:
        thresholds = profile.get("fragment_display_thresholds") or {}
        if score >= float(thresholds.get("severe", 0.9)):
            return "severe"
        if score >= float(thresholds.get("moderate", 0.8)):
            return "moderate"
        if score >= float(thresholds.get("mild", 0.7)):
            return "mild"
        return ""

    def _legacy_simulate_platform_detect_score_v0(self, platform: str, text: str, base_score: float) -> tuple[float, dict, dict]:
        profile = self._platform_detect_profile(platform)
        stats = self._text_stats(text)
        clean = (text or "").strip()
        compact = " ".join(clean.split())
        unique_ratio = (len(set(compact)) / len(compact)) if compact else 1.0
        repeat_signal = self._clamp_score(1.0 - unique_ratio)
        avg_len = float(stats.get("avg_sentence_length") or 0.0)
        style_signal = self._clamp_score((avg_len - 18.0) / 52.0)
        template_signal, template_hits = self._template_signal(clean)
        context_signal = self._uniformity_signal(self._split_detect_sentences(clean))
        opening_signal = self._opening_signal(clean)
        citation_relief = self._citation_relief_signal(clean)
        evidence_relief = self._evidence_relief_signal(clean)

        weighted = (
            float(base_score) * profile["baseline_weight"]
            + style_signal * profile["style_weight"]
            + repeat_signal * profile["repeat_weight"]
            + template_signal * profile["template_weight"]
            + context_signal * profile["context_weight"]
            + opening_signal * profile["opening_weight"]
            - citation_relief
            - evidence_relief
            + profile["offset"]
        )
        score = round(self._clamp_score(weighted), 4)
        breakdown = {
            "base_score": round(float(base_score), 4),
            "style_signal": round(style_signal, 4),
            "repeat_signal": round(repeat_signal, 4),
            "template_signal": round(template_signal, 4),
            "context_signal": round(context_signal, 4),
            "opening_signal": round(opening_signal, 4),
            "citation_relief": round(citation_relief, 4),
            "evidence_relief": round(evidence_relief, 4),
            "template_hits": template_hits,
            "weights": {
                "baseline": profile["baseline_weight"],
                "style": profile["style_weight"],
                "repeat": profile["repeat_weight"],
                "template": profile["template_weight"],
                "context": profile["context_weight"],
                "opening": profile["opening_weight"],
                "offset": profile["offset"],
            },
            "thresholds": {"high": profile["high"], "medium": profile["medium"]},
        }
        return score, profile, breakdown

    def _legacy_local_suspicious_segments_v1(self, paragraph: str, platform: str, profile: dict) -> list[dict]:
        segments: list[dict] = []
        for sentence in self._split_detect_sentences(paragraph):
            if len(sentence) < 8:
                continue
            base_score = self._heuristic_ai_score(sentence)
            score, _profile, breakdown = self._simulate_platform_detect_score(platform, sentence, base_score)
            if score < float(profile.get("medium", 0.35)) and len(breakdown.get("template_hits") or []) < 2:
                continue
            reasons: list[str] = []
            if float(breakdown.get("template_signal") or 0.0) >= 0.22:
                reasons.append("模板连接词偏多")
            if float(breakdown.get("repeat_signal") or 0.0) >= 0.32:
                reasons.append("重复表达偏多")
            if float(breakdown.get("context_signal") or 0.0) >= 0.58:
                reasons.append("句式波动偏小")
            if float(breakdown.get("opening_signal") or 0.0) >= 0.44:
                reasons.append("段首表述模板化")
            segments.append(
                {
                    "text": self._clip_text(sentence, 76),
                    "score": round(score * 100, 2),
                    "reason": "、".join(reasons[:2]) or "综合风险偏高",
                }
            )
        segments.sort(key=lambda item: item["score"], reverse=True)
        return segments[:3]

    def _legacy_paragraph_reason_tags_v1(self, breakdown: dict) -> list[str]:
        tags: list[str] = []
        if float(breakdown.get("template_signal") or 0.0) >= 0.22:
            tags.append("模板连接词偏多")
        if float(breakdown.get("repeat_signal") or 0.0) >= 0.30:
            tags.append("重复表达偏高")
        if float(breakdown.get("context_signal") or 0.0) >= 0.56:
            tags.append("句式波动偏小")
        if float(breakdown.get("style_signal") or 0.0) >= 0.55:
            tags.append("长句占比较高")
        if float(breakdown.get("opening_signal") or 0.0) >= 0.44:
            tags.append("段首表述模板化")
        return tags[:3]

    def _legacy_build_fragment_distribution_v1(
        self,
        text: str,
        platform: str,
        profile: dict,
        paragraph_details: list[dict],
        document_outline: list[dict] | None = None,
    ) -> dict:
        paragraphs = self._split_detect_paragraphs(text)
        paragraph_score_map = {
            int(item.get("index") or 0): round(float(item.get("score") or 0.0) / 100.0, 4) for item in paragraph_details
        }
        count_map = {"high": 0, "medium": 0, "low": 0, "no_ai": 0}
        char_map = {"high": 0, "medium": 0, "low": 0, "no_ai": 0}
        display_count_map = {"mild": 0, "moderate": 0, "severe": 0}
        display_char_map = {"mild": 0, "moderate": 0, "severe": 0}
        weighted_scores: list[float] = []

        for paragraph_index, paragraph in enumerate(paragraphs, start=1):
            paragraph_ratio = paragraph_score_map.get(paragraph_index, 0.0)
            for sentence in self._split_detect_sentences(paragraph):
                compact = " ".join(sentence.split())
                if not compact:
                    continue
                char_count = count_billable_chars(compact)
                if char_count <= 0:
                    continue
                if self._is_no_ai_fragment(compact):
                    label = "no_ai"
                    score_ratio = 0.0
                else:
                    base_score = self._heuristic_ai_score(compact)
                    score_ratio, _profile, _breakdown = self._simulate_platform_detect_score(platform, compact, base_score)
                    if paragraph_ratio > 0:
                        score_ratio = round(self._clamp_score(score_ratio * 0.72 + paragraph_ratio * 0.28), 4)
                    label = self._score_to_detect_label(score_ratio, profile)
                    weighted_scores.append(score_ratio)
                    display_band = self._fragment_display_band(score_ratio, profile)
                    if display_band:
                        display_count_map[display_band] += 1
                        display_char_map[display_band] += char_count
                count_map[label] += 1
                char_map[label] += char_count

        total_fragments = sum(count_map.values())
        total_chars = sum(char_map.values())
        if total_fragments <= 0 or total_chars <= 0:
            return {
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
                "mild_fragment_count": 0,
                "moderate_fragment_count": 0,
                "severe_fragment_count": 0,
                "mild_fragment_ratio": 0.0,
                "moderate_fragment_ratio": 0.0,
                "severe_fragment_ratio": 0.0,
                "mild_text_ratio": 0.0,
                "moderate_text_ratio": 0.0,
                "severe_text_ratio": 0.0,
                "display_thresholds": {"mild": 70.0, "moderate": 80.0, "severe": 90.0},
            }

        def ratio(part: int, whole: int) -> float:
            return round(part / max(whole, 1) * 100, 2)

        high_middle_fragments = count_map["high"] + count_map["medium"]
        suspected_fragments = high_middle_fragments + count_map["low"]
        high_middle_chars = char_map["high"] + char_map["medium"]
        suspected_chars = high_middle_chars + char_map["low"]
        thresholds = profile.get("fragment_display_thresholds") or {}
        return {
            "fragment_count": total_fragments,
            "high_fragment_count": count_map["high"],
            "middle_fragment_count": count_map["medium"],
            "low_fragment_count": count_map["low"],
            "no_ai_fragment_count": count_map["no_ai"],
            "high_suspected_fragment_ratio": ratio(count_map["high"], total_fragments),
            "middle_suspected_fragment_ratio": ratio(count_map["medium"], total_fragments),
            "low_suspected_fragment_ratio": ratio(count_map["low"], total_fragments),
            "no_ai_fragment_ratio": ratio(count_map["no_ai"], total_fragments),
            "high_and_middle_suspected_fragment_ratio": ratio(high_middle_fragments, total_fragments),
            "total_suspected_fragment_ratio": ratio(suspected_fragments, total_fragments),
            "high_suspected_text_ratio": ratio(char_map["high"], total_chars),
            "middle_suspected_text_ratio": ratio(char_map["medium"], total_chars),
            "low_suspected_text_ratio": ratio(char_map["low"], total_chars),
            "no_ai_suspected_text_ratio": ratio(char_map["no_ai"], total_chars),
            "high_and_middle_suspected_text_ratio": ratio(high_middle_chars, total_chars),
            "total_suspected_text_ratio": ratio(suspected_chars, total_chars),
            "weighted_score_pct": round(sum(weighted_scores) / max(len(weighted_scores), 1) * 100, 2)
            if weighted_scores
            else 0.0,
            "mild_fragment_count": display_count_map["mild"],
            "moderate_fragment_count": display_count_map["moderate"],
            "severe_fragment_count": display_count_map["severe"],
            "mild_fragment_ratio": ratio(display_count_map["mild"], total_fragments),
            "moderate_fragment_ratio": ratio(display_count_map["moderate"], total_fragments),
            "severe_fragment_ratio": ratio(display_count_map["severe"], total_fragments),
            "mild_text_ratio": ratio(display_char_map["mild"], total_chars),
            "moderate_text_ratio": ratio(display_char_map["moderate"], total_chars),
            "severe_text_ratio": ratio(display_char_map["severe"], total_chars),
            "display_thresholds": {
                "mild": round(float(thresholds.get("mild", 0.7)) * 100, 2),
                "moderate": round(float(thresholds.get("moderate", 0.8)) * 100, 2),
                "severe": round(float(thresholds.get("severe", 0.9)) * 100, 2),
            },
        }

    def _legacy_build_document_metrics_v1(
        self,
        *,
        text: str,
        paragraph_details: list[dict],
        section_distribution: list[dict],
        document_outline: list[dict],
        profile: dict,
    ) -> dict:
        total = len(paragraph_details)
        total_chars = sum(int(item.get("char_count") or 0) for item in paragraph_details)
        high_medium_count = sum(1 for item in paragraph_details if item.get("label") in {"high", "medium"})
        high_medium_chars = sum(
            int(item.get("char_count") or 0) for item in paragraph_details if item.get("label") in {"high", "medium"}
        )
        longest_streak = 0
        current_streak = 0
        for item in paragraph_details:
            if item.get("label") in {"high", "medium"}:
                current_streak += 1
                longest_streak = max(longest_streak, current_streak)
            else:
                current_streak = 0
        medium_threshold = float(profile.get("medium", 0.35)) * 100
        suspicious_sections = sum(
            1
            for item in section_distribution
            if float(item.get("avg_score") or 0.0) >= medium_threshold or int(item.get("high_count") or 0) > 0
        )
        paragraphs = self._split_detect_paragraphs(text)
        opening_similarity = self._paragraph_opening_similarity(paragraphs)
        evidence_relief = max(self._citation_relief_signal(text), self._evidence_relief_signal(text))
        return {
            "paragraph_count": total,
            "high_medium_paragraph_count": high_medium_count,
            "high_medium_paragraph_ratio": round(high_medium_count / max(total, 1) * 100, 2) if total else 0.0,
            "high_medium_text_ratio": round(high_medium_chars / max(total_chars, 1) * 100, 2) if total_chars else 0.0,
            "longest_risk_streak": longest_streak,
            "longest_risk_streak_ratio": round(longest_streak / max(total, 1) * 100, 2) if total else 0.0,
            "opening_similarity_ratio": round(opening_similarity * 100, 2),
            "section_count": len(section_distribution),
            "suspicious_section_count": suspicious_sections,
            "section_coverage_ratio": round(suspicious_sections / max(len(section_distribution), 1) * 100, 2)
            if section_distribution
            else 0.0,
            "outline_sections": len(document_outline),
            "distribution_mode": "outline" if document_outline else "band",
            "evidence_relief_pct": round(evidence_relief * 100, 2),
        }

    def _legacy_build_decision_basis_v1(
        self,
        *,
        breakdown: dict,
        document_metrics: dict,
        fragment_distribution: dict,
        suspicious_segments: list[dict],
    ) -> list[dict]:
        items: list[dict] = []
        template_signal = float(breakdown.get("template_signal") or 0.0)
        context_signal = float(breakdown.get("context_signal") or 0.0)
        repeat_signal = float(breakdown.get("repeat_signal") or 0.0)
        opening_signal = float(breakdown.get("opening_signal") or 0.0)
        template_hits = [str(item) for item in (breakdown.get("template_hits") or []) if str(item).strip()]

        if template_signal >= 0.2:
            hit_text = "、".join(template_hits[:3]) if template_hits else "高频模板连接词"
            items.append(
                {
                    "title": "模板连接词密度偏高",
                    "detail": f"命中 {hit_text}，模板信号 {round(template_signal * 100, 2)}%。",
                    "direction": "risk",
                }
            )
        if context_signal >= 0.55:
            items.append(
                {
                    "title": "句长波动偏小",
                    "detail": f"上下文均匀度 {round(context_signal * 100, 2)}%，更接近机器批量生成的平直节奏。",
                    "direction": "risk",
                }
            )
        if repeat_signal >= 0.3:
            items.append(
                {
                    "title": "重复表达偏多",
                    "detail": f"重复信号 {round(repeat_signal * 100, 2)}%，存在近义重复或固定总结句反复出现。",
                    "direction": "risk",
                }
            )
        if opening_signal >= 0.44 or float(document_metrics.get("opening_similarity_ratio") or 0.0) >= 25:
            items.append(
                {
                    "title": "段首表达重复度较高",
                    "detail": f"段首相似度 {document_metrics.get('opening_similarity_ratio', 0.0)}%，段落展开方式较集中。",
                    "direction": "risk",
                }
            )
        if float(document_metrics.get("section_coverage_ratio") or 0.0) >= 35:
            items.append(
                {
                    "title": "中高风险内容跨章节分布",
                    "detail": f"可疑章节覆盖率 {document_metrics.get('section_coverage_ratio', 0.0)}%，不是单点异常。",
                    "direction": "risk",
                }
            )
        if int(document_metrics.get("longest_risk_streak") or 0) >= 3:
            items.append(
                {
                    "title": "存在连续风险片段带",
                    "detail": f"最长连续中高风险段落 {document_metrics.get('longest_risk_streak', 0)} 段。",
                    "direction": "risk",
                }
            )
        if float(fragment_distribution.get("high_and_middle_suspected_text_ratio") or 0.0) >= 20:
            items.append(
                {
                    "title": "高中风险文字占比较高",
                    "detail": f"高中风险文字占比 {fragment_distribution.get('high_and_middle_suspected_text_ratio', 0.0)}%。",
                    "direction": "risk",
                }
            )
        if float(fragment_distribution.get("severe_fragment_ratio") or 0.0) >= 5:
            items.append(
                {
                    "title": "存在重度疑似片段",
                    "detail": f"90%以上片段占比 {fragment_distribution.get('severe_fragment_ratio', 0.0)}%。",
                    "direction": "risk",
                }
            )
        if float(document_metrics.get("evidence_relief_pct") or 0.0) >= 6:
            items.append(
                {
                    "title": "引文与样本证据较多",
                    "detail": f"实证减权 {document_metrics.get('evidence_relief_pct', 0.0)}%，用于抑制纯模板误判。",
                    "direction": "relief",
                }
            )
        if not items:
            items.append(
                {
                    "title": "以全文统计与片段聚合综合判定",
                    "detail": f"当前识别到 {len(suspicious_segments)} 个可疑片段，建议人工复核摘要、引言与结论段。",
                    "direction": "risk",
                }
            )
        return items[:6]

    def _legacy_build_detect_result_v0(
        self,
        *,
        text: str,
        platform: str,
        mode: str,
        report_summary: dict,
        algo_result,
        llm_result: dict | None,
    ) -> dict:
        base_score = self._heuristic_ai_score(text)
        score, profile, breakdown = self._simulate_platform_detect_score(platform, text, base_score)
        paragraph_details = self._build_detect_paragraph_details(text, platform, profile, algo_result)
        distribution = self._build_detect_distribution(paragraph_details)
        document_outline = self._build_document_outline(text)
        section_distribution = self._build_section_distribution(paragraph_details, document_outline=document_outline)
        suspicious_segments = self._collect_suspicious_segments(paragraph_details)
        fragment_distribution = self._build_fragment_distribution(
            text,
            platform,
            profile,
            paragraph_details,
            document_outline=document_outline,
        )
        document_metrics = self._build_document_metrics(
            text=text,
            paragraph_details=paragraph_details,
            section_distribution=section_distribution,
            document_outline=document_outline,
            profile=profile,
        )

        mean_paragraph_ratio = round(float(distribution.get("avg_score") or 0.0) / 100.0, 4)
        max_paragraph_ratio = round(float(distribution.get("max_score") or 0.0) / 100.0, 4)
        segment_ratio = round(
            min(
                1.0,
                (
                    sum(float(item.get("score") or 0.0) for item in suspicious_segments[:5])
                    / max(len(suspicious_segments[:5]), 1)
                )
                / 100.0,
            ),
            4,
        )
        fragment_weighted_ratio = round(float(fragment_distribution.get("weighted_score_pct") or 0.0) / 100.0, 4)
        high_middle_text_ratio = round(
            float(fragment_distribution.get("high_and_middle_suspected_text_ratio") or 0.0) / 100.0,
            4,
        )
        coverage_ratio = round(float(document_metrics.get("high_medium_paragraph_ratio") or 0.0) / 100.0, 4)
        section_coverage_ratio = round(float(document_metrics.get("section_coverage_ratio") or 0.0) / 100.0, 4)
        streak_ratio = round(float(document_metrics.get("longest_risk_streak_ratio") or 0.0) / 100.0, 4)
        opening_similarity_ratio = round(float(document_metrics.get("opening_similarity_ratio") or 0.0) / 100.0, 4)
        evidence_relief_ratio = round(float(document_metrics.get("evidence_relief_pct") or 0.0) / 100.0, 4)
        score = round(
            self._clamp_score(
                score * 0.32
                + mean_paragraph_ratio * 0.22
                + max_paragraph_ratio * 0.14
                + segment_ratio * 0.10
                + fragment_weighted_ratio * 0.12
                + high_middle_text_ratio * 0.10
                + coverage_ratio * float(profile.get("coverage_weight", 0.0))
                + section_coverage_ratio * float(profile.get("section_weight", 0.0))
                + streak_ratio * float(profile.get("streak_weight", 0.0))
                + opening_similarity_ratio * float(profile.get("opening_similarity_weight", 0.0))
                - evidence_relief_ratio * float(profile.get("evidence_relief_weight", 0.0))
            ),
            4,
        )

        algo_label = ""
        llm_label = ""
        if isinstance(algo_result, dict):
            package_score = self._extract_algo_score(algo_result)
            if package_score is not None:
                score = round(self._clamp_score(score * 0.7 + package_score * 0.3), 4)
                breakdown["algo_package_score"] = round(package_score, 4)
                breakdown["algo_package_blended"] = True
            else:
                breakdown["algo_package_blended"] = False
            algo_label = self._extract_algo_label(algo_result)
        else:
            breakdown["algo_package_blended"] = False

        if isinstance(llm_result, dict):
            llm_score = self._coerce_ratio(llm_result.get("ai_score"))
            if llm_score is not None:
                score = round(self._clamp_score(score * 0.82 + llm_score * 0.18), 4)
                breakdown["llm_score"] = round(llm_score, 4)
                breakdown["llm_blended"] = True
            else:
                breakdown["llm_blended"] = False
            llm_label = self._normalize_detect_label(llm_result.get("label"))
            reason = llm_result.get("reason")
            if isinstance(reason, str) and reason.strip():
                breakdown["llm_reason"] = reason.strip()[:180]
        else:
            breakdown["llm_blended"] = False

        if algo_label:
            label = algo_label
        elif llm_label:
            label = llm_label
        else:
            label = self._score_to_detect_label(score, profile)

        decision_basis = self._build_decision_basis(
            breakdown=breakdown,
            document_metrics=document_metrics,
            fragment_distribution=fragment_distribution,
            suspicious_segments=suspicious_segments,
        )
        band = self._risk_band(score, high=profile["high"], medium=profile["medium"])
        risk_paragraphs = sorted(paragraph_details, key=lambda item: item["score"], reverse=True)[:5]
        report_no = f"GW-AIGC-{platform.upper()}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{self._current_task_id or 0}"
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        breakdown["paragraph_mean_score"] = mean_paragraph_ratio
        breakdown["peak_paragraph_score"] = max_paragraph_ratio
        breakdown["segment_signal"] = segment_ratio
        breakdown["fragment_weighted_score"] = fragment_weighted_ratio
        breakdown["high_middle_text_ratio"] = high_middle_text_ratio
        breakdown["outline_sections"] = len(document_outline)
        breakdown["coverage_ratio"] = coverage_ratio
        breakdown["section_coverage_ratio"] = section_coverage_ratio
        breakdown["streak_ratio"] = streak_ratio
        breakdown["opening_similarity_ratio"] = opening_similarity_ratio
        breakdown["evidence_relief_ratio"] = evidence_relief_ratio

        basis_titles = [str(item.get("title") or "").strip() for item in decision_basis if item.get("direction") == "risk"]
        summary = (
            f"{profile['provider_label']}全文检测完成，{profile['score_label']} {round(score * 100, 2)}%，"
            f"高风险段落占比 {distribution.get('high_ratio', 0.0)}%，"
            f"高中风险文字占比 {fragment_distribution.get('high_and_middle_suspected_text_ratio', 0.0)}%。"
        )
        if basis_titles:
            summary += f" 主要依据：{'、'.join(basis_titles[:2])}。"
        summary += " 结果用于内部研判与人工复核，不等同于官方报告。"

        return {
            "type": TaskType.AIGC_DETECT.value,
            "platform": platform,
            "provider_label": profile["provider_label"],
            "score_label": profile["score_label"],
            "simulation_profile": profile["name"],
            "report_no": report_no,
            "generated_at": generated_at,
            "mode": mode,
            "llm_used": self._pipeline_usage["llm_used"],
            "algo_package_used": self._pipeline_usage["algo_package_used"],
            "ai_score": score,
            "score_pct": round(score * 100, 2),
            "label": label,
            "risk_band": band,
            "summary": summary,
            "source_stats": self._text_stats(text),
            "report_summary": report_summary,
            "score_breakdown": breakdown,
            "distribution": distribution,
            "fragment_distribution": fragment_distribution,
            "document_metrics": document_metrics,
            "decision_basis": decision_basis,
            "document_outline": document_outline,
            "section_distribution": section_distribution,
            "risk_paragraphs": risk_paragraphs,
            "paragraph_details": paragraph_details,
            "suspicious_segments": suspicious_segments,
        }

    def _split_detect_sentences(self, text: str) -> list[str]:
        return [seg.strip() for seg in re.split(r"[。！？!?；;\n]+", str(text or "")) if seg.strip()]

    def _split_detect_paragraphs(self, text: str) -> list[str]:
        paragraphs = [part.strip() for part in str(text or "").splitlines() if part.strip()]
        if not paragraphs and str(text or "").strip():
            paragraphs = [str(text).strip()]
        return paragraphs

    def _build_detect_llm_excerpt(self, text: str, platform: str) -> str:
        clean = str(text or "").strip()
        paragraphs = self._split_detect_paragraphs(clean)
        if len(clean) <= 4800 and len(paragraphs) <= 12:
            return clean

        scored: list[tuple[int, float]] = []
        for index, paragraph in enumerate(paragraphs, start=1):
            if len(paragraph) < 20:
                continue
            base_score = self._heuristic_ai_score(paragraph)
            score, _profile, _breakdown = self._simulate_platform_detect_score(platform, paragraph, base_score)
            scored.append((index, score))

        keep: set[int] = set(range(1, min(len(paragraphs), 2) + 1))
        if paragraphs:
            keep.update(range(max(1, len(paragraphs) - 1), len(paragraphs) + 1))
        for index, _score in sorted(scored, key=lambda item: item[1], reverse=True)[:4]:
            keep.add(index)

        excerpt = "\n".join(paragraphs[index - 1] for index in sorted(keep) if 1 <= index <= len(paragraphs)).strip()
        if len(excerpt) > 4200:
            excerpt = excerpt[:4200]
        return excerpt or clean[:4200]

    def _template_signal(self, text: str) -> tuple[float, list[str]]:
        hits: list[str] = []
        phrases = [
            "研究表明",
            "本研究旨在",
            "本文基于",
            "在此背景下",
            "可以看出",
            "由此可见",
            "综上所述",
            "总而言之",
            "值得注意的是",
            "首先",
            "其次",
            "再次",
            "最后",
            "此外",
            "与此同时",
            "另一方面",
            "进一步而言",
            "从整体上看",
            "不难发现",
            "基于此",
        ]
        content = str(text or "")
        for phrase in phrases:
            if phrase in content:
                hits.append(phrase)
        density = len(hits) / max(len(content) / 85.0, 1.0)
        return round(self._clamp_score(density), 4), hits[:4]

    def _citation_relief_signal(self, text: str) -> float:
        content = str(text or "")
        patterns = [r"\[\d+\]", r"（\d{4}）", r"\(\d{4}\)", r"表\d+", r"图\d+", r"\d+%"]
        hit_count = 0
        for pattern in patterns:
            hit_count += len(re.findall(pattern, content))
        return round(min(0.18, hit_count * 0.025), 4)

    def _uniformity_signal(self, sentences: list[str]) -> float:
        lengths = [len(item.strip()) for item in sentences if item.strip()]
        if not lengths:
            return 0.0
        if len(lengths) == 1:
            return 0.5
        avg_len = sum(lengths) / len(lengths)
        variance = sum((value - avg_len) ** 2 for value in lengths) / len(lengths)
        signal = 1.0 - min(1.0, variance / max(avg_len * 14.0, 1.0))
        return round(self._clamp_score(signal), 4)

    def _opening_signal(self, text: str) -> float:
        clean = re.sub(
            r"^(?:第[一二三四五六七八九十百零0-9]+[章节部分篇]|[一二三四五六七八九十百零]+[、.．]|"
            r"\d+(?:\.\d+){0,3}[、.．]?|[（(][一二三四五六七八九十百零0-9]+[)）])",
            "",
            " ".join(str(text or "").split()),
        ).lstrip("：:.。;；、，, ")
        starters = (
            "本研究",
            "本文",
            "研究表明",
            "综上所述",
            "总而言之",
            "值得注意的是",
            "首先",
            "其次",
            "再次",
            "此外",
            "另一方面",
            "由此可见",
            "基于此",
        )
        signal = 0.48 if any(clean.startswith(token) for token in starters) else 0.0
        if re.search(r"^在.{0,8}背景下", clean):
            signal += 0.18
        return round(self._clamp_score(signal), 4)

    def _evidence_relief_signal(self, text: str) -> float:
        content = str(text or "")
        patterns = [
            r"\bN\s*=\s*\d+",
            r"样本量",
            r"问卷",
            r"访谈",
            r"实验",
            r"受访者",
            r"标准差",
            r"均值",
            r"统计",
            r"案例",
            r"观察记录",
        ]
        hit_count = 0
        for pattern in patterns:
            hit_count += len(re.findall(pattern, content, flags=re.IGNORECASE))
        return round(min(0.16, hit_count * 0.018), 4)

    def _normalized_opening_key(self, paragraph: str) -> str:
        clean = " ".join(str(paragraph or "").split())
        if not clean:
            return ""
        heading_level, _heading = self._detect_outline_heading(clean)
        if heading_level is not None:
            return ""
        normalized = re.sub(
            r"^(?:第[一二三四五六七八九十百零0-9]+[章节部分篇]|[一二三四五六七八九十百零]+[、.．]|"
            r"\d+(?:\.\d+){0,3}[、.．]?|[（(][一二三四五六七八九十百零0-9]+[)）])",
            "",
            clean,
        ).lstrip("：:.。;；、，, ")
        normalized = re.sub(r"\s+", "", normalized)
        return normalized[:12]

    def _paragraph_opening_similarity(self, paragraphs: list[str]) -> float:
        keys: list[str] = []
        starter_counts: dict[str, int] = {}
        starters = (
            "本研究",
            "本文",
            "研究表明",
            "首先",
            "其次",
            "再次",
            "最后",
            "此外",
            "另一方面",
            "值得注意的是",
            "综上所述",
            "由此可见",
            "基于此",
        )
        for paragraph in paragraphs:
            key = self._normalized_opening_key(paragraph)
            if len(key) < 6:
                continue
            keys.append(key)
            for starter in starters:
                if key.startswith(starter):
                    starter_counts[starter] = starter_counts.get(starter, 0) + 1
                    break
        if not keys:
            return 0.0
        duplicate_ratio = max(0, len(keys) - len(set(keys))) / max(len(keys), 1)
        starter_repeat_ratio = sum(max(0, count - 1) for count in starter_counts.values()) / max(len(keys), 1)
        return round(self._clamp_score(duplicate_ratio * 0.68 + starter_repeat_ratio * 0.62), 4)

    def _fragment_display_band(self, score: float, profile: dict) -> str:
        thresholds = profile.get("fragment_display_thresholds") or {}
        if score >= float(thresholds.get("severe", 0.9)):
            return "severe"
        if score >= float(thresholds.get("moderate", 0.8)):
            return "moderate"
        if score >= float(thresholds.get("mild", 0.7)):
            return "mild"
        return ""

    def _simulate_platform_detect_score(self, platform: str, text: str, base_score: float) -> tuple[float, dict, dict]:
        profile = self._platform_detect_profile(platform)
        stats = self._text_stats(text)
        clean = (text or "").strip()
        compact = " ".join(clean.split())
        unique_ratio = (len(set(compact)) / len(compact)) if compact else 1.0
        repeat_signal = self._clamp_score(1.0 - unique_ratio)
        avg_len = float(stats.get("avg_sentence_length") or 0.0)
        style_signal = self._clamp_score((avg_len - 18.0) / 52.0)
        template_signal, template_hits = self._template_signal(clean)
        context_signal = self._uniformity_signal(self._split_detect_sentences(clean))
        opening_signal = self._opening_signal(clean)
        citation_relief = self._citation_relief_signal(clean)
        evidence_relief = self._evidence_relief_signal(clean)

        weighted = (
            float(base_score) * profile["baseline_weight"]
            + style_signal * profile["style_weight"]
            + repeat_signal * profile["repeat_weight"]
            + template_signal * profile["template_weight"]
            + context_signal * profile["context_weight"]
            + opening_signal * profile["opening_weight"]
            - citation_relief
            - evidence_relief
            + profile["offset"]
        )
        score = round(self._clamp_score(weighted), 4)
        breakdown = {
            "base_score": round(float(base_score), 4),
            "style_signal": round(style_signal, 4),
            "repeat_signal": round(repeat_signal, 4),
            "template_signal": round(template_signal, 4),
            "context_signal": round(context_signal, 4),
            "opening_signal": round(opening_signal, 4),
            "citation_relief": round(citation_relief, 4),
            "evidence_relief": round(evidence_relief, 4),
            "template_hits": template_hits,
            "weights": {
                "baseline": profile["baseline_weight"],
                "style": profile["style_weight"],
                "repeat": profile["repeat_weight"],
                "template": profile["template_weight"],
                "context": profile["context_weight"],
                "opening": profile["opening_weight"],
                "offset": profile["offset"],
            },
            "thresholds": {"high": profile["high"], "medium": profile["medium"]},
        }
        return score, profile, breakdown

    def _score_to_detect_label(self, score: float, profile: dict) -> str:
        if score >= float(profile.get("high", 0.65)):
            return "high"
        if score >= float(profile.get("medium", 0.35)):
            return "medium"
        return "low"

    def _extract_algo_paragraphs(self, algo_result) -> list[dict]:
        candidates: list = []
        if not isinstance(algo_result, dict):
            return []
        for current in self._iter_result_dicts(algo_result):
            for key in ("paragraphs", "paragraph_details", "risk_paragraphs", "full_text_analysis"):
                value = current.get(key)
                if isinstance(value, list):
                    candidates = value
                    break
            if candidates:
                break

        rows: list[dict] = []
        for fallback_index, item in enumerate(candidates, start=1):
            if not isinstance(item, dict):
                continue
            score = self._coerce_ratio(
                item.get("score_ratio")
                or item.get("ai_score")
                or item.get("score")
                or item.get("score_pct")
                or item.get("risk_score")
            )
            segments: list[dict] = []
            raw_segments = item.get("suspicious_segments") or item.get("fragments") or item.get("sentences") or []
            if isinstance(raw_segments, list):
                for raw_segment in raw_segments[:6]:
                    if isinstance(raw_segment, dict):
                        text = raw_segment.get("text") or raw_segment.get("excerpt") or raw_segment.get("content") or ""
                        segment_score = self._coerce_ratio(
                            raw_segment.get("score") or raw_segment.get("score_pct") or raw_segment.get("risk_score")
                        )
                        reason = raw_segment.get("reason") or raw_segment.get("signal") or ""
                    else:
                        text = str(raw_segment or "")
                        segment_score = None
                        reason = ""
                    compact = self._clip_text(str(text), 72)
                    if not compact:
                        continue
                    segments.append(
                        {
                            "text": compact,
                            "score": round((segment_score or 0.0) * 100, 2) if segment_score is not None else 0.0,
                            "reason": str(reason).strip(),
                        }
                    )

            rows.append(
                {
                    "index": int(item.get("index") or fallback_index),
                    "score_ratio": score,
                    "label": self._normalize_detect_label(item.get("label") or item.get("risk_level")),
                    "excerpt": self._clip_text(
                        str(item.get("excerpt") or item.get("text") or item.get("content") or ""),
                        110,
                    ),
                    "segments": segments,
                }
            )
        return rows

    def _local_suspicious_segments(self, paragraph: str, platform: str, profile: dict) -> list[dict]:
        segments: list[dict] = []
        for sentence in self._split_detect_sentences(paragraph):
            if len(sentence) < 8:
                continue
            base_score = self._heuristic_ai_score(sentence)
            score, _profile, breakdown = self._simulate_platform_detect_score(platform, sentence, base_score)
            if score < float(profile.get("medium", 0.35)) and len(breakdown.get("template_hits") or []) < 2:
                continue
            reasons: list[str] = []
            if float(breakdown.get("template_signal") or 0.0) >= 0.22:
                reasons.append("模板衔接词偏多")
            if float(breakdown.get("repeat_signal") or 0.0) >= 0.32:
                reasons.append("重复表达偏多")
            if float(breakdown.get("context_signal") or 0.0) >= 0.58:
                reasons.append("句式波动较小")
            if float(breakdown.get("opening_signal") or 0.0) >= 0.44:
                reasons.append("段首表述模板化")
            segments.append(
                {
                    "text": self._clip_text(sentence, 76),
                    "score": round(score * 100, 2),
                    "reason": "、".join(reasons[:2]) or "综合风险偏高",
                }
            )
        segments.sort(key=lambda item: item["score"], reverse=True)
        return segments[:3]

    def _merge_suspicious_segments(self, *group_lists) -> list[dict]:
        merged: list[dict] = []
        seen: set[str] = set()
        for group in group_lists:
            if not isinstance(group, list):
                continue
            for item in group:
                if not isinstance(item, dict):
                    continue
                text = self._clip_text(str(item.get("text") or item.get("excerpt") or ""), 76)
                if not text or text in seen:
                    continue
                seen.add(text)
                merged.append(
                    {
                        "text": text,
                        "score": round(float(item.get("score") or 0.0), 2),
                        "reason": str(item.get("reason") or "").strip(),
                    }
                )
        merged.sort(key=lambda item: item["score"], reverse=True)
        return merged[:4]

    def _paragraph_reason_tags(self, breakdown: dict) -> list[str]:
        tags: list[str] = []
        if float(breakdown.get("template_signal") or 0.0) >= 0.22:
            tags.append("模板衔接词偏多")
        if float(breakdown.get("repeat_signal") or 0.0) >= 0.30:
            tags.append("重复表达偏高")
        if float(breakdown.get("context_signal") or 0.0) >= 0.56:
            tags.append("句式波动偏小")
        if float(breakdown.get("style_signal") or 0.0) >= 0.55:
            tags.append("长句占比较高")
        if float(breakdown.get("opening_signal") or 0.0) >= 0.44:
            tags.append("段首表述模板化")
        return tags[:3]

    def _build_detect_paragraph_details(self, text: str, platform: str, profile: dict, algo_result) -> list[dict]:
        paragraphs = self._split_detect_paragraphs(text)

        algo_map = {item["index"]: item for item in self._extract_algo_paragraphs(algo_result)}
        rows: list[dict] = []
        for index, paragraph in enumerate(paragraphs, start=1):
            base_score = self._heuristic_ai_score(paragraph)
            score_ratio, _profile, breakdown = self._simulate_platform_detect_score(platform, paragraph, base_score)
            algo_row = algo_map.get(index)
            if algo_row and algo_row.get("score_ratio") is not None:
                score_ratio = round(
                    self._clamp_score(score_ratio * 0.68 + float(algo_row["score_ratio"]) * 0.32),
                    4,
                )

            local_segments = self._local_suspicious_segments(paragraph, platform, profile)
            merged_segments = self._merge_suspicious_segments(local_segments, (algo_row or {}).get("segments") or [])
            if merged_segments:
                score_ratio = round(self._clamp_score(score_ratio + min(0.06, len(merged_segments) * 0.012)), 4)

            label = (algo_row or {}).get("label") or self._score_to_detect_label(score_ratio, profile)
            rows.append(
                {
                    "index": index,
                    "label": label,
                    "risk_band": self._risk_band(score_ratio, high=profile["high"], medium=profile["medium"]),
                    "score": round(score_ratio * 100, 2),
                    "char_count": count_billable_chars(paragraph),
                    "sentence_count": len(self._split_detect_sentences(paragraph)),
                    "excerpt": self._clip_text(paragraph, 110),
                    "reason_tags": self._paragraph_reason_tags(breakdown),
                    "suspicious_segments": merged_segments,
                }
            )
        return rows

    def _detect_outline_heading(self, text: str) -> tuple[int | None, str]:
        clean = " ".join(str(text or "").split())
        normalized = re.sub(r"\s+", "", clean).strip("：:.。;；")
        if not normalized or len(normalized) > 40:
            return None, ""

        special_labels = ("摘要", "关键词", "引言", "绪论", "前言", "结语", "结论", "参考文献", "附录", "致谢")
        if normalized in special_labels:
            return 1, clean
        if len(normalized) <= 12:
            for label in special_labels:
                if normalized.startswith(label):
                    return 1, clean

        numeric_match = re.match(r"^(\d+(?:\.\d+){0,3})[、.．]?", normalized)
        if numeric_match:
            level = min(4, numeric_match.group(1).count(".") + 1)
            return level, clean

        patterns = [
            (r"^第[一二三四五六七八九十百零0-9]+[章节部分篇]", 1),
            (r"^[一二三四五六七八九十百零]+[、.．]", 1),
            (r"^[（(][一二三四五六七八九十百零0-9]+[)）]", 2),
        ]
        for pattern, level in patterns:
            if re.match(pattern, normalized):
                return level, clean
        return None, ""

    def _is_no_ai_fragment(self, text: str) -> bool:
        clean = " ".join(str(text or "").split())
        if not clean:
            return True
        heading_level, _heading = self._detect_outline_heading(clean)
        if heading_level is not None:
            return True
        if self._citation_relief_signal(clean) >= 0.08 and len(clean) <= 90:
            return True
        if len(clean) <= 10 and not re.search(r"[\u4e00-\u9fffA-Za-z]{4,}", clean):
            return True
        return False

    def _build_document_outline(self, text: str) -> list[dict]:
        paragraphs = self._split_detect_paragraphs(text)
        outline: list[dict] = []
        seen: set[str] = set()
        for index, paragraph in enumerate(paragraphs, start=1):
            level, heading = self._detect_outline_heading(paragraph)
            if level is None:
                continue
            key = re.sub(r"\s+", "", heading)
            if key in seen:
                continue
            seen.add(key)
            outline.append(
                {
                    "section": self._clip_text(heading, 32),
                    "level": level,
                    "start_index": index,
                }
            )

        for pos, item in enumerate(outline):
            next_start = outline[pos + 1]["start_index"] if pos + 1 < len(outline) else len(paragraphs) + 1
            item["end_index"] = max(int(item["start_index"]), next_start - 1)
            item["paragraph_count"] = item["end_index"] - int(item["start_index"]) + 1
        return outline[:24]

    def _build_section_distribution(
        self,
        paragraph_details: list[dict],
        document_outline: list[dict] | None = None,
    ) -> list[dict]:
        if not paragraph_details:
            return []
        if document_outline:
            outline_rows: list[dict] = []
            for item in document_outline:
                start_index = int(item.get("start_index") or 0)
                end_index = int(item.get("end_index") or 0)
                rows = [
                    detail
                    for detail in paragraph_details
                    if start_index <= int(detail.get("index") or 0) <= end_index
                ]
                if not rows:
                    continue
                avg_score = round(sum(float(detail["score"]) for detail in rows) / len(rows), 2)
                high_count = sum(1 for detail in rows if detail.get("label") == "high")
                outline_rows.append(
                    {
                        "section": item.get("section") or "-",
                        "level": int(item.get("level") or 1),
                        "paragraph_count": len(rows),
                        "avg_score": avg_score,
                        "high_count": high_count,
                        "start_index": start_index,
                        "end_index": end_index,
                    }
                )
            if outline_rows:
                return outline_rows

        total = len(paragraph_details)
        buckets = [
            ("开篇", range(1, max(2, total // 3 + 1))),
            ("中段", range(max(2, total // 3 + 1), max(3, total * 2 // 3 + 1))),
            ("结尾", range(max(3, total * 2 // 3 + 1), total + 1)),
        ]
        results: list[dict] = []
        for label, index_range in buckets:
            rows = [item for item in paragraph_details if item["index"] in index_range]
            if not rows:
                continue
            avg_score = round(sum(float(item["score"]) for item in rows) / len(rows), 2)
            high_count = sum(1 for item in rows if item.get("label") == "high")
            results.append(
                {
                    "section": label,
                    "paragraph_count": len(rows),
                    "avg_score": avg_score,
                    "high_count": high_count,
                }
            )
        return results

    def _build_fragment_distribution(
        self,
        text: str,
        platform: str,
        profile: dict,
        paragraph_details: list[dict],
        document_outline: list[dict] | None = None,
    ) -> dict:
        paragraphs = self._split_detect_paragraphs(text)
        paragraph_score_map = {
            int(item.get("index") or 0): round(float(item.get("score") or 0.0) / 100.0, 4) for item in paragraph_details
        }

        count_map = {"high": 0, "medium": 0, "low": 0, "no_ai": 0}
        char_map = {"high": 0, "medium": 0, "low": 0, "no_ai": 0}
        display_count_map = {"mild": 0, "moderate": 0, "severe": 0}
        display_char_map = {"mild": 0, "moderate": 0, "severe": 0}
        weighted_scores: list[float] = []

        for paragraph_index, paragraph in enumerate(paragraphs, start=1):
            paragraph_ratio = paragraph_score_map.get(paragraph_index, 0.0)
            for sentence in self._split_detect_sentences(paragraph):
                compact = " ".join(sentence.split())
                if not compact:
                    continue
                char_count = count_billable_chars(compact)
                if char_count <= 0:
                    continue

                if self._is_no_ai_fragment(compact):
                    label = "no_ai"
                    score_ratio = 0.0
                else:
                    base_score = self._heuristic_ai_score(compact)
                    score_ratio, _profile, _breakdown = self._simulate_platform_detect_score(platform, compact, base_score)
                    if paragraph_ratio > 0:
                        score_ratio = round(self._clamp_score(score_ratio * 0.72 + paragraph_ratio * 0.28), 4)
                    label = self._score_to_detect_label(score_ratio, profile)
                    weighted_scores.append(score_ratio)
                    display_band = self._fragment_display_band(score_ratio, profile)
                    if display_band:
                        display_count_map[display_band] += 1
                        display_char_map[display_band] += char_count

                count_map[label] += 1
                char_map[label] += char_count

        total_fragments = sum(count_map.values())
        total_chars = sum(char_map.values())
        if total_fragments <= 0 or total_chars <= 0:
            return {
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
                "mild_fragment_count": 0,
                "moderate_fragment_count": 0,
                "severe_fragment_count": 0,
                "mild_fragment_ratio": 0.0,
                "moderate_fragment_ratio": 0.0,
                "severe_fragment_ratio": 0.0,
                "mild_text_ratio": 0.0,
                "moderate_text_ratio": 0.0,
                "severe_text_ratio": 0.0,
                "display_thresholds": {"mild": 70.0, "moderate": 80.0, "severe": 90.0},
            }

        def ratio(part: int, whole: int) -> float:
            return round(part / max(whole, 1) * 100, 2)

        high_middle_fragments = count_map["high"] + count_map["medium"]
        suspected_fragments = high_middle_fragments + count_map["low"]
        high_middle_chars = char_map["high"] + char_map["medium"]
        suspected_chars = high_middle_chars + char_map["low"]
        thresholds = profile.get("fragment_display_thresholds") or {}

        return {
            "fragment_count": total_fragments,
            "high_fragment_count": count_map["high"],
            "middle_fragment_count": count_map["medium"],
            "low_fragment_count": count_map["low"],
            "no_ai_fragment_count": count_map["no_ai"],
            "high_suspected_fragment_ratio": ratio(count_map["high"], total_fragments),
            "middle_suspected_fragment_ratio": ratio(count_map["medium"], total_fragments),
            "low_suspected_fragment_ratio": ratio(count_map["low"], total_fragments),
            "no_ai_fragment_ratio": ratio(count_map["no_ai"], total_fragments),
            "high_and_middle_suspected_fragment_ratio": ratio(high_middle_fragments, total_fragments),
            "total_suspected_fragment_ratio": ratio(suspected_fragments, total_fragments),
            "high_suspected_text_ratio": ratio(char_map["high"], total_chars),
            "middle_suspected_text_ratio": ratio(char_map["medium"], total_chars),
            "low_suspected_text_ratio": ratio(char_map["low"], total_chars),
            "no_ai_suspected_text_ratio": ratio(char_map["no_ai"], total_chars),
            "high_and_middle_suspected_text_ratio": ratio(high_middle_chars, total_chars),
            "total_suspected_text_ratio": ratio(suspected_chars, total_chars),
            "weighted_score_pct": round(sum(weighted_scores) / max(len(weighted_scores), 1) * 100, 2)
            if weighted_scores
            else 0.0,
            "mild_fragment_count": display_count_map["mild"],
            "moderate_fragment_count": display_count_map["moderate"],
            "severe_fragment_count": display_count_map["severe"],
            "mild_fragment_ratio": ratio(display_count_map["mild"], total_fragments),
            "moderate_fragment_ratio": ratio(display_count_map["moderate"], total_fragments),
            "severe_fragment_ratio": ratio(display_count_map["severe"], total_fragments),
            "mild_text_ratio": ratio(display_char_map["mild"], total_chars),
            "moderate_text_ratio": ratio(display_char_map["moderate"], total_chars),
            "severe_text_ratio": ratio(display_char_map["severe"], total_chars),
            "display_thresholds": {
                "mild": round(float(thresholds.get("mild", 0.7)) * 100, 2),
                "moderate": round(float(thresholds.get("moderate", 0.8)) * 100, 2),
                "severe": round(float(thresholds.get("severe", 0.9)) * 100, 2),
            },
        }

    def _build_document_metrics(
        self,
        *,
        text: str,
        paragraph_details: list[dict],
        section_distribution: list[dict],
        document_outline: list[dict],
        profile: dict,
    ) -> dict:
        total = len(paragraph_details)
        total_chars = sum(int(item.get("char_count") or 0) for item in paragraph_details)
        high_medium_count = sum(1 for item in paragraph_details if item.get("label") in {"high", "medium"})
        high_medium_chars = sum(
            int(item.get("char_count") or 0) for item in paragraph_details if item.get("label") in {"high", "medium"}
        )
        longest_streak = 0
        current_streak = 0
        for item in paragraph_details:
            if item.get("label") in {"high", "medium"}:
                current_streak += 1
                longest_streak = max(longest_streak, current_streak)
            else:
                current_streak = 0
        medium_threshold = float(profile.get("medium", 0.35)) * 100
        suspicious_sections = sum(
            1
            for item in section_distribution
            if float(item.get("avg_score") or 0.0) >= medium_threshold or int(item.get("high_count") or 0) > 0
        )
        paragraphs = self._split_detect_paragraphs(text)
        opening_similarity = self._paragraph_opening_similarity(paragraphs)
        evidence_relief = max(self._citation_relief_signal(text), self._evidence_relief_signal(text))
        return {
            "paragraph_count": total,
            "high_medium_paragraph_count": high_medium_count,
            "high_medium_paragraph_ratio": round(high_medium_count / max(total, 1) * 100, 2) if total else 0.0,
            "high_medium_text_ratio": round(high_medium_chars / max(total_chars, 1) * 100, 2) if total_chars else 0.0,
            "longest_risk_streak": longest_streak,
            "longest_risk_streak_ratio": round(longest_streak / max(total, 1) * 100, 2) if total else 0.0,
            "opening_similarity_ratio": round(opening_similarity * 100, 2),
            "section_count": len(section_distribution),
            "suspicious_section_count": suspicious_sections,
            "section_coverage_ratio": round(suspicious_sections / max(len(section_distribution), 1) * 100, 2)
            if section_distribution
            else 0.0,
            "outline_sections": len(document_outline),
            "distribution_mode": "outline" if document_outline else "band",
            "evidence_relief_pct": round(evidence_relief * 100, 2),
        }

    def _build_decision_basis(
        self,
        *,
        breakdown: dict,
        document_metrics: dict,
        fragment_distribution: dict,
        suspicious_segments: list[dict],
    ) -> list[dict]:
        items: list[dict] = []
        template_signal = float(breakdown.get("template_signal") or 0.0)
        context_signal = float(breakdown.get("context_signal") or 0.0)
        repeat_signal = float(breakdown.get("repeat_signal") or 0.0)
        opening_signal = float(breakdown.get("opening_signal") or 0.0)
        template_hits = [str(item) for item in (breakdown.get("template_hits") or []) if str(item).strip()]

        if template_signal >= 0.2:
            hit_text = "、".join(template_hits[:3]) if template_hits else "高频模板连接词"
            items.append(
                {
                    "title": "模板连接词密度偏高",
                    "detail": f"命中 {hit_text}，模板信号 {round(template_signal * 100, 2)}%。",
                    "direction": "risk",
                }
            )
        if context_signal >= 0.55:
            items.append(
                {
                    "title": "句长波动偏小",
                    "detail": f"上下文均匀度 {round(context_signal * 100, 2)}%，更接近机器批量生成的平直节奏。",
                    "direction": "risk",
                }
            )
        if repeat_signal >= 0.3:
            items.append(
                {
                    "title": "重复表达偏多",
                    "detail": f"重复信号 {round(repeat_signal * 100, 2)}%，存在近义重复或固定总结句反复出现。",
                    "direction": "risk",
                }
            )
        if opening_signal >= 0.44 or float(document_metrics.get("opening_similarity_ratio") or 0.0) >= 25:
            items.append(
                {
                    "title": "段首表达重复度较高",
                    "detail": f"段首相似度 {document_metrics.get('opening_similarity_ratio', 0.0)}%，段落展开方式较集中。",
                    "direction": "risk",
                }
            )
        if float(document_metrics.get("section_coverage_ratio") or 0.0) >= 35:
            items.append(
                {
                    "title": "中高风险内容跨章节分布",
                    "detail": f"可疑章节覆盖率 {document_metrics.get('section_coverage_ratio', 0.0)}%，不是单点异常。",
                    "direction": "risk",
                }
            )
        if int(document_metrics.get("longest_risk_streak") or 0) >= 3:
            items.append(
                {
                    "title": "存在连续风险片段带",
                    "detail": f"最长连续中高风险段落 {document_metrics.get('longest_risk_streak', 0)} 段。",
                    "direction": "risk",
                }
            )
        if float(fragment_distribution.get("high_and_middle_suspected_text_ratio") or 0.0) >= 20:
            items.append(
                {
                    "title": "高中风险文字占比较高",
                    "detail": f"高中风险文字占比 {fragment_distribution.get('high_and_middle_suspected_text_ratio', 0.0)}%。",
                    "direction": "risk",
                }
            )
        if float(fragment_distribution.get("severe_fragment_ratio") or 0.0) >= 5:
            items.append(
                {
                    "title": "存在重度疑似片段",
                    "detail": f"90%以上片段占比 {fragment_distribution.get('severe_fragment_ratio', 0.0)}%。",
                    "direction": "risk",
                }
            )
        if float(document_metrics.get("evidence_relief_pct") or 0.0) >= 6:
            items.append(
                {
                    "title": "引文与样本证据较多",
                    "detail": f"实证减权 {document_metrics.get('evidence_relief_pct', 0.0)}%，用于抑制纯模板误判。",
                    "direction": "relief",
                }
            )
        if not items:
            items.append(
                {
                    "title": "以全文统计与片段聚合综合判定",
                    "detail": f"当前识别到 {len(suspicious_segments)} 个可疑片段，建议人工复核摘要、引言与结论段。",
                    "direction": "risk",
                }
            )
        return items[:6]

    def _collect_suspicious_segments(self, paragraph_details: list[dict]) -> list[dict]:
        items: list[dict] = []
        seen: set[str] = set()
        for paragraph in paragraph_details:
            for segment in paragraph.get("suspicious_segments") or []:
                text = str(segment.get("text") or "").strip()
                if not text or text in seen:
                    continue
                seen.add(text)
                items.append(
                    {
                        "paragraph_index": paragraph.get("index"),
                        "score": round(float(segment.get("score") or 0.0), 2),
                        "text": text,
                        "reason": str(segment.get("reason") or "").strip(),
                    }
                )
        items.sort(key=lambda item: item["score"], reverse=True)
        return items[:12]

    def _build_detect_distribution(self, paragraph_details: list[dict]) -> dict:
        total = len(paragraph_details)
        if total == 0:
            return {
                "paragraph_count": 0,
                "high_count": 0,
                "medium_count": 0,
                "low_count": 0,
                "high_ratio": 0.0,
                "medium_ratio": 0.0,
                "low_ratio": 0.0,
                "avg_score": 0.0,
                "max_score": 0.0,
            }
        high_count = sum(1 for item in paragraph_details if item.get("label") == "high")
        medium_count = sum(1 for item in paragraph_details if item.get("label") == "medium")
        low_count = total - high_count - medium_count
        scores = [float(item.get("score") or 0.0) for item in paragraph_details]
        return {
            "paragraph_count": total,
            "high_count": high_count,
            "medium_count": medium_count,
            "low_count": low_count,
            "high_ratio": round(high_count / total * 100, 2),
            "medium_ratio": round(medium_count / total * 100, 2),
            "low_ratio": round(low_count / total * 100, 2),
            "avg_score": round(sum(scores) / total, 2),
            "max_score": round(max(scores), 2),
        }

    def _build_detect_result(
        self,
        *,
        text: str,
        platform: str,
        mode: str,
        report_summary: dict,
        algo_result,
        llm_result: dict | None,
    ) -> dict:
        base_score = self._heuristic_ai_score(text)
        score, profile, breakdown = self._simulate_platform_detect_score(platform, text, base_score)
        paragraph_details = self._build_detect_paragraph_details(text, platform, profile, algo_result)
        distribution = self._build_detect_distribution(paragraph_details)
        document_outline = self._build_document_outline(text)
        section_distribution = self._build_section_distribution(paragraph_details, document_outline=document_outline)
        suspicious_segments = self._collect_suspicious_segments(paragraph_details)
        fragment_distribution = self._build_fragment_distribution(
            text,
            platform,
            profile,
            paragraph_details,
            document_outline=document_outline,
        )
        document_metrics = self._build_document_metrics(
            text=text,
            paragraph_details=paragraph_details,
            section_distribution=section_distribution,
            document_outline=document_outline,
            profile=profile,
        )

        mean_paragraph_ratio = round(float(distribution.get("avg_score") or 0.0) / 100.0, 4)
        max_paragraph_ratio = round(float(distribution.get("max_score") or 0.0) / 100.0, 4)
        segment_ratio = round(
            min(
                1.0,
                (
                    sum(float(item.get("score") or 0.0) for item in suspicious_segments[:5])
                    / max(len(suspicious_segments[:5]), 1)
                )
                / 100.0,
            ),
            4,
        )
        fragment_weighted_ratio = round(float(fragment_distribution.get("weighted_score_pct") or 0.0) / 100.0, 4)
        high_middle_text_ratio = round(
            float(fragment_distribution.get("high_and_middle_suspected_text_ratio") or 0.0) / 100.0,
            4,
        )
        coverage_ratio = round(float(document_metrics.get("high_medium_paragraph_ratio") or 0.0) / 100.0, 4)
        section_coverage_ratio = round(float(document_metrics.get("section_coverage_ratio") or 0.0) / 100.0, 4)
        streak_ratio = round(float(document_metrics.get("longest_risk_streak_ratio") or 0.0) / 100.0, 4)
        opening_similarity_ratio = round(float(document_metrics.get("opening_similarity_ratio") or 0.0) / 100.0, 4)
        evidence_relief_ratio = round(float(document_metrics.get("evidence_relief_pct") or 0.0) / 100.0, 4)
        score = round(
            self._clamp_score(
                score * 0.32
                + mean_paragraph_ratio * 0.22
                + max_paragraph_ratio * 0.14
                + segment_ratio * 0.10
                + fragment_weighted_ratio * 0.12
                + high_middle_text_ratio * 0.10
                + coverage_ratio * float(profile.get("coverage_weight", 0.0))
                + section_coverage_ratio * float(profile.get("section_weight", 0.0))
                + streak_ratio * float(profile.get("streak_weight", 0.0))
                + opening_similarity_ratio * float(profile.get("opening_similarity_weight", 0.0))
                - evidence_relief_ratio * float(profile.get("evidence_relief_weight", 0.0))
            ),
            4,
        )
        algo_label = ""
        llm_label = ""

        if isinstance(algo_result, dict):
            package_score = self._extract_algo_score(algo_result)
            if package_score is not None:
                score = round(self._clamp_score(score * 0.7 + package_score * 0.3), 4)
                breakdown["algo_package_score"] = round(package_score, 4)
                breakdown["algo_package_blended"] = True
            else:
                breakdown["algo_package_blended"] = False

            algo_label = self._extract_algo_label(algo_result)
        else:
            breakdown["algo_package_blended"] = False

        if isinstance(llm_result, dict):
            llm_score = self._coerce_ratio(llm_result.get("ai_score"))
            if llm_score is not None:
                score = round(self._clamp_score(score * 0.82 + llm_score * 0.18), 4)
                breakdown["llm_score"] = round(llm_score, 4)
                breakdown["llm_blended"] = True
            else:
                breakdown["llm_blended"] = False

            llm_label = self._normalize_detect_label(llm_result.get("label"))

            reason = llm_result.get("reason")
            if isinstance(reason, str) and reason.strip():
                breakdown["llm_reason"] = reason.strip()[:180]
        else:
            breakdown["llm_blended"] = False

        if algo_label:
            label = algo_label
        elif llm_label:
            label = llm_label
        else:
            label = self._score_to_detect_label(score, profile)

        decision_basis = self._build_decision_basis(
            breakdown=breakdown,
            document_metrics=document_metrics,
            fragment_distribution=fragment_distribution,
            suspicious_segments=suspicious_segments,
        )

        band = self._risk_band(score, high=profile["high"], medium=profile["medium"])
        risk_paragraphs = sorted(paragraph_details, key=lambda item: item["score"], reverse=True)[:5]
        report_no = f"GW-AIGC-{platform.upper()}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{self._current_task_id or 0}"
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        breakdown["paragraph_mean_score"] = mean_paragraph_ratio
        breakdown["peak_paragraph_score"] = max_paragraph_ratio
        breakdown["segment_signal"] = segment_ratio
        breakdown["fragment_weighted_score"] = fragment_weighted_ratio
        breakdown["high_middle_text_ratio"] = high_middle_text_ratio
        breakdown["outline_sections"] = len(document_outline)
        breakdown["coverage_ratio"] = coverage_ratio
        breakdown["section_coverage_ratio"] = section_coverage_ratio
        breakdown["streak_ratio"] = streak_ratio
        breakdown["opening_similarity_ratio"] = opening_similarity_ratio
        breakdown["evidence_relief_ratio"] = evidence_relief_ratio

        basis_titles = [str(item.get("title") or "").strip() for item in decision_basis if item.get("direction") == "risk"]
        summary = (
            f"{profile['provider_label']}全文检测完成，{profile['score_label']} {round(score * 100, 2)}%，"
            f"高风险段落占比 {distribution.get('high_ratio', 0.0)}%，"
            f"高中风险文字占比 {fragment_distribution.get('high_and_middle_suspected_text_ratio', 0.0)}%。"
        )
        if basis_titles:
            summary += f" 主要依据：{'、'.join(basis_titles[:2])}。"
        summary += " 结果用于内部研判与人工复核，不等同于官方报告。"

        return {
            "type": TaskType.AIGC_DETECT.value,
            "platform": platform,
            "provider_label": profile["provider_label"],
            "score_label": profile["score_label"],
            "simulation_profile": profile["name"],
            "report_no": report_no,
            "generated_at": generated_at,
            "mode": mode,
            "llm_used": self._pipeline_usage["llm_used"],
            "algo_package_used": self._pipeline_usage["algo_package_used"],
            "ai_score": score,
            "score_pct": round(score * 100, 2),
            "label": label,
            "risk_band": band,
            "summary": summary,
            "source_stats": self._text_stats(text),
            "report_summary": report_summary,
            "score_breakdown": breakdown,
            "distribution": distribution,
            "fragment_distribution": fragment_distribution,
            "document_metrics": document_metrics,
            "decision_basis": decision_basis,
            "document_outline": document_outline,
            "section_distribution": section_distribution,
            "risk_paragraphs": risk_paragraphs,
            "paragraph_details": paragraph_details,
            "suspicious_segments": suspicious_segments,
        }

    def _risk_band(self, score: float, *, high: float = 0.65, medium: float = 0.35) -> str:
        if score >= high:
            return "高风险"
        if score >= medium:
            return "中风险"
        return "低风险"

    def _legacy_top_risk_paragraphs_v0(self, text: str, platform: str = "cnki") -> list[dict]:
        profile = self._platform_detect_profile(platform)
        rows = self._build_detect_paragraph_details(text, platform, profile, None)
        return sorted(rows, key=lambda item: item["score"], reverse=True)[:5]

    def _wrap_pdf_line(self, text: str, width: int = 56) -> list[str]:
        compact = " ".join(str(text or "").split())
        if not compact:
            return [""]

        lines: list[str] = []
        current = ""
        current_width = 0
        for char in compact:
            char_width = 1 if ord(char) < 128 else 2
            if current and current_width + char_width > width:
                lines.append(current.rstrip())
                current = char
                current_width = char_width
                continue
            current += char
            current_width += char_width
        if current:
            lines.append(current.rstrip())
        return lines or [""]

    def _pdf_text_hex(self, text: str) -> str:
        value = str(text or " ")
        return value.encode("utf-16-be").hex().upper()

    def _render_pdf(self, lines: list[str]) -> bytes:
        page_width = 595
        page_height = 842
        margin_x = 44
        margin_top = 56
        margin_bottom = 48
        font_size = 11
        line_height = 16

        expanded_lines: list[str] = []
        for line in lines:
            wrapped = self._wrap_pdf_line(line, width=56)
            expanded_lines.extend(wrapped if wrapped else [""])
        if not expanded_lines:
            expanded_lines = [""]

        usable_height = page_height - margin_top - margin_bottom
        lines_per_page = max(1, int(usable_height // line_height))
        page_line_chunks = [
            expanded_lines[i : i + lines_per_page] for i in range(0, len(expanded_lines), lines_per_page)
        ]

        objects: list[tuple[int, bytes]] = [(1, b"<< /Type /Catalog /Pages 2 0 R >>")]
        page_refs: list[str] = []
        next_obj_id = 3
        font_obj_id = 2 + len(page_line_chunks) * 2 + 1
        descendant_font_obj_id = font_obj_id + 1

        for chunk in page_line_chunks:
            page_obj_id = next_obj_id
            content_obj_id = next_obj_id + 1
            next_obj_id += 2
            page_refs.append(f"{page_obj_id} 0 R")

            text_ops: list[str] = []
            for index, line in enumerate(chunk):
                y = page_height - margin_top - index * line_height
                hex_text = self._pdf_text_hex(line)
                text_ops.append(f"BT /F1 {font_size} Tf 1 0 0 1 {margin_x} {y:.2f} Tm <{hex_text}> Tj ET")
            stream_text = "\n".join(text_ops)
            stream_bytes = stream_text.encode("ascii")

            page_obj = (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] "
                f"/Resources << /Font << /F1 {font_obj_id} 0 R >> >> /Contents {content_obj_id} 0 R >>"
            ).encode("ascii")
            content_obj = (
                f"<< /Length {len(stream_bytes)} >>\nstream\n".encode("ascii")
                + stream_bytes
                + b"\nendstream"
            )
            objects.append((page_obj_id, page_obj))
            objects.append((content_obj_id, content_obj))

        pages_obj = f"<< /Type /Pages /Count {len(page_line_chunks)} /Kids [{' '.join(page_refs)}] >>".encode("ascii")
        objects.insert(1, (2, pages_obj))
        objects.append(
            (
                font_obj_id,
                (
                    f"<< /Type /Font /Subtype /Type0 /BaseFont /STSong-Light "
                    f"/Encoding /UniGB-UCS2-H /DescendantFonts [{descendant_font_obj_id} 0 R] >>"
                ).encode("ascii"),
            )
        )
        objects.append(
            (
                descendant_font_obj_id,
                b"<< /Type /Font /Subtype /CIDFontType0 /BaseFont /STSong-Light "
                b"/CIDSystemInfo << /Registry (Adobe) /Ordering (GB1) /Supplement 4 >> /DW 1000 >>",
            )
        )

        objects.sort(key=lambda item: item[0])
        output = bytearray()
        output.extend(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets: dict[int, int] = {}

        for obj_id, obj_body in objects:
            offsets[obj_id] = len(output)
            output.extend(f"{obj_id} 0 obj\n".encode("ascii"))
            output.extend(obj_body)
            output.extend(b"\nendobj\n")

        xref_offset = len(output)
        max_obj_id = max(offsets)
        output.extend(f"xref\n0 {max_obj_id + 1}\n".encode("ascii"))
        output.extend(b"0000000000 65535 f \n")
        for obj_id in range(1, max_obj_id + 1):
            offset = offsets.get(obj_id, 0)
            output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
        output.extend(f"trailer\n<< /Size {max_obj_id + 1} /Root 1 0 R >>\n".encode("ascii"))
        output.extend(f"startxref\n{xref_offset}\n%%EOF".encode("ascii"))
        return bytes(output)

    def _build_transform_result(
        self,
        *,
        task_type: TaskType,
        platform: str,
        mode: str,
        source_text: str,
        output_text: str,
        report_summary: dict,
    ) -> dict:
        source_stats = self._text_stats(source_text)
        output_stats = self._text_stats(output_text)
        sample_before = source_text[:4000]
        sample_after = output_text[:4000]
        similarity = SequenceMatcher(None, sample_before, sample_after).ratio() if sample_before or sample_after else 1.0
        change_ratio = round((1 - similarity) * 100, 2)
        task_label = "降重" if task_type == TaskType.DEDUP else "学术润色"
        review_points = list(report_summary.get("recommended_actions") or [])
        review_points.append("建议下载结果文档后结合原文进行人工终审。")
        review_points.append("重点检查摘要、结论、数据表述和引用位置。")
        deduped_points = list(dict.fromkeys(review_points))
        return {
            "type": task_type.value,
            "platform": platform,
            "mode": mode,
            "llm_used": self._pipeline_usage["llm_used"],
            "algo_package_used": self._pipeline_usage["algo_package_used"],
            "summary": f"{task_label}任务已完成，本次结果已结合正文与辅助报告生成处理摘要。",
            "source_stats": source_stats,
            "output_stats": output_stats,
            "change_ratio": change_ratio,
            "report_summary": report_summary,
            "review_points": deduped_points[:4],
            "output_preview": self._clip_text(output_text, 220),
        }

    def _clip_text(self, text: str, limit: int) -> str:
        compact = " ".join((text or "").split())
        if len(compact) <= limit:
            return compact
        return f"{compact[:limit].rstrip()}..."

    def _current_task_report_meta(self) -> dict:
        from app.models import Task

        if not self._current_task_id:
            return {}
        task = self.db.get(Task, self._current_task_id)
        if task is None:
            return {}
        payload = task.result_json if isinstance(task.result_json, dict) else {}
        return {
            "paper_title": str(payload.get("paper_title") or "").strip(),
            "authors": str(payload.get("authors") or "").strip(),
            "source_filename": str(task.source_filename or "").strip(),
        }

    def _build_detect_band_rows(self, paragraph_details: list[dict]) -> list[dict]:
        total = len(paragraph_details)
        if total <= 0:
            return [
                {"label": "前部20%", "paragraph_count": 0, "avg_score": 0.0, "high_count": 0, "char_count": 0},
                {"label": "中部60%", "paragraph_count": 0, "avg_score": 0.0, "high_count": 0, "char_count": 0},
                {"label": "后部20%", "paragraph_count": 0, "avg_score": 0.0, "high_count": 0, "char_count": 0},
            ]

        front_end = max(1, math.ceil(total * 0.2))
        middle_end = max(front_end, math.ceil(total * 0.8))
        chunks = [
            ("前部20%", paragraph_details[:front_end]),
            ("中部60%", paragraph_details[front_end:middle_end]),
            ("后部20%", paragraph_details[middle_end:]),
        ]

        rows: list[dict] = []
        for label, items in chunks:
            paragraph_count = len(items)
            avg_score = round(sum(float(item.get("score") or 0.0) for item in items) / paragraph_count, 2) if items else 0.0
            high_count = sum(1 for item in items if str(item.get("label") or "").lower() == "high")
            char_count = sum(int(item.get("char_count") or 0) for item in items)
            rows.append(
                {
                    "label": label,
                    "paragraph_count": paragraph_count,
                    "avg_score": avg_score,
                    "high_count": high_count,
                    "char_count": char_count,
                }
            )
        return rows

    def _escape_pdf_text(self, text: str) -> str:
        return (
            str(text or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br/>")
        )

    def _write_detect_report_pdf(self, output_path: Path, result: dict) -> None:
        output_path.write_bytes(self._render_detect_report_pdf(result))

    def _render_detect_report_pdf(self, result: dict) -> bytes:
        from io import BytesIO

        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=16 * mm,
            rightMargin=16 * mm,
            topMargin=16 * mm,
            bottomMargin=14 * mm,
            title="格物学术 AIGC 全文检测报告",
            author="格物学术",
        )

        base_styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "DetectTitle",
            parent=base_styles["Title"],
            fontName="STSong-Light",
            fontSize=20,
            leading=26,
            textColor=colors.HexColor("#111111"),
            alignment=1,
            spaceAfter=6,
        )
        subtitle_style = ParagraphStyle(
            "DetectSubtitle",
            parent=base_styles["BodyText"],
            fontName="STSong-Light",
            fontSize=10.5,
            leading=15,
            textColor=colors.HexColor("#666666"),
            alignment=1,
            spaceAfter=12,
        )
        section_style = ParagraphStyle(
            "DetectSection",
            parent=base_styles["Heading2"],
            fontName="STSong-Light",
            fontSize=13,
            leading=18,
            textColor=colors.HexColor("#111111"),
            spaceBefore=8,
            spaceAfter=8,
        )
        body_style = ParagraphStyle(
            "DetectBody",
            parent=base_styles["BodyText"],
            fontName="STSong-Light",
            fontSize=10,
            leading=15,
            textColor=colors.HexColor("#222222"),
        )
        small_style = ParagraphStyle(
            "DetectSmall",
            parent=body_style,
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#666666"),
        )
        emphasis_style = ParagraphStyle(
            "DetectEmphasis",
            parent=body_style,
            fontSize=11,
            leading=16,
            textColor=colors.HexColor("#111111"),
        )

        meta = self._current_task_report_meta()
        stats = result.get("source_stats") or {}
        distribution = result.get("distribution") or {}
        fragment_distribution = result.get("fragment_distribution") or {}
        document_metrics = result.get("document_metrics") or {}
        decision_basis = result.get("decision_basis") or []
        document_outline = result.get("document_outline") or []
        section_distribution = result.get("section_distribution") or []
        paragraph_details = result.get("paragraph_details") or []
        suspicious_segments = result.get("suspicious_segments") or []
        band_rows = self._build_detect_band_rows(paragraph_details)
        paper_title = meta.get("paper_title") or "未填写"
        authors = meta.get("authors") or "未填写"
        source_filename = meta.get("source_filename") or "未记录"

        def para(text: str, style: ParagraphStyle) -> Paragraph:
            return Paragraph(self._escape_pdf_text(text), style)

        def build_table(rows, col_widths=None, header=False, font_size=9.5):
            table = Table(rows, colWidths=col_widths, repeatRows=1 if header else 0)
            base_style = [
                ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                ("FONTSIZE", (0, 0), (-1, -1), font_size),
                ("LEADING", (0, 0), (-1, -1), font_size + 4),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#222222")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f5f1e8") if header else colors.white),
                ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#d7d0c2")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
            if header:
                base_style.extend(
                    [
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#111111")),
                        ("FONTNAME", (0, 0), (-1, 0), "STSong-Light"),
                    ]
                )
            table.setStyle(TableStyle(base_style))
            return table

        story: list = [
            para("AIGC检测 · 全文报告单", title_style),
            para("格物学术仿真版，结构参考知网公开报告形态，结果仅作内部研判与人工复核辅助。", subtitle_style),
        ]

        summary_rows = [
            [para("报告编号", body_style), para(str(result.get("report_no") or "-"), body_style)],
            [para("检测时间", body_style), para(str(result.get("generated_at") or "-"), body_style)],
            [para("检测平台", body_style), para(str(result.get("provider_label") or result.get("platform") or "-"), body_style)],
            [para("检测模式", body_style), para(str(result.get("mode") or "-"), body_style)],
            [para("篇名", body_style), para(paper_title, body_style)],
            [para("作者", body_style), para(authors, body_style)],
            [para("文件名", body_style), para(source_filename, body_style)],
        ]
        story.append(build_table(summary_rows, col_widths=[28 * mm, 150 * mm]))
        story.append(Spacer(1, 6))

        story.append(para("一、全文检测结果", section_style))
        headline_rows = [
            [para("AI特征值", small_style), para("风险等级", small_style), para("总字符数", small_style), para("可疑片段数", small_style)],
            [
                para(f"{result.get('score_pct', 0)}%", emphasis_style),
                para(str(result.get("risk_band") or "-"), emphasis_style),
                para(str(stats.get("char_count", 0)), emphasis_style),
                para(str(len(suspicious_segments)), emphasis_style),
            ],
        ]
        story.append(build_table(headline_rows, col_widths=[42 * mm, 42 * mm, 42 * mm, 42 * mm], header=True, font_size=10))
        story.append(Spacer(1, 4))
        story.append(para(str(result.get("summary") or ""), body_style))
        if decision_basis:
            story.append(Spacer(1, 6))
            story.append(para("判定依据摘要", small_style))
            basis_rows = [["方向", "依据", "说明"]]
            for item in decision_basis[:6]:
                basis_rows.append(
                    [
                        "减权" if str(item.get("direction") or "") == "relief" else "风险",
                        str(item.get("title") or "-"),
                        str(item.get("detail") or "-"),
                    ]
                )
            story.append(
                build_table(
                    basis_rows,
                    col_widths=[18 * mm, 46 * mm, 114 * mm],
                    header=True,
                    font_size=8.8,
                )
            )

        story.append(Spacer(1, 10))
        story.append(para("二、AIGC文字与片段分布", section_style))
        ratio_rows = [["等级", "文字占比", "片段数", "片段占比"]]
        ratio_rows.extend(
            [
                [
                    "高风险",
                    f"{fragment_distribution.get('high_suspected_text_ratio', 0)}%",
                    str(fragment_distribution.get("high_fragment_count", 0)),
                    f"{fragment_distribution.get('high_suspected_fragment_ratio', 0)}%",
                ],
                [
                    "中风险",
                    f"{fragment_distribution.get('middle_suspected_text_ratio', 0)}%",
                    str(fragment_distribution.get("middle_fragment_count", 0)),
                    f"{fragment_distribution.get('middle_suspected_fragment_ratio', 0)}%",
                ],
                [
                    "低风险",
                    f"{fragment_distribution.get('low_suspected_text_ratio', 0)}%",
                    str(fragment_distribution.get("low_fragment_count", 0)),
                    f"{fragment_distribution.get('low_suspected_fragment_ratio', 0)}%",
                ],
                [
                    "不计入片段",
                    f"{fragment_distribution.get('no_ai_suspected_text_ratio', 0)}%",
                    str(fragment_distribution.get("no_ai_fragment_count", 0)),
                    f"{fragment_distribution.get('no_ai_fragment_ratio', 0)}%",
                ],
            ]
        )
        story.append(build_table(ratio_rows, col_widths=[36 * mm, 44 * mm, 44 * mm, 44 * mm], header=True))
        story.append(Spacer(1, 6))
        story.append(
            para(
                f"高中风险文字占比 {fragment_distribution.get('high_and_middle_suspected_text_ratio', 0)}%，"
                f"总疑似文字占比 {fragment_distribution.get('total_suspected_text_ratio', 0)}%，"
                f"片段加权值 {fragment_distribution.get('weighted_score_pct', 0)}%。",
                small_style,
            )
        )
        story.append(Spacer(1, 8))
        story.append(para("按全文位置统计", small_style))
        band_table = [["区段", "段落数", "均值", "高风险段落", "字符数"]]
        for item in band_rows:
            band_table.append(
                [
                    item["label"],
                    str(item["paragraph_count"]),
                    f"{item['avg_score']}%",
                    str(item["high_count"]),
                    str(item["char_count"]),
                ]
            )
        story.append(build_table(band_table, col_widths=[32 * mm, 28 * mm, 28 * mm, 34 * mm, 34 * mm], header=True))

        story.append(Spacer(1, 10))
        story.append(para("三、章节目录与分布", section_style))
        if document_outline:
            outline_map = {str(item.get("section") or ""): item for item in section_distribution}
            outline_rows = [["章节", "起止段落", "层级", "平均风险"]]
            for item in document_outline[:18]:
                section_row = outline_map.get(str(item.get("section") or ""))
                outline_rows.append(
                    [
                        str(item.get("section") or "-"),
                        f"P{int(item.get('start_index') or 0):02d}-P{int(item.get('end_index') or 0):02d}",
                        str(item.get("level") or 1),
                        f"{(section_row or {}).get('avg_score', 0)}%",
                    ]
                )
            story.append(build_table(outline_rows, col_widths=[88 * mm, 34 * mm, 20 * mm, 34 * mm], header=True))
        elif section_distribution:
            section_rows = [["章节区段", "段落数", "均值", "高风险段落"]]
            for item in section_distribution:
                section_rows.append(
                    [
                        str(item.get("section") or "-"),
                        str(item.get("paragraph_count") or 0),
                        f"{item.get('avg_score', 0)}%",
                        str(item.get("high_count") or 0),
                    ]
                )
            story.append(build_table(section_rows, col_widths=[54 * mm, 30 * mm, 30 * mm, 44 * mm], header=True))
        else:
            story.append(para("未识别到可用的章节目录信息。", body_style))

        story.append(Spacer(1, 10))
        story.append(para("四、片段指标列表", section_style))
        indicator_rows = [["序号", "片段名称", "所在段落", "字符数", "风险值", "判定"]]
        for idx, item in enumerate(suspicious_segments[:12], start=1):
            indicator_rows.append(
                [
                    str(idx),
                    f"片段{idx}",
                    f"P{int(item.get('paragraph_index') or 0):02d}",
                    str(len(str(item.get("text") or ""))),
                    f"{item.get('score', 0)}%",
                    str(item.get("reason") or "综合风险偏高"),
                ]
            )
        if len(indicator_rows) == 1:
            indicator_rows.append(["-", "-", "-", "0", "0%", "未识别到高风险片段"])
        story.append(
            build_table(
                indicator_rows,
                col_widths=[14 * mm, 24 * mm, 22 * mm, 20 * mm, 20 * mm, 72 * mm],
                header=True,
                font_size=8.8,
            )
        )

        story.append(Spacer(1, 10))
        story.append(para("五、原文重点片段详情", section_style))
        if suspicious_segments:
            for idx, item in enumerate(suspicious_segments[:10], start=1):
                detail_rows = [
                    [para(f"NO.{idx} 片段{idx}", emphasis_style), para(f"段落：P{int(item.get('paragraph_index') or 0):02d}    风险值：{item.get('score', 0)}%", emphasis_style)],
                    [para("风险判定", body_style), para(str(item.get("reason") or "综合风险偏高"), body_style)],
                    [para("原文内容", body_style), para(self._clip_text(str(item.get("text") or ""), 220), body_style)],
                ]
                story.append(KeepTogether([build_table(detail_rows, col_widths=[28 * mm, 150 * mm]), Spacer(1, 6)]))
        else:
            story.append(para("本次未识别到高置信的可疑片段。", body_style))

        story.append(PageBreak())
        story.append(para("六、全文段落明细", section_style))
        if paragraph_details:
            for item in paragraph_details:
                reason_tags = "、".join(item.get("reason_tags") or []) or "综合语义判定"
                lines = [
                    para(
                        f"P{int(item.get('index') or 0):02d} | {item.get('risk_band') or '-'} | {item.get('score', 0)}% | 字符 {item.get('char_count', 0)} | 句子 {item.get('sentence_count', 0)}",
                        emphasis_style,
                    ),
                    para(f"信号：{reason_tags}", small_style),
                    para(f"摘要：{self._clip_text(str(item.get('excerpt') or ''), 260)}", body_style),
                ]
                for segment in (item.get("suspicious_segments") or [])[:2]:
                    lines.append(
                        para(
                            f"片段：{segment.get('score', 0)}% | {self._clip_text(str(segment.get('text') or ''), 180)}",
                            small_style,
                        )
                    )
                lines.append(Spacer(1, 6))
                story.append(KeepTogether(lines))
        else:
            story.append(para("未生成段落级明细。", body_style))

        story.append(Spacer(1, 8))
        story.append(para("七、辅助指标与说明", section_style))
        metric_rows = [["文档级指标", "值"]]
        metric_rows.extend(
            [
                ["中高风险段落占比", f"{document_metrics.get('high_medium_paragraph_ratio', 0)}%"],
                ["中高风险文字占比", f"{document_metrics.get('high_medium_text_ratio', 0)}%"],
                ["最长连续风险段落", str(document_metrics.get("longest_risk_streak", 0))],
                ["段首相似度", f"{document_metrics.get('opening_similarity_ratio', 0)}%"],
                ["可疑章节覆盖率", f"{document_metrics.get('section_coverage_ratio', 0)}%"],
                ["实证减权", f"{document_metrics.get('evidence_relief_pct', 0)}%"],
            ]
        )
        story.append(build_table(metric_rows, col_widths=[62 * mm, 116 * mm], header=True))
        story.append(Spacer(1, 6))
        aux_rows = [
            [para("句子数", body_style), para(str(stats.get("sentence_count", 0)), body_style)],
            [para("段落数", body_style), para(str(stats.get("paragraph_count", 0)), body_style)],
            [para("平均句长", body_style), para(str(stats.get("avg_sentence_length", 0)), body_style)],
            [para("高风险段落", body_style), para(f"{distribution.get('high_count', 0)}（{distribution.get('high_ratio', 0)}%）", body_style)],
            [
                para("高中风险文字占比", body_style),
                para(f"{fragment_distribution.get('high_and_middle_suspected_text_ratio', 0)}%", body_style),
            ],
            [
                para("总疑似片段占比", body_style),
                para(f"{fragment_distribution.get('total_suspected_fragment_ratio', 0)}%", body_style),
            ],
            [
                para("重度疑似片段", body_style),
                para(
                    f"{fragment_distribution.get('severe_fragment_count', 0)}（{fragment_distribution.get('severe_fragment_ratio', 0)}%）",
                    body_style,
                ),
            ],
        ]
        story.append(build_table(aux_rows, col_widths=[34 * mm, 144 * mm]))
        report_summary = result.get("report_summary") or {}
        if report_summary.get("available"):
            metric_rows = [["辅助报告指标", "值"]]
            for metric in (report_summary.get("metrics") or [])[:6]:
                metric_rows.append(
                    [
                        str(metric.get("label") or "指标"),
                        f"{metric.get('value', '-')}{metric.get('unit', '')}",
                    ]
                )
            if len(metric_rows) > 1:
                story.append(Spacer(1, 6))
                story.append(build_table(metric_rows, col_widths=[72 * mm, 106 * mm], header=True))
        if section_distribution and not document_outline:
            story.append(Spacer(1, 6))
            section_rows = [["章节区段", "段落数", "均值", "高风险段落"]]
            for item in section_distribution:
                section_rows.append(
                    [
                        str(item.get("section") or "-"),
                        str(item.get("paragraph_count") or 0),
                        f"{item.get('avg_score', 0)}%",
                        str(item.get("high_count") or 0),
                    ]
                )
            story.append(build_table(section_rows, col_widths=[54 * mm, 30 * mm, 30 * mm, 44 * mm], header=True))

        story.append(Spacer(1, 8))
        story.append(para("说明：", section_style))
        story.extend(
            [
                para("1. 本报告参考知网公开报告的栏目结构组织全文结果，但不是知网官方出具报告。", body_style),
                para("2. AI特征值属于概率研判结果，应结合人工复核、学校制度与正式送检结果综合理解。", body_style),
                para("3. 红色/棕色等官方标色不直接复刻，当前版本以结构化文本与段落指标替代。", body_style),
            ]
        )

        def draw_page(canvas, _doc):
            width, height = A4
            canvas.setFont("STSong-Light", 8)
            canvas.setFillColor(colors.HexColor("#666666"))
            canvas.drawString(_doc.leftMargin, height - 8 * mm, "格物学术 AIGC检测仿真报告")
            canvas.drawRightString(width - _doc.rightMargin, 8 * mm, f"第 {_doc.page} 页")

        doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
        return buffer.getvalue()

    # Override AIGC detection logic with the latest multi-signal rules.
    def _platform_detect_profile(self, platform: str) -> dict:
        key = (platform or "").strip().lower()
        profiles = {
            "cnki": {
                "name": "cnki_like",
                "provider_label": "知网AIGC检测仿真",
                "score_label": "AIGC值",
                "baseline_weight": 0.56,
                "style_weight": 0.14,
                "repeat_weight": 0.12,
                "template_weight": 0.10,
                "context_weight": 0.08,
                "opening_weight": 0.06,
                "offset": 0.0,
                "high": 0.67,
                "medium": 0.42,
                "coverage_weight": 0.06,
                "section_weight": 0.08,
                "streak_weight": 0.03,
                "opening_similarity_weight": 0.02,
                "evidence_relief_weight": 0.06,
                "fragment_display_thresholds": {"mild": 0.70, "moderate": 0.80, "severe": 0.90},
            },
            "vip": {
                "name": "vip_like",
                "provider_label": "维普AIGC检测仿真",
                "score_label": "AIGC疑似度",
                "baseline_weight": 0.52,
                "style_weight": 0.16,
                "repeat_weight": 0.12,
                "template_weight": 0.11,
                "context_weight": 0.09,
                "opening_weight": 0.07,
                "offset": -0.02,
                "high": 0.64,
                "medium": 0.40,
                "coverage_weight": 0.08,
                "section_weight": 0.08,
                "streak_weight": 0.03,
                "opening_similarity_weight": 0.02,
                "evidence_relief_weight": 0.05,
                "fragment_display_thresholds": {"mild": 0.70, "moderate": 0.80, "severe": 0.90},
            },
            "paperpass": {
                "name": "paperpass_like",
                "provider_label": "PaperPass AIGC检测仿真",
                "score_label": "AIGC风险值",
                "baseline_weight": 0.48,
                "style_weight": 0.14,
                "repeat_weight": 0.14,
                "template_weight": 0.10,
                "context_weight": 0.14,
                "opening_weight": 0.05,
                "offset": 0.03,
                "high": 0.60,
                "medium": 0.38,
                "coverage_weight": 0.05,
                "section_weight": 0.04,
                "streak_weight": 0.05,
                "opening_similarity_weight": 0.03,
                "evidence_relief_weight": 0.04,
                "fragment_display_thresholds": {"mild": 0.70, "moderate": 0.80, "severe": 0.90},
            },
        }
        return profiles.get(key, profiles["cnki"])

