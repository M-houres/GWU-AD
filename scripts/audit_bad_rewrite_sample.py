from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from docx import Document


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.rewrite_strategies.assets import COMMON_BAD_PATTERNS, CNKI_BAD_PATTERNS


DEFAULT_BAD_SAMPLE_PATH = Path(r"C:\Users\m\Desktop\rewrite_result_113.docx")
OUTPUT_DIR = REPO_ROOT / "docs"
MECHANICAL_PREFIXES = ("同时，", "此外，", "进一步看，", "在此基础上，", "由此可见，")


@dataclass(frozen=True)
class FlaggedParagraph:
    index: int
    bad_pattern_hits: tuple[str, ...]
    prefix_hits: int
    preview: str


def audit_bad_rewrite_doc(path: Path = DEFAULT_BAD_SAMPLE_PATH) -> tuple[FlaggedParagraph, ...]:
    if not path.exists():
        return ()
    doc = Document(path)
    rows: list[FlaggedParagraph] = []
    patterns = [*COMMON_BAD_PATTERNS, *CNKI_BAD_PATTERNS]
    for index, paragraph in enumerate(doc.paragraphs, 1):
        text = " ".join(paragraph.text.split()).strip()
        if not text:
            continue
        hits: list[str] = []
        for item in patterns:
            if item.regex:
                if re.search(item.pattern, text):
                    hits.append(item.pattern)
            elif item.pattern in text:
                hits.append(item.pattern)
        prefix_hits = sum(text.count(prefix) for prefix in MECHANICAL_PREFIXES)
        if not hits and prefix_hits < 2:
            continue
        rows.append(
            FlaggedParagraph(
                index=index,
                bad_pattern_hits=tuple(dict.fromkeys(hits)),
                prefix_hits=prefix_hits,
                preview=text[:220],
            )
        )
    return tuple(rows)


def render_audit_report(path: Path = DEFAULT_BAD_SAMPLE_PATH) -> str:
    rows = audit_bad_rewrite_doc(path)
    lines = [
        "# 已知坏样本审计",
        "",
        f"更新日期：{date.today().isoformat()}",
        "",
        f"- 样本路径：`{path}`",
        f"- 是否存在：`{path.exists()}`",
        f"- 命中段落数：`{len(rows)}`",
        "",
        "## 1. 命中段落",
        "",
    ]
    if not rows:
        lines.append("- 未发现可审计的命中段落。")
    for row in rows:
        lines.append(f"### 1.{row.index}")
        lines.append(f"- 段落序号：`{row.index}`")
        lines.append(f"- 坏模式命中：`{','.join(row.bad_pattern_hits) or 'none'}`")
        lines.append(f"- 机械连接词次数：`{row.prefix_hits}`")
        lines.append(f"- 预览：`{row.preview}`")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    report = render_audit_report()
    output_path = OUTPUT_DIR / f"BAD_REWRITE_AUDIT_{date.today().isoformat()}.md"
    output_path.write_text(report, encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
