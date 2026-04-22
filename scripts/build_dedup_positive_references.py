from __future__ import annotations

import html
import io
import json
import re
import sys
import zipfile
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from pypdf import PdfReader


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.exceptions import BizError
from app.services.dedup_strategies.validators import validate_dedup_output


STRATEGY_ASSET_DIR = REPO_ROOT / "data" / "strategy_assets"
OUTPUT_PATH = STRATEGY_ASSET_DIR / "dedup_positive_references_v1.jsonl"

CNKI_REPORT_DIR = Path(r"C:\Users\m\Desktop\算法报告\知网降重复率")
VIP_REPORT_DIR = Path(r"C:\Users\m\Desktop\算法报告\维普降重复率")

MIN_EXCERPT_LEN = 72
MAX_EXCERPT_LEN = 320
PER_SOURCE_LIMIT = 2
DISCIPLINE_PRIORITY = {
    "engineering_it_patent": 0,
    "finance_management": 1,
    "medicine_public_health": 2,
    "law_policy": 3,
    "humanities_social_science": 4,
    "education": 5,
}
NOISE_PATTERNS = (
    "知网个人查重服务",
    "官方网址",
    "报告编号",
    "检测时间",
    "检测结果",
    "相似文献列表",
    "总文字复制比",
    "全文总相似比",
    "总相似片段",
    "颜色标注说明",
    "原文对照报告",
    "格式分析报告",
    "比对报告",
    "片段对照报告",
    "简洁报告",
    "高频词",
    "检测结论",
    "目录",
    "参考文献",
    "致谢",
    "pageNum",
    "catalogueItem",
)
BAD_FRAGMENT_PATTERNS = (
    "要要",
    "了了",
    "进行进行",
    "各个自",
    "摘要I",
    "AbstractII",
)


@dataclass(frozen=True)
class ReportReference:
    platform: str
    title: str
    source_path: Path
    source_kind: str
    discipline: str
    excerpt: str
    notes: str


def infer_discipline(text: str) -> str:
    content = str(text or "")
    if any(token in content for token in ("小学", "幼儿", "课堂", "绘本", "诗歌教学", "语文", "英语", "心理健康教育")):
        return "education"
    if any(token in content for token in ("护理", "患者", "肺癌", "中药", "抗生素", "压疮", "神经重症")):
        return "medicine_public_health"
    if any(token in content for token in ("行政", "服务中心", "治理", "法", "监督", "路径探析")):
        return "law_policy"
    if any(token in content for token in ("财务", "营运资金", "餐饮公司", "应收账款", "薪酬", "存货", "短视频APP")):
        return "finance_management"
    if any(token in content for token in ("SSM", "WEB", "BIM", "建筑工程", "施工进度", "管理系统", "液化石油气", "技术")):
        return "engineering_it_patent"
    if any(token in content for token in ("苏轼", "黄州诗文", "古代小说", "社会风貌", "人物形象", "人生意识")):
        return "humanities_social_science"
    return "education"


def cnki_title(path: Path) -> str:
    title = path.stem
    title = re.sub(r"^查重_全文\(标明引文\)报告单_", "", title)
    return title.strip(". ")


def vip_title(path: Path) -> str:
    return re.sub(r"\s*\(\d+\)$", "", path.stem).replace("+", "").strip()


def read_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def read_pdf_text_from_zip(path: Path) -> tuple[str, str]:
    with zipfile.ZipFile(path) as archive:
        candidates = [name for name in archive.namelist() if name.endswith("原文对照报告.pdf")]
        if not candidates:
            raise FileNotFoundError(f"{path.name} missing 原文对照报告.pdf")
        member = candidates[0]
        payload = io.BytesIO(archive.read(member))
    reader = PdfReader(payload)
    return member, "\n".join((page.extract_text() or "") for page in reader.pages)


def read_html_text_from_zip(path: Path) -> tuple[str, str]:
    with zipfile.ZipFile(path) as archive:
        candidates = [name for name in archive.namelist() if name.endswith("比对报告.html")]
        if not candidates:
            raise FileNotFoundError(f"{path.name} missing 比对报告.html")
        member = candidates[0]
        payload = archive.read(member).decode("utf-8", errors="ignore")

    payload = re.sub(r"<style\b[^>]*>.*?</style>", "", payload, flags=re.S | re.I)
    payload = re.sub(r"<script\b[^>]*>.*?</script>", "", payload, flags=re.S | re.I)
    payload = re.sub(r"<br\s*/?>", "\n", payload, flags=re.I)
    payload = re.sub(r"</(div|p|li|tr|h\d)>", "\n", payload, flags=re.I)
    payload = re.sub(r"<[^>]+>", "", payload)
    payload = html.unescape(payload)
    payload = re.sub(r"\n{2,}", "\n", payload)
    return member, payload


def trim_cnki_text(text: str) -> str:
    content = str(text or "")
    if "原文内容" in content:
        content = content.split("原文内容", 1)[1]
    return content


def trim_vip_text(text: str) -> str:
    content = str(text or "")
    start = last_marker_index(content, markers=("摘 要", "摘  要", "摘要"), within=6000)
    if start < 0:
        start = first_marker_index(content, markers=("引言", "一、 引言", "一、引言"), within=8000)
    if start >= 0:
        content = content[start:]
    for marker in ("Abstract", "ABSTRACT", "目录", "参考文献", "致谢"):
        index = content.find(marker, 40)
        if index >= 0:
            content = content[:index]
            break
    return content


def first_marker_index(text: str, *, markers: tuple[str, ...], within: int) -> int:
    positions = [index for marker in markers for index in [text.find(marker)] if 0 <= index <= within]
    return min(positions) if positions else -1


def last_marker_index(text: str, *, markers: tuple[str, ...], within: int) -> int:
    positions: list[int] = []
    for marker in markers:
        start = 0
        while True:
            index = text.find(marker, start)
            if index < 0 or index > within:
                break
            positions.append(index)
            start = index + len(marker)
    return max(positions) if positions else -1


def normalize_line(line: str) -> str:
    text = str(line or "").replace("\u3000", " ").strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    return text.strip(" -")


def extract_paragraphs(text: str, *, platform: str) -> list[str]:
    lines = [normalize_line(line) for line in str(text or "").splitlines()]
    lines = [line for line in lines if line and not is_noise_line(line)]
    paragraphs: list[str] = []
    buffer = ""

    for line in lines:
        if looks_like_heading(line):
            if is_valid_excerpt(buffer, platform=platform):
                paragraphs.append(clean_excerpt(buffer))
            buffer = line
            continue

        if not buffer:
            buffer = line
        else:
            joiner = "" if should_tight_join(buffer, line) else " "
            buffer = f"{buffer}{joiner}{line}".strip()

        if should_flush(buffer, line):
            if is_valid_excerpt(buffer, platform=platform):
                paragraphs.append(clean_excerpt(buffer))
            buffer = ""

    if is_valid_excerpt(buffer, platform=platform):
        paragraphs.append(clean_excerpt(buffer))
    return deduplicate_paragraphs(paragraphs)


def looks_like_heading(line: str) -> bool:
    text = str(line or "").strip()
    if not text:
        return False
    if len(text) <= 24 and re.match(r"^(摘\s*要|摘要|关键词|目\s*录|引言|结语|总结)$", text):
        return True
    if len(text) <= 28 and re.match(r"^[一二三四五六七八九十]+[、.．]", text):
        return True
    if len(text) <= 28 and re.match(r"^（[一二三四五六七八九十]+）", text):
        return True
    return False


def should_tight_join(current: str, new_line: str) -> bool:
    if not current:
        return True
    if current.endswith(("：", "，", "、", "（", "(")):
        return True
    if new_line.startswith(("）", ")", "，", "。", "；", "：")):
        return True
    return True


def should_flush(buffer: str, last_line: str) -> bool:
    content = str(buffer or "").strip()
    tail = str(last_line or "").strip()
    if len(content) >= MAX_EXCERPT_LEN:
        return True
    if len(content) >= MIN_EXCERPT_LEN and tail.endswith(("。", "！", "？", "；")):
        return True
    return False


def is_noise_line(line: str) -> bool:
    text = str(line or "").strip()
    if not text:
        return True
    if text in {"1", "2", "3", "4", "5", "6", "7", "8", "9"}:
        return True
    if re.fullmatch(r"-\s*\d+\s*-", text):
        return True
    if re.search(r"^\d+\s*/\s*\d+$", text):
        return True
    if any(pattern in text for pattern in NOISE_PATTERNS):
        return True
    if re.search(r"(检测字符数|复写率|自写率|相似片段|典型相似文章|学生姓名|指导教师|专业名称|学生学号)", text):
        return True
    if re.search(r"(图\d+|表\d+)", text) and len(text) <= 36:
        return True
    if re.search(r"(篇目|册次|核心意象|培养指向|教师行为|学生任务|AI介入方式)", text):
        return True
    if re.search(r"[A-Za-z]{8,}", text) and len(text) <= 30:
        return True
    return False


def clean_excerpt(text: str) -> str:
    content = str(text or "").strip()
    content = re.sub(r"\s+", " ", content)
    content = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", content)
    content = re.sub(r"[。]{2,}", "。", content)
    content = re.sub(r"[，]{2,}", "，", content)
    content = re.sub(r"^[^。！？\n]{0,80}?摘要[:：]?", "摘要：", content)
    content = re.sub(r"^引言(?![:：])", "引言：", content)
    return content.strip()


def is_valid_excerpt(text: str, *, platform: str) -> bool:
    content = clean_excerpt(text)
    if not content:
        return False
    if len(content) < MIN_EXCERPT_LEN or len(content) > MAX_EXCERPT_LEN:
        return False
    if any(pattern in content for pattern in BAD_FRAGMENT_PATTERNS):
        return False
    if any(pattern in content for pattern in NOISE_PATTERNS):
        return False
    if re.search(r"(摘\s*要 I|Abstract II|篇目册次核心意象|目录摘 要)", content):
        return False
    if content.count("？") + content.count("?") >= 2:
        return False
    if content.count("。") + content.count("！") + content.count("？") <= 0 and len(content) < 120:
        return False
    if has_repeated_half(content):
        return False

    chinese_chars = re.findall(r"[\u4e00-\u9fff]", content)
    if len(chinese_chars) < 48:
        return False
    if len(chinese_chars) / max(len(content), 1) < 0.55:
        return False

    digit_count = len(re.findall(r"\d", content))
    if digit_count > max(12, len(content) // 7):
        return False

    try:
        validation = validate_dedup_output(
            platform=platform,
            source_text=content,
            rewritten_text=content,
            rule_trace={"mode": "reference_filter"},
        )
    except BizError:
        return False
    if not validation.quality_flags.get("basic_legality_ok", True):
        return False
    if not validation.quality_flags.get("structure_natural_ok", True):
        return False
    return True


def has_repeated_half(text: str) -> bool:
    content = str(text or "").strip()
    midpoint = len(content) // 2
    if midpoint < 60:
        return False
    left = re.sub(r"\W+", "", content[:midpoint])
    right = re.sub(r"\W+", "", content[midpoint:])
    if min(len(left), len(right)) < 48:
        return False
    return SequenceMatcher(None, left, right).ratio() >= 0.72


def deduplicate_paragraphs(paragraphs: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for paragraph in paragraphs:
        normalized = re.sub(r"\W+", "", paragraph)
        if len(normalized) < 36 or normalized in seen:
            continue
        seen.add(normalized)
        output.append(paragraph)
    return output


def target_slots(platform: str) -> list[str]:
    normalized = str(platform or "").strip().lower()
    return [f"{normalized}.dedup.algorithm", f"{normalized}.dedup.llm"]


def build_cnki_references() -> list[ReportReference]:
    output: list[ReportReference] = []
    for path in sorted(CNKI_REPORT_DIR.glob("*.pdf")):
        title = cnki_title(path)
        content = trim_cnki_text(read_pdf_text(path))
        excerpts = extract_paragraphs(content, platform="cnki")[:PER_SOURCE_LIMIT]
        for index, excerpt in enumerate(excerpts, 1):
            output.append(
                ReportReference(
                    platform="cnki",
                    title=title,
                    source_path=path,
                    source_kind="cnki_dedup_report_pdf",
                    discipline=infer_discipline(title),
                    excerpt=excerpt,
                    notes=f"extracted_from=cnki_pdf#{index}",
                )
            )
    return output


def build_vip_references() -> list[ReportReference]:
    output: list[ReportReference] = []
    for path in sorted(VIP_REPORT_DIR.glob("*.zip")):
        title = vip_title(path)
        try:
            member_name, raw_text = read_html_text_from_zip(path)
            source_kind = "vip_dedup_report_html"
        except Exception:
            try:
                member_name, raw_text = read_pdf_text_from_zip(path)
                source_kind = "vip_dedup_report_pdf"
            except Exception:
                continue
        content = trim_vip_text(raw_text)
        excerpts = extract_paragraphs(content, platform="vip")[:PER_SOURCE_LIMIT]
        for index, excerpt in enumerate(excerpts, 1):
            output.append(
                ReportReference(
                    platform="vip",
                    title=title,
                    source_path=path,
                    source_kind=source_kind,
                    discipline=infer_discipline(title),
                    excerpt=excerpt,
                    notes=f"extracted_from={member_name}#{index}",
                )
            )
    return output


def to_asset_row(reference: ReportReference, *, index: int) -> dict:
    return {
        "sample_id": f"{reference.platform}_dedup_ref_{index:03d}",
        "status": "active",
        "platform": reference.platform,
        "scenario": "dedup",
        "discipline": reference.discipline,
        "mode_scope": ["algorithm", "llm"],
        "target_slots": target_slots(reference.platform),
        "source_kind": reference.source_kind,
        "title": reference.title,
        "source_path": str(reference.source_path),
        "excerpt": reference.excerpt,
        "notes": reference.notes,
    }


def ordered_references() -> list[ReportReference]:
    rows = [*build_cnki_references(), *build_vip_references()]
    return sorted(
        rows,
        key=lambda item: (
            item.platform,
            DISCIPLINE_PRIORITY.get(item.discipline, 99),
            -excerpt_rank(item.excerpt),
            abs(len(item.excerpt) - 160),
            item.title,
        ),
    )


def excerpt_rank(text: str) -> int:
    content = str(text or "").strip()
    score = 0
    if content.startswith("摘要："):
        score += 6
    elif content.startswith("引言："):
        score += 5
    elif re.match(r"^（[一二三四五六七八九十]+）", content):
        score += 3
    elif re.match(r"^[一二三四五六七八九十]+[、.．]", content):
        score += 2
    if content.endswith(("。", "！", "？")):
        score += 1
    if content.count("。") >= 2:
        score += 1
    if re.match(r"^[\u4e00-\u9fff]", content):
        score += 1
    if "摘要：" not in content and "引言：" not in content and content[:1] in {"本", "该", "其", "而", "但"}:
        score += 1
    return score


def main() -> None:
    references = ordered_references()
    rows = [to_asset_row(reference, index=index) for index, reference in enumerate(references, 1)]
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"{OUTPUT_PATH.name}\t{len(rows)}")


if __name__ == "__main__":
    main()
