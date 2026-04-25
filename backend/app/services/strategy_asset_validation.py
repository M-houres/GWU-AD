from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
STRATEGY_ASSET_DIR = REPO_ROOT / "data" / "strategy_assets"
SUPPLEMENTAL_POSITIVE_PAIR_PATH = STRATEGY_ASSET_DIR / "supplemental_positive_few_shot_pairs_v1.jsonl"
SUPPLEMENTAL_DEDUP_REFERENCE_PATH = STRATEGY_ASSET_DIR / "supplemental_dedup_positive_references_v1.jsonl"

SLOT_KEYS = {
    "cnki.rewrite.llm",
    "cnki.dedup.llm",
    "vip.rewrite.llm",
    "vip.dedup.llm",
}

DISCIPLINE_KEYS = {
    "education",
    "medicine_public_health",
    "law_policy",
    "finance_management",
    "engineering_it_patent",
    "humanities_social_science",
}

SYNTHETIC_REQUIRED_FIELDS = {
    "sample_id",
    "status",
    "target_slot",
    "target_layer",
    "source_type",
    "source_reference",
    "error_type",
    "severity",
    "source_text",
    "synthetic_text",
    "expected_action",
    "notes",
}

POSITIVE_PAIR_REQUIRED_FIELDS = {
    "sample_id",
    "status",
    "source_asset_id",
    "tier",
    "platform",
    "scenario",
    "discipline",
    "mode_scope",
    "target_slots",
    "source_kind",
    "title",
    "source_excerpt",
    "rewritten_excerpt",
    "similarity",
    "notes",
}

DEDUP_POSITIVE_REFERENCE_REQUIRED_FIELDS = {
    "sample_id",
    "status",
    "platform",
    "scenario",
    "discipline",
    "mode_scope",
    "target_slots",
    "source_kind",
    "title",
    "source_path",
    "excerpt",
    "notes",
}


@dataclass(frozen=True)
class AssetFileSummary:
    name: str
    count: int


@dataclass(frozen=True)
class SyntheticCoverageSummary:
    total: int
    slots: dict[str, int]
    disciplines: dict[str, int]


@dataclass(frozen=True)
class PositivePairSummary:
    total: int
    slots: dict[str, int]
    disciplines: dict[str, int]


@dataclass(frozen=True)
class DedupPositiveReferenceSummary:
    total: int
    slots: dict[str, int]
    disciplines: dict[str, int]


def _load_jsonl_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            raw = line.strip()
            if not raw:
                continue
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError(f"{path.name}:{line_no} must be a JSON object")
            rows.append(payload)
    return rows


def validate_strategy_asset_files(asset_dir: Path = STRATEGY_ASSET_DIR) -> list[AssetFileSummary]:
    summaries: list[AssetFileSummary] = []
    for path in sorted(asset_dir.glob("*.jsonl")):
        rows = _load_jsonl_rows(path)
        summaries.append(AssetFileSummary(name=path.name, count=len(rows)))
    return summaries


def validate_synthetic_negative_samples(
    asset_path: Path = STRATEGY_ASSET_DIR / "synthetic_negative_samples_v1.jsonl",
) -> SyntheticCoverageSummary:
    rows = _load_jsonl_rows(asset_path)
    slot_counts = {slot: 0 for slot in sorted(SLOT_KEYS)}
    discipline_counts: dict[str, int] = {}

    for index, row in enumerate(rows, 1):
        missing = sorted(field for field in SYNTHETIC_REQUIRED_FIELDS if not row.get(field))
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"{asset_path.name}:{index} missing required fields: {joined}")

        slot = str(row["target_slot"]).strip()
        if slot not in SLOT_KEYS:
            raise ValueError(f"{asset_path.name}:{index} has unsupported slot: {slot}")
        slot_counts[slot] += 1

        discipline = str(row.get("discipline", "unspecified")).strip() or "unspecified"
        if discipline != "unspecified" and discipline not in DISCIPLINE_KEYS:
            raise ValueError(f"{asset_path.name}:{index} has unsupported discipline: {discipline}")
        discipline_counts[discipline] = discipline_counts.get(discipline, 0) + 1

    return SyntheticCoverageSummary(
        total=len(rows),
        slots=slot_counts,
        disciplines=dict(sorted(discipline_counts.items())),
    )


def validate_positive_few_shot_pairs(
    asset_path: Path = STRATEGY_ASSET_DIR / "positive_few_shot_pairs_v1.jsonl",
) -> PositivePairSummary:
    rows = _load_jsonl_rows(asset_path)
    slot_counts = {slot: 0 for slot in sorted(SLOT_KEYS)}
    discipline_counts: dict[str, int] = {}

    for index, row in enumerate(rows, 1):
        missing = sorted(field for field in POSITIVE_PAIR_REQUIRED_FIELDS if row.get(field) in (None, "", []))
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"{asset_path.name}:{index} missing required fields: {joined}")

        scenario = str(row.get("scenario") or "").strip()
        if scenario != "rewrite":
            raise ValueError(f"{asset_path.name}:{index} has unsupported scenario: {scenario}")

        discipline = str(row.get("discipline") or "").strip()
        if discipline not in DISCIPLINE_KEYS:
            raise ValueError(f"{asset_path.name}:{index} has unsupported discipline: {discipline}")
        discipline_counts[discipline] = discipline_counts.get(discipline, 0) + 1

        target_slots = tuple(row.get("target_slots") or [])
        if not target_slots:
            raise ValueError(f"{asset_path.name}:{index} has empty target_slots")
        for slot in target_slots:
            normalized = str(slot).strip()
            if normalized not in SLOT_KEYS:
                raise ValueError(f"{asset_path.name}:{index} has unsupported slot: {normalized}")
            slot_counts[normalized] += 1

        similarity = float(row.get("similarity"))
        if not (0.22 <= similarity <= 0.88):
            raise ValueError(f"{asset_path.name}:{index} has out-of-range similarity: {similarity}")

    return PositivePairSummary(
        total=len(rows),
        slots=slot_counts,
        disciplines=dict(sorted(discipline_counts.items())),
    )


def validate_supplemental_positive_few_shot_pairs(
    asset_path: Path = SUPPLEMENTAL_POSITIVE_PAIR_PATH,
) -> PositivePairSummary:
    return validate_positive_few_shot_pairs(asset_path)


def validate_dedup_positive_references(
    asset_path: Path = STRATEGY_ASSET_DIR / "dedup_positive_references_v1.jsonl",
) -> DedupPositiveReferenceSummary:
    rows = _load_jsonl_rows(asset_path)
    slot_counts = {slot: 0 for slot in sorted(SLOT_KEYS)}
    discipline_counts: dict[str, int] = {}

    for index, row in enumerate(rows, 1):
        missing = sorted(field for field in DEDUP_POSITIVE_REFERENCE_REQUIRED_FIELDS if row.get(field) in (None, "", []))
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"{asset_path.name}:{index} missing required fields: {joined}")

        scenario = str(row.get("scenario") or "").strip()
        if scenario != "dedup":
            raise ValueError(f"{asset_path.name}:{index} has unsupported scenario: {scenario}")

        platform = str(row.get("platform") or "").strip()
        if platform not in {"cnki", "vip"}:
            raise ValueError(f"{asset_path.name}:{index} has unsupported platform: {platform}")

        discipline = str(row.get("discipline") or "").strip()
        if discipline not in DISCIPLINE_KEYS:
            raise ValueError(f"{asset_path.name}:{index} has unsupported discipline: {discipline}")
        discipline_counts[discipline] = discipline_counts.get(discipline, 0) + 1

        target_slots = tuple(row.get("target_slots") or [])
        expected_slot_count = 1
        if len(target_slots) != expected_slot_count:
            raise ValueError(f"{asset_path.name}:{index} must target exactly {expected_slot_count} dedup slots")
        for slot in target_slots:
            normalized = str(slot).strip()
            if normalized not in SLOT_KEYS:
                raise ValueError(f"{asset_path.name}:{index} has unsupported slot: {normalized}")
            if f"{platform}.dedup." not in normalized:
                raise ValueError(f"{asset_path.name}:{index} mixes platform and slot: {normalized}")
            slot_counts[normalized] += 1

        excerpt = str(row.get("excerpt") or "").strip()
        if not (72 <= len(excerpt) <= 320):
            raise ValueError(f"{asset_path.name}:{index} has out-of-range excerpt length: {len(excerpt)}")

    return DedupPositiveReferenceSummary(
        total=len(rows),
        slots=slot_counts,
        disciplines=dict(sorted(discipline_counts.items())),
    )


def validate_supplemental_dedup_positive_references(
    asset_path: Path = SUPPLEMENTAL_DEDUP_REFERENCE_PATH,
) -> DedupPositiveReferenceSummary:
    return validate_dedup_positive_references(asset_path)
