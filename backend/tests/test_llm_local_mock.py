import json

import httpx
import pytest
from sqlalchemy.orm import Session

from app.exceptions import BizError
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


def _enable_remote_mock_provider(db_session: Session) -> None:
    db_session.add(
        SystemConfig(
            category="system",
            config_key="llm",
            config_value={
                "enabled": True,
                "provider": "openai",
                "model": "gpt-4o-mini",
                "api_key": "test-key",
                "base_url": "https://llm.example.com/v1",
                "timeout_seconds": 5,
                "retry_attempts": 3,
                "retry_backoff_seconds": 0.1,
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


def test_generate_with_llm_retries_retryable_errors(db_session: Session, monkeypatch) -> None:
    _enable_remote_mock_provider(db_session)

    class DummyClient:
        def __init__(self) -> None:
            self.calls = 0

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json=None, headers=None, params=None):  # noqa: A002
            self.calls += 1
            request = httpx.Request("POST", url)
            if self.calls < 3:
                raise httpx.ReadError("temporary upstream failure", request=request)
            return httpx.Response(
                200,
                request=request,
                json={"choices": [{"message": {"content": "rewritten content"}}]},
            )

    dummy = DummyClient()
    monkeypatch.setattr("app.services.llm_service.httpx.Client", lambda *args, **kwargs: dummy)
    monkeypatch.setattr("app.services.llm_service.time.sleep", lambda *_args, **_kwargs: None)

    output = generate_with_llm(
        db_session,
        task_type=TaskType.REWRITE,
        text="这是用于验证重试逻辑的一段文本。",
    )

    assert output == "rewritten content"
    assert dummy.calls == 3


def test_generate_with_llm_hides_provider_error_detail(db_session: Session, monkeypatch) -> None:
    _enable_remote_mock_provider(db_session)

    class FailingClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json=None, headers=None, params=None):  # noqa: A002
            request = httpx.Request("POST", url)
            response = httpx.Response(503, request=request, text="provider exploded: secret stack")
            raise httpx.HTTPStatusError("provider exploded: secret stack", request=request, response=response)

    monkeypatch.setattr("app.services.llm_service.httpx.Client", lambda *args, **kwargs: FailingClient())
    monkeypatch.setattr("app.services.llm_service.time.sleep", lambda *_args, **_kwargs: None)

    with pytest.raises(BizError) as exc_info:
        generate_with_llm(
            db_session,
            task_type=TaskType.REWRITE,
            text="这是用于验证错误脱敏的一段文本。",
        )

    assert exc_info.value.code == 4604
    assert "provider exploded" not in exc_info.value.message
    assert "暂时不可用" in exc_info.value.message
