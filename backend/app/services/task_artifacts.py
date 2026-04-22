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


def safe_remove_task_artifact(raw_path: str | None, *, warn_on_untrusted: bool = True) -> None:
    if not raw_path:
        return
    try:
        path = Path(raw_path).resolve()
        allowed_roots = [settings.upload_dir.resolve(), settings.output_dir.resolve()]
        if not any(path == root or root in path.parents for root in allowed_roots):
            if warn_on_untrusted:
                logger.warning("skip_untrusted_task_artifact_delete", extra={"path": str(path)})
            return
        path.unlink(missing_ok=True)
    except Exception:
        logger.warning("task_artifact_delete_failed", exc_info=True, extra={"path": raw_path})
