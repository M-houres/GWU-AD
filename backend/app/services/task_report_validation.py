from pathlib import Path

from app.models import TaskType
from app.utils import extract_text_from_file

REPORT_ERROR_DEDUP = "请上传全文查重报告"
REPORT_ERROR_REWRITE = "请上传全文AIGC检测报告"


def report_is_full(task_type: TaskType, text: str) -> bool:
    content = " ".join((text or "").split()).lower()
    if not content:
        return False
    if task_type == TaskType.DEDUP:
        markers = [
            "全文",
            "总文字复制比",
            "去除引用复制比",
            "去除本人已发表文献复制比",
            "检测报告",
            "全文标明引文",
        ]
        return sum(1 for marker in markers if marker in content) >= 2
    if task_type == TaskType.REWRITE:
        markers = [
            "aigc",
            "ai生成",
            "疑似ai",
            "检测报告",
            "全文",
            "总体风险",
            "高风险段落",
        ]
        return sum(1 for marker in markers if marker in content) >= 2
    return False


def validate_full_report_content(task_type: TaskType, path: Path) -> str | None:
    if task_type not in {TaskType.DEDUP, TaskType.REWRITE}:
        return None
    report_text = extract_text_from_file(path)
    if report_is_full(task_type, report_text):
        return None
    if task_type == TaskType.DEDUP:
        return REPORT_ERROR_DEDUP
    return REPORT_ERROR_REWRITE
