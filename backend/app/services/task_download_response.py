from __future__ import annotations

from pathlib import Path


_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain; charset=utf-8",
}


def build_download_media_type(path: str | Path | None) -> str | None:
    suffix = Path(str(path or "")).suffix.lower()
    return _MEDIA_TYPES.get(suffix)
