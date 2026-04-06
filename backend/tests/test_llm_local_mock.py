import json

from sqlalchemy.orm import Session

from app.models import SystemConfig, TaskType
from app.services.llm_service import generate_with_llm


def _enable_local_mock(db_session: Session) -> None:
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


def test_local_mock_llm_rewrite_and_detect(db_session: Session) -> None:
    _enable_local_mock(db_session)

    source = "首先，这是一段用于本地大模型链路测试的学术文本。其次，我们需要验证改写和检测都能返回结果。"
    rewritten = generate_with_llm(db_session, task_type=TaskType.REWRITE, text=source)
    assert isinstance(rewritten, str)
    assert rewritten.strip()
    assert rewritten != source

    detect_raw = generate_with_llm(db_session, task_type=TaskType.AIGC_DETECT, text=source)
    payload = json.loads(detect_raw)
    assert isinstance(payload, dict)
    assert 0 <= float(payload["ai_score"]) <= 1
    assert payload["label"] in {"low", "medium", "high"}
    assert isinstance(payload.get("reason"), str)
