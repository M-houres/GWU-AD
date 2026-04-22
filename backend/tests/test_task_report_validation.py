from pathlib import Path

import pytest

from app.api.tasks import _validate_report_content as validate_task_report_content
from app.exceptions import BizError
from app.models import TaskType
from app.worker_tasks import _validate_report_content as validate_worker_report_content


def test_task_report_validation_keeps_dedup_error_code(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "report.docx"
    path.write_text("这不是完整报告", encoding="utf-8")
    monkeypatch.setattr("app.services.task_report_validation.extract_text_from_file", lambda _path: "简短摘要")

    with pytest.raises(BizError) as exc:
        validate_task_report_content(TaskType.DEDUP, path)

    assert exc.value.code == 4114
    assert "请上传全文查重报告" in str(exc.value.message)


def test_task_report_validation_keeps_rewrite_error_code(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "report.docx"
    path.write_text("这不是完整报告", encoding="utf-8")
    monkeypatch.setattr("app.services.task_report_validation.extract_text_from_file", lambda _path: "简短摘要")

    with pytest.raises(BizError) as exc:
        validate_task_report_content(TaskType.REWRITE, path)

    assert exc.value.code == 4115
    assert "请上传全文AIGC检测报告" in str(exc.value.message)


def test_worker_report_validation_keeps_value_error_message(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "report.docx"
    path.write_text("这不是完整报告", encoding="utf-8")
    monkeypatch.setattr("app.services.task_report_validation.extract_text_from_file", lambda _path: "简短摘要")

    with pytest.raises(ValueError, match="请上传全文AIGC检测报告"):
        validate_worker_report_content(TaskType.REWRITE, path)


def test_report_validation_accepts_full_report(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "report.docx"
    path.write_text("完整报告", encoding="utf-8")
    monkeypatch.setattr(
        "app.services.task_report_validation.extract_text_from_file",
        lambda _path: "全文 检测报告 总体风险 高风险段落",
    )

    validate_task_report_content(TaskType.REWRITE, path)
    validate_worker_report_content(TaskType.REWRITE, path)
