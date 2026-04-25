import logging
from pathlib import Path
import uuid

from fastapi import UploadFile

from app.config import get_settings
from app.constants import MAX_FILE_SIZE_MB
from app.exceptions import BizError
from app.utils import safe_filename

logger = logging.getLogger("app.services.task_artifacts")
settings = get_settings()
UPLOAD_PREFIX = "uploads"
OUTPUT_PREFIX = "output"


def save_upload_to(path: Path, upload: UploadFile, max_bytes: int) -> None:
    total = 0
    chunk_size = 1024 * 1024
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        while True:
            chunk = upload.file.read(chunk_size)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise BizError(code=4103, message=f"文件超过{MAX_FILE_SIZE_MB}MB限制")
            f.write(chunk)
    if total <= 0:
        raise BizError(code=4102, message="上传文件为空")


def build_storage_name(name: str, fallback_name: str) -> tuple[str, str]:
    original_name = safe_filename(name or fallback_name)
    unique_name = f"{uuid.uuid4().hex[:12]}_{original_name}"
    return original_name, unique_name


def remove_uploads(*paths: Path | None) -> None:
    for path in paths:
        if path is None:
            continue
        try:
            path.unlink(missing_ok=True)
        except Exception:
            logger.warning("uploaded_file_cleanup_failed", exc_info=True, extra={"path": str(path)})


def _normalize_artifact_string(raw_path: str | Path | None) -> str:
    return str(raw_path or "").strip().replace("\\", "/")


def _split_artifact_relative_path(normalized: str, prefix: str) -> str | None:
    target = f"/{prefix}/"
    lowered = normalized.lower()
    direct = f"{prefix}/"
    if lowered.startswith(direct):
        return normalized[len(direct) :].lstrip("/")
    idx = lowered.find(target)
    if idx >= 0:
        return normalized[idx + len(target) :].lstrip("/")
    return None


def serialize_task_artifact_path(path: Path | None) -> str | None:
    if path is None:
        return None
    if settings.app_env == "test":
        return str(path)
    try:
        resolved = path.resolve()
    except Exception:
        resolved = path
    roots = (
        (UPLOAD_PREFIX, settings.upload_dir),
        (OUTPUT_PREFIX, settings.output_dir),
    )
    for prefix, root in roots:
        try:
            root_resolved = root.resolve()
            if resolved == root_resolved or root_resolved in resolved.parents:
                relative = resolved.relative_to(root_resolved).as_posix().lstrip("/")
                return f"{prefix}/{relative}" if relative else prefix
        except Exception:
            continue
    normalized = _normalize_artifact_string(path)
    for prefix in (UPLOAD_PREFIX, OUTPUT_PREFIX):
        relative = _split_artifact_relative_path(normalized, prefix)
        if relative is not None:
            return f"{prefix}/{relative}" if relative else prefix
    return normalized or None


def resolve_task_artifact_path(raw_path: str | Path | None) -> Path | None:
    normalized = _normalize_artifact_string(raw_path)
    if not normalized:
        return None
    path = Path(normalized)
    if path.is_absolute() and path.exists():
        return path
    roots = (
        (UPLOAD_PREFIX, settings.upload_dir),
        (OUTPUT_PREFIX, settings.output_dir),
    )
    for prefix, root in roots:
        relative = _split_artifact_relative_path(normalized, prefix)
        if relative is None:
            continue
        if not relative:
            return root
        return root / Path(relative)
    return path


def safe_remove_task_artifact(raw_path: str | None, *, warn_on_untrusted: bool = True) -> None:
    path = resolve_task_artifact_path(raw_path)
    if path is None:
        return
    try:
        path = path.resolve()
        allowed_roots = [settings.upload_dir.resolve(), settings.output_dir.resolve()]
        if not any(path == root or root in path.parents for root in allowed_roots):
            if warn_on_untrusted:
                logger.warning("skip_untrusted_task_artifact_delete", extra={"path": str(raw_path)})
            return
        path.unlink(missing_ok=True)
    except Exception:
        logger.warning("task_artifact_delete_failed", exc_info=True, extra={"path": raw_path})
