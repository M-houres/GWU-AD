from contextlib import contextmanager
from io import BytesIO
from pathlib import Path

from docx import Document
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session

from app import worker_tasks
from app.deps import current_user
from app.exceptions import BizError
from app.main import app
from app.models import SystemConfig, Task, TaskStatus, TaskType, User
from app.services.process_strategy_service import get_process_strategy, resolve_task_processing_mode


def _make_docx_bytes(text: str) -> BytesIO:
    doc = Document()
    doc.add_paragraph(text)
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

def test_admin_strategies_list_default_six_cells(
    client: TestClient,
    admin_override,
) -> None:
    resp = client.get("/api/v1/admin/strategies")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0

    data = body["data"]
    items = data["items"]
    assert len(items) == 6
    assert set(data["platforms"]) == {"cnki", "vip"}
    assert set(data["task_types"]) == {"aigc_detect", "dedup", "rewrite"}

    for row in items:
        if row["platform"] in {"cnki", "vip"} and row["task_type"] in {"rewrite", "dedup"}:
            assert row["process_mode"] == "algo_llm"
        else:
            assert row["process_mode"] == "algo_only"
        assert row["is_enabled"] is True
        assert row["timeout_sec"] == 300


def test_admin_enable_rewrite_strategy_without_active_package(
    client: TestClient,
    admin_override,
) -> None:
    resp = client.put(
        "/api/v1/admin/strategies/rewrite/cnki",
        json={"is_enabled": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["is_enabled"] is True


def test_admin_enable_aigc_strategy_without_active_package(
    client: TestClient,
    admin_override,
) -> None:
    resp = client.put(
        "/api/v1/admin/strategies/aigc_detect/cnki",
        json={"is_enabled": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["is_enabled"] is True


def test_admin_enable_aigc_strategy_without_package_activation_for_cnki(
    client: TestClient,
    admin_override,
) -> None:
    resp = client.put(
        "/api/v1/admin/strategies/aigc_detect/cnki",
        json={
            "is_enabled": True,
            "process_mode": "algo_llm",
            "timeout_sec": 600,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["process_mode"] == "algo_llm"
    assert body["data"]["is_enabled"] is True
    assert body["data"]["timeout_sec"] == 600


def test_admin_algo_config_table_has_no_package_version_fields(
    client: TestClient,
    admin_override,
) -> None:
    resp = client.get("/api/v1/admin/algo-config/table")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0

    row = next(item for item in body["data"]["items"] if item["platform"] == "cnki" and item["task_type"] == "aigc_detect")
    assert "active_package" not in row
    assert "latest_package" not in row
    assert "current_version" not in row
    assert "latest_version" not in row


def test_submit_and_process_rewrite_task_with_algo_llm_strategy(
    client: TestClient,
    db_session: Session,
    monkeypatch,
    admin_override,
    settings_override,
) -> None:
    user = User(phone="13800008883", nickname="algo-llm-user", credits=10000)
    db_session.add(user)
    db_session.flush()

    db_session.add(
        SystemConfig(
            category="system",
            config_key="llm",
            config_value={
                "enabled": True,
                "provider": "local_mock",
                "model": "local-mock-v1",
                "api_key": "",
                "base_url": "",
                "timeout_seconds": 20,
            },
            updated_by=1,
        )
    )
    db_session.commit()

    strategy_resp = client.put(
        "/api/v1/admin/strategies/rewrite/cnki",
        json={"is_enabled": True, "process_mode": "algo_llm", "timeout_sec": 600},
    )
    assert strategy_resp.status_code == 200
    assert strategy_resp.json()["data"]["process_mode"] == "algo_llm"

    monkeypatch.setattr("app.worker_tasks.dispatch_background_task", lambda *_args, **_kwargs: "test-inline")
    monkeypatch.setattr(
        "app.services.processing_engine.execute_rewrite_strategy",
        lambda *_args, **_kwargs: {
            "rewritten_text": (
                "This paragraph validates the combined pipeline where the rewrite task runs the "
                "internal strategy first and then the local mock LLM, while retaining the task metadata."
            ),
            "strategy": "llm",
            "platform": "cnki",
            "task_type": TaskType.REWRITE.value,
            "length_before": 110,
            "length_after": 117,
            "change_ratio": 0.0636,
            "quality_flags": {
                "length_ok": True,
                "protected_content_ok": True,
                "basic_legality_ok": True,
            },
            "warnings": [],
            "rule_trace": {"provider": "stubbed-llm"},
        },
    )
    app.dependency_overrides[current_user] = lambda: user
    try:
        submit_resp = client.post(
            "/api/v1/tasks/submit",
            data={
                "task_type": "rewrite",
                "platform": "cnki",
                "paper_title": "Algo LLM Rewrite Test",
                "authors": "Tester",
            },
            files={
                "paper": (
                    "sample.docx",
                    _make_docx_bytes(
                        "This paragraph validates the combined pipeline where the rewrite task "
                        "runs the internal strategy first and then the local mock LLM."
                    ),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        assert submit_resp.status_code == 200
        task_id = submit_resp.json()["data"]["id"]
    finally:
        app.dependency_overrides.pop(current_user, None)

    task = db_session.get(Task, task_id)
    assert task is not None
    assert task.status == TaskStatus.PENDING
    assert task.processing_mode == "LLM_PLUS_ALGO"

    @contextmanager
    def _db_session_override():
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    monkeypatch.setattr(worker_tasks, "db_session", _db_session_override)

    result = worker_tasks.process_task_async(task_id)
    assert result["ok"] is True

    db_session.refresh(task)
    assert task.status == TaskStatus.COMPLETED
    assert task.processing_mode == "LLM_PLUS_ALGO"
    assert task.output_path is not None
    assert Path(task.output_path).exists()
    assert isinstance(task.result_json, dict)
    assert task.result_json["type"] == "rewrite"
    assert task.result_json["mode"] == "LLM_PLUS_ALGO"
    assert task.result_json["llm_used"] is True
    assert "algo_package_used" not in task.result_json
    assert task.result_json["paper_title"] == "Algo LLM Rewrite Test"
    assert task.result_json["authors"] == "Tester"
    assert task.result_json["rewrite_strategy"]["strategy"] == "llm"
    assert task.result_json["rewrite_strategy"]["quality_flags"]["length_ok"] is True


def test_task_submit_auto_bootstraps_builtin_package_when_slot_missing(
    client: TestClient,
    db_session: Session,
    monkeypatch,
    settings_override,
) -> None:
    user = User(phone="13800008881", nickname="strategy-user", credits=10000)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    monkeypatch.setattr("app.worker_tasks.process_task_async.delay", lambda *_args, **_kwargs: None)
    app.dependency_overrides[current_user] = lambda: user
    try:
        file_bytes = _make_docx_bytes("abcdefghij")
        resp = client.post(
            "/api/v1/tasks/submit",
            data={"task_type": "dedup", "platform": "cnki"},
            files={"paper": ("sample.docx", file_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        task = db_session.get(Task, body["data"]["id"])
        assert task is not None
        assert task.processing_mode == "LLM_PLUS_ALGO"
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_user_task_result_keeps_visible_pipeline_summary_and_hides_internal_breakdown(
    client: TestClient,
    db_session: Session,
) -> None:
    user = User(phone="13800008882", nickname="hide-mode-user", credits=10000)
    db_session.add(user)
    db_session.flush()

    task = Task(
        user_id=user.id,
        task_type=TaskType.AIGC_DETECT,
        platform="cnki",
        processing_mode="LLM_PLUS_ALGO",
        source="web",
        status=TaskStatus.COMPLETED,
        source_filename="paper.docx",
        source_path="/tmp/paper.docx",
        output_path="/tmp/out.pdf",
        char_count=10,
        cost_credits=10,
        result_json={
            "ai_score": 0.3,
            "mode": "LLM_PLUS_ALGO",
            "llm_used": True,
            "score_breakdown": {
                "base_score": 0.2,
                "llm_score": 0.6,
                "algo_package_score": 0.4,
                "pipeline_mode": "llm_plus_algo",
            },
        },
    )
    db_session.add(task)
    db_session.commit()

    app.dependency_overrides[current_user] = lambda: user
    try:
        list_resp = client.get("/api/v1/tasks/my")
        assert list_resp.status_code == 200
        list_item = list_resp.json()["data"]["items"][0]
        result = list_item["result_json"]
        assert result["mode"] == "LLM_PLUS_ALGO"
        assert "processing_mode" not in result
        assert result["llm_used"] is True
        assert "algo_package_used" not in result
        assert "llm_score" not in result.get("score_breakdown", {})
        assert "algo_package_score" not in result.get("score_breakdown", {})
        assert "pipeline_mode" not in result.get("score_breakdown", {})

        detail_resp = client.get(f"/api/v1/tasks/{task.id}")
        assert detail_resp.status_code == 200
        detail_result = detail_resp.json()["data"]["result_json"]
        assert detail_result["mode"] == "LLM_PLUS_ALGO"
        assert detail_result["llm_used"] is True
        assert "algo_package_used" not in detail_result
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_strategy_string_false_is_parsed_as_disabled(db_session: Session) -> None:
    db_session.add(
        SystemConfig(
            category="process_strategies_v1",
            config_key="rewrite:cnki",
            config_value={"process_mode": "algo_only", "is_enabled": "false", "timeout_sec": 300},
            updated_by=1,
        )
    )
    db_session.commit()

    strategy = get_process_strategy(db_session, task_type=TaskType.REWRITE, platform="cnki")
    assert strategy["is_enabled"] is False
    assert strategy["process_mode"] == "algo_llm"


def test_admin_cnki_rewrite_strategy_cannot_be_set_back_to_algo_only(
    client: TestClient,
    admin_override,
) -> None:
    resp = client.put(
        "/api/v1/admin/strategies/rewrite/cnki",
        json={"is_enabled": True, "process_mode": "algo_only", "timeout_sec": 600},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["process_mode"] == "algo_llm"


def test_admin_cnki_dedup_strategy_cannot_be_set_back_to_algo_only(
    client: TestClient,
    admin_override,
) -> None:
    resp = client.put(
        "/api/v1/admin/strategies/dedup/cnki",
        json={"is_enabled": True, "process_mode": "algo_only", "timeout_sec": 600},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["process_mode"] == "algo_llm"


def test_admin_algo_config_table_returns_platforms_and_execution_rows(
    client: TestClient,
    admin_override,
) -> None:
    resp = client.get("/api/v1/admin/algo-config/table")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert len(data["platforms"]) == 2
    assert {item["key"] for item in data["platforms"]} == {"cnki", "vip"}
    assert len(data["items"]) == 6


def test_admin_can_create_platform_and_generate_default_execution_rows(
    client: TestClient,
    admin_override,
) -> None:
    resp = client.post(
        "/api/v1/admin/algo-config/platforms",
        json={
            "key": "wanfang",
            "label": "万方",
            "aigc_label": "模拟万方",
            "enabled": True,
            "sort_order": 3,
            "task_types": ["aigc_detect", "dedup", "rewrite"],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["key"] == "wanfang"

    table_resp = client.get("/api/v1/admin/algo-config/table")
    assert table_resp.status_code == 200
    data = table_resp.json()["data"]
    assert any(item["key"] == "wanfang" for item in data["platforms"])
    wanfang_rows = [item for item in data["items"] if item["platform"] == "wanfang"]
    assert len(wanfang_rows) == 3
    assert {item["task_type"] for item in wanfang_rows} == {"aigc_detect", "dedup", "rewrite"}


def test_cnki_rewrite_strategy_is_reset_pending(db_session: Session) -> None:
    strategy = get_process_strategy(db_session, task_type=TaskType.REWRITE, platform="cnki")

    assert strategy["is_enabled"] is True
    assert strategy["process_mode"] == "algo_llm"
    assert not strategy.get("blocked_reason")


def test_vip_dedup_strategy_is_enabled_with_w4_runtime(db_session: Session) -> None:
    strategy = get_process_strategy(db_session, task_type=TaskType.DEDUP, platform="vip")
    mode, resolved = resolve_task_processing_mode(db_session, task_type=TaskType.DEDUP, platform="vip")

    assert strategy["is_enabled"] is True
    assert strategy["process_mode"] == "algo_llm"
    assert not strategy.get("blocked_reason")
    assert mode == "LLM_PLUS_ALGO"
    assert resolved["process_mode"] == "algo_llm"
