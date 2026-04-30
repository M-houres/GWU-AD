from app.models import TaskType
from app.services.task_filename import build_task_result_filename


def test_rewrite_doc_source_outputs_docx() -> None:
    assert build_task_result_filename(TaskType.REWRITE, "论文终稿.doc") == "改写+论文终稿.docx"


def test_dedup_doc_source_outputs_docx() -> None:
    assert build_task_result_filename(TaskType.DEDUP, "论文终稿.doc") == "改写+论文终稿.docx"


def test_rewrite_txt_source_keeps_txt() -> None:
    assert build_task_result_filename(TaskType.REWRITE, "pasted_text.txt") == "改写+pasted_text.txt"
