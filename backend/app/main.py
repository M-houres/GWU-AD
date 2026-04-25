from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import json
import logging
from pathlib import Path
import time
import traceback
import uuid

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError

from app.api.router import api_router
from app.config import get_settings
from app.database import Base, engine
from app.deps import redis_is_available
from app.exceptions import BizError
from app.logging_setup import clear_log_context, set_log_context, setup_logging
from app.models import AdminUser, RegistrationRiskLog, Task, TaskStatus, User
from app.responses import fail, ok
from app.security import hash_password
from app.services.task_artifacts import resolve_task_artifact_path

settings = get_settings()
setup_logging(level=getattr(logging, str(settings.log_level or "INFO").upper(), logging.INFO))
logger = logging.getLogger("app.main")


def _cors_origins() -> list[str]:
    origins = settings.cors_allow_origin_list
    if settings.is_prod and (not origins or origins == ["*"]):
        raise RuntimeError("生产环境必须显式配置 CORS_ALLOW_ORIGINS，不能使用通配符")
    if origins == ["*"]:
        if settings.is_prod:
            raise RuntimeError("生产环境必须显式配置 CORS_ALLOW_ORIGINS，不能使用通配符")
        origins = []
    if origins:
        return origins
    defaults = {
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
        "http://127.0.0.1:8080",
        "http://localhost:8080",
    }
    if settings.frontend_base_url:
        parsed = settings.frontend_base_url.split("/api/", 1)[0].rstrip("/")
        if parsed:
            defaults.add(parsed)
    return sorted(defaults)


def _is_weak_secret(value: str, defaults: set[str]) -> bool:
    normalized = str(value or "").strip()
    return (not normalized) or normalized in defaults


def assert_production_secrets() -> None:
    if not settings.is_prod:
        return
    weak_items = []
    if _is_weak_secret(settings.jwt_secret, {"change_me_in_prod"}):
        weak_items.append("JWT_SECRET")
    if _is_weak_secret(settings.admin_init_password, {"admin123456"}):
        weak_items.append("ADMIN_INIT_PASSWORD")
    if settings.payment_test_mode:
        weak_items.append("PAYMENT_TEST_MODE")
    if _is_weak_secret(settings.payment_sign_secret, {"change_me_payment_sign_key"}):
        weak_items.append("PAYMENT_SIGN_SECRET")
    if settings.db_fallback_sqlite:
        weak_items.append("DB_FALLBACK_SQLITE")
    if settings.celery_local_fallback_enabled:
        weak_items.append("CELERY_LOCAL_FALLBACK_ENABLED")
    if settings.mysql_password.strip() == "root":
        weak_items.append("MYSQL_PASSWORD")
    if settings.cors_allow_origin_list == ["*"]:
        weak_items.append("CORS_ALLOW_ORIGINS")
    if weak_items:
        joined = ", ".join(weak_items)
        raise RuntimeError(f"生产环境存在危险默认配置: {joined}")


def run_runtime_bootstrap_tasks() -> None:
    run_migrations()
    repair_missing_tables()
    normalize_runtime_configs()
    normalize_user_phone_storage()
    cleanup_expired_task_artifacts()
    init_super_admin()


@asynccontextmanager
async def app_lifespan(_: FastAPI):
    assert_production_secrets()
    if not settings.is_prod and settings.app_env != "test":
        run_runtime_bootstrap_tasks()
    logger.info("startup_completed", extra={"app_env": settings.app_env})
    yield


app = FastAPI(title=settings.app_name, lifespan=app_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(BizError)
async def biz_error_handler(request: Request, exc: BizError) -> JSONResponse:
    response = JSONResponse(status_code=exc.http_status, content=fail(exc.code, exc.message).model_dump())
    request_id = str(getattr(getattr(request, "state", object()), "request_id", "") or "").strip()
    if request_id:
        response.headers["x-request-id"] = request_id
    return response


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    response = JSONResponse(
        status_code=422,
        content=fail(1001, "参数校验失败", data={"errors": exc.errors()}).model_dump(),
    )
    request_id = str(getattr(getattr(request, "state", object()), "request_id", "") or "").strip()
    if request_id:
        response.headers["x-request-id"] = request_id
    return response


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    code = exc.status_code
    msg = exc.detail if isinstance(exc.detail, str) else "请求失败"
    response = JSONResponse(status_code=exc.status_code, content=fail(code, msg).model_dump())
    request_id = str(getattr(getattr(request, "state", object()), "request_id", "") or "").strip()
    if request_id:
        response.headers["x-request-id"] = request_id
    return response


@app.exception_handler(Exception)
async def unknown_error_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = (
        str(getattr(getattr(request, "state", object()), "request_id", "") or "").strip()
        or str(request.headers.get("x-request-id") or "").strip()
        or uuid.uuid4().hex[:16]
    )
    logger.exception(
        "unhandled_exception",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
        },
    )
    try:
        exception_log_path = settings.log_dir / "exceptions.log"
        payload = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "error": repr(exc),
            "traceback": traceback.format_exc(),
        }
        with exception_log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        logger.exception("unhandled_exception_persist_failed", extra={"request_id": request_id})
    response = JSONResponse(
        status_code=500,
        content=fail(5000, f"服务器内部错误（请求ID: {request_id}）").model_dump(),
    )
    response.headers["x-request-id"] = request_id
    return response


@app.middleware("http")
async def access_log_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id", "").strip() or uuid.uuid4().hex[:16]
    start = time.perf_counter()
    status_code = 500
    response = None
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    client_ip = forwarded or (request.client.host if request.client else "")
    set_log_context(
        request_id=request_id,
        client_ip=client_ip,
        user_id=None,
        method=request.method,
        path=request.url.path,
    )
    try:
        request.state.request_id = request_id
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "http_request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "elapsed_ms": elapsed_ms,
                "client_ip": client_ip,
            },
        )
        if response is not None:
            response.headers["x-request-id"] = request_id
        clear_log_context()


def init_super_admin() -> None:
    from sqlalchemy.orm import Session

    with Session(engine) as db:
        row = db.query(AdminUser).filter(AdminUser.username == settings.admin_init_username).first()
        if row:
            return
        db.add(
            AdminUser(
                username=settings.admin_init_username,
                password_hash=hash_password(settings.admin_init_password),
                role="super_admin",
                last_login=datetime.utcnow(),
            )
        )
        db.commit()


def normalize_runtime_configs() -> None:
    from sqlalchemy.orm import Session

    from app.models import SystemConfig

    desired_initial_credits = int(settings.initial_credits)
    with Session(engine) as db:
        login_row = (
            db.query(SystemConfig)
            .filter(SystemConfig.category == "system", SystemConfig.config_key == "login")
            .first()
        )
        if login_row is None or not isinstance(login_row.config_value, dict):
            return

        login_cfg = dict(login_row.config_value)
        raw_initial = login_cfg.get("new_user_initial_credits", desired_initial_credits)
        try:
            current_initial_credits = int(raw_initial)
        except Exception:
            current_initial_credits = desired_initial_credits

        should_upgrade_legacy_default = current_initial_credits == 1000 and desired_initial_credits == 5000
        missing_value = "new_user_initial_credits" not in login_cfg
        if not (missing_value or should_upgrade_legacy_default):
            return

        login_cfg["new_user_initial_credits"] = desired_initial_credits
        login_row.config_value = login_cfg
        db.commit()
        logger.warning(
            "runtime_login_config_normalized",
            extra={
                "field": "new_user_initial_credits",
                "from_value": current_initial_credits,
                "to_value": desired_initial_credits,
            },
        )


def run_migrations() -> None:
    base_dir = Path(__file__).resolve().parent.parent
    alembic_ini = base_dir / "alembic.ini"
    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(base_dir / "alembic"))
    try:
        command.upgrade(cfg, "head")
    except OperationalError as exc:
        msg = str(exc).lower()
        if "already exists" not in msg:
            raise
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        has_legacy_tables = "admin_users" in tables
        has_alembic_version = "alembic_version" in tables
        alembic_version_empty = False
        if has_alembic_version:
            with engine.connect() as conn:
                rows = conn.execute(text("select version_num from alembic_version limit 1")).fetchall()
                alembic_version_empty = len(rows) == 0
        if not (has_legacy_tables and (not has_alembic_version or alembic_version_empty)):
            raise
        logger.warning("legacy_schema_detected_auto_stamp_head")
        command.stamp(cfg, "head")


def repair_missing_tables() -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    expected_tables = set(Base.metadata.tables.keys())
    missing_tables = sorted(expected_tables - existing_tables)
    if not missing_tables:
        return
    Base.metadata.create_all(
        bind=engine,
        tables=[Base.metadata.tables[name] for name in missing_tables],
        checkfirst=True,
    )
    logger.warning(
        "schema_repair_created_missing_tables",
        extra={"tables": missing_tables},
    )


def normalize_user_phone_storage() -> None:
    from app.security import decrypt_at_rest, encrypt_at_rest

    changed = 0
    skipped = 0
    user_updates: list[dict[str, object]] = []
    risk_log_updates: list[dict[str, object]] = []

    with engine.begin() as conn:
        user_rows = conn.execute(text("SELECT id, phone, phone_last4 FROM users")).mappings().all()
        for row in user_rows:
            raw_stored = str(row.get("phone") or "").strip()
            if not raw_stored:
                continue
            try:
                plain_phone = str(decrypt_at_rest(raw_stored) or "").strip()
            except Exception:
                skipped += 1
                continue
            if not plain_phone:
                continue
            expected_last4 = plain_phone[-4:] if len(plain_phone) >= 4 else plain_phone
            normalized_phone = encrypt_at_rest(plain_phone) if not raw_stored.startswith("enc:") else raw_stored
            current_last4 = str(row.get("phone_last4") or "").strip()
            if current_last4 == expected_last4 and normalized_phone == raw_stored:
                continue
            user_updates.append(
                {
                    "id": row["id"],
                    "phone": normalized_phone,
                    "phone_last4": expected_last4,
                }
            )

        if user_updates:
            conn.execute(
                text("UPDATE users SET phone = :phone, phone_last4 = :phone_last4 WHERE id = :id"),
                user_updates,
            )
            changed += len(user_updates)

        risk_log_rows = conn.execute(text("SELECT id, phone FROM registration_risk_logs")).mappings().all()
        for row in risk_log_rows:
            raw_stored = str(row.get("phone") or "").strip()
            if not raw_stored or raw_stored.startswith("enc:"):
                continue
            try:
                plain_phone = str(decrypt_at_rest(raw_stored) or "").strip()
            except Exception:
                skipped += 1
                continue
            if not plain_phone:
                continue
            risk_log_updates.append(
                {
                    "id": row["id"],
                    "phone": encrypt_at_rest(plain_phone),
                }
            )

        if risk_log_updates:
            conn.execute(
                text("UPDATE registration_risk_logs SET phone = :phone WHERE id = :id"),
                risk_log_updates,
            )
            changed += len(risk_log_updates)

    if changed:
        logger.warning("runtime_phone_storage_normalized", extra={"rows_changed": changed})
    if skipped:
        logger.warning("runtime_phone_storage_skipped_unreadable_rows", extra={"rows_skipped": skipped})


def cleanup_expired_task_artifacts() -> None:
    from sqlalchemy.orm import Session

    retention_days = max(int(settings.task_artifact_retention_days or 0), 0)
    if retention_days <= 0:
        return
    deadline = datetime.utcnow() - timedelta(days=retention_days)

    def _safe_delete(raw_path: str | None) -> bool:
        path = resolve_task_artifact_path(raw_path)
        if path is None:
            return False
        try:
            path = path.resolve()
            allowed_roots = [settings.upload_dir.resolve(), settings.output_dir.resolve()]
            if not any(path == root or root in path.parents for root in allowed_roots):
                return False
            if path.exists():
                path.unlink(missing_ok=True)
                return True
        except Exception:
            logger.warning("expired_task_artifact_delete_failed", exc_info=True, extra={"path": raw_path})
        return False

    with Session(engine) as db:
        rows = (
            db.query(Task)
            .filter(
                Task.created_at <= deadline,
                Task.status.in_([TaskStatus.COMPLETED, TaskStatus.FAILED]),
            )
            .all()
        )
        if not rows:
            return
        deleted = 0
        for row in rows:
            deleted += int(_safe_delete(row.source_path))
            deleted += int(_safe_delete(row.report_path))
            deleted += int(_safe_delete(row.output_path))
            row.source_path = ""
            row.report_path = None
            row.output_path = None
        db.commit()
        logger.warning(
            "expired_task_artifacts_cleaned",
            extra={"tasks": len(rows), "files_deleted": deleted, "retention_days": retention_days},
        )


def _db_is_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@app.get("/health/live")
def health_live() -> dict:
    return ok(data={"status": "ok"}).model_dump()


@app.get("/health")
def health() -> JSONResponse:
    db_ok = _db_is_available()
    redis_ok = redis_is_available()
    ready = db_ok and redis_ok
    status_code = 200 if ready else 503
    payload = ok(
        data={
            "status": "ok" if ready else "degraded",
            "checks": {
                "database": "ok" if db_ok else "error",
                "redis": "ok" if redis_ok else "error",
            },
        }
    ).model_dump()
    return JSONResponse(status_code=status_code, content=payload)


app.include_router(api_router, prefix="/api/v1")
