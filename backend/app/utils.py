import random
import re
import string
from pathlib import Path
import zipfile

from docx import Document
from pypdf import PdfReader

def make_order_no() -> str:
    prefix = "OD"
    rand = "".join(random.choices(string.digits, k=12))
    return f"{prefix}{rand}"


def gen_code() -> str:
    return "".join(random.choices(string.digits, k=6))


def is_phone_valid(phone: str) -> bool:
    return bool(re.fullmatch(r"1\d{10}", phone))


def safe_filename(name: str) -> str:
    allow = set(string.ascii_letters + string.digits + "._-")
    return "".join(ch if ch in allow else "_" for ch in name)


_DOCX_REQUIRED_MEMBERS = {"[Content_Types].xml", "word/document.xml"}


def detect_file_magic(path: Path) -> str:
    with path.open("rb") as f:
        head = f.read(16)
    if head.startswith(b"%PDF-"):
        with path.open("rb") as f:
            try:
                f.seek(-2048, 2)
            except OSError:
                f.seek(0)
            tail = f.read()
        return ".pdf" if b"%%EOF" in tail else ""
    if head.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(path, "r") as zf:
                members = {name for name in zf.namelist() if name and not name.endswith("/")}
        except zipfile.BadZipFile:
            return ""
        return ".docx" if _DOCX_REQUIRED_MEMBERS.issubset(members) else ""
    try:
        raw = path.read_bytes()
        if not raw.strip():
            return ""
        if b"\x00" in raw[:4096]:
            return ""
        raw.decode("utf-8")
        return ".txt"
    except Exception:
        return ""
    return ""


def extract_text_from_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".docx":
        doc = Document(str(path))
        parts: list[str] = [p.text for p in doc.paragraphs if p.text]
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    text = cell.text.strip()
                    if text:
                        parts.append(text)
        return "\n".join(parts)
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        parts: list[str] = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        return "\n".join(parts)
    raise ValueError("unsupported file type")


def count_billable_chars(text: str) -> int:
    filtered = [ch for ch in text if ch.isalnum() or ("\u4e00" <= ch <= "\u9fff")]
    return len(filtered)
