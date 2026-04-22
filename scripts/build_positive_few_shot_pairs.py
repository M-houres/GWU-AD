from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from docx import Document


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.rewrite_strategies.validators import validate_rewrite_output
from app.services.processing_text_tools import merge_short_sentences, soften_connective_prefixes

STRATEGY_ASSET_DIR = REPO_ROOT / "data" / "strategy_assets"
STRICT_BENCHMARK_PATH = STRATEGY_ASSET_DIR / "strict_benchmark_samples_v1.jsonl"
WEAK_SUPERVISED_PATH = STRATEGY_ASSET_DIR / "weak_supervised_pairs_v1.jsonl"
OUTPUT_PATH = STRATEGY_ASSET_DIR / "positive_few_shot_pairs_v1.jsonl"
MAX_OUTPUT_ROWS = 24
DISCIPLINE_PRIORITY = {
    "finance_management": 0,
    "law_policy": 1,
    "engineering_it_patent": 2,
    "medicine_public_health": 3,
    "humanities_social_science": 4,
    "education": 5,
}


@dataclass(frozen=True)
class ParagraphPair:
    source: str
    rewritten: str
    similarity: float
    curated: bool = False


def load_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            payload = json.loads(raw)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def read_docx_paragraphs(path: Path) -> list[str]:
    if not path.exists() or path.suffix.lower() != ".docx":
        return []
    doc = Document(path)
    paragraphs: list[str] = []
    for paragraph in doc.paragraphs:
        text = " ".join(paragraph.text.split()).strip()
        if len(text) < 24:
            continue
        if text in paragraphs:
            continue
        paragraphs.append(text)
    return paragraphs


def align_pairs(source_paragraphs: list[str], rewritten_paragraphs: list[str], *, limit: int = 2) -> list[ParagraphPair]:
    pairs: list[ParagraphPair] = []
    for source, rewritten in zip(source_paragraphs, rewritten_paragraphs):
        if not source or not rewritten or source == rewritten:
            continue
        similarity = SequenceMatcher(None, source[:500], rewritten[:500]).ratio()
        if similarity < 0.22 or similarity > 0.88:
            continue
        if abs(len(source) - len(rewritten)) > max(80, int(len(source) * 0.7)):
            continue
        pairs.append(ParagraphPair(source=source, rewritten=rewritten, similarity=round(similarity, 4)))
    pairs.sort(key=lambda item: (abs(item.similarity - 0.62), -min(len(item.source), len(item.rewritten))))
    return pairs[:limit]


def infer_discipline(row: dict) -> str:
    text = f"{row.get('title') or ''} {row.get('notes') or ''}"
    if any(token in text for token in ("小学", "课堂", "书香校园", "少先队", "劳动教育", "阅读教学", "教师队伍")):
        return "education"
    if any(token in text for token in ("医学", "临床", "护理", "患者", "肺癌", "中药")):
        return "medicine_public_health"
    if any(token in text for token in ("纪检", "监督", "行政", "服务中心", "治理", "法")):
        return "law_policy"
    if any(token in text for token in ("营销", "财务", "营运资金", "餐饮", "公司", "应收账款")):
        return "finance_management"
    if any(token in text for token in ("AI", "信息科技", "系统", "WEB", "BIM", "技术")):
        return "engineering_it_patent"
    if any(token in text for token in ("红色资源", "黄州诗文", "古代小说", "人生意识", "社会风貌")):
        return "humanities_social_science"
    return "education"


def resolve_rewritten_paths(row: dict) -> list[Path]:
    paths: list[Path] = []
    rewritten_text_path = str(row.get("rewritten_text_path") or "").strip()
    if rewritten_text_path:
        paths.append(Path(rewritten_text_path))
    for candidate in row.get("rewritten_candidates") or []:
        candidate_path = Path(str(candidate))
        if candidate_path not in paths:
            paths.append(candidate_path)
    return paths


def build_positive_rows() -> list[dict]:
    rows = [*load_rows(STRICT_BENCHMARK_PATH), *load_rows(WEAK_SUPERVISED_PATH)]
    candidates: list[dict] = []
    for row in rows:
        status = str(row.get("status") or "").strip().lower()
        scenario = str(row.get("scenario") or "").strip().lower()
        if status != "active" or scenario != "rewrite":
            continue

        source_path = Path(str(row.get("source_text_path") or ""))
        source_paragraphs = read_docx_paragraphs(source_path)
        if not source_paragraphs:
            continue

        for rewritten_path in resolve_rewritten_paths(row):
            rewritten_paragraphs = read_docx_paragraphs(rewritten_path)
            if not rewritten_paragraphs:
                continue

            sample_platform = str(row.get("platform") or "")
            sample_discipline = infer_discipline(row)
            aligned = [
                _normalize_pair_for_asset(sample_platform, pair)
                for pair in align_pairs(source_paragraphs, rewritten_paragraphs)
            ]
            aligned = [
                pair
                for pair in aligned
                if pair is not None and _pair_is_valid_for_platform(sample_platform, pair)
            ]
            for index, pair in enumerate(aligned, 1):
                candidates.append(
                    {
                        "sample_id": f"{row['sample_id']}_pair_{index:02d}",
                        "status": "active",
                        "source_asset_id": row["sample_id"],
                        "tier": str(row.get("tier") or ""),
                        "platform": str(row.get("platform") or ""),
                        "scenario": scenario,
                        "discipline": sample_discipline,
                        "mode_scope": list(row.get("mode_scope") or []),
                        "target_slots": list(row.get("target_slots") or []),
                        "source_kind": _source_kind(row, pair),
                        "title": str(row.get("title") or ""),
                        "source_excerpt": pair.source,
                        "rewritten_excerpt": pair.rewritten,
                        "similarity": pair.similarity,
                        "notes": str(row.get("notes") or ""),
                    }
                )
            break
    return _finalize_rows(candidates)


def _normalize_pair_for_asset(platform: str, pair: ParagraphPair) -> ParagraphPair | None:
    original = str(pair.rewritten or "")
    normalized = _curate_rewritten_text(platform, original)
    similarity = SequenceMatcher(None, pair.source[:500], normalized[:500]).ratio()
    if similarity < 0.22 or similarity > 0.88:
        return None
    return ParagraphPair(
        source=pair.source,
        rewritten=normalized,
        similarity=round(similarity, 4),
        curated=normalized != original,
    )


def _curate_rewritten_text(platform: str, text: str) -> str:
    output = str(text or "").strip()
    normalized_platform = str(platform or "").strip().lower()
    keep_first = 0 if normalized_platform == "cnki" else 1
    output = soften_connective_prefixes(output, keep_first=keep_first)
    merge_length = 26 if normalized_platform == "cnki" else 24
    output = merge_short_sentences(output, max_sentence_length=merge_length, merge_limit=2)
    output = output.replace("。定制品质体验", "，“定制品质体验”")
    output = output.replace("。明确", "，明确")
    output = output.replace("。制定", "，制定")
    output = output.replace("摘要：", "摘要：", 1)
    return output.strip()


def _source_kind(row: dict, pair: ParagraphPair) -> str:
    base_kind = "strict_benchmark" if "strict_benchmark" in (row.get("benchmark_role") or []) else "weak_supervision"
    if pair.curated:
        return f"{base_kind}_curated"
    return base_kind


def _finalize_rows(rows: list[dict]) -> list[dict]:
    if not rows:
        return []

    ordered = sorted(
        rows,
        key=lambda row: (
            DISCIPLINE_PRIORITY.get(str(row.get("discipline") or "education"), 99),
            0 if "strict_benchmark" in str(row.get("source_kind") or "") else 1,
            abs(float(row.get("similarity") or 0.0) - 0.62),
            -min(len(str(row.get("source_excerpt") or "")), len(str(row.get("rewritten_excerpt") or ""))),
        ),
    )

    picked: list[dict] = []
    per_asset_counts: dict[str, int] = {}
    per_discipline_counts: dict[str, int] = {}
    for row in ordered:
        source_asset_id = str(row.get("source_asset_id") or "")
        discipline = str(row.get("discipline") or "education")
        if per_asset_counts.get(source_asset_id, 0) >= 2:
            continue
        if discipline != "education" and per_discipline_counts.get(discipline, 0) >= 3:
            continue
        if discipline == "education" and per_discipline_counts.get(discipline, 0) >= 12:
            continue
        picked.append(row)
        per_asset_counts[source_asset_id] = per_asset_counts.get(source_asset_id, 0) + 1
        per_discipline_counts[discipline] = per_discipline_counts.get(discipline, 0) + 1
        if len(picked) >= MAX_OUTPUT_ROWS:
            break
    return picked


def _pair_is_valid_for_platform(platform: str, pair: ParagraphPair) -> bool:
    try:
        validation = validate_rewrite_output(
            platform=str(platform or ""),
            source_text=pair.source,
            rewritten_text=pair.rewritten,
            strict_length=False,
            rule_trace={"mode": "pair_filter"},
        )
    except Exception:
        return False
    if validation.quality_flags.get("structure_natural_ok") is False:
        return False
    return True


def main() -> None:
    rows = build_positive_rows()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"{OUTPUT_PATH.name}\t{len(rows)}")


if __name__ == "__main__":
    main()
