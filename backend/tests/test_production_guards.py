import pytest
import redis
from fastapi import HTTPException

from app import deps
from app import main
from app import worker_tasks


def test_prod_secret_guard_rejects_all_weak_runtime_defaults(monkeypatch) -> None:
    settings = main.settings
    original = {
        "app_env": settings.app_env,
        "jwt_secret": settings.jwt_secret,
        "admin_init_password": settings.admin_init_password,
        "payment_test_mode": settings.payment_test_mode,
        "payment_sign_secret": settings.payment_sign_secret,
        "db_fallback_sqlite": settings.db_fallback_sqlite,
        "celery_local_fallback_enabled": settings.celery_local_fallback_enabled,
        "mysql_password": settings.mysql_password,
        "cors_allow_origins": settings.cors_allow_origins,
    }
    monkeypatch.setattr(settings, "app_env", "prod")
    monkeypatch.setattr(settings, "jwt_secret", "change_me_in_prod")
    monkeypatch.setattr(settings, "admin_init_password", "admin123456")
    monkeypatch.setattr(settings, "payment_test_mode", True)
    monkeypatch.setattr(settings, "payment_sign_secret", "change_me_payment_sign_key")
    monkeypatch.setattr(settings, "db_fallback_sqlite", True)
    monkeypatch.setattr(settings, "celery_local_fallback_enabled", True)
    monkeypatch.setattr(settings, "mysql_password", "root")
    monkeypatch.setattr(settings, "cors_allow_origins", "*")

    with pytest.raises(RuntimeError) as exc_info:
        main.assert_production_secrets()

    message = str(exc_info.value)
    for item in (
        "JWT_SECRET",
        "ADMIN_INIT_PASSWORD",
        "PAYMENT_TEST_MODE",
        "PAYMENT_SIGN_SECRET",
        "DB_FALLBACK_SQLITE",
        "CELERY_LOCAL_FALLBACK_ENABLED",
        "MYSQL_PASSWORD",
        "CORS_ALLOW_ORIGINS",
    ):
        assert item in message

    for key, value in original.items():
        monkeypatch.setattr(settings, key, value)


def test_prod_secret_guard_accepts_hardened_runtime_config(monkeypatch) -> None:
    settings = main.settings
    monkeypatch.setattr(settings, "app_env", "prod")
    monkeypatch.setattr(settings, "jwt_secret", "prod_jwt_secret_value")
    monkeypatch.setattr(settings, "admin_init_password", "prod_admin_password_value")
    monkeypatch.setattr(settings, "payment_test_mode", False)
    monkeypatch.setattr(settings, "payment_sign_secret", "prod_payment_sign_secret")
    monkeypatch.setattr(settings, "db_fallback_sqlite", False)
    monkeypatch.setattr(settings, "celery_local_fallback_enabled", False)
    monkeypatch.setattr(settings, "mysql_password", "prod_mysql_password")
    monkeypatch.setattr(settings, "cors_allow_origins", "https://example.com")

    main.assert_production_secrets()


def test_get_redis_rejects_memory_fallback_in_prod(monkeypatch) -> None:
    settings = deps.settings
    monkeypatch.setattr(settings, "app_env", "prod")

    def _raise_ping():
        raise redis.RedisError("down")

    monkeypatch.setattr(deps.redis_client, "ping", _raise_ping)

    with pytest.raises(HTTPException) as exc_info:
        deps.get_redis()

    assert exc_info.value.status_code == 503


def test_dispatch_background_task_rejects_local_fallback_in_prod(monkeypatch) -> None:
    monkeypatch.setattr(worker_tasks.settings, "app_env", "prod")
    monkeypatch.setattr(worker_tasks.settings, "celery_local_fallback_enabled", True)
    monkeypatch.setattr(worker_tasks, "_celery_broker_available", lambda: False)

    def _dummy_task():
        return None

    with pytest.raises(RuntimeError) as exc_info:
        worker_tasks.dispatch_background_task(_dummy_task)

    assert "celery broker unavailable" in str(exc_info.value)
