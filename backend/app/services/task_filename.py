from pathlib import Path

from app.models import TaskType


_TASK_FILENAME_SUFFIX = {
    TaskType.REWRITE.value: "降AIGC率结果",
    TaskType.DEDUP.value: "降重复率结果",
    TaskType.AIGC_DETECT.value: "AIGC检测报告",
}


def _normalize_task_type(task_type: TaskType | str | None) -> str:
    if isinstance(task_type, TaskType):
        return task_type.value
    return str(task_type or "").strip().lower()


def _normalize_source_stem(source_filename: str | None) -> str:
    stem = Path(str(source_filename or "").strip()).stem.strip()
    return stem or "任务结果"


def _resolve_output_ext(task_type: str, source_filename: str | None, output_path: str | Path | None) -> str:
    if task_type == TaskType.AIGC_DETECT.value:
        return ".pdf"
    if output_path:
        ext = Path(str(output_path)).suffix.lower()
        if ext:
            return ext
    source_ext = Path(str(source_filename or "")).suffix.lower()
    if task_type in {TaskType.REWRITE.value, TaskType.DEDUP.value} and source_ext == ".doc":
        return ".docx"
    if source_ext:
        return source_ext
    return ".docx"


def build_task_result_filename(
    task_type: TaskType | str | None,
    source_filename: str | None,
    output_path: str | Path | None = None,
) -> str:
    normalized_task_type = _normalize_task_type(task_type)
    source_stem = _normalize_source_stem(source_filename)
    ext = _resolve_output_ext(normalized_task_type, source_filename, output_path)
    if normalized_task_type in {TaskType.REWRITE.value, TaskType.DEDUP.value}:
        return f"改写+{source_stem}{ext}"
    suffix = _TASK_FILENAME_SUFFIX.get(normalized_task_type, "处理结果")
    return f"{source_stem}_{suffix}{ext}"


def build_task_filename_pair(
    source_filename: str | None,
    result_filename: str | None,
) -> str:
    source = str(source_filename or "").strip() or "-"
    result = str(result_filename or "").strip() or "-"
    return f"{source} + {result}"
