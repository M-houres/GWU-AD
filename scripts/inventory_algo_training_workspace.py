from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
from typing import Any
import zipfile


DEFAULT_WORKSPACE_ROOT = Path(r"C:\Users\m\Desktop\001项目\算法训练资料包")
PLATFORM_NAME_MAP = {
    "知网资料包": "cnki",
    "维普资料包": "vip",
    "PaperPass资料包": "paperpass",
}
ROLE_LABELS = ("aigc_report", "dedup_report", "rewrite_doc", "source_doc", "other")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inventory algorithm training materials by platform and function role.")
    parser.add_argument("--root", default=str(DEFAULT_WORKSPACE_ROOT), help="Training workspace root path.")
    parser.add_argument("--output-json", help="Optional JSON output path.")
    parser.add_argument("--output-md", help="Optional Markdown output path.")
    return parser.parse_args()


def read_zip_entries(path: Path) -> list[str]:
    try:
        with zipfile.ZipFile(path) as archive:
            return archive.namelist()
    except Exception:
        return []


def classify_role(path: Path, archive_entries: list[str] | None = None) -> str:
    probe_parts = [path.name]
    if archive_entries:
        probe_parts.extend(archive_entries)
    probe = " ".join(probe_parts)

    if "AIGC" in probe or "AI特征值" in probe or "AIGC报告单" in probe:
        return "aigc_report"
    if any(
        marker in probe
        for marker in (
            "查重",
            "原文对照报告",
            "片段对照报告",
            "比对报告",
            "简洁报告",
            "格式分析报告",
            "标明引文",
            "复写率",
            "综合报告",
            "存档报告",
        )
    ):
        return "dedup_report"
    if any(marker in probe for marker in ("润色前", "润色后", "改写结果", "降AIGC")):
        return "rewrite_doc"
    if path.suffix.lower() == ".docx":
        return "source_doc"
    return "other"


def normalize_group_title(name: str) -> str:
    title = Path(name).stem
    title = title.replace("+", "").replace("\u00a0", " ")
    title = re.sub(r"[（(][0-9]+[)）]$", "", title)
    title = re.sub(r"^查重_全文\(标明引文\)报告单_", "", title)
    title = re.sub(r"^查重_全文对照报告单_", "", title)
    title = re.sub(r"^查重_简洁报告单_", "", title)
    title = re.sub(r"^AIGC全文报告_", "", title)
    title = re.sub(r"_AIGC报告单集.*$", "", title)
    title = re.sub(r"_AIGC_全文报告单$", "", title)
    title = re.sub(r"_AIGC_简洁报告单$", "", title)
    title = re.sub(r"_原文对照报告$", "", title)
    title = re.sub(r"_片段对照报告$", "", title)
    title = re.sub(r"_比对报告$", "", title)
    title = re.sub(r"_格式分析报告$", "", title)
    title = re.sub(r"_简洁报告$", "", title)
    title = re.sub(r"_综合报告$", "", title)
    title = re.sub(r"_存档报告$", "", title)
    title = re.sub(r"\s+", " ", title)
    return title.strip()


def summarize_platform(platform_dir: Path) -> dict[str, Any]:
    files = [item for item in platform_dir.rglob("*") if item.is_file()]
    extension_counts = Counter(item.suffix.lower() for item in files)
    role_counts: Counter[str] = Counter()
    title_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    archive_patterns: Counter[str] = Counter()

    for file_path in files:
        archive_entries = read_zip_entries(file_path) if file_path.suffix.lower() == ".zip" else []
        role = classify_role(file_path, archive_entries)
        role_counts[role] += 1

        if archive_entries:
            archive_signature = {
                "has_original_compare": any("原文对照报告" in name for name in archive_entries),
                "has_segment_html": any("片段对照报告" in name for name in archive_entries),
                "has_compare_html": any("比对报告" in name for name in archive_entries),
                "has_simple_pdf": any("简洁报告" in name for name in archive_entries),
                "has_txt": any(name.lower().endswith(".txt") for name in archive_entries),
                "entry_count": len(archive_entries),
            }
            archive_patterns.update([json.dumps(archive_signature, ensure_ascii=False, sort_keys=True)])

        title_groups[normalize_group_title(file_path.name)].append(
            {
                "name": file_path.name,
                "relative_path": str(file_path.relative_to(platform_dir)),
                "role": role,
            }
        )

    duplicated_groups = []
    for title, group_items in title_groups.items():
        if len(group_items) <= 1:
            continue
        duplicated_groups.append(
            {
                "title": title,
                "count": len(group_items),
                "items": sorted(group_items, key=lambda item: item["name"]),
            }
        )
    duplicated_groups.sort(key=lambda item: (-item["count"], item["title"]))

    archive_pattern_rows = []
    for encoded_signature, count in archive_patterns.most_common():
        archive_pattern_rows.append(
            {
                "count": count,
                "signature": json.loads(encoded_signature),
            }
        )

    return {
        "path": str(platform_dir),
        "file_count": len(files),
        "extension_counts": dict(sorted(extension_counts.items())),
        "role_counts": {role: role_counts.get(role, 0) for role in ROLE_LABELS},
        "duplicate_title_groups": duplicated_groups,
        "archive_patterns": archive_pattern_rows,
    }


def build_inventory(root: Path) -> dict[str, Any]:
    platforms = {}
    for item in sorted([node for node in root.iterdir() if node.is_dir()], key=lambda node: node.name):
        key = PLATFORM_NAME_MAP.get(item.name, item.name)
        platforms[key] = summarize_platform(item)
    return {
        "workspace_root": str(root),
        "platforms": platforms,
    }


def to_markdown(inventory: dict[str, Any]) -> str:
    lines = [
        "# Algorithm Training Workspace Inventory",
        "",
        f"- Workspace root: `{inventory['workspace_root']}`",
        "",
    ]
    for platform, data in inventory["platforms"].items():
        lines.append(f"## {platform}")
        lines.append("")
        lines.append(f"- File count: `{data['file_count']}`")
        ext_summary = ", ".join(f"`{key}`={value}" for key, value in data["extension_counts"].items()) or "none"
        lines.append(f"- Extension counts: {ext_summary}")
        role_summary = ", ".join(f"`{key}`={value}" for key, value in data["role_counts"].items())
        lines.append(f"- Role counts: {role_summary}")
        lines.append("")

        if data["archive_patterns"]:
            lines.append("### Archive Patterns")
            lines.append("")
            for row in data["archive_patterns"][:5]:
                signature = row["signature"]
                lines.append(
                    "- "
                    + f"`count={row['count']}` "
                    + f"original_compare={signature['has_original_compare']}, "
                    + f"segment_html={signature['has_segment_html']}, "
                    + f"compare_html={signature['has_compare_html']}, "
                    + f"simple_pdf={signature['has_simple_pdf']}, "
                    + f"txt={signature['has_txt']}, "
                    + f"entry_count={signature['entry_count']}"
                )
            lines.append("")

        if data["duplicate_title_groups"]:
            lines.append("### Multi-Version Title Groups")
            lines.append("")
            for group in data["duplicate_title_groups"][:10]:
                lines.append(f"- `{group['title']}` x `{group['count']}`")
                for item in group["items"][:6]:
                    lines.append(f"  - `{item['name']}` [{item['role']}]")
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"Workspace root not found: {root}")

    inventory = build_inventory(root)
    output = json.dumps(inventory, ensure_ascii=False, indent=2)
    print(output)

    if args.output_json:
        json_path = Path(args.output_json).expanduser().resolve()
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(output, encoding="utf-8")

    if args.output_md:
        md_path = Path(args.output_md).expanduser().resolve()
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(to_markdown(inventory), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
