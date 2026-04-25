from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from docx import Document

from app.services.strategy_asset_paths import resolve_project_path, resolve_strategy_asset_dir
from app.services.strategy_prompt_assets import slot_negative_examples, slot_positive_examples
from app.services.strategy_style_profiles import build_dedup_style_guidance, build_rewrite_style_guidance


STRATEGY_ASSET_DIR = resolve_strategy_asset_dir()
STRICT_BENCHMARK_PATH = STRATEGY_ASSET_DIR / "strict_benchmark_samples_v1.jsonl"
WEAK_SUPERVISED_PATH = STRATEGY_ASSET_DIR / "weak_supervised_pairs_v1.jsonl"
DEDUP_REFERENCE_PATH = STRATEGY_ASSET_DIR / "dedup_positive_references_v1.jsonl"
REPORT_OUTPUT_DIR = resolve_project_path("docs")

SLOT_ORDER = (
    "cnki.rewrite.llm",
    "cnki.dedup.llm",
    "vip.rewrite.llm",
    "vip.dedup.llm",
)


@dataclass(frozen=True)
class SlotEvaluation:
    slot: str
    slot_type: str
    status: str
    sample_count: int
    qualified_count: int
    qualified_rate: float
    details: dict[str, object]


def evaluate_strategy_slots() -> dict[str, object]:
    rows = [
        _evaluate_rewrite_llm_slot("cnki"),
        _evaluate_dedup_llm_slot("cnki"),
        _evaluate_rewrite_llm_slot("vip"),
        _evaluate_dedup_llm_slot("vip"),
    ]
    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row.status] = status_counts.get(row.status, 0) + 1
    return {
        "generated_on": date.today().isoformat(),
        "summary": {
            "slot_count": len(rows),
            "status_counts": dict(sorted(status_counts.items())),
        },
        "slots": [row.__dict__ for row in rows],
    }


def render_strategy_slot_evaluation_report(payload: dict[str, object]) -> str:
    lines = [
        "# 四槽位策略评估",
        "",
        f"更新日期：{payload.get('generated_on')}",
        "",
        "## 1. 总体结论",
        "",
    ]
    summary = payload.get("summary") or {}
    status_counts = summary.get("status_counts") or {}
    lines.append(f"- 槽位总数：{summary.get('slot_count', 0)}")
    for status in ("strong", "moderate", "weak"):
        lines.append(f"- `{status}`：{status_counts.get(status, 0)}")

    lines.extend(["", "## 2. 槽位明细", ""])
    for index, row in enumerate(payload.get("slots") or [], 1):
        details = row.get("details") or {}
        lines.append(f"### 2.{index} `{row['slot']}`")
        lines.append(f"- 类型：`{row['slot_type']}`")
        lines.append(f"- 状态：`{row['status']}`")
        lines.append(f"- 样本数：`{row['sample_count']}`")
        lines.append(f"- 合格数：`{row['qualified_count']}`")
        lines.append(f"- 合格率：`{row['qualified_rate']:.2f}`")
        for key, value in details.items():
            lines.append(f"- {key}：`{value}`")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def write_strategy_slot_evaluation_report(payload: dict[str, object], *, date_label: str | None = None) -> Path:
    label = str(date_label or payload.get("generated_on") or date.today().isoformat())
    output_path = REPORT_OUTPUT_DIR / f"STRATEGY_SLOT_EVALUATION_{label}.md"
    output_path.write_text(render_strategy_slot_evaluation_report(payload), encoding="utf-8")
    return output_path


def _evaluate_rewrite_llm_slot(platform: str) -> SlotEvaluation:
    slot = f"{platform}.rewrite.llm"
    positive_rows = slot_positive_examples(slot, limit=3)
    negative_rows = slot_negative_examples(slot, limit=2)
    guidance = build_rewrite_style_guidance(platform)
    disciplines = {str(row.get("discipline") or "") for row in positive_rows}
    checks = {
        "style_guidance": bool(guidance),
        "positive_examples": bool(positive_rows),
        "negative_examples": bool(negative_rows),
        "non_education_example_present": any(item and item != "education" for item in disciplines),
    }
    qualified = sum(1 for value in checks.values() if value)
    qualified_rate = round(qualified / len(checks), 4)
    return SlotEvaluation(
        slot=slot,
        slot_type="llm_prompt_readiness",
        status=_prompt_status(qualified_rate),
        sample_count=len(checks),
        qualified_count=qualified,
        qualified_rate=qualified_rate,
        details={
            "positive_example_count": len(positive_rows),
            "negative_example_count": len(negative_rows),
            "disciplines": ",".join(sorted(item for item in disciplines if item)) or "none",
        },
    )


def _evaluate_dedup_llm_slot(platform: str) -> SlotEvaluation:
    slot = f"{platform}.dedup.llm"
    positive_rows = slot_positive_examples(slot, limit=3)
    negative_rows = slot_negative_examples(slot, limit=2)
    guidance = build_dedup_style_guidance(platform)
    disciplines = {str(row.get("discipline") or "") for row in positive_rows}
    checks = {
        "style_guidance": bool(guidance),
        "positive_examples": bool(positive_rows),
        "negative_examples": bool(negative_rows),
        "non_education_example_present": any(item and item != "education" for item in disciplines),
    }
    qualified = sum(1 for value in checks.values() if value)
    qualified_rate = round(qualified / len(checks), 4)
    return SlotEvaluation(
        slot=slot,
        slot_type="llm_prompt_readiness",
        status=_prompt_status(qualified_rate),
        sample_count=len(checks),
        qualified_count=qualified,
        qualified_rate=qualified_rate,
        details={
            "positive_example_count": len(positive_rows),
            "negative_example_count": len(negative_rows),
            "disciplines": ",".join(sorted(item for item in disciplines if item)) or "none",
        },
    )
def _prompt_status(qualified_rate: float) -> str:
    if qualified_rate >= 1.0:
        return "strong"
    if qualified_rate >= 0.75:
        return "moderate"
    return "weak"


def _load_rewrite_source_paragraphs(platform: str) -> list[str]:
    rows = [* _load_jsonl_rows(STRICT_BENCHMARK_PATH), * _load_jsonl_rows(WEAK_SUPERVISED_PATH)]
    paragraphs: list[str] = []
    for row in rows:
        if str(row.get("platform") or "").strip().lower() != platform:
            continue
        if str(row.get("scenario") or "").strip().lower() != "rewrite":
            continue
        paragraphs.extend(_read_source_paragraphs(Path(str(row.get("source_text_path") or "")), limit=2))
    return paragraphs


def _load_dedup_excerpts(platform: str) -> list[str]:
    rows = _load_jsonl_rows(DEDUP_REFERENCE_PATH)
    excerpts: list[str] = []
    for row in rows:
        if str(row.get("platform") or "").strip().lower() != platform:
            continue
        if str(row.get("scenario") or "").strip().lower() != "dedup":
            continue
        excerpt = str(row.get("excerpt") or "").strip()
        if excerpt:
            excerpts.append(excerpt)
        if len(excerpts) >= 8:
            break
    return excerpts


def _read_source_paragraphs(path: Path, *, limit: int) -> list[str]:
    if not path.exists():
        return []
    if path.suffix.lower() == ".docx":
        doc = Document(path)
        paragraphs = [
            " ".join(paragraph.text.split()).strip()
            for paragraph in doc.paragraphs
            if len(" ".join(paragraph.text.split()).strip()) >= 80
        ]
        return paragraphs[:limit]
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    return [paragraph.strip() for paragraph in text.splitlines() if len(paragraph.strip()) >= 80][:limit]


def _load_jsonl_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            payload = json.loads(raw)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows
