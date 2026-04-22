from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from fastapi import UploadFile

from app.services import task_artifacts
from app.services.task_artifacts import build_storage_name, safe_remove_task_artifact, save_upload_to


def test_build_storage_name_keeps_original_and_adds_unique_prefix() -> None:
    original_name, unique_name = build_storage_name("sample.docx", "fallback.docx")

    assert original_name == "sample.docx"
    assert unique_name.endswith("_sample.docx")
    assert unique_name != original_name


def test_save_upload_to_rejects_empty_upload(tmp_path: Path) -> None:
    path = tmp_path / "empty.docx"
    upload = UploadFile(file=BytesIO(b""), filename="empty.docx")

    try:
        try:
            save_upload_to(path, upload, 1024)
            assert False, "expected BizError"
        except Exception as exc:
            assert getattr(exc, "code", None) == 4102
    finally:
        upload.file.close()


def test_safe_remove_task_artifact_only_deletes_inside_allowed_roots(tmp_path: Path, monkeypatch) -> None:
    allowed_upload = tmp_path / "uploads"
    allowed_output = tmp_path / "output"
    outside_root = tmp_path / "outside"
    monkeypatch.setattr(
        task_artifacts,
        "settings",
        SimpleNamespace(upload_dir=allowed_upload, output_dir=allowed_output),
    )

    inside_file = allowed_upload / "1" / "source.docx"
    outside_file = outside_root / "source.docx"
    inside_file.parent.mkdir(parents=True, exist_ok=True)
    outside_file.parent.mkdir(parents=True, exist_ok=True)
    inside_file.write_text("inside", encoding="utf-8")
    outside_file.write_text("outside", encoding="utf-8")

    safe_remove_task_artifact(str(inside_file))
    safe_remove_task_artifact(str(outside_file))

    assert not inside_file.exists()
    assert outside_file.exists()
