from app.models import Task, TaskStatus, TaskType, User
from app.services.task_response_builder import (
    build_detail_payload,
    build_list_item,
    build_recover_payload,
    build_submit_payload,
)


def test_task_response_builder_preserves_public_task_fields(db_session) -> None:
    user = User(phone="13800008881", nickname="payload-user", credits=3210)
    db_session.add(user)
    db_session.flush()

    task = Task(
        user_id=user.id,
        task_type=TaskType.AIGC_DETECT,
        platform="cnki",
        source="web",
        status=TaskStatus.COMPLETED,
        source_filename="paper.docx",
        source_path="/tmp/source.docx",
        report_path="/tmp/report.pdf",
        output_path="/tmp/output.pdf",
        char_count=1234,
        cost_credits=567,
        refund_done=True,
        result_json={
            "billing": {"points_per_char": 0.5, "cost_fen": 567, "cost_points": 567},
            "score_breakdown": {"llm_score": 0.9, "base_score": 0.2},
        },
        error_message="done",
    )
    db_session.add(task)
    db_session.commit()

    submit_payload = build_submit_payload(
        db_session,
        task=task,
        strategy={"timeout_sec": 180},
        idempotent=True,
        dispatch_mode="local",
    )
    list_item = build_list_item(task)
    detail_payload = build_detail_payload(task)
    recover_payload = build_recover_payload(task)

    assert submit_payload["id"] == task.id
    assert submit_payload["has_report"] is True
    assert submit_payload["balance_after"] == 3210
    assert submit_payload["balance_after_fen"] == 3210
    assert submit_payload["idempotent"] is True
    assert submit_payload["dispatch_mode"] == "local"
    assert submit_payload["estimated_time"] == 180
    assert submit_payload["billing"]["cost_fen"] == 567
    assert "llm_score" not in submit_payload["result_json"]["score_breakdown"]

    assert list_item["cost_fen"] == 567
    assert list_item["cost_points"] == 567
    assert list_item["refund_done"] is True
    assert "download_ready" not in list_item

    assert detail_payload["download_ready"] is True
    assert detail_payload["source_filename"] == "paper.docx"

    assert recover_payload["id"] == task.id
    assert recover_payload["task_type"] == "aigc_detect"
    assert recover_payload["cost_fen"] == 567
    assert "result_json" not in recover_payload
