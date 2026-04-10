from __future__ import annotations

import argparse
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from docx import Document
from pypdf import PdfReader


HEADER_LINES = {"https://cx.cnki.net", "知网个人AIGC检测服务", "cx.cnki.net"}
RISK_ORDER = {"clean": 0, "low": 1, "medium": 2, "high": 3}
SECTION_HEADER_RE = re.compile(r"^\d+\.\s+.+$")
FRAGMENT_ROW_RE = re.compile(r"^(\d+)\s+片段\d+\s+(\d+)\s+(疑似|显著)\s+([0-9]+(?:\.[0-9]+)?)%$")
MARKER_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)%\((\d+)\)")
HEADING_RE = re.compile(
    r"^(摘要|ABSTRACT|关键词[:：]?|关\s*键\s*词[:：]?|研究类型[:：]?|说明[:：]?|"
    r"[一二三四五六七八九十]+、.+|（[一二三四五六七八九十]+）.+|"
    r"\d+(?:\.\d+){0,3}\s*.+)$"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build normalized CNKI AIGC reference samples from report PDFs.")
    parser.add_argument("--pdf", action="append", required=True, help="CNKI AIGC report PDF path. Repeat for multiple files.")
    parser.add_argument("--output", required=True, help="Output JSON path.")
    parser.add_argument(
        "--source-docx",
        action="append",
        default=[],
        help="Optional source DOCX path. The file stem is used to match corresponding report input names.",
    )
    return parser.parse_args()


def clean_line(line: str) -> str:
    return str(line or "").replace("\u3000", " ").strip()


def is_page_number(line: str) -> bool:
    compact = line.replace(" ", "")
    return compact.startswith("—") and compact.endswith("—") and any(ch.isdigit() for ch in compact)


def is_header_line(line: str) -> bool:
    return not line or line in HEADER_LINES or is_page_number(line)


def normalize_text(text: str) -> str:
    compact = re.sub(r"\s+", "", str(text or "").lower())
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", compact)


def slugify(text: str) -> str:
    compact = re.sub(r"[^0-9a-zA-Z]+", "_", text).strip("_").lower()
    return compact[:48] or "sample"


def count_billable_chars(text: str) -> int:
    return len(re.sub(r"\s+", "", str(text or "")))


def label_from_fragment(fragment_type: str, score_pct: float) -> str:
    if fragment_type == "显著" or score_pct >= 60:
        return "high"
    if score_pct >= 30:
        return "medium"
    if fragment_type == "疑似" or score_pct > 0:
        return "low"
    return "clean"


def stronger_label(left: str, right: str) -> str:
    return left if RISK_ORDER.get(left, 0) >= RISK_ORDER.get(right, 0) else right


def extract_pdf_lines(pdf_path: Path) -> list[str]:
    reader = PdfReader(str(pdf_path))
    lines: list[str] = []
    for page in reader.pages:
        lines.extend(clean_line(item) for item in (page.extract_text() or "").splitlines())
    return [line for line in lines if line]


def read_docx_text(docx_path: Path) -> str:
    doc = Document(str(docx_path))
    paragraphs = [clean_line(paragraph.text) for paragraph in doc.paragraphs if clean_line(paragraph.text)]
    return "\n".join(paragraphs)


def parse_metadata(lines: list[str], pdf_path: Path) -> dict[str, Any]:
    info: dict[str, Any] = {
        "report_pdf": str(pdf_path),
        "report_filename": pdf_path.name,
    }
    for index, line in enumerate(lines[:80]):
        if "检测时间：" in line:
            info["detect_time"] = line.split("检测时间：", 1)[1].strip()
            no_match = re.search(r"NO:([^\s]+)", line)
            if no_match:
                info["report_no"] = no_match.group(1).strip()
        elif line.startswith("篇名："):
            info["title"] = line.split("：", 1)[1].strip()
        elif line.startswith("作者："):
            info["author"] = line.split("：", 1)[1].strip()
        elif line.startswith("文件名："):
            info["input_filename"] = line.split("：", 1)[1].strip()
        elif line.startswith("AI特征值：") and "total_score_pct" not in info:
            info["total_score_pct"] = float(line.split("：", 1)[1].strip().rstrip("%"))
        elif line.startswith("AI特征字符数：") and "ai_chars" not in info:
            info["ai_chars"] = int(line.split("：", 1)[1].strip())
        elif line.startswith("总字符数："):
            info["total_chars"] = int(line.split("：", 1)[1].strip())
        elif index > 0 and lines[index - 1].startswith("全文检测结果") and line.endswith("%"):
            info.setdefault("total_score_pct", float(line.rstrip("%")))
    return info


def choose_docx(docx_paths: list[Path], input_filename: str) -> Path | None:
    if not docx_paths:
        return None
    normalized_input = normalize_text(Path(input_filename).stem)
    ranked: list[tuple[int, Path]] = []
    for path in docx_paths:
        normalized_name = normalize_text(path.stem)
        score = 0
        if normalized_input and normalized_input in normalized_name:
            score = len(normalized_input)
        elif normalized_name and normalized_name in normalized_input:
            score = len(normalized_name)
        ranked.append((score, path))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked[0][1] if ranked and ranked[0][0] > 0 else None


def parse_report_content(lines: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    fragments: list[dict[str, Any]] = []
    spans: list[dict[str, Any]] = []
    content_lines: list[str] = []
    current_fragments: list[dict[str, Any]] = []
    in_content = False
    span_buffer: list[str] = []

    for line in lines:
        if is_header_line(line):
            continue
        if line == "说明:":
            break

        fragment_match = FRAGMENT_ROW_RE.match(line)
        if fragment_match:
            fragment = {
                "row_no": int(fragment_match.group(1)),
                "char_count": int(fragment_match.group(2)),
                "fragment_type": fragment_match.group(3),
                "score_pct": float(fragment_match.group(4)),
            }
            fragments.append(fragment)
            current_fragments.append(fragment)
            continue

        if line == "原文内容":
            in_content = True
            span_buffer = []
            continue

        if SECTION_HEADER_RE.match(line):
            in_content = False
            current_fragments = []
            continue

        if not in_content:
            continue

        marker_match = MARKER_RE.search(line)
        if marker_match:
            before = clean_line(line[: marker_match.start()])
            if before:
                content_lines.append(before)
                span_buffer.append(before)

            score_pct = float(marker_match.group(1))
            char_count = int(marker_match.group(2))
            fragment = find_fragment(current_fragments, char_count=char_count, score_pct=score_pct)
            spans.append(
                {
                    "score_pct": score_pct,
                    "char_count": char_count,
                    "fragment_type": (fragment or {}).get("fragment_type", ""),
                    "label": label_from_fragment((fragment or {}).get("fragment_type", ""), score_pct),
                    "text": "".join(span_buffer).strip(),
                }
            )
            span_buffer = []

            after = clean_line(line[marker_match.end() :])
            if after:
                content_lines.append(after)
                span_buffer.append(after)
            continue

        content_lines.append(line)
        span_buffer.append(line)

    return spans, content_lines


def find_fragment(fragments: list[dict[str, Any]], *, char_count: int, score_pct: float) -> dict[str, Any] | None:
    for item in fragments:
        if item["char_count"] == char_count and abs(item["score_pct"] - score_pct) < 0.01:
            return item
    for item in fragments:
        if item["char_count"] == char_count:
            return item
    for item in fragments:
        if abs(item["score_pct"] - score_pct) < 0.01:
            return item
    return None


def is_heading_line(line: str) -> bool:
    if HEADING_RE.match(line):
        return True
    if len(line) <= 28 and not re.search(r"[。！？；,，]", line):
        return True
    return False


def join_fragments(left: str, right: str) -> str:
    if not left:
        return right
    if re.search(r"[A-Za-z0-9]$", left) and re.match(r"^[A-Za-z0-9]", right):
        return f"{left} {right}"
    return f"{left}{right}"


def should_flush_paragraph(line: str) -> bool:
    stripped = line.rstrip()
    if not stripped:
        return True
    if stripped.endswith(("。", "！", "？", "；", ":", "：")):
        return True
    if stripped.endswith(".") and len(stripped) > 24:
        return True
    return False


def build_paragraphs(content_lines: list[str]) -> list[str]:
    paragraphs: list[str] = []
    current = ""
    for line in content_lines:
        if is_heading_line(line):
            if current:
                paragraphs.append(current)
                current = ""
            paragraphs.append(line)
            continue
        current = join_fragments(current, line)
        if should_flush_paragraph(line):
            paragraphs.append(current)
            current = ""
    if current:
        paragraphs.append(current)
    return [item for item in paragraphs if item]


def overlap_ratio(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if left in right:
        return min(1.0, len(left) / max(len(right), 1))
    if right in left:
        return min(1.0, len(right) / max(len(left), 1))
    return SequenceMatcher(None, left[:2400], right[:2400]).ratio()


def find_best_range(span_text: str, paragraph_norms: list[str], cursor: int) -> tuple[int, int, float]:
    best_start = 0
    best_end = 0
    best_score = 0.0
    target = normalize_text(span_text)
    if not target:
        return best_start, best_end, best_score

    start_limit = min(len(paragraph_norms), max(cursor + 30, 30))
    for start in range(min(cursor, len(paragraph_norms)), start_limit):
        merged = ""
        for end in range(start, min(start + 8, len(paragraph_norms))):
            merged += paragraph_norms[end]
            score = overlap_ratio(target, merged)
            if score > best_score:
                best_start, best_end, best_score = start, end, score
            if len(merged) > len(target) * 1.6 and best_score >= 0.72:
                break
    return best_start, best_end, best_score


def attach_spans_to_paragraphs(paragraphs: list[str], spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    paragraph_norms = [normalize_text(item) for item in paragraphs]
    rows: dict[int, dict[str, Any]] = {}
    cursor = 0

    for span in spans:
        start, end, score = find_best_range(span["text"], paragraph_norms, cursor)
        if score < 0.22:
            continue
        cursor = start
        for index in range(start, end + 1):
            row = rows.setdefault(
                index,
                {
                    "index": index + 1,
                    "score_pct": 0.0,
                    "label": "clean",
                    "text": paragraphs[index],
                    "spans": [],
                },
            )
            row["score_pct"] = round(max(row["score_pct"], span["score_pct"]), 2)
            row["label"] = stronger_label(row["label"], span["label"])
            row["spans"].append(
                {
                    "text": paragraphs[index][:220],
                    "label": span["label"],
                    "score_pct": round(span["score_pct"], 2),
                }
            )

    return [rows[index] for index in sorted(rows)]


def build_band_ratio(total_chars: int, spans: list[dict[str, Any]]) -> dict[str, float]:
    high_chars = sum(item["char_count"] for item in spans if item["label"] == "high")
    medium_chars = sum(item["char_count"] for item in spans if item["label"] == "medium")
    low_chars = sum(item["char_count"] for item in spans if item["label"] == "low")
    if total_chars <= 0:
        return {"high": 0.0, "medium": 0.0, "low": 0.0, "clean": 0.0}
    high = round(high_chars / total_chars * 100, 2)
    medium = round(medium_chars / total_chars * 100, 2)
    low = round(low_chars / total_chars * 100, 2)
    clean = round(max(0.0, 100.0 - high - medium - low), 2)
    return {"high": high, "medium": medium, "low": low, "clean": clean}


def build_sample(pdf_path: Path, docx_paths: list[Path]) -> dict[str, Any]:
    lines = extract_pdf_lines(pdf_path)
    metadata = parse_metadata(lines, pdf_path)
    spans, content_lines = parse_report_content(lines)

    source_docx = choose_docx(docx_paths, str(metadata.get("input_filename") or ""))
    if source_docx is not None:
        source_text = read_docx_text(source_docx)
        source_kind = "docx"
    else:
        source_paragraphs = build_paragraphs(content_lines)
        source_text = "\n".join(source_paragraphs)
        source_kind = "report_pdf"

    source_paragraphs = [line for line in source_text.splitlines() if clean_line(line)]
    if source_kind == "docx":
        source_paragraphs = [clean_line(line) for line in source_paragraphs if clean_line(line)]

    paragraph_rows = attach_spans_to_paragraphs(source_paragraphs, spans)
    total_chars = int(metadata.get("total_chars") or count_billable_chars(source_text))
    band_text_ratio = build_band_ratio(total_chars, spans)

    detect_time = str(metadata.get("detect_time") or "").replace("-", "").replace(":", "").replace(" ", "_")
    digest = hashlib.md5(str(pdf_path).encode("utf-8")).hexdigest()[:8]
    sample_id = f"cnki_aigc_{slugify(detect_time)}_{digest}"

    return {
        "sample_id": sample_id,
        "platform": "cnki",
        "source_text": source_text,
        "reference": {
            "total_score_pct": round(float(metadata.get("total_score_pct") or 0.0), 2),
            "band_text_ratio": band_text_ratio,
            "paragraphs": paragraph_rows,
            "metadata": {
                "title": metadata.get("title", ""),
                "author": metadata.get("author", ""),
                "input_filename": metadata.get("input_filename", ""),
                "report_filename": metadata.get("report_filename", ""),
                "report_no": metadata.get("report_no", ""),
                "detect_time": metadata.get("detect_time", ""),
                "total_chars": total_chars,
                "ai_chars": int(metadata.get("ai_chars") or 0),
                "source_kind": source_kind,
                "source_docx": str(source_docx) if source_docx is not None else "",
                "span_count": len(spans),
            },
            "raw_spans": spans,
            "notes": [
                "Derived from CNKI PDF text layer.",
                "Span-to-paragraph alignment is approximate and intended for offline package calibration.",
            ],
        },
    }


def main() -> int:
    args = parse_args()
    pdf_paths = [Path(item).expanduser().resolve() for item in args.pdf]
    docx_paths = [Path(item).expanduser().resolve() for item in args.source_docx]
    samples = [build_sample(path, docx_paths) for path in pdf_paths]

    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(samples, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = [
        {
            "sample_id": item["sample_id"],
            "title": item["reference"]["metadata"]["title"],
            "total_score_pct": item["reference"]["total_score_pct"],
            "paragraphs": len(item["reference"]["paragraphs"]),
            "spans": item["reference"]["metadata"]["span_count"],
            "source_kind": item["reference"]["metadata"]["source_kind"],
        }
        for item in samples
    ]
    print(json.dumps({"output": str(output_path), "samples": summary}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
