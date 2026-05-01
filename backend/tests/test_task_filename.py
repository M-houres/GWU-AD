from app.models import TaskType
from app.services.task_filename import build_task_result_filename


def test_rewrite_doc_source_outputs_docx() -> None:
    assert build_task_result_filename(TaskType.REWRITE, "论文终稿.doc") == "改写+论文终稿.docx"


def test_dedup_doc_source_outputs_docx() -> None:
    assert build_task_result_filename(TaskType.DEDUP, "论文终稿.doc") == "改写+论文终稿.docx"


def test_rewrite_txt_source_keeps_txt() -> None:
    assert build_task_result_filename(TaskType.REWRITE, "pasted_text.txt") == "改写+pasted_text.txt"


def test_aigc_detect_always_uses_pdf_even_if_output_path_has_wrong_docx_ext() -> None:
    assert (
        build_task_result_filename(
            TaskType.AIGC_DETECT,
            "论文终稿.docx",
            "C:/tmp/论文终稿_AIGC检测报告.docx",
        )
        == "论文终稿_AIGC检测报告.pdf"
    )
