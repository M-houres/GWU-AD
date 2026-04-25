from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from fastapi import UploadFile

from app.services import task_artifacts
from app.services.task_artifacts import (
    build_storage_name,
    resolve_task_artifact_path,
    safe_remove_task_artifact,
    save_upload_to,
    serialize_task_artifact_path,
)


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


def test_serialize_and_resolve_task_artifact_path_supports_relative_storage(tmp_path: Path, monkeypatch) -> None:
    upload_root = tmp_path / "uploads"
    output_root = tmp_path / "output"
    monkeypatch.setattr(
        task_artifacts,
        "settings",
        SimpleNamespace(upload_dir=upload_root, output_dir=output_root, app_env="prod"),
    )

    source_file = upload_root / "2" / "sample.docx"
    output_file = output_root / "2" / "task_9_result.docx"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("source", encoding="utf-8")
    output_file.write_text("output", encoding="utf-8")

    serialized_source = serialize_task_artifact_path(source_file)
    serialized_output = serialize_task_artifact_path(output_file)

    assert serialized_source == "uploads/2/sample.docx"
    assert serialized_output == "output/2/task_9_result.docx"
    assert resolve_task_artifact_path(serialized_source) == source_file
    assert resolve_task_artifact_path(serialized_output) == output_file
