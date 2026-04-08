import importlib.util
import io
import json
import zipfile
from pathlib import Path

from app.services.algo_package_service import run_package_smoke_test


PACKAGE_DIR = Path(__file__).resolve().parents[1] / "custom_algo_packages" / "cnki_rewrite_sampled_v1"


def _build_package_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in ("manifest.json", "main.py", "README.md"):
            zf.writestr(name, (PACKAGE_DIR / name).read_text(encoding="utf-8"))
    return buf.getvalue()


def _load_module():
    spec = importlib.util.spec_from_file_location("cnki_rewrite_sampled_v1", PACKAGE_DIR / "main.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_cnki_rewrite_sample_package_smoke_passes():
    package_bytes = _build_package_bytes()

    manifest = json.loads((PACKAGE_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["platform"] == "cnki"
    assert manifest["function_type"] == "rewrite"

    smoke = run_package_smoke_test(package_bytes)
    assert smoke["status"] == "passed"


def test_cnki_rewrite_sample_package_rewrites_cnki_style_text():
    module = _load_module()
    sample = (
        "案例一（四年级·小数的认识·中等发展型）：AI诊断显示，该组学生需要构建系统性的评价体系，"
        "并从课程设计、资源开发三个维度推进课堂优化。"
    )

    result = module.process({"text": sample})

    assert "通过AI诊断可以看出" in result["text"]
    assert "评价框架" in result["text"]
    assert "从课程设计、资源开发这三个维度" in result["text"]
    assert result["rewritten_aigc_score"] <= result["original_aigc_score"]
    assert result["transformation_count"] > 0
    assert result["algorithm"] == "cnki_rewrite_sampled_v1"
