from __future__ import annotations

from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
import math
import re
import statistics
from typing import Any, Iterable


LABEL_ORDER = ("high", "medium", "low", "clean")
LABEL_RELEVANCE = {"high": 3, "medium": 2, "low": 1, "clean": 0}


@dataclass(slots=True)
class EvaluatorConfig:
    full_text_diff_zero_score_pct: float = 20.0
    band_ratio_zero_score_pct: float = 15.0
    paragraph_top_k: int = 5
    clean_paragraph_score_threshold: float = 5.0
    hard_gate_total_diff_pct: float = 10.0
    hard_gate_high_medium_diff_pct: float = 12.0
    hard_gate_risky_paragraph_recall: float = 0.75
    hard_gate_span_f1: float = 0.65
    hard_gate_severity_match: float = 0.75
    hard_gate_score_variance: float = 1.0


@dataclass(slots=True)
class NormalizedSpan:
    paragraph_index: int
    label: str
    score_pct: float
    text: str = ""
    normalized_text: str = ""
    start: int | None = None
    end: int | None = None
    length: int = 0

    def fingerprint(self) -> tuple:
        return (
            self.paragraph_index,
            self.label,
            self.start,
            self.end,
            self.normalized_text[:160],
            round(self.score_pct, 2),
        )


@dataclass(slots=True)
class NormalizedParagraph:
    index: int
    label: str
    score_pct: float
    text: str = ""
    spans: list[NormalizedSpan] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "label": self.label,
            "score_pct": round(self.score_pct, 2),
            "span_count": len(self.spans),
        }


@dataclass(slots=True)
class NormalizedResult:
    sample_id: str
    platform: str
    total_score_pct: float
    band_text_ratio: dict[str, float]
    paragraphs: list[NormalizedParagraph]
    spans: list[NormalizedSpan]
    paragraph_count: int
    notes: list[str] = field(default_factory=list)

    def paragraph_map(self) -> dict[int, NormalizedParagraph]:
        return {item.index: item for item in self.paragraphs}

    def summary(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "platform": self.platform,
            "total_score_pct": round(self.total_score_pct, 2),
            "paragraph_count": self.paragraph_count,
            "span_count": len(self.spans),
            "band_text_ratio": self.band_text_ratio,
            "notes": list(self.notes),
        }


class AigcDetectEvaluator:
    def __init__(self, config: EvaluatorConfig | None = None) -> None:
        self.config = config or EvaluatorConfig()

    def normalize_reference(self, payload: dict[str, Any]) -> NormalizedResult:
        return self._normalize_payload(payload, role="reference")

    def normalize_candidate(self, payload: dict[str, Any]) -> NormalizedResult:
        return self._normalize_payload(payload, role="candidate")

    def evaluate(
        self,
        reference_payload: dict[str, Any],
        candidate_payload: dict[str, Any],
        candidate_runs: Iterable[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        reference = self.normalize_reference(reference_payload)
        candidate = self.normalize_candidate(candidate_payload)
        repeated_runs = [candidate]
        for item in candidate_runs or []:
            repeated_runs.append(self.normalize_candidate(item))

        total_score = self._score_total(reference, candidate)
        risk_structure = self._score_risk_structure(reference, candidate)
        paragraph_alignment = self._score_paragraph_alignment(reference, candidate)
        span_alignment = self._score_span_alignment(reference, candidate)
        stability = self._score_stability(repeated_runs)

        final_score = round(
            total_score["points"]
            + risk_structure["points"]
            + paragraph_alignment["points"]
            + span_alignment["points"]
            + stability["points"],
            2,
        )
        hard_gates = self._build_hard_gates(
            total_score=total_score,
            risk_structure=risk_structure,
            paragraph_alignment=paragraph_alignment,
            span_alignment=span_alignment,
            stability=stability,
        )
        passed_all_gates = all(item["passed"] for item in hard_gates.values())
        notes = list(reference.notes) + list(candidate.notes)
        if stability["run_count"] < 3:
            notes.append("Stability check used fewer than 3 runs; promotion checks should supply 3 repeated runs.")

        return {
            "sample_id": candidate.sample_id or reference.sample_id,
            "platform": candidate.platform or reference.platform,
            "final_score": final_score,
            "grade": self._grade(final_score),
            "promotion_ready": final_score >= 85 and passed_all_gates,
            "passed_all_gates": passed_all_gates,
            "dimension_scores": {
                "full_text_score_consistency": total_score,
                "risk_structure_consistency": risk_structure,
                "paragraph_alignment": paragraph_alignment,
                "highlight_span_alignment": span_alignment,
                "stability_and_determinism": stability,
            },
            "hard_gates": hard_gates,
            "reference_summary": reference.summary(),
            "candidate_summary": candidate.summary(),
            "notes": notes,
        }

    def evaluate_batch(self, cases: Iterable[dict[str, Any]]) -> dict[str, Any]:
        reports = []
        for case in cases:
            reports.append(
                self.evaluate(
                    reference_payload=case["reference"],
                    candidate_payload=case["candidate"],
                    candidate_runs=case.get("candidate_runs") or case.get("runs"),
                )
            )
        if not reports:
            raise ValueError("At least one evaluation case is required.")
        aggregate = self._aggregate_reports(reports)
        aggregate["samples"] = reports
        return aggregate

    def _normalize_payload(self, payload: dict[str, Any], *, role: str) -> NormalizedResult:
        if not isinstance(payload, dict):
            raise ValueError("Evaluation payload must be a dict.")

        root = payload
        result = self._unwrap_result(root, role=role)
        sample_id = str(
            root.get("sample_id")
            or result.get("sample_id")
            or root.get("task_id")
            or result.get("task_id")
            or "sample"
        ).strip()
        platform = str(
            root.get("platform") or result.get("platform") or root.get("target_platform") or result.get("target_platform") or ""
        ).strip().lower()
        source_text = str(root.get("source_text") or result.get("source_text") or "")
        source_paragraphs = self._split_source_paragraphs(source_text)
        paragraph_rows = self._extract_paragraph_rows(result)
        paragraph_count = self._resolve_paragraph_count(result, paragraph_rows, source_paragraphs)

        paragraph_map: dict[int, NormalizedParagraph] = {}
        spans: list[NormalizedSpan] = []
        seen_spans: set[tuple] = set()

        for fallback_index, row in enumerate(paragraph_rows, start=1):
            paragraph_text = source_paragraphs[fallback_index - 1] if fallback_index - 1 < len(source_paragraphs) else ""
            paragraph = self._normalize_paragraph(row, fallback_index=fallback_index, fallback_text=paragraph_text)
            paragraph_map[paragraph.index] = paragraph
            for span in paragraph.spans:
                marker = span.fingerprint()
                if marker in seen_spans:
                    continue
                seen_spans.add(marker)
                spans.append(span)

        for span in self._extract_top_level_spans(result, source_paragraphs):
            marker = span.fingerprint()
            if marker in seen_spans:
                continue
            seen_spans.add(marker)
            spans.append(span)

        if paragraph_count <= 0:
            paragraph_count = max(paragraph_map.keys(), default=0)

        for index in range(1, paragraph_count + 1):
            if index in paragraph_map:
                continue
            fallback_text = source_paragraphs[index - 1] if index - 1 < len(source_paragraphs) else ""
            paragraph_map[index] = NormalizedParagraph(index=index, label="clean", score_pct=0.0, text=fallback_text, spans=[])

        paragraphs = [paragraph_map[index] for index in sorted(paragraph_map)]
        spans.sort(key=lambda item: (-item.score_pct, item.paragraph_index, item.normalized_text))

        return NormalizedResult(
            sample_id=sample_id,
            platform=platform,
            total_score_pct=self._extract_total_score_pct(result),
            band_text_ratio=self._extract_band_text_ratio(result),
            paragraphs=paragraphs,
            spans=spans,
            paragraph_count=max(paragraph_count, len(paragraphs)),
            notes=self._normalization_notes(result, source_paragraphs, paragraphs, spans),
        )

    def _unwrap_result(self, payload: dict[str, Any], *, role: str) -> dict[str, Any]:
        if role == "reference" and isinstance(payload.get("reference"), dict):
            return payload["reference"]
        if role == "candidate" and isinstance(payload.get("candidate"), dict):
            return payload["candidate"]
        for key in ("result_json", "result", "data"):
            value = payload.get(key)
            if isinstance(value, dict) and any(
                item in value for item in ("score_pct", "total_score_pct", "paragraph_details", "paragraphs", "fragment_distribution")
            ):
                return value
        return payload

    def _extract_paragraph_rows(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        for key in ("paragraph_details", "paragraphs", "risk_paragraphs"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return []

    def _resolve_paragraph_count(
        self,
        payload: dict[str, Any],
        paragraph_rows: list[dict[str, Any]],
        source_paragraphs: list[str],
    ) -> int:
        candidates = [
            payload.get("paragraph_count"),
            (payload.get("distribution") or {}).get("paragraph_count"),
            (payload.get("document_metrics") or {}).get("paragraph_count"),
            len(source_paragraphs),
        ]
        candidates.extend(self._coerce_int(item.get("index")) for item in paragraph_rows if isinstance(item, dict))
        valid = [item for item in candidates if isinstance(item, int) and item > 0]
        return max(valid, default=0)

    def _extract_total_score_pct(self, payload: dict[str, Any]) -> float:
        for key in ("total_score_pct", "score_pct", "overall_score_pct", "ai_score", "risk_score"):
            if key in payload:
                return self._coerce_pct(payload.get(key))
        return 0.0

    def _extract_band_text_ratio(self, payload: dict[str, Any]) -> dict[str, float]:
        ratio_map = payload.get("band_text_ratio")
        if not isinstance(ratio_map, dict):
            fragment_distribution = payload.get("fragment_distribution") or {}
            ratio_map = {
                "high": fragment_distribution.get("high_suspected_text_ratio") or fragment_distribution.get("high"),
                "medium": fragment_distribution.get("middle_suspected_text_ratio")
                or fragment_distribution.get("medium_suspected_text_ratio")
                or fragment_distribution.get("medium"),
                "low": fragment_distribution.get("low_suspected_text_ratio") or fragment_distribution.get("low"),
                "clean": fragment_distribution.get("no_ai_suspected_text_ratio") or fragment_distribution.get("clean"),
            }
        normalized = {label: self._coerce_pct(ratio_map.get(label)) for label in LABEL_ORDER}
        if normalized["clean"] <= 0:
            normalized["clean"] = round(max(0.0, 100.0 - normalized["high"] - normalized["medium"] - normalized["low"]), 2)
        if sum(normalized.values()) <= 0:
            return {label: 0.0 for label in LABEL_ORDER}
        return {label: round(normalized[label], 2) for label in LABEL_ORDER}

    def _normalize_paragraph(
        self,
        row: dict[str, Any],
        *,
        fallback_index: int,
        fallback_text: str,
    ) -> NormalizedParagraph:
        index = self._coerce_int(row.get("index"), fallback_index) or fallback_index
        score_pct = self._coerce_pct(
            row.get("score_pct") or row.get("score") or row.get("risk_score") or row.get("ai_score")
        )
        paragraph_text = str(row.get("paragraph_text") or row.get("text") or row.get("excerpt") or fallback_text or "").strip()
        spans = self._extract_spans_from_row(row, paragraph_index=index, paragraph_text=paragraph_text or fallback_text)
        label = self._normalize_label(row.get("label") or row.get("risk_level") or row.get("risk_band"))
        if not label:
            label = self._score_to_label(score_pct, has_spans=bool(spans))
        elif label == "low" and score_pct <= self.config.clean_paragraph_score_threshold and not spans:
            label = "clean"
        return NormalizedParagraph(index=index, label=label, score_pct=round(score_pct, 2), text=paragraph_text, spans=spans)

    def _extract_spans_from_row(
        self,
        row: dict[str, Any],
        *,
        paragraph_index: int,
        paragraph_text: str,
    ) -> list[NormalizedSpan]:
        raw_items = row.get("spans") or row.get("suspicious_segments") or row.get("segments") or []
        items: list[NormalizedSpan] = []
        for raw_item in raw_items:
            span = self._normalize_span(raw_item, paragraph_index=paragraph_index, paragraph_text=paragraph_text)
            if span:
                items.append(span)
        return items

    def _extract_top_level_spans(self, payload: dict[str, Any], source_paragraphs: list[str]) -> list[NormalizedSpan]:
        raw_items = payload.get("suspicious_segments") or payload.get("spans") or []
        items: list[NormalizedSpan] = []
        for raw_item in raw_items:
            paragraph_index = self._coerce_int((raw_item or {}).get("paragraph_index"), 0) if isinstance(raw_item, dict) else 0
            paragraph_text = source_paragraphs[paragraph_index - 1] if 0 < paragraph_index <= len(source_paragraphs) else ""
            span = self._normalize_span(raw_item, paragraph_index=paragraph_index, paragraph_text=paragraph_text)
            if span:
                items.append(span)
        return items

    def _normalize_span(
        self,
        raw_item: Any,
        *,
        paragraph_index: int,
        paragraph_text: str,
    ) -> NormalizedSpan | None:
        if isinstance(raw_item, str):
            text = raw_item.strip()
            if not text:
                return None
            normalized_text = self._normalize_span_text(text)
            return NormalizedSpan(
                paragraph_index=paragraph_index,
                label="low",
                score_pct=0.0,
                text=text,
                normalized_text=normalized_text,
                length=max(len(normalized_text), 1),
            )

        if not isinstance(raw_item, dict):
            return None

        start = self._coerce_int(raw_item.get("start"))
        end = self._coerce_int(raw_item.get("end"))
        text = str(raw_item.get("text") or raw_item.get("excerpt") or raw_item.get("content") or "").strip()
        if not text and start is not None and end is not None and paragraph_text:
            left = max(0, min(start, len(paragraph_text)))
            right = max(left, min(end, len(paragraph_text)))
            text = paragraph_text[left:right].strip()
        normalized_text = self._normalize_span_text(text)
        score_pct = self._coerce_pct(
            raw_item.get("score_pct") or raw_item.get("score") or raw_item.get("risk_score") or raw_item.get("ai_score")
        )
        label = self._normalize_label(raw_item.get("label") or raw_item.get("risk_level"))
        if not label:
            label = self._score_to_label(score_pct, has_spans=True)
        length = max((end - start) if start is not None and end is not None and end >= start else len(normalized_text), 1)
        if not text and start is None and end is None:
            return None
        return NormalizedSpan(
            paragraph_index=self._coerce_int(raw_item.get("paragraph_index"), paragraph_index) or paragraph_index,
            label=label,
            score_pct=round(score_pct, 2),
            text=text,
            normalized_text=normalized_text,
            start=start,
            end=end,
            length=length,
        )

    def _score_total(self, reference: NormalizedResult, candidate: NormalizedResult) -> dict[str, Any]:
        diff = abs(candidate.total_score_pct - reference.total_score_pct)
        score_ratio = max(0.0, 1.0 - diff / self.config.full_text_diff_zero_score_pct)
        return {
            "points": round(score_ratio * 25, 2),
            "score_ratio": round(score_ratio, 4),
            "diff_pct": round(diff, 2),
            "reference_total_score_pct": round(reference.total_score_pct, 2),
            "candidate_total_score_pct": round(candidate.total_score_pct, 2),
        }

    def _score_risk_structure(self, reference: NormalizedResult, candidate: NormalizedResult) -> dict[str, Any]:
        band_scores = {}
        band_diffs = {}
        for label in LABEL_ORDER:
            diff = abs(candidate.band_text_ratio.get(label, 0.0) - reference.band_text_ratio.get(label, 0.0))
            band_diffs[label] = round(diff, 2)
            band_scores[label] = max(0.0, 1.0 - diff / self.config.band_ratio_zero_score_pct)
        score_ratio = sum(band_scores.values()) / len(LABEL_ORDER)
        high_medium_diff = abs(
            (candidate.band_text_ratio.get("high", 0.0) + candidate.band_text_ratio.get("medium", 0.0))
            - (reference.band_text_ratio.get("high", 0.0) + reference.band_text_ratio.get("medium", 0.0))
        )
        return {
            "points": round(score_ratio * 20, 2),
            "score_ratio": round(score_ratio, 4),
            "band_scores": {key: round(value, 4) for key, value in band_scores.items()},
            "band_diffs_pct": band_diffs,
            "high_medium_diff_pct": round(high_medium_diff, 2),
            "reference_band_text_ratio": reference.band_text_ratio,
            "candidate_band_text_ratio": candidate.band_text_ratio,
        }

    def _score_paragraph_alignment(self, reference: NormalizedResult, candidate: NormalizedResult) -> dict[str, Any]:
        reference_map = reference.paragraph_map()
        candidate_map = candidate.paragraph_map()
        indexes = sorted(set(reference_map) | set(candidate_map))
        reference_labels = {index: reference_map.get(index, self._clean_paragraph(index)).label for index in indexes}
        candidate_labels = {index: candidate_map.get(index, self._clean_paragraph(index)).label for index in indexes}

        reference_risky = {index for index, label in reference_labels.items() if label != "clean"}
        candidate_risky = {index for index, label in candidate_labels.items() if label != "clean"}
        recall, precision, risk_f1 = self._binary_f1(reference_risky, candidate_risky)
        macro_f1 = self._macro_label_f1(reference_labels, candidate_labels)
        ndcg = self._ndcg(reference_map, candidate_map, indexes=indexes, k=self.config.paragraph_top_k)
        score_ratio = 0.5 * risk_f1 + 0.3 * macro_f1 + 0.2 * ndcg

        return {
            "points": round(score_ratio * 25, 2),
            "score_ratio": round(score_ratio, 4),
            "risk_paragraph_recall": round(recall, 4),
            "risk_paragraph_precision": round(precision, 4),
            "paragraph_risk_f1": round(risk_f1, 4),
            "paragraph_label_macro_f1": round(macro_f1, 4),
            "topk_ndcg": round(ndcg, 4),
            "reference_risky_indexes": sorted(reference_risky),
            "candidate_risky_indexes": sorted(candidate_risky),
        }

    def _score_span_alignment(self, reference: NormalizedResult, candidate: NormalizedResult) -> dict[str, Any]:
        reference_total = sum(item.length for item in reference.spans)
        candidate_total = sum(item.length for item in candidate.spans)

        if reference_total == 0 and candidate_total == 0:
            return {
                "points": 25.0,
                "score_ratio": 1.0,
                "span_overlap_f1": 1.0,
                "severity_match_rate": 1.0,
                "overlap_chars": 0,
                "reference_span_chars": 0,
                "candidate_span_chars": 0,
            }

        overlap_chars = 0
        same_label_chars = 0
        pairs = []
        for ref_index, ref_span in enumerate(reference.spans):
            for cand_index, cand_span in enumerate(candidate.spans):
                if ref_span.paragraph_index and cand_span.paragraph_index and ref_span.paragraph_index != cand_span.paragraph_index:
                    continue
                overlap = self._span_overlap_chars(ref_span, cand_span)
                if overlap <= 0:
                    continue
                pairs.append((overlap, 1 if ref_span.label == cand_span.label else 0, ref_index, cand_index))

        used_ref: set[int] = set()
        used_cand: set[int] = set()
        for overlap, same_label, ref_index, cand_index in sorted(pairs, key=lambda item: (item[0], item[1]), reverse=True):
            if ref_index in used_ref or cand_index in used_cand:
                continue
            used_ref.add(ref_index)
            used_cand.add(cand_index)
            overlap_chars += overlap
            if same_label:
                same_label_chars += overlap

        span_precision = overlap_chars / max(candidate_total, 1)
        span_recall = overlap_chars / max(reference_total, 1)
        span_f1 = 0.0 if span_precision + span_recall == 0 else (2 * span_precision * span_recall) / (span_precision + span_recall)
        severity_match = same_label_chars / max(overlap_chars, 1) if overlap_chars else 0.0
        score_ratio = 0.7 * span_f1 + 0.3 * severity_match

        return {
            "points": round(score_ratio * 25, 2),
            "score_ratio": round(score_ratio, 4),
            "span_overlap_f1": round(span_f1, 4),
            "severity_match_rate": round(severity_match, 4),
            "overlap_chars": int(overlap_chars),
            "reference_span_chars": int(reference_total),
            "candidate_span_chars": int(candidate_total),
        }

    def _score_stability(self, runs: list[NormalizedResult]) -> dict[str, Any]:
        total_scores = [item.total_score_pct for item in runs]
        score_variance = statistics.pvariance(total_scores) if len(total_scores) > 1 else 0.0
        paragraph_fingerprints = [self._paragraph_fingerprint(item) for item in runs]
        span_fingerprints = [self._span_fingerprint(item) for item in runs]
        paragraph_set_stable = len(set(paragraph_fingerprints)) <= 1
        span_set_stable = len(set(span_fingerprints)) <= 1

        if score_variance <= 0.5:
            variance_score = 1.0
        else:
            variance_score = max(0.0, 1.0 - (score_variance - 0.5) / max(self.config.hard_gate_score_variance, 0.5))
        score_ratio = 0.4 * variance_score + 0.3 * float(paragraph_set_stable) + 0.3 * float(span_set_stable)

        return {
            "points": round(score_ratio * 5, 2),
            "score_ratio": round(score_ratio, 4),
            "run_count": len(runs),
            "score_variance": round(score_variance, 4),
            "paragraph_set_stable": paragraph_set_stable,
            "span_set_stable": span_set_stable,
        }

    def _build_hard_gates(
        self,
        *,
        total_score: dict[str, Any],
        risk_structure: dict[str, Any],
        paragraph_alignment: dict[str, Any],
        span_alignment: dict[str, Any],
        stability: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "full_text": {
                "passed": total_score["diff_pct"] <= self.config.hard_gate_total_diff_pct,
                "value": total_score["diff_pct"],
                "threshold": f"<= {self.config.hard_gate_total_diff_pct}",
            },
            "risk_structure": {
                "passed": risk_structure["high_medium_diff_pct"] <= self.config.hard_gate_high_medium_diff_pct,
                "value": risk_structure["high_medium_diff_pct"],
                "threshold": f"<= {self.config.hard_gate_high_medium_diff_pct}",
            },
            "paragraph": {
                "passed": paragraph_alignment["risk_paragraph_recall"] >= self.config.hard_gate_risky_paragraph_recall,
                "value": paragraph_alignment["risk_paragraph_recall"],
                "threshold": f">= {self.config.hard_gate_risky_paragraph_recall}",
            },
            "highlight_span": {
                "passed": span_alignment["span_overlap_f1"] >= self.config.hard_gate_span_f1
                and span_alignment["severity_match_rate"] >= self.config.hard_gate_severity_match,
                "value": {
                    "span_overlap_f1": span_alignment["span_overlap_f1"],
                    "severity_match_rate": span_alignment["severity_match_rate"],
                },
                "threshold": {
                    "span_overlap_f1": f">= {self.config.hard_gate_span_f1}",
                    "severity_match_rate": f">= {self.config.hard_gate_severity_match}",
                },
            },
            "stability": {
                "passed": stability["score_variance"] <= self.config.hard_gate_score_variance,
                "value": stability["score_variance"],
                "threshold": f"<= {self.config.hard_gate_score_variance}",
            },
        }

    def _aggregate_reports(self, reports: list[dict[str, Any]]) -> dict[str, Any]:
        final_score = round(self._mean(report["final_score"] for report in reports), 2)
        hard_gates = {
            "full_text": self._aggregate_numeric_gate(
                reports,
                gate_name="full_text",
                metric_values=[report["dimension_scores"]["full_text_score_consistency"]["diff_pct"] for report in reports],
                pass_fn=lambda value: value <= self.config.hard_gate_total_diff_pct,
                threshold=f"avg <= {self.config.hard_gate_total_diff_pct}",
            ),
            "risk_structure": self._aggregate_numeric_gate(
                reports,
                gate_name="risk_structure",
                metric_values=[report["dimension_scores"]["risk_structure_consistency"]["high_medium_diff_pct"] for report in reports],
                pass_fn=lambda value: value <= self.config.hard_gate_high_medium_diff_pct,
                threshold=f"avg <= {self.config.hard_gate_high_medium_diff_pct}",
            ),
            "paragraph": self._aggregate_numeric_gate(
                reports,
                gate_name="paragraph",
                metric_values=[report["dimension_scores"]["paragraph_alignment"]["risk_paragraph_recall"] for report in reports],
                pass_fn=lambda value: value >= self.config.hard_gate_risky_paragraph_recall,
                threshold=f"avg >= {self.config.hard_gate_risky_paragraph_recall}",
            ),
            "highlight_span": self._aggregate_span_gate(reports),
            "stability": self._aggregate_numeric_gate(
                reports,
                gate_name="stability",
                metric_values=[report["dimension_scores"]["stability_and_determinism"]["score_variance"] for report in reports],
                pass_fn=lambda value: value <= self.config.hard_gate_score_variance,
                threshold=f"avg <= {self.config.hard_gate_score_variance}",
            ),
        }
        passed_all_gates = all(item["passed"] for item in hard_gates.values())
        notes = []
        failed_samples = sorted(
            {sample_id for gate in hard_gates.values() for sample_id in gate.get("failed_samples", []) if sample_id}
        )
        if failed_samples:
            notes.append(f"Failed sample gates: {', '.join(failed_samples)}")

        return {
            "sample_count": len(reports),
            "final_score": final_score,
            "grade": self._grade(final_score),
            "promotion_ready": final_score >= 85 and passed_all_gates,
            "passed_all_gates": passed_all_gates,
            "dimension_scores": {
                "full_text_score_consistency": round(
                    self._mean(report["dimension_scores"]["full_text_score_consistency"]["points"] for report in reports), 2
                ),
                "risk_structure_consistency": round(
                    self._mean(report["dimension_scores"]["risk_structure_consistency"]["points"] for report in reports), 2
                ),
                "paragraph_alignment": round(
                    self._mean(report["dimension_scores"]["paragraph_alignment"]["points"] for report in reports), 2
                ),
                "highlight_span_alignment": round(
                    self._mean(report["dimension_scores"]["highlight_span_alignment"]["points"] for report in reports), 2
                ),
                "stability_and_determinism": round(
                    self._mean(report["dimension_scores"]["stability_and_determinism"]["points"] for report in reports), 2
                ),
            },
            "hard_gates": hard_gates,
            "notes": notes,
        }

    def _aggregate_numeric_gate(
        self,
        reports: list[dict[str, Any]],
        *,
        gate_name: str,
        metric_values: list[float],
        pass_fn,
        threshold: str,
    ) -> dict[str, Any]:
        failed_samples = [report["sample_id"] for report in reports if not report["hard_gates"][gate_name]["passed"]]
        aggregate_value = self._mean(metric_values)
        return {
            "passed": pass_fn(aggregate_value),
            "failed_samples": failed_samples,
            "value": round(aggregate_value, 4),
            "threshold": threshold,
        }

    def _aggregate_span_gate(self, reports: list[dict[str, Any]]) -> dict[str, Any]:
        failed_samples = [report["sample_id"] for report in reports if not report["hard_gates"]["highlight_span"]["passed"]]
        span_f1 = self._mean(report["dimension_scores"]["highlight_span_alignment"]["span_overlap_f1"] for report in reports)
        severity = self._mean(
            report["dimension_scores"]["highlight_span_alignment"]["severity_match_rate"] for report in reports
        )
        return {
            "passed": span_f1 >= self.config.hard_gate_span_f1 and severity >= self.config.hard_gate_severity_match,
            "failed_samples": failed_samples,
            "value": {
                "avg_span_overlap_f1": round(span_f1, 4),
                "avg_severity_match_rate": round(severity, 4),
            },
            "threshold": {
                "avg_span_overlap_f1": f">= {self.config.hard_gate_span_f1}",
                "avg_severity_match_rate": f">= {self.config.hard_gate_severity_match}",
            },
        }

    def _paragraph_fingerprint(self, result: NormalizedResult) -> tuple:
        return tuple((item.index, item.label, round(item.score_pct, 2)) for item in result.paragraphs)

    def _span_fingerprint(self, result: NormalizedResult) -> tuple:
        return tuple(
            (item.paragraph_index, item.label, item.start, item.end, item.normalized_text[:120]) for item in result.spans
        )

    def _normalization_notes(
        self,
        payload: dict[str, Any],
        source_paragraphs: list[str],
        paragraphs: list[NormalizedParagraph],
        spans: list[NormalizedSpan],
    ) -> list[str]:
        notes = []
        if not source_paragraphs:
            notes.append("Source text is missing; clean paragraph backfill is based on observed paragraph indexes only.")
        if payload.get("fragment_distribution") is None and payload.get("band_text_ratio") is None:
            notes.append("Band text ratios were not supplied; missing bands default to 0.")
        if spans and not any(item.start is not None and item.end is not None for item in spans):
            notes.append("Span scoring uses text-overlap approximation because explicit offsets are not available.")
        if not paragraphs:
            notes.append("No paragraph-level annotations were supplied.")
        return notes

    def _span_overlap_chars(self, left: NormalizedSpan, right: NormalizedSpan) -> int:
        if (
            left.start is not None
            and left.end is not None
            and right.start is not None
            and right.end is not None
            and left.paragraph_index == right.paragraph_index
        ):
            return max(0, min(left.end, right.end) - max(left.start, right.start))
        if not left.normalized_text or not right.normalized_text:
            return 0
        matcher = SequenceMatcher(None, left.normalized_text, right.normalized_text)
        return sum(block.size for block in matcher.get_matching_blocks() if block.size > 0)

    def _binary_f1(self, reference: set[int], candidate: set[int]) -> tuple[float, float, float]:
        if not reference and not candidate:
            return 1.0, 1.0, 1.0
        true_positive = len(reference & candidate)
        precision = true_positive / len(candidate) if candidate else 0.0
        recall = true_positive / len(reference) if reference else 0.0
        f1 = 0.0 if precision + recall == 0 else (2 * precision * recall) / (precision + recall)
        return recall, precision, f1

    def _macro_label_f1(self, reference_labels: dict[int, str], candidate_labels: dict[int, str]) -> float:
        indexes = sorted(set(reference_labels) | set(candidate_labels))
        if not indexes:
            return 1.0
        f1_scores = []
        for label in LABEL_ORDER:
            true_positive = sum(1 for index in indexes if reference_labels.get(index) == label and candidate_labels.get(index) == label)
            false_positive = sum(1 for index in indexes if reference_labels.get(index) != label and candidate_labels.get(index) == label)
            false_negative = sum(1 for index in indexes if reference_labels.get(index) == label and candidate_labels.get(index) != label)
            if true_positive == 0 and false_positive == 0 and false_negative == 0:
                f1_scores.append(1.0)
                continue
            precision = true_positive / max(true_positive + false_positive, 1)
            recall = true_positive / max(true_positive + false_negative, 1)
            f1_scores.append(0.0 if precision + recall == 0 else (2 * precision * recall) / (precision + recall))
        return sum(f1_scores) / len(f1_scores)

    def _ndcg(
        self,
        reference_map: dict[int, NormalizedParagraph],
        candidate_map: dict[int, NormalizedParagraph],
        *,
        indexes: list[int],
        k: int,
    ) -> float:
        if not indexes:
            return 1.0
        reference_relevance = {
            index: LABEL_RELEVANCE.get(reference_map.get(index, self._clean_paragraph(index)).label, 0) for index in indexes
        }
        ideal_ranking = sorted(
            indexes,
            key=lambda index: (
                reference_relevance.get(index, 0),
                reference_map.get(index, self._clean_paragraph(index)).score_pct,
                -index,
            ),
            reverse=True,
        )
        candidate_ranking = sorted(
            indexes,
            key=lambda index: (
                candidate_map.get(index, self._clean_paragraph(index)).score_pct,
                LABEL_RELEVANCE.get(candidate_map.get(index, self._clean_paragraph(index)).label, 0),
                -index,
            ),
            reverse=True,
        )
        ideal_dcg = self._dcg(ideal_ranking[:k], reference_relevance)
        if ideal_dcg <= 0:
            return 1.0
        return self._dcg(candidate_ranking[:k], reference_relevance) / ideal_dcg

    def _dcg(self, ranking: list[int], reference_relevance: dict[int, int]) -> float:
        total = 0.0
        for position, index in enumerate(ranking, start=1):
            relevance = reference_relevance.get(index, 0)
            total += (2**relevance - 1) / math.log2(position + 1)
        return total

    def _score_to_label(self, score_pct: float, *, has_spans: bool) -> str:
        if score_pct >= 60:
            return "high"
        if score_pct >= 30:
            return "medium"
        if score_pct > self.config.clean_paragraph_score_threshold or has_spans:
            return "low"
        return "clean"

    def _clean_paragraph(self, index: int) -> NormalizedParagraph:
        return NormalizedParagraph(index=index, label="clean", score_pct=0.0, text="", spans=[])

    def _normalize_label(self, raw_value: Any) -> str:
        value = str(raw_value or "").strip().lower()
        compact = re.sub(r"[\s_-]+", "", value)
        if not compact:
            return ""
        if compact in {"high", "severe", "critical"}:
            return "high"
        if compact in {"medium", "moderate", "mid"}:
            return "medium"
        if compact in {"low", "mild", "light"}:
            return "low"
        if compact in {"clean", "noai", "human", "safe", "none"}:
            return "clean"
        if any(token in compact for token in ("高风险", "重度", "高度疑似")):
            return "high"
        if any(token in compact for token in ("中风险", "中度", "中度疑似")):
            return "medium"
        if any(token in compact for token in ("低风险", "轻度", "轻度疑似")):
            return "low"
        if any(token in compact for token in ("无风险", "正常", "人写", "无异常")):
            return "clean"
        return ""

    def _normalize_span_text(self, value: str) -> str:
        text = str(value or "").lower().strip()
        text = re.sub(r"\s+", "", text)
        return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", text)

    def _split_source_paragraphs(self, source_text: str) -> list[str]:
        return [item.strip() for item in re.split(r"\r?\n+", source_text or "") if item.strip()]

    def _coerce_pct(self, raw_value: Any, default: float = 0.0) -> float:
        if raw_value is None or raw_value == "":
            return round(default, 2)
        try:
            if isinstance(raw_value, str):
                compact = raw_value.strip().replace(",", "")
                if not compact:
                    return round(default, 2)
                has_percent = "%" in compact or "％" in compact
                match = re.search(r"-?\d+(?:\.\d+)?", compact)
                if not match:
                    return round(default, 2)
                value = float(match.group(0))
                if has_percent:
                    return round(max(0.0, min(value, 100.0)), 2)
                if 0.0 <= value <= 1.0:
                    value *= 100.0
                return round(max(0.0, min(value, 100.0)), 2)
            value = float(raw_value)
            if 0.0 <= value <= 1.0:
                value *= 100.0
            return round(max(0.0, min(value, 100.0)), 2)
        except (TypeError, ValueError):
            return round(default, 2)

    def _coerce_int(self, raw_value: Any, default: int | None = None) -> int | None:
        if raw_value is None or raw_value == "":
            return default
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            return default

    def _grade(self, final_score: float) -> str:
        if final_score >= 90:
            return "S"
        if final_score >= 85:
            return "A"
        if final_score >= 75:
            return "B"
        if final_score >= 60:
            return "C"
        return "D"

    def _mean(self, values: Iterable[float]) -> float:
        data = list(values)
        return statistics.fmean(data) if data else 0.0


def evaluate_aigc_detect_result(
    reference_payload: dict[str, Any],
    candidate_payload: dict[str, Any],
    candidate_runs: Iterable[dict[str, Any]] | None = None,
    *,
    config: EvaluatorConfig | None = None,
) -> dict[str, Any]:
    evaluator = AigcDetectEvaluator(config=config)
    return evaluator.evaluate(reference_payload, candidate_payload, candidate_runs=candidate_runs)


def evaluate_aigc_detect_batch(
    cases: Iterable[dict[str, Any]],
    *,
    config: EvaluatorConfig | None = None,
) -> dict[str, Any]:
    evaluator = AigcDetectEvaluator(config=config)
    return evaluator.evaluate_batch(cases)


def normalized_result_to_dict(result: NormalizedResult) -> dict[str, Any]:
    return asdict(result)
