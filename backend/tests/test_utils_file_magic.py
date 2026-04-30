from app.utils import detect_file_magic


def test_detect_file_magic_returns_doc_for_legacy_ole_file(tmp_path) -> None:
    path = tmp_path / "legacy.doc"
    path.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64)
    assert detect_file_magic(path) == ".doc"
