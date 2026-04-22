from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from docx import Document


REPO_ROOT = Path(__file__).resolve().parents[3]
SYNTHETIC_NEGATIVE_PATH = REPO_ROOT / "data" / "strategy_assets" / "synthetic_negative_samples_v1.jsonl"
STRICT_BENCHMARK_PATH = REPO_ROOT / "data" / "strategy_assets" / "strict_benchmark_samples_v1.jsonl"
WEAK_SUPERVISED_PATH = REPO_ROOT / "data" / "strategy_assets" / "weak_supervised_pairs_v1.jsonl"
POSITIVE_PAIR_PATH = REPO_ROOT / "data" / "strategy_assets" / "positive_few_shot_pairs_v1.jsonl"
SUPPLEMENTAL_POSITIVE_PAIR_PATH = (
    REPO_ROOT / "data" / "strategy_assets" / "supplemental_positive_few_shot_pairs_v1.jsonl"
)
DEDUP_POSITIVE_REFERENCE_PATH = REPO_ROOT / "data" / "strategy_assets" / "dedup_positive_references_v1.jsonl"
SUPPLEMENTAL_DEDUP_REFERENCE_PATH = (
    REPO_ROOT / "data" / "strategy_assets" / "supplemental_dedup_positive_references_v1.jsonl"
)

DISCIPLINE_LABELS = {
    "education": "教育",
    "medicine_public_health": "医学/公卫",
    "law_policy": "法学/政策",
    "finance_management": "财经/管理",
    "engineering_it_patent": "工程/专利",
    "humanities_social_science": "人文社科",
    "unspecified": "未标注",
}

DISCIPLINE_PRIORITY = {
    "finance_management": 0,
    "law_policy": 1,
    "engineering_it_patent": 2,
    "medicine_public_health": 3,
    "humanities_social_science": 4,
    "education": 5,
    "unspecified": 6,
}


@lru_cache(maxsize=1)
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


@lru_cache(maxsize=1)
def _load_synthetic_negative_rows() -> tuple[dict, ...]:
    return _load_jsonl_rows(SYNTHETIC_NEGATIVE_PATH)


@lru_cache(maxsize=1)
def _load_strict_benchmark_rows() -> tuple[dict, ...]:
    return _load_jsonl_rows(STRICT_BENCHMARK_PATH)


@lru_cache(maxsize=1)
def _load_weak_supervised_rows() -> tuple[dict, ...]:
    return _load_jsonl_rows(WEAK_SUPERVISED_PATH)


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
def _load_dedup_positive_reference_rows() -> tuple[dict, ...]:
    if not DEDUP_POSITIVE_REFERENCE_PATH.exists():
        return ()
    return _load_jsonl_rows(DEDUP_POSITIVE_REFERENCE_PATH)


@lru_cache(maxsize=1)
def _load_supplemental_dedup_positive_reference_rows() -> tuple[dict, ...]:
    if not SUPPLEMENTAL_DEDUP_REFERENCE_PATH.exists():
        return ()
    return _load_jsonl_rows(SUPPLEMENTAL_DEDUP_REFERENCE_PATH)


def slot_negative_examples(slot: str, *, limit: int = 2) -> tuple[dict, ...]:
    key = str(slot or "").strip()
    rows = [
        row
        for row in _load_synthetic_negative_rows()
        if str(row.get("status") or "").strip().lower() == "active"
        and str(row.get("target_slot") or "").strip() == key
    ]
    preferred = [
        row for row in rows if str(row.get("target_layer") or "").strip() in {"few_shot_negative", "negative_assets"}
    ]
    picked = preferred[: max(limit, 0)]
    return tuple(picked)


def build_slot_prompt_examples(slot: str, *, limit: int = 2) -> str:
    examples = slot_negative_examples(slot, limit=limit)
    if not examples:
        return ""

    lines = ["禁止模仿以下坏写法示例："]
    for index, row in enumerate(examples, 1):
        discipline = DISCIPLINE_LABELS.get(str(row.get("discipline") or "unspecified"), "未标注")
        bad_text = str(row.get("synthetic_text") or "").strip()
        error_type = str(row.get("error_type") or "").strip()
        if len(bad_text) > 46:
            bad_text = f"{bad_text[:46]}..."
        lines.append(f"{index}. [{discipline}/{error_type}] {bad_text}")
    return "\n".join(lines)


def slot_positive_examples(slot: str, *, limit: int = 2) -> tuple[dict, ...]:
    key = str(slot or "").strip()
    dedup_reference_rows = [
        row
        for row in [*_load_supplemental_dedup_positive_reference_rows(), *_load_dedup_positive_reference_rows()]
        if str(row.get("status") or "").strip().lower() == "active"
        and key in tuple(row.get("target_slots") or [])
    ]
    if dedup_reference_rows:
        return _pick_diverse_rows(_sort_rows_by_discipline(dedup_reference_rows), limit=limit)

    supplemental_pair_rows = [
        row
        for row in _load_supplemental_positive_pair_rows()
        if str(row.get("status") or "").strip().lower() == "active"
        and key in tuple(row.get("target_slots") or [])
    ]
    pair_rows = [
        row
        for row in _load_positive_pair_rows()
        if str(row.get("status") or "").strip().lower() == "active"
        and key in tuple(row.get("target_slots") or [])
    ]
    rewrite_rows = _sort_rewrite_positive_rows([*supplemental_pair_rows, *pair_rows])
    if rewrite_rows:
        return _pick_diverse_rows(rewrite_rows, limit=limit)

    strict_rows = [
        row
        for row in _load_strict_benchmark_rows()
        if str(row.get("status") or "").strip().lower() == "active"
        and key in tuple(row.get("target_slots") or [])
    ]
    weak_rows = [
        row
        for row in _load_weak_supervised_rows()
        if str(row.get("status") or "").strip().lower() == "active"
        and key in tuple(row.get("target_slots") or [])
    ]
    return _pick_diverse_rows([*strict_rows, *weak_rows], limit=limit)


def _pick_diverse_rows(rows: list[dict] | tuple[dict, ...], *, limit: int) -> tuple[dict, ...]:
    cap = max(limit, 0)
    if cap <= 0:
        return ()
    picked: list[dict] = []
    seen_disciplines: set[str] = set()
    for row in rows:
        discipline = str(row.get("discipline") or "").strip()
        if discipline and discipline not in seen_disciplines:
            picked.append(row)
            seen_disciplines.add(discipline)
        if len(picked) >= cap:
            return tuple(picked[:cap])
    for row in rows:
        if row in picked:
            continue
        picked.append(row)
        if len(picked) >= cap:
            break
    return tuple(picked[:cap])


def _sort_rewrite_positive_rows(rows: list[dict]) -> list[dict]:
    return sorted(
        rows,
        key=lambda row: (
            DISCIPLINE_PRIORITY.get(str(row.get("discipline") or "unspecified"), 99),
            _rewrite_source_kind_priority(str(row.get("source_kind") or "")),
            abs(float(row.get("similarity") or 0.0) - 0.62),
        ),
    )


def _sort_rows_by_discipline(rows: list[dict]) -> list[dict]:
    return sorted(
        rows,
        key=lambda row: (
            DISCIPLINE_PRIORITY.get(str(row.get("discipline") or "unspecified"), 99),
            str(row.get("sample_id") or ""),
        ),
    )


def _rewrite_source_kind_priority(source_kind: str) -> int:
    value = str(source_kind or "").strip()
    if value.startswith("strict_benchmark"):
        return 0
    if value.startswith("supplemental_real"):
        return 1
    if value.startswith("supplemental_synthetic"):
        return 2
    if value.startswith("weak_supervision"):
        return 3
    return 4


def build_slot_positive_examples(slot: str, *, limit: int = 2) -> str:
    examples = slot_positive_examples(slot, limit=limit)
    if not examples:
        return _fallback_positive_guidance(slot)

    lines = ["优先参考以下正向改写风格示例："]
    for index, row in enumerate(examples, 1):
        if row.get("excerpt"):
            discipline = DISCIPLINE_LABELS.get(str(row.get("discipline") or "unspecified"), "未标注")
            source_kind = str(row.get("source_kind") or "").strip() or "reference"
            excerpt = _clip_preview(str(row.get("excerpt") or ""), limit=58)
            lines.append(f"{index}. [{discipline}/{source_kind}] {excerpt}")
            continue
        if row.get("source_excerpt") and row.get("rewritten_excerpt"):
            discipline = DISCIPLINE_LABELS.get(str(row.get("discipline") or "unspecified"), "未标注")
            tier = str(row.get("tier") or "").strip() or "sample"
            source_preview = _clip_preview(str(row.get("source_excerpt") or ""), limit=34)
            rewritten_preview = _clip_preview(str(row.get("rewritten_excerpt") or ""), limit=34)
            lines.append(f"{index}. [{discipline}/{tier}] {source_preview} -> {rewritten_preview}")
            continue
        discipline = _infer_discipline_label(row)
        source_text = _read_sample_preview(Path(str(row.get("source_text_path") or "")))
        rewritten_text = _read_sample_preview(_resolve_rewritten_path(row))
        title = str(row.get("title") or "").strip() or "未命名样本"
        tier = str(row.get("tier") or "").strip() or "sample"
        source_preview = _clip_preview(source_text or title, limit=34)
        rewritten_preview = _clip_preview(rewritten_text or str(row.get("notes") or ""), limit=34)
        lines.append(f"{index}. [{discipline}/{tier}] {source_preview} -> {rewritten_preview}")
    return "\n".join(lines)


def _resolve_rewritten_path(row: dict) -> Path:
    rewritten_path = str(row.get("rewritten_text_path") or "").strip()
    if rewritten_path:
        return Path(rewritten_path)
    candidates = row.get("rewritten_candidates") or []
    if isinstance(candidates, list) and candidates:
        return Path(str(candidates[0]))
    return Path()


def _read_sample_preview(path: Path) -> str:
    if not path or not str(path):
        return ""
    try:
        if path.suffix.lower() == ".docx" and path.exists():
            doc = Document(path)
            paragraphs = [para.text.strip() for para in doc.paragraphs if para.text and para.text.strip()]
            for paragraph in paragraphs:
                if len(paragraph) >= 16:
                    return paragraph
            return paragraphs[0] if paragraphs else ""
        if path.exists():
            return path.read_text(encoding="utf-8", errors="ignore").strip()
    except Exception:
        return ""
    return ""


def _infer_discipline_label(row: dict) -> str:
    notes = f"{row.get('title') or ''} {row.get('notes') or ''}"
    text = str(notes)
    if any(token in text for token in ("医学", "临床", "诊疗", "公卫", "糖尿病")):
        return DISCIPLINE_LABELS["medicine_public_health"]
    if any(token in text for token in ("法", "监督", "纪检", "复议", "案件", "治理")):
        return DISCIPLINE_LABELS["law_policy"]
    if any(token in text for token in ("营销", "财务", "企业", "餐饮", "管理")):
        return DISCIPLINE_LABELS["finance_management"]
    if any(token in text for token in ("AI", "信息科技", "工程", "技术", "智能")):
        return DISCIPLINE_LABELS["engineering_it_patent"]
    if any(token in text for token in ("红色资源", "地方志", "社会", "文化", "记忆")):
        return DISCIPLINE_LABELS["humanities_social_science"]
    return DISCIPLINE_LABELS["education"]


def _clip_preview(text: str, *, limit: int = 34) -> str:
    content = str(text or "").strip()
    if not content:
        return "示例待补"
    if len(content) <= limit:
        return content
    return f"{content[:limit]}..."


def _fallback_positive_guidance(slot: str) -> str:
    key = str(slot or "").strip().lower()
    if key == "cnki.dedup.llm":
        return (
            "优先参考以下正向改写风格示例：\n"
            "1. [知网/降重] 以完整定义句和综述句为单位微调句式，优先改动句序、修饰层次和连接关系，不扩写。"
        )
    if key == "vip.dedup.llm":
        return (
            "优先参考以下正向改写风格示例：\n"
            "1. [维普/降重] 允许适度重组长短句，但必须保持术语完整、逻辑连贯，并避免模板化连接词开头。"
        )
    if key == "cnki.rewrite.llm":
        return (
            "优先参考以下正向改写风格示例：\n"
            "1. [知网/降AIGC] 以段落级语义块重写为主，保持学术论证密度和专业术语稳定，避免表层近义词堆叠。"
        )
    if key == "vip.rewrite.llm":
        return (
            "优先参考以下正向改写风格示例：\n"
            "1. [维普/降AIGC] 优先做句式重组、长短句调节和段落顺滑处理，保持表达自然且术语完整。"
        )
    return ""
