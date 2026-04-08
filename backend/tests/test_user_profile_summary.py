from io import BytesIO

from app.deps import current_user
from app.main import app
from app.models import CreditType, Task, TaskStatus, TaskType, User
from app.services.algo_package_service import install_algorithm_package
from app.services.credit_service import change_credits


def _build_package_zip(*, platform: str, function_type: str) -> bytes:
    import io
    import json
    import zipfile

    manifest = {
        "name": f"{function_type}_engine",
        "version": "1.0.0",
        "platform": platform,
        "function_type": function_type,
        "entry": "main.py",
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
        zf.writestr("main.py", "def process(text):\n    return {'text': str(text)}\n")
    return buf.getvalue()


def _activate_slot(db_session, *, platform: str, function_type: str) -> None:
    install_algorithm_package(
        db_session,
        file_bytes=_build_package_zip(platform=platform, function_type=function_type),
        platform=platform,
        function_type=function_type,
        uploaded_by=1,
        activate_after_upload=True,
    )
    db_session.commit()


def test_aigc_daily_free_quota_applies_to_first_six_submissions(
    client,
    db_session,
    monkeypatch,
    settings_override,
) -> None:
    user = User(phone="13800006661", nickname="quota-user", credits=100)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    _activate_slot(db_session, platform="cnki", function_type="aigc_detect")

    monkeypatch.setattr("app.worker_tasks.process_task_async.delay", lambda *_args, **_kwargs: None)
    app.dependency_overrides[current_user] = lambda: user
    try:
        for index in range(1, 8):
            resp = client.post(
                "/api/v1/tasks/submit",
                data={"task_type": "aigc_detect", "platform": "cnki"},
                files={"paper": (f"sample_{index}.txt", BytesIO(b"abcdefghij"), "text/plain")},
            )
            assert resp.status_code == 200
            payload = resp.json()["data"]
            if index <= 6:
                assert payload["cost_credits"] == 0
                assert payload["billing"]["free_applied"] is True
            else:
                assert payload["cost_credits"] == 10
                assert payload["billing"]["free_applied"] is False

        db_session.refresh(user)
        assert user.credits == 90
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_user_profile_summary_returns_real_counts(client, db_session) -> None:
    user = User(phone="13800006662", nickname="summary-user", credits=0)
    db_session.add(user)
    db_session.flush()

    change_credits(
        db_session,
        user,
        tx_type=CreditType.INIT,
        delta=5000,
        reason="初始积分",
        related_id=f"user_init:{user.id}",
        source="web",
    )
    change_credits(
        db_session,
        user,
        tx_type=CreditType.TASK_CONSUME,
        delta=-120,
        reason="任务消费",
        related_id="task:1001",
        source="web",
    )
    db_session.add_all(
        [
            Task(
                user_id=user.id,
                task_type=TaskType.AIGC_DETECT,
                platform="cnki",
                status=TaskStatus.COMPLETED,
                source_filename="paper-a.txt",
                source_path="/tmp/paper-a.txt",
                char_count=120,
                cost_credits=0,
                result_json={"paper_title": "A 文稿", "authors": "张三"},
            ),
            Task(
                user_id=user.id,
                task_type=TaskType.DEDUP,
                platform="vip",
                status=TaskStatus.PENDING,
                source_filename="paper-b.docx",
                source_path="/tmp/paper-b.docx",
                char_count=240,
                cost_credits=120,
                result_json={"paper_title": "B 文稿", "authors": "李四"},
            ),
        ]
    )
    db_session.commit()
    db_session.refresh(user)

    app.dependency_overrides[current_user] = lambda: user
    try:
        resp = client.get("/api/v1/users/me/summary")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["task_counts"]["total"] == 2
        assert data["task_counts"]["by_type"]["aigc_detect"] == 1
        assert data["task_counts"]["by_type"]["dedup"] == 1
        assert data["task_counts"]["by_status"]["completed"] == 1
        assert data["task_counts"]["by_status"]["pending"] == 1
        assert data["credit_overview"]["income_total"] == 5000
        assert data["credit_overview"]["outcome_total"] == 120
        assert data["aigc_quota"]["daily_free_limit"] == 6
        assert data["aigc_quota"]["submitted_today"] == 1
        assert len(data["recent_tasks"]) == 2
        assert len(data["recent_transactions"]) == 2
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_update_me_allows_clearing_nickname(client, db_session) -> None:
    user = User(phone="13800006663", nickname="will-clear", credits=100)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    app.dependency_overrides[current_user] = lambda: user
    try:
        resp = client.patch("/api/v1/users/me", json={"nickname": "   "})
        assert resp.status_code == 200
        db_session.refresh(user)
        assert user.nickname == ""
        assert resp.json()["data"]["nickname"] == ""
    finally:
        app.dependency_overrides.pop(current_user, None)
