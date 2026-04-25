from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.services.strategy_asset_paths import resolve_strategy_asset_path


POSITIVE_PAIR_PATH = resolve_strategy_asset_path("positive_few_shot_pairs_v1.jsonl")
SUPPLEMENTAL_POSITIVE_PAIR_PATH = resolve_strategy_asset_path("supplemental_positive_few_shot_pairs_v1.jsonl")
DEDUP_REFERENCE_PATH = resolve_strategy_asset_path("dedup_positive_references_v1.jsonl")
SUPPLEMENTAL_DEDUP_REFERENCE_PATH = resolve_strategy_asset_path("supplemental_dedup_positive_references_v1.jsonl")
CONNECTOR_PREFIXES = ("同时，", "此外，", "进一步看，", "在此基础上，", "由此可见，")


@dataclass(frozen=True)
class RewriteStyleProfile:
    platform: str
    sample_count: int
    avg_sentence_length: float
    avg_sentence_count: float
    avg_connector_ratio: float


@dataclass(frozen=True)
class DedupStyleProfile:
    platform: str
    sample_count: int
    avg_sentence_length: float
    avg_sentence_count: float
    avg_connector_ratio: float


def rewrite_text_style_signals(platform: str, text: str) -> dict[str, float | int]:
    metrics = _text_metrics(text)
    profile = rewrite_style_profile(platform)
    return _style_signals(
        profile=profile,
        metrics=metrics,
        connector_padding=0.18,
        connector_floor=0.34,
        sentence_length_limit=0.8,
    )


def dedup_text_style_signals(platform: str, text: str) -> dict[str, float | int]:
    metrics = _text_metrics(text)
    profile = dedup_style_profile(platform)
    return _style_signals(
        profile=profile,
        metrics=metrics,
        connector_padding=0.16,
        connector_floor=0.3,
        sentence_length_limit=0.85,
    )


def build_rewrite_style_guidance(platform: str) -> str:
    profile = rewrite_style_profile(platform)
    if profile is None:
        return ""
    connector_limit = max(profile.avg_connector_ratio + 0.18, 0.34)
    return (
        "参考当前平台高质量样本风格基线："
        f"单段平均句长约 {round(profile.avg_sentence_length)} 字，"
        f"平均句数约 {round(profile.avg_sentence_count, 1)} 句，"
        f"连接词起句占比尽量控制在 {round(connector_limit, 2)} 以下。"
    )


def build_dedup_style_guidance(platform: str) -> str:
    profile = dedup_style_profile(platform)
    if profile is None:
        return ""
    connector_limit = max(profile.avg_connector_ratio + 0.16, 0.3)
    return (
        "参考当前平台高质量降重样本风格基线："
        f"单段平均句长约 {round(profile.avg_sentence_length)} 字，"
        f"平均句数约 {round(profile.avg_sentence_count, 1)} 句，"
        f"连接词起句占比尽量控制在 {round(connector_limit, 2)} 以下，"
        "优先保持定义句、综述句和结论句的紧凑表达。"
    )


@lru_cache(maxsize=8)
def rewrite_style_profile(platform: str) -> RewriteStyleProfile | None:
    key = str(platform or "").strip().lower()
    rows = [*_load_positive_pair_rows(), *_load_supplemental_positive_pair_rows()]
    rewritten_texts = [
        str(row.get("rewritten_excerpt") or "")
        for row in rows
        if str(row.get("platform") or "").strip().lower() == key
        and str(row.get("scenario") or "").strip().lower() == "rewrite"
        and str(row.get("status") or "").strip().lower() == "active"
    ]
    return _build_style_profile(
        platform=key,
        texts=rewritten_texts,
        profile_type=RewriteStyleProfile,
    )


@lru_cache(maxsize=8)
def dedup_style_profile(platform: str) -> DedupStyleProfile | None:
    key = str(platform or "").strip().lower()
    rows = [*_load_supplemental_dedup_reference_rows(), *_load_dedup_reference_rows()]
    excerpts = [
        str(row.get("excerpt") or "")
        for row in rows
        if str(row.get("platform") or "").strip().lower() == key
        and str(row.get("scenario") or "").strip().lower() == "dedup"
        and str(row.get("status") or "").strip().lower() == "active"
    ]
    return _build_style_profile(
        platform=key,
        texts=excerpts,
        profile_type=DedupStyleProfile,
    )


def _build_style_profile(platform: str, texts: list[str], profile_type):
    if not texts:
        return None

    metrics = [_text_metrics(text) for text in texts if str(text or "").strip()]
    metrics = [item for item in metrics if item["sentence_count"] > 0]
    if not metrics:
        return None

    sample_count = len(metrics)
    avg_sentence_length = sum(item["avg_sentence_length"] for item in metrics) / sample_count
    avg_sentence_count = sum(item["sentence_count"] for item in metrics) / sample_count
    avg_connector_ratio = sum(item["connector_ratio"] for item in metrics) / sample_count
    return profile_type(
        platform=platform,
        sample_count=sample_count,
        avg_sentence_length=round(avg_sentence_length, 4),
        avg_sentence_count=round(avg_sentence_count, 4),
        avg_connector_ratio=round(avg_connector_ratio, 4),
    )


@lru_cache(maxsize=1)
def _load_positive_pair_rows() -> tuple[dict, ...]:
    if not POSITIVE_PAIR_PATH.exists():
        return ()
    return _load_jsonl_rows(POSITIVE_PAIR_PATH)


@lru_cache(maxsize=1)
def _load_supplemental_positive_pair_rows() -> tuple[dict, ...]:
    if not SUPPLEMENTAL_POSITIVE_PAIR_PATH.exists():
        return ()
    return _load_jsonl_rows(SUPPLEMENTAL_POSITIVE_PAIR_PATH)


@lru_cache(maxsize=1)
def _load_dedup_reference_rows() -> tuple[dict, ...]:
    if not DEDUP_REFERENCE_PATH.exists():
        return ()
    return _load_jsonl_rows(DEDUP_REFERENCE_PATH)


@lru_cache(maxsize=1)
def _load_supplemental_dedup_reference_rows() -> tuple[dict, ...]:
    if not SUPPLEMENTAL_DEDUP_REFERENCE_PATH.exists():
        return ()
    return _load_jsonl_rows(SUPPLEMENTAL_DEDUP_REFERENCE_PATH)


def _load_jsonl_rows(path: Path) -> tuple[dict, ...]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            payload = json.loads(raw)
            if isinstance(payload, dict):
                rows.append(payload)
    return tuple(rows)


def _style_signals(
    *,
    profile: RewriteStyleProfile | DedupStyleProfile | None,
    metrics: dict[str, float | int],
    connector_padding: float,
    connector_floor: float,
    sentence_length_limit: float,
) -> dict[str, float | int]:
    if profile is None or metrics["sentence_count"] <= 0:
        return {
            "style_profile_available": False,
            "style_alignment_ok": True,
            "style_sentence_length_delta": 0.0,
            "style_connector_ratio": round(metrics["connector_ratio"], 4),
        }

    sentence_length_delta = 0.0
    if profile.avg_sentence_length > 0:
        sentence_length_delta = round(
            abs(metrics["avg_sentence_length"] - profile.avg_sentence_length) / profile.avg_sentence_length,
            4,
        )
    connector_limit = max(profile.avg_connector_ratio + connector_padding, connector_floor)
    style_alignment_ok = not (
        sentence_length_delta > sentence_length_limit or metrics["connector_ratio"] > connector_limit
    )
    return {
        "style_profile_available": True,
        "style_alignment_ok": style_alignment_ok,
        "style_sentence_length_delta": sentence_length_delta,
        "style_connector_ratio": round(metrics["connector_ratio"], 4),
    }


def _text_metrics(text: str) -> dict[str, float | int]:
    content = str(text or "").strip()
    sentences = [part.strip() for part in re.split(r"[。！？!?；;]+", content) if part.strip()]
    sentence_count = len(sentences)
    if sentence_count <= 0:
        return {"sentence_count": 0, "avg_sentence_length": 0.0, "connector_ratio": 0.0}

    total_chars = sum(len(sentence) for sentence in sentences)
    connector_hits = sum(1 for sentence in sentences if sentence.startswith(CONNECTOR_PREFIXES))
    return {
        "sentence_count": sentence_count,
        "avg_sentence_length": round(total_chars / sentence_count, 4),
        "connector_ratio": round(connector_hits / sentence_count, 4),
    }
