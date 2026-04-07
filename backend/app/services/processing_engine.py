import json
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
            llm_detect_result = self._parse_llm_detect_result(self._run_llm(task_type, source_text))
            detect_result = self._build_detect_result(
                text=source_text,
                platform=normalized_platform,
                mode=self._effective_mode,
                report_summary=report_summary,
                algo_result=algo_result,
                llm_result=llm_detect_result,
            )
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

    def _platform_detect_profile(self, platform: str) -> dict:
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

    def _simulate_platform_detect_score(self, platform: str, text: str, base_score: float) -> tuple[float, dict, dict]:
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

    def _top_risk_paragraphs(self, text: str, platform: str = "cnki") -> list[dict]:
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


    def _write_detect_report_pdf(self, output_path: Path, result: dict) -> None:
        lines = self._build_detect_report_lines(result)
        output_path.write_bytes(self._render_pdf(lines))

    def _build_detect_report_lines(self, result: dict) -> list[str]:
        platform_key = str(result.get("platform") or "cnki").strip().lower()
        platform_label = {
            "cnki": "Imitation CNKI Detection",
            "vip": "Imitation VIP Detection",
            "paperpass": "Imitation PaperPass Detection",
        }.get(platform_key, f"Imitation {platform_key.upper()} Detection")
        score_pct = float(result.get("score_pct") or 0.0)
        risk_level = "HIGH" if score_pct >= 65 else "MEDIUM" if score_pct >= 35 else "LOW"
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stats = result.get("source_stats") or {}

        lines: list[str] = [
            "格物学术 AIGC 检测报告",
            f"Generated At: {generated_at}",
            f"Platform: {platform_label}",
            "Engine Type: Imitation provider algorithm (not official provider API)",
            f"Simulation Profile: {result.get('simulation_profile', platform_key + '_like')}",
            "",
            "1. Detection Summary",
            f"   - Composite Score: {score_pct:.2f}%",
            f"   - Risk Level: {risk_level}",
            "",
            "2. Source Text Statistics",
            f"   - Characters: {stats.get('char_count', 0)}",
            f"   - Paragraphs: {stats.get('paragraph_count', 0)}",
            f"   - Sentences: {stats.get('sentence_count', 0)}",
            f"   - Avg Sentence Length: {stats.get('avg_sentence_length', 0)}",
            "",
            "3. Supplementary Report Signals",
        ]

        report_summary = result.get("report_summary") or {}
        if report_summary.get("available"):
            metrics = report_summary.get("metrics") or []
            actions = report_summary.get("recommended_actions") or []
            if metrics:
                lines.append("   - Parsed Metrics:")
                for metric in metrics:
                    lines.append(
                        f"     * {metric.get('label', 'Metric')}: {metric.get('value', '-')}{metric.get('unit', '')}"
                    )
            if actions:
                lines.append("   - Suggested Actions:")
                for action in actions[:5]:
                    lines.append(f"     * {action}")
            if not metrics and not actions:
                lines.append("   - Supplementary report uploaded, but no structured metrics were extracted.")
        else:
            lines.append("   - No supplementary report uploaded.")

        lines.extend(["", "4. Top Risk Paragraphs"])
        risk_paragraphs = result.get("risk_paragraphs") or []
        if risk_paragraphs:
            for item in risk_paragraphs:
                lines.append(
                    f"   - Paragraph {item.get('index', '-')}: {item.get('score', 0)}% | {self._clip_text(item.get('excerpt', ''), 120)}"
                )
        else:
            lines.append("   - No high-risk paragraph extracted.")

        lines.extend(
            [
                "",
                "Disclaimer:",
                "This report is generated by an internal imitation engine for operational use.",
                "It is not an official report issued by CNKI, VIP, or PaperPass.",
            ]
        )
        return lines

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


    def _render_detect_report(self, result: dict) -> str:
        lines = [
            "格物学术 AIGC 检测报告",
            f"平台：{result.get('platform')}",
            f"综合分值：{result.get('score_pct')}%",
            f"风险等级：{result.get('risk_band')}",
            f"摘要：{result.get('summary')}",
            "",
            "文本概览：",
        ]
        stats = result.get("source_stats", {})
        lines.extend(
            [
                f"- 字符数：{stats.get('char_count', 0)}",
                f"- 段落数：{stats.get('paragraph_count', 0)}",
                f"- 句子数：{stats.get('sentence_count', 0)}",
                f"- 平均句长：{stats.get('avg_sentence_length', 0)}",
            ]
        )
        report_summary = result.get("report_summary") or {}
        if report_summary.get("available"):
            lines.extend(["", "辅助报告信息："])
            for metric in report_summary.get("metrics", []):
                lines.append(f"- {metric.get('label')}：{metric.get('value')}{metric.get('unit', '')}")
            for action in report_summary.get("recommended_actions", []):
                lines.append(f"- {action}")
        risk_paragraphs = result.get("risk_paragraphs") or []
        if risk_paragraphs:
            lines.extend(["", "高风险段落："])
            for item in risk_paragraphs:
                lines.append(f"- 段落{item.get('index')} | 风险 {item.get('score')}% | {item.get('excerpt')}")
        return "\n".join(lines)

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

    def _split_detect_sentences(self, text: str) -> list[str]:
        return [seg.strip() for seg in re.split(r"[。！？!?；;\n]+", str(text or "")) if seg.strip()]

    def _template_signal(self, text: str) -> tuple[float, list[str]]:
        hits: list[str] = []
        phrases = [
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
        citation_relief = self._citation_relief_signal(clean)

        weighted = (
            float(base_score) * profile["baseline_weight"]
            + style_signal * profile["style_weight"]
            + repeat_signal * profile["repeat_weight"]
            + template_signal * profile["template_weight"]
            + context_signal * profile["context_weight"]
            - citation_relief
            + profile["offset"]
        )
        score = round(self._clamp_score(weighted), 4)
        breakdown = {
            "base_score": round(float(base_score), 4),
            "style_signal": round(style_signal, 4),
            "repeat_signal": round(repeat_signal, 4),
            "template_signal": round(template_signal, 4),
            "context_signal": round(context_signal, 4),
            "citation_relief": round(citation_relief, 4),
            "template_hits": template_hits,
            "weights": {
                "baseline": profile["baseline_weight"],
                "style": profile["style_weight"],
                "repeat": profile["repeat_weight"],
                "template": profile["template_weight"],
                "context": profile["context_weight"],
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
                reasons.append("模板衔接词偏密")
            if float(breakdown.get("repeat_signal") or 0.0) >= 0.32:
                reasons.append("重复表达偏多")
            if float(breakdown.get("context_signal") or 0.0) >= 0.58:
                reasons.append("句式波动较小")
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
        return tags[:3]

    def _build_detect_paragraph_details(self, text: str, platform: str, profile: dict, algo_result) -> list[dict]:
        paragraphs = [part.strip() for part in str(text or "").splitlines() if part.strip()]
        if not paragraphs and str(text or "").strip():
            paragraphs = [str(text).strip()]

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

    def _build_section_distribution(self, paragraph_details: list[dict]) -> list[dict]:
        if not paragraph_details:
            return []
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
        section_distribution = self._build_section_distribution(paragraph_details)
        suspicious_segments = self._collect_suspicious_segments(paragraph_details)

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
        score = round(
            self._clamp_score(
                score * 0.42
                + mean_paragraph_ratio * profile["overall_paragraph_weight"] * 0.58
                + max_paragraph_ratio * profile["overall_peak_weight"] * 0.42
                + segment_ratio * profile["overall_segment_weight"] * 0.30
            ),
            4,
        )
        label = self._score_to_detect_label(score, profile)
        algo_has_label = False

        if isinstance(algo_result, dict):
            package_score = self._extract_algo_score(algo_result)
            if package_score is not None:
                score = round(self._clamp_score(score * 0.7 + package_score * 0.3), 4)
                breakdown["algo_package_score"] = round(package_score, 4)
                breakdown["algo_package_blended"] = True
            else:
                breakdown["algo_package_blended"] = False

            algo_label = self._extract_algo_label(algo_result)
            if algo_label:
                label = algo_label
                algo_has_label = True
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
            if llm_label and not algo_has_label:
                label = llm_label

            reason = llm_result.get("reason")
            if isinstance(reason, str) and reason.strip():
                breakdown["llm_reason"] = reason.strip()[:180]
        else:
            breakdown["llm_blended"] = False

        band = self._risk_band(score, high=profile["high"], medium=profile["medium"])
        risk_paragraphs = sorted(paragraph_details, key=lambda item: item["score"], reverse=True)[:5]
        report_no = f"GW-AIGC-{platform.upper()}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{self._current_task_id or 0}"
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        breakdown["paragraph_mean_score"] = mean_paragraph_ratio
        breakdown["peak_paragraph_score"] = max_paragraph_ratio
        breakdown["segment_signal"] = segment_ratio

        summary = (
            f"{profile['provider_label']}全文检测完成，{profile['score_label']}为 {round(score * 100, 2)}%，"
            f"高风险段落占比 {distribution.get('high_ratio', 0.0)}%。结果用于内部研判与改写辅助，不等同于官方报告。"
        )

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

    def _top_risk_paragraphs(self, text: str, platform: str = "cnki") -> list[dict]:
        profile = self._platform_detect_profile(platform)
        rows = self._build_detect_paragraph_details(text, platform, profile, None)
        return sorted(rows, key=lambda item: item["score"], reverse=True)[:5]

    def _write_detect_report_pdf(self, output_path: Path, result: dict) -> None:
        lines = self._build_detect_report_lines(result)
        output_path.write_bytes(self._render_pdf(lines))

    def _build_detect_report_lines(self, result: dict) -> list[str]:
        stats = result.get("source_stats") or {}
        distribution = result.get("distribution") or {}
        section_distribution = result.get("section_distribution") or []
        paragraph_details = result.get("paragraph_details") or []
        suspicious_segments = result.get("suspicious_segments") or []
        report_summary = result.get("report_summary") or {}

        lines: list[str] = [
            "格物学术 AIGC 全文检测报告",
            f"报告编号：{result.get('report_no') or '-'}",
            f"生成时间：{result.get('generated_at') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"检测平台：{result.get('provider_label') or result.get('platform')}",
            f"检测模式：{result.get('mode') or '-'}",
            f"{result.get('score_label') or 'AIGC分值'}：{result.get('score_pct', 0)}%",
            f"风险等级：{result.get('risk_band') or '-'}",
            "",
            "一、报告摘要",
            str(result.get("summary") or ""),
            "",
            "二、正文统计",
            f"- 字符数：{stats.get('char_count', 0)}",
            f"- 段落数：{stats.get('paragraph_count', 0)}",
            f"- 句子数：{stats.get('sentence_count', 0)}",
            f"- 平均句长：{stats.get('avg_sentence_length', 0)}",
            "",
            "三、全文分布",
            f"- 高风险段落：{distribution.get('high_count', 0)}（{distribution.get('high_ratio', 0)}%）",
            f"- 中风险段落：{distribution.get('medium_count', 0)}（{distribution.get('medium_ratio', 0)}%）",
            f"- 低风险段落：{distribution.get('low_count', 0)}（{distribution.get('low_ratio', 0)}%）",
            f"- 段落均值：{distribution.get('avg_score', 0)}%",
            f"- 最高段落：{distribution.get('max_score', 0)}%",
            "",
            "四、章节分布",
        ]

        if section_distribution:
            for item in section_distribution:
                lines.append(
                    f"- {item.get('section')}：段落 {item.get('paragraph_count')} 个，均值 {item.get('avg_score')}%，高风险 {item.get('high_count')} 个"
                )
        else:
            lines.append("- 未生成章节分布。")

        lines.extend(["", "五、重点可疑片段"])
        if suspicious_segments:
            for item in suspicious_segments[:10]:
                detail = f"P{int(item.get('paragraph_index') or 0):02d} | {item.get('score', 0)}%"
                reason = str(item.get("reason") or "").strip()
                if reason:
                    detail = f"{detail} | {reason}"
                lines.append(f"- {detail}")
                lines.append(f"  {self._clip_text(str(item.get('text') or ''), 140)}")
        else:
            lines.append("- 未提取到高置信可疑片段。")

        lines.extend(["", "六、辅助报告信号"])
        if report_summary.get("available"):
            metrics = report_summary.get("metrics") or []
            actions = report_summary.get("recommended_actions") or []
            if metrics:
                for metric in metrics:
                    lines.append(f"- {metric.get('label', '指标')}：{metric.get('value', '-')}{metric.get('unit', '')}")
            if actions:
                for action in actions[:5]:
                    lines.append(f"- 建议：{action}")
            if not metrics and not actions:
                lines.append("- 已上传辅助报告，但未解析出结构化指标。")
        else:
            lines.append("- 本次任务未上传辅助报告。")

        lines.extend(["", "七、全文段落明细"])
        if paragraph_details:
            for item in paragraph_details:
                lines.append(
                    f"P{int(item.get('index') or 0):02d} | {item.get('risk_band') or '-'} | {item.get('score', 0)}% | 字符 {item.get('char_count', 0)} | 句子 {item.get('sentence_count', 0)}"
                )
                if item.get("reason_tags"):
                    lines.append(f"  信号：{'、'.join(item.get('reason_tags') or [])}")
                lines.append(f"  摘要：{self._clip_text(str(item.get('excerpt') or ''), 150)}")
                for segment in (item.get("suspicious_segments") or [])[:2]:
                    lines.append(
                        f"  片段：{segment.get('score', 0)}% | {self._clip_text(str(segment.get('text') or ''), 120)}"
                    )
        else:
            lines.append("- 未生成段落级结果。")

        lines.extend(
            [
                "",
                "说明：",
                "1. 本报告参考公开产品特征构建全文风险结构，用于内部流程优化与人工复核辅助。",
                "2. 本报告不是知网、维普或 PaperPass 官方出具的检测报告。",
                "3. AIGC相关分值属于概率研判，需结合人工审阅与真实送检结果理解。",
            ]
        )
        return lines

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

