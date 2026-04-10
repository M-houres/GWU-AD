from contextlib import contextmanager
import io
import json
from io import BytesIO
from pathlib import Path
import zipfile

from docx import Document
from sqlalchemy.orm import Session

from app import worker_tasks
from app.config import get_settings
from app.deps import current_user
from app.main import app
from app.models import CreditTransaction, CreditType, SystemConfig, Task, TaskStatus, User
from app.services.algo_package_service import install_algorithm_package


def _make_docx_bytes(paragraphs: list[str]) -> BytesIO:
    doc = Document()
    for paragraph in paragraphs:
        doc.add_paragraph(paragraph)
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


def _build_package_zip(*, platform: str, function_type: str, name: str) -> bytes:
    manifest = {
        "name": name,
        "version": "1.0.0",
        "platform": platform,
        "function_type": function_type,
        "entry": "main.py",
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
        zf.writestr(
            "main.py",
            "def process(text):\n"
            "    value = str(text)\n"
            "    if value.strip().startswith('{'):\n"
            "        return {'text': value}\n"
            "    return {'text': value}\n",
        )
    return buf.getvalue()


def _activate_slot(db_session: Session, *, platform: str, function_type: str) -> None:
    install_algorithm_package(
        db_session,
        file_bytes=_build_package_zip(
            platform=platform,
            function_type=function_type,
            name=f"{platform}_{function_type}_engine",
        ),
        platform=platform,
        function_type=function_type,
        uploaded_by=1,
        activate_after_upload=True,
    )
    db_session.commit()


def test_user_can_submit_and_finish_all_three_task_flows(
    client,
    db_session: Session,
    monkeypatch,
    settings_override,
) -> None:
    settings = get_settings()
    old_free_limit = settings.aigc_daily_free_limit
    settings.aigc_daily_free_limit = 0

    user = User(phone="13800006688", nickname="full-flow-user", credits=20000)
    db_session.add(user)
    db_session.add(
        SystemConfig(
            category="system",
            config_key="billing",
            config_value={"aigc_rate": 1, "dedup_rate": 2, "rewrite_rate": 2},
        )
    )
    db_session.commit()
    db_session.refresh(user)

    for function_type in ("aigc_detect", "dedup", "rewrite"):
        _activate_slot(db_session, platform="cnki", function_type=function_type)

    monkeypatch.setattr("app.worker_tasks.dispatch_background_task", lambda *_args, **_kwargs: "test-noop")
    app.dependency_overrides[current_user] = lambda: user
    try:
        aigc_resp = client.post(
            "/api/v1/tasks/submit",
            data={
                "task_type": "aigc_detect",
                "platform": "cnki",
                "paper_title": "AIGC检测链路测试",
                "authors": "测试作者",
            },
            files={
                "paper": (
                    "aigc.txt",
                    BytesIO(
                        (
                            "本研究围绕课堂教学评价展开分析，研究表明相关路径具备稳定执行特征。"
                            "此外，文本中包含统一总结句与模板化连接词，用于验证检测链路。"
                        ).encode("utf-8")
                    ),
                    "text/plain",
                )
            },
        )
        assert aigc_resp.status_code == 200
        aigc_task_id = aigc_resp.json()["data"]["id"]

        dedup_resp = client.post(
            "/api/v1/tasks/submit",
            data={
                "task_type": "dedup",
                "platform": "cnki",
                "paper_title": "降重复率链路测试",
                "authors": "测试作者",
            },
            files={
                "paper": (
                    "dedup.docx",
                    _make_docx_bytes(
                        [
                            "本研究对企业营销措施现状进行研究，并从客户体验、渠道组合和服务质量方面进行分析。",
                            "文章用于验证降重复率任务从提交、扣费到处理完成的完整链路。",
                        ]
                    ),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        assert dedup_resp.status_code == 200
        dedup_task_id = dedup_resp.json()["data"]["id"]

        rewrite_resp = client.post(
            "/api/v1/tasks/submit",
            data={
                "task_type": "rewrite",
                "platform": "cnki",
                "paper_title": "降AIGC链路测试",
                "authors": "测试作者",
            },
            files={
                "paper": (
                    "rewrite.docx",
                    _make_docx_bytes(
                        [
                            "研究表明，这一教学方案具有较强参考价值，而且很多类似研究都采用了接近的表达方式。",
                            "本文用于验证降AIGC任务在上传正文和辅助报告后能够顺利完成处理。",
                        ]
                    ),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
                "report": (
                    "rewrite_report.docx",
                    _make_docx_bytes(
                        [
                            "全文AIGC检测报告",
                            "总体风险 52%",
                            "高风险段落 2 段",
                            "AIGC 检测结果仅供改写参考。",
                        ]
                    ),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
            },
        )
        assert rewrite_resp.status_code == 200
        rewrite_task_id = rewrite_resp.json()["data"]["id"]
    finally:
        app.dependency_overrides.pop(current_user, None)
        settings.aigc_daily_free_limit = old_free_limit

    total_cost = 0
    for payload in (aigc_resp.json()["data"], dedup_resp.json()["data"], rewrite_resp.json()["data"]):
        assert payload["cost_credits"] > 0
        total_cost += payload["cost_credits"]

    @contextmanager
    def _db_session_override():
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    monkeypatch.setattr(worker_tasks, "db_session", _db_session_override)

    for task_id in (aigc_task_id, dedup_task_id, rewrite_task_id):
        result = worker_tasks.process_task_async(task_id)
        assert result["ok"] is True

    db_session.refresh(user)
    assert user.credits == 20000 - total_cost

    tasks = (
        db_session.query(Task)
        .filter(Task.id.in_([aigc_task_id, dedup_task_id, rewrite_task_id]))
        .order_by(Task.id.asc())
        .all()
    )
    assert len(tasks) == 3
    assert all(task.status == TaskStatus.COMPLETED for task in tasks)
    assert all(task.output_path and Path(task.output_path).exists() for task in tasks)

    task_by_type = {task.task_type.value: task for task in tasks}
    assert task_by_type["aigc_detect"].result_json["type"] == "aigc_detect"
    assert task_by_type["dedup"].result_json["type"] == "dedup"
    assert task_by_type["rewrite"].result_json["type"] == "rewrite"

    for task in tasks:
        tx = (
            db_session.query(CreditTransaction)
            .filter(
                CreditTransaction.user_id == user.id,
                CreditTransaction.tx_type == CreditType.TASK_CONSUME,
                CreditTransaction.related_id == f"task:{task.id}",
            )
            .first()
        )
        assert tx is not None
        assert tx.delta == -task.cost_credits
        assert task.result_json["paper_title"]
        assert task.result_json["authors"]

    app.dependency_overrides[current_user] = lambda: user
    try:
        for task in tasks:
            download_resp = client.get(f"/api/v1/tasks/{task.id}/download")
            assert download_resp.status_code == 200
            assert len(download_resp.content) > 0
    finally:
        app.dependency_overrides.pop(current_user, None)
