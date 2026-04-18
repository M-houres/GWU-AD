from pathlib import Path
from datetime import datetime
import hashlib
import logging
import uuid

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse
from redis import RedisError
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.config import get_settings
from app.constants import ALLOWED_EXTENSIONS, MAX_FILE_SIZE_MB
from app.deps import client_source_dep, current_user, db_dep, get_redis
from app.exceptions import BizError
from app.models import CreditType, Task, TaskStatus, TaskType, User
from app.money import cny_to_api, fen_to_cny
from app.pagination import paginate
from app.responses import ok
from app.schemas import APIResp
from app.services.billing_rules_service import (
    build_task_rate_payload,
    calc_task_cost_fen,
    resolve_task_points_per_char,
)
from app.services.credit_service import change_credits
from app.services.aigc_quota_service import get_aigc_daily_quota
from app.services.process_strategy_service import (
    normalize_platform,
    resolve_task_processing_mode,
    sanitize_user_result_json,
)
from app.utils import count_billable_chars, detect_file_magic, extract_text_from_file, safe_filename

router = APIRouter()
settings = get_settings()
logger = logging.getLogger("app.api.tasks")
IDEMPOTENCY_KEY_MAX_LEN = 128
IDEMPOTENCY_HEADER_MAX_LEN = 96
IDEMPOTENCY_HASH_HEX_LEN = 40
TASK_CHAIN_GUARD_TIMEOUT_MESSAGE = "任务链路保护触发：处理超时未完成，请重试（算法包升级除外）"

TASK_PAPER_EXTENSIONS: dict[TaskType, set[str]] = {
    TaskType.AIGC_DETECT: {".docx", ".pdf", ".txt"},
    TaskType.DEDUP: {".docx"},
    TaskType.REWRITE: {".docx"},
}
TASK_REPORT_EXTENSIONS: dict[TaskType, set[str]] = {
    TaskType.AIGC_DETECT: set(),
    TaskType.DEDUP: {".docx", ".pdf"},
    TaskType.REWRITE: {".docx", ".pdf"},
}
TASK_PAPER_MIME_TYPES: dict[TaskType, set[str]] = {
    TaskType.AIGC_DETECT: {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/pdf",
        "text/plain",
        "application/octet-stream",
    },
    TaskType.DEDUP: {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    },
    TaskType.REWRITE: {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    },
}
TASK_REPORT_MIME_TYPES: dict[TaskType, set[str]] = {
    TaskType.AIGC_DETECT: set(),
    TaskType.DEDUP: {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/pdf",
        "application/octet-stream",
    },
    TaskType.REWRITE: {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/pdf",
        "application/octet-stream",
    },
}
TASK_CHAIN_GUARD_STATUSES = (
    TaskStatus.PREPROCESSING,
    TaskStatus.PENDING,
    TaskStatus.QUEUED,
    TaskStatus.RUNNING,
)


def _parse_task_type(raw: str) -> TaskType:
    try:
        return TaskType(raw)
    except Exception as exc:
        raise BizError(code=4101, message="任务类型不支持") from exc


def _task_chain_guard_timeout_seconds(status: TaskStatus) -> int:
    mapping = {
        TaskStatus.PREPROCESSING: settings.task_chain_guard_preprocessing_timeout_seconds,
        TaskStatus.PENDING: settings.task_chain_guard_pending_timeout_seconds,
        TaskStatus.QUEUED: settings.task_chain_guard_queued_timeout_seconds,
        TaskStatus.RUNNING: settings.task_chain_guard_running_timeout_seconds,
    }
    return max(int(mapping.get(status, 0) or 0), 0)


def _guard_stale_tasks_for_user(db: Session, *, user_id: int) -> int:
    if not settings.task_chain_guard_enabled:
        return 0
    now = datetime.utcnow()
    rows = (
        db.query(Task)
        .filter(Task.user_id == user_id, Task.status.in_(TASK_CHAIN_GUARD_STATUSES))
        .all()
    )
    if not rows:
        return 0

    stale_rows: list[Task] = []
    user: User | None = None
    refund_count = 0
    for row in rows:
        timeout_seconds = _task_chain_guard_timeout_seconds(row.status)
        if timeout_seconds <= 0:
            continue
        anchor = row.updated_at or row.created_at
        if not anchor:
            continue
        age_seconds = max((now - anchor).total_seconds(), 0)
        if age_seconds < timeout_seconds:
            continue
        stale_rows.append(row)

    if not stale_rows:
        return 0

    for row in stale_rows:
        prev_status = row.status.value
        row.status = TaskStatus.FAILED
        row.error_message = TASK_CHAIN_GUARD_TIMEOUT_MESSAGE
        row.updated_at = now

        if row.cost_credits > 0 and not row.refund_done:
            if user is None:
                user = db.query(User).filter(User.id == user_id).with_for_update().first()
            if user is not None:
                try:
                    change_credits(
                        db,
                        user,
                        tx_type=CreditType.TASK_REFUND,
                        delta=row.cost_credits,
                        reason=f"任务链路保护退款(task_id={row.id})",
                        related_id=f"task_refund:{row.id}",
                        source=row.source,
                    )
                    row.refund_done = True
                    refund_count += 1
                except Exception:
                    logger.exception("task_chain_guard_refund_failed", extra={"task_id": row.id, "user_id": user_id})
        logger.warning(
            "task_chain_guard_mark_stale",
            extra={
                "task_id": row.id,
                "user_id": user_id,
                "prev_status": prev_status,
                "cost_credits": row.cost_credits,
            },
        )
    db.commit()
    logger.info(
        "task_chain_guard_applied",
        extra={"user_id": user_id, "task_count": len(stale_rows), "refund_count": refund_count},
    )
    return len(stale_rows)


def _save_upload_to(path: Path, upload: UploadFile, max_bytes: int) -> None:
    total = 0
    chunk_size = 1024 * 1024
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        while True:
            chunk = upload.file.read(chunk_size)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise BizError(code=4103, message=f"文件超过{MAX_FILE_SIZE_MB}MB限制")
            f.write(chunk)
    if total <= 0:
        raise BizError(code=4102, message="上传文件为空")


def _build_storage_name(name: str, fallback_name: str) -> tuple[str, str]:
    original_name = safe_filename(name or fallback_name)
    unique_name = f"{uuid.uuid4().hex[:12]}_{original_name}"
    return original_name, unique_name


def _remove_uploads(*paths: Path | None) -> None:
    for path in paths:
        if path is None:
            continue
        try:
            path.unlink(missing_ok=True)
        except Exception:
            logger.warning("uploaded_file_cleanup_failed", exc_info=True, extra={"path": str(path)})


def _clean_form_text(value: str, *, max_len: int) -> str:
    return str(value or "").strip()[:max_len]


def _format_exts(exts: set[str]) -> str:
    return " / ".join(sorted(exts))


def _validate_paper_extension(task_type: TaskType, ext: str) -> None:
    allowed = TASK_PAPER_EXTENSIONS[task_type]
    if ext not in allowed:
        if task_type in {TaskType.DEDUP, TaskType.REWRITE}:
            raise BizError(code=4104, message="仅支持 Word 文档（.docx）")
        raise BizError(code=4104, message=f"文件格式不支持，仅支持{_format_exts(allowed)}")


def _validate_report_extension(task_type: TaskType, ext: str) -> None:
    allowed = TASK_REPORT_EXTENSIONS[task_type]
    if not allowed:
        raise BizError(code=4106, message="当前任务不支持上传辅助报告")
    if ext not in allowed:
        raise BizError(code=4106, message=f"报告文件格式不支持，仅支持{_format_exts(allowed)}")


def _validate_upload_content_type(upload: UploadFile, *, allowed: set[str], label: str, code: int) -> None:
    content_type = str(upload.content_type or "").split(";")[0].strip().lower()
    if not content_type or content_type not in allowed:
        raise BizError(code=code, message=f"{label} MIME 类型不支持")


def _report_is_full(task_type: TaskType, text: str) -> bool:
    content = " ".join((text or "").split()).lower()
    if not content:
        return False
    if task_type == TaskType.DEDUP:
        markers = [
            "全文",
            "总文字复制比",
            "去除引用复制比",
            "去除本人已发表文献复制比",
            "检测报告",
            "全文标明引文",
        ]
        return sum(1 for marker in markers if marker in content) >= 2
    if task_type == TaskType.REWRITE:
        markers = [
            "aigc",
            "ai生成",
            "疑似ai",
            "检测报告",
            "全文",
            "总体风险",
            "高风险段落",
        ]
        return sum(1 for marker in markers if marker in content) >= 2
    return False


def _validate_report_content(task_type: TaskType, path: Path) -> None:
    if task_type not in {TaskType.DEDUP, TaskType.REWRITE}:
        return
    report_text = extract_text_from_file(path)
    if _report_is_full(task_type, report_text):
        return
    if task_type == TaskType.DEDUP:
        raise BizError(code=4114, message="请上传全文查重报告", http_status=422)
    raise BizError(code=4115, message="请上传全文AIGC检测报告", http_status=422)


def _request_client_ip(request: Request) -> str:
    forwarded = str(request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    return request.client.host if request.client else "unknown"


def _check_submit_limits(redis_conn, *, user_id: int, client_ip: str) -> None:
    if settings.app_env == "test":
        return
    checks = [
        (f"task:submit:user:{user_id}:1m", settings.task_submit_user_1m_limit, "提交过于频繁，请稍后再试"),
        (f"task:submit:ip:{client_ip}:1m", settings.task_submit_ip_1m_limit, "当前网络提交过于频繁，请稍后再试"),
    ]
    for key, limit, message in checks:
        if limit <= 0:
            continue
        current = redis_conn.incr(key)
        if current == 1:
            redis_conn.expire(key, 60)
        if current > limit:
            raise BizError(code=4116, message=message, http_status=429)


def _submit_backlog_keys(user_id: int) -> tuple[str, str]:
    return ("task:submit:backlog", f"task:submit:inflight:user:{user_id}")


def _acquire_submit_backlog(redis_conn, *, user_id: int) -> bool:
    if settings.app_env == "test":
        return False
    backlog_key, user_key = _submit_backlog_keys(user_id)
    user_limit = max(int(settings.task_submit_user_inflight_limit or 0), 0)
    backlog_limit = max(int(settings.task_submit_queue_backlog_limit or 0), 0)
    try:
        backlog = int(redis_conn.incr(backlog_key))
        if backlog == 1:
            redis_conn.expire(backlog_key, 3600)
        if backlog_limit > 0 and backlog > backlog_limit:
            _decrement_submit_backlog(redis_conn, user_id=user_id)
            raise BizError(code=4118, message="系统繁忙，请稍后再试", http_status=503)

        inflight = int(redis_conn.incr(user_key))
        if inflight == 1:
            redis_conn.expire(user_key, 3600)
        if user_limit > 0 and inflight > user_limit:
            _decrement_submit_backlog(redis_conn, user_id=user_id)
            raise BizError(code=4117, message="当前处理中任务较多，请稍后再提交", http_status=429)
        return True
    except BizError:
        raise
    except RedisError as exc:
        if settings.is_prod:
            raise BizError(code=4118, message="系统繁忙，请稍后再试", http_status=503) from exc
        logger.warning("task_submit_backlog_acquire_failed", exc_info=True, extra={"user_id": user_id})
        return False


def _increment_submit_backlog(redis_conn, *, user_id: int) -> None:
    acquired = _acquire_submit_backlog(redis_conn, user_id=user_id)
    if not acquired:
        return
    _, user_key = _submit_backlog_keys(user_id)
    if int(redis_conn.get(user_key) or 0) <= 0:
        redis_conn.expire(user_key, 3600)


def _decrement_submit_backlog(redis_conn, *, user_id: int) -> None:
    if settings.app_env == "test":
        return
    backlog_key, user_key = _submit_backlog_keys(user_id)
    try:
        backlog = int(redis_conn.get(backlog_key) or 0)
        user_inflight = int(redis_conn.get(user_key) or 0)
        if backlog > 0:
            redis_conn.decr(backlog_key)
        if user_inflight > 0:
            redis_conn.decr(user_key)
    except Exception:
        logger.warning("task_submit_counter_decrement_failed", exc_info=True, extra={"user_id": user_id})


def _safe_remove_task_artifact(raw_path: str | None) -> None:
    if not raw_path:
        return
    try:
        path = Path(raw_path).resolve()
        allowed_roots = [settings.upload_dir.resolve(), settings.output_dir.resolve()]
        if not any(path == root or root in path.parents for root in allowed_roots):
            logger.warning("skip_untrusted_task_artifact_delete", extra={"path": str(path)})
            return
        path.unlink(missing_ok=True)
    except Exception:
        logger.warning("task_artifact_delete_failed", exc_info=True, extra={"path": raw_path})


def _build_idempotency_key(request: Request, *, user_id: int, task_type: TaskType, platform: str, filename: str) -> str | None:
    raw = str(request.headers.get("Idempotency-Key") or request.headers.get("X-Idempotency-Key") or "").strip()
    if not raw:
        return None
    normalized = raw[:IDEMPOTENCY_HEADER_MAX_LEN]
    # Always persist a short stable hash key to avoid schema drift issues
    # across environments where historical column width may be narrower.
    seed = f"{user_id}:{task_type.value}:{platform}:{filename}:{normalized}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:IDEMPOTENCY_HASH_HEX_LEN]
    hashed_key = f"{user_id}:{task_type.value}:{platform}:sha256:{digest}"
    return hashed_key[:IDEMPOTENCY_KEY_MAX_LEN]


def _prepare_task_for_processing(db: Session, *, task: Task) -> dict:
    if task.report_path:
        _validate_report_content(task.task_type, Path(task.report_path))

    text = extract_text_from_file(Path(task.source_path))
    char_count = count_billable_chars(text)
    if char_count <= 0:
        raise BizError(code=4102, message="上传文件为空")

    points_per_char = resolve_task_points_per_char(db, task.task_type)
    quota_before = (
        get_aigc_daily_quota(db, user_id=task.user_id, submitted_delta=-1)
        if task.task_type == TaskType.AIGC_DETECT
        else None
    )
    free_applied = bool(quota_before and quota_before["free_remaining_today"] > 0)
    cost_fen = 0 if free_applied else calc_task_cost_fen(char_count, points_per_char)

    user = db.query(User).filter(User.id == task.user_id).with_for_update().first()
    if user is None:
        raise BizError(code=4001, message="用户不存在")

    change_credits(
        db,
        user,
        tx_type=CreditType.TASK_CONSUME,
        delta=-cost_fen,
        reason="AIGC每日免费额度抵扣" if free_applied else f"{task.task_type.value}任务提交扣费",
        related_id=f"task:{task.id}",
        source=task.source,
    )

    result_json = dict(task.result_json or {})
    billing = {
        "points_per_char": float(points_per_char),
        "free_applied": free_applied,
        "quota_before": quota_before,
        "cost_fen": int(cost_fen),
        "cost_points": int(cost_fen),
    }
    result_json["billing"] = billing
    task.char_count = char_count
    task.cost_credits = cost_fen
    task.result_json = result_json
    task.status = TaskStatus.PENDING
    task.updated_at = datetime.utcnow()
    db.flush()

    return {
        "points_per_char": float(points_per_char),
        "free_applied": free_applied,
        "quota": quota_before,
        "cost_fen": int(cost_fen),
        "cost_points": int(cost_fen),
    }


def _initial_billing_payload(db: Session, *, user_id: int, task_type: TaskType) -> dict:
    quota = get_aigc_daily_quota(db, user_id=user_id) if task_type == TaskType.AIGC_DETECT else None
    return {
        "points_per_char": float(resolve_task_points_per_char(db, task_type)),
        "free_applied": bool(quota and quota["free_remaining_today"] > 0),
        "quota": quota,
    }


def _task_submit_payload(
    db: Session,
    *,
    task: Task,
    strategy: dict | None = None,
    billing_payload: dict | None = None,
    idempotent: bool = False,
    dispatch_mode: str | None = None,
    balance_after: int | None = None,
) -> dict:
    result_json = dict(task.result_json or {})
    billing = billing_payload or result_json.get("billing")
    if not isinstance(billing, dict):
        billing = {
            "points_per_char": float(resolve_task_points_per_char(db, task.task_type)),
            "free_applied": False,
            "quota": None,
            "cost_fen": int(task.cost_credits or 0),
            "cost_points": int(task.cost_credits or 0),
        }
    if balance_after is None:
        user_row = db.get(User, task.user_id)
        balance_after = int(user_row.credits) if user_row is not None else None
    payload = {
        "id": task.id,
        "task_type": task.task_type.value,
        "platform": task.platform,
        "source": task.source,
        "status": task.status.value,
        "source_filename": task.source_filename,
        "has_report": bool(task.report_path),
        "char_count": int(task.char_count or 0),
        "cost_credits": int(task.cost_credits or 0),
        "cost_fen": int(task.cost_credits or 0),
        "cost_points": int(task.cost_credits or 0),
        "refund_done": bool(task.refund_done),
        "result_json": sanitize_user_result_json(task.result_json),
        "billing": billing,
        "balance_after": balance_after,
        "balance_after_fen": balance_after,
        "idempotent": bool(idempotent),
        "error_message": task.error_message,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }
    if strategy is not None:
        payload["estimated_time"] = int(strategy.get("timeout_sec", 300))
    if dispatch_mode is not None:
        payload["dispatch_mode"] = dispatch_mode
    return payload


@router.get("/rates", response_model=APIResp)
def task_rates(db: Session = Depends(db_dep)) -> APIResp:
    payload = build_task_rate_payload(db)
    return ok(
        data={
            **payload,
            "aigc_daily_free_limit": max(int(settings.aigc_daily_free_limit or 0), 0),
        }
    )


@router.post("/submit", response_model=APIResp)
def submit_task(
    request: Request,
    task_type: str = Form(...),
    platform: str = Form("cnki"),
    paper_title: str = Form(""),
    authors: str = Form(""),
    paper: UploadFile = File(...),
    report: UploadFile | None = File(default=None),
    client_source: str = Depends(client_source_dep),
    user: User = Depends(current_user),
    db: Session = Depends(db_dep),
    redis_conn=Depends(get_redis),
) -> APIResp:
    client_ip = _request_client_ip(request)
    _check_submit_limits(redis_conn, user_id=user.id, client_ip=client_ip)
    submit_slot_acquired = _acquire_submit_backlog(redis_conn, user_id=user.id)

    t = _parse_task_type(task_type)
    normalized_platform = normalize_platform(platform)
    internal_processing_mode, strategy = resolve_task_processing_mode(db, task_type=t, platform=normalized_platform)
    ext = Path(paper.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise BizError(code=4104, message="文件格式不支持")
    _validate_paper_extension(t, ext)
    _validate_upload_content_type(paper, allowed=TASK_PAPER_MIME_TYPES[t], label="主文稿", code=4104)

    upload_dir = settings.upload_dir / str(user.id)
    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    src_name, src_storage_name = _build_storage_name(paper.filename or f"source{ext}", f"source{ext}")
    src_path = upload_dir / src_storage_name
    report_file_path: Path | None = None
    report_path: str | None = None
    idempotency_key = _build_idempotency_key(
        request,
        user_id=user.id,
        task_type=t,
        platform=normalized_platform,
        filename=src_name,
    )
    logger.info(
        "task_submit_checkpoint_in",
        extra={
            "user_id": user.id,
            "task_type": t.value,
            "platform": normalized_platform,
            "client_source": client_source,
            "source_filename": src_name,
            "has_report": bool(report and report.filename),
            "idempotency_key_present": bool(idempotency_key),
        },
    )

    existing_task = None
    task: Task | None = None
    if idempotency_key:
        existing_task = (
            db.query(Task)
            .filter(Task.user_id == user.id, Task.idempotency_key == idempotency_key)
            .order_by(desc(Task.id))
            .first()
        )
        if existing_task is not None:
            if submit_slot_acquired:
                _decrement_submit_backlog(redis_conn, user_id=user.id)
            logger.info(
                "task_submit_checkpoint_idempotent_hit",
                extra={
                    "user_id": user.id,
                    "task_id": existing_task.id,
                    "task_type": t.value,
                    "platform": normalized_platform,
                },
            )
            return ok(data=_task_submit_payload(db, task=existing_task, strategy=strategy, idempotent=True))

    try:
        _save_upload_to(src_path, paper, max_bytes)

        magic = detect_file_magic(src_path)
        if magic != ext:
            raise BizError(code=4105, message="文件内容与扩展名不匹配")

        if report is not None and report.filename:
            rpt_ext = Path(report.filename).suffix.lower()
            if rpt_ext not in ALLOWED_EXTENSIONS:
                raise BizError(code=4106, message="报告文件格式不支持")
            _validate_report_extension(t, rpt_ext)
            _validate_upload_content_type(report, allowed=TASK_REPORT_MIME_TYPES[t], label="辅助报告", code=4106)
            _, report_storage_name = _build_storage_name(report.filename, f"report{rpt_ext or '.tmp'}")
            report_file_path = upload_dir / report_storage_name
            _save_upload_to(report_file_path, report, max_bytes)
            report_magic = detect_file_magic(report_file_path)
            if report_magic != rpt_ext:
                raise BizError(code=4106, message="报告文件内容与扩展名不匹配")
            report_path = str(report_file_path)

        submission_meta = {}
        normalized_title = _clean_form_text(paper_title, max_len=300)
        normalized_authors = _clean_form_text(authors, max_len=200)
        if normalized_title:
            submission_meta["paper_title"] = normalized_title
        if normalized_authors:
            submission_meta["authors"] = normalized_authors

        task = Task(
            user_id=user.id,
            task_type=t,
            platform=normalized_platform,
            processing_mode=internal_processing_mode,
            source=client_source,
            status=TaskStatus.PREPROCESSING if settings.app_env != "test" else TaskStatus.PENDING,
            source_filename=src_name,
            source_path=str(src_path),
            report_path=report_path,
            char_count=0,
            cost_credits=0,
            result_json=submission_meta or None,
            idempotency_key=idempotency_key,
        )
        db.add(task)
        db.flush()
        billing_payload = (
            _prepare_task_for_processing(db, task=task)
            if settings.app_env == "test"
            else _initial_billing_payload(db, user_id=user.id, task_type=t)
        )
        db.commit()
    except Exception:
        db.rollback()
        if submit_slot_acquired:
            _decrement_submit_backlog(redis_conn, user_id=user.id)
        _remove_uploads(src_path, report_file_path)
        raise
    logger.info(
        "task_submitted",
        extra={
            "task_id": task.id,
            "user_id": user.id,
            "task_type": t.value,
            "strategy_mode": strategy.get("process_mode"),
            "engine_mode": internal_processing_mode,
            "cost_fen": int(task.cost_credits or 0),
            "cost_points": int(task.cost_credits or 0),
            "billing_free_applied": bool((billing_payload or {}).get("free_applied")),
        },
    )

    dispatch_mode = "skipped"
    if settings.app_env != "test":
        from app.worker_tasks import dispatch_background_task, preprocess_submission_async

        try:
            dispatch_mode = dispatch_background_task(preprocess_submission_async, task.id, queue="submission")
            logger.info(
                "task_dispatch_checkpoint",
                extra={
                    "task_id": task.id,
                    "user_id": user.id,
                    "task_type": t.value,
                    "dispatch_mode": dispatch_mode,
                },
            )
        except Exception as exc:
            if submit_slot_acquired:
                _decrement_submit_backlog(redis_conn, user_id=user.id)
                submit_slot_acquired = False
            logger.exception(
                "task_dispatch_failed_after_submit",
                extra={
                    "task_id": task.id,
                    "user_id": user.id,
                    "task_type": t.value,
                    "platform": normalized_platform,
                },
            )
            failed_task = db.get(Task, task.id)
            if failed_task is not None:
                failed_task.status = TaskStatus.FAILED
                failed_task.error_message = f"任务排队失败: {exc}"
                failed_task.updated_at = datetime.utcnow()
                db.commit()
            dispatch_mode = "failed"
    elif submit_slot_acquired:
        _decrement_submit_backlog(redis_conn, user_id=user.id)
        submit_slot_acquired = False
    final_task = db.get(Task, task.id) or task
    logger.info(
        "task_submit_checkpoint_out",
        extra={
            "task_id": task.id,
            "user_id": user.id,
            "task_type": t.value,
            "status": final_task.status.value,
            "dispatch_mode": dispatch_mode,
        },
    )
    return ok(
        data=_task_submit_payload(
            db,
            task=final_task,
            strategy=strategy,
            billing_payload=billing_payload,
            idempotent=False,
            dispatch_mode=dispatch_mode,
        )
    )


@router.post("/submit/recover", response_model=APIResp)
def recover_submitted_task(
    request: Request,
    payload: dict,
    user: User = Depends(current_user),
    db: Session = Depends(db_dep),
) -> APIResp:
    task_type = _parse_task_type(str(payload.get("task_type", "")).strip())
    source_filename = safe_filename(str(payload.get("source_filename", "")).strip())
    if not source_filename:
        raise BizError(code=4119, message="缺少源文件名", http_status=422)
    normalized_platform = normalize_platform(str(payload.get("platform", "cnki")))
    idempotency_key = _build_idempotency_key(
        request,
        user_id=user.id,
        task_type=task_type,
        platform=normalized_platform,
        filename=source_filename,
    )
    if not idempotency_key:
        raise BizError(code=4120, message="缺少提交幂等键", http_status=422)
    row = (
        db.query(Task)
        .filter(Task.user_id == user.id, Task.idempotency_key == idempotency_key)
        .order_by(desc(Task.id))
        .first()
    )
    if row is None:
        raise BizError(code=4041, message="任务不存在", http_status=404)
    return ok(
        data={
            "id": row.id,
            "task_type": row.task_type.value,
            "platform": row.platform,
            "status": row.status.value,
            "source_filename": row.source_filename,
            "cost_credits": row.cost_credits,
            "cost_fen": int(row.cost_credits or 0),
            "cost_points": int(row.cost_credits or 0),
            "refund_done": bool(row.refund_done),
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
    )


@router.get("/my", response_model=APIResp)
def my_tasks(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    task_type: str | None = Query(default=None),
    platform: str | None = Query(default=None),
    status: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    user: User = Depends(current_user),
    db: Session = Depends(db_dep),
) -> APIResp:
    _guard_stale_tasks_for_user(db, user_id=user.id)
    base_query = db.query(Task).filter(Task.user_id == user.id)
    if task_type:
        try:
            base_query = base_query.filter(Task.task_type == TaskType(task_type))
        except Exception:
            raise BizError(code=4101, message="任务类型不支持")
    if platform:
        normalized_platform = normalize_platform(platform)
        base_query = base_query.filter(Task.platform == normalized_platform)
    if status:
        try:
            base_query = base_query.filter(Task.status == TaskStatus(status))
        except Exception:
            raise BizError(code=4110, message="任务状态不支持")
    if start_date:
        try:
            dt = datetime.strptime(start_date, "%Y-%m-%d")
            base_query = base_query.filter(Task.created_at >= dt)
        except Exception:
            raise BizError(code=4111, message="开始日期格式错误，应为YYYY-MM-DD")
    if end_date:
        try:
            dt = datetime.strptime(end_date, "%Y-%m-%d")
            dt = dt.replace(hour=23, minute=59, second=59)
            base_query = base_query.filter(Task.created_at <= dt)
        except Exception:
            raise BizError(code=4112, message="结束日期格式错误，应为YYYY-MM-DD")
    total = base_query.count()
    rows = (
        base_query.order_by(desc(Task.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        {
            "id": row.id,
            "task_type": row.task_type.value,
            "platform": row.platform,
            "source": row.source,
            "status": row.status.value,
            "source_filename": row.source_filename,
            "has_report": bool(row.report_path),
            "char_count": row.char_count,
            "cost_credits": row.cost_credits,
            "cost_fen": int(row.cost_credits or 0),
            "cost_points": int(row.cost_credits or 0),
            "refund_done": bool(row.refund_done),
            "result_json": sanitize_user_result_json(row.result_json),
            "error_message": row.error_message,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        for row in rows
    ]
    return ok(data={"items": items, "pagination": paginate(total, page, page_size)})


@router.get("/{task_id}", response_model=APIResp)
def task_detail(task_id: int, user: User = Depends(current_user), db: Session = Depends(db_dep)) -> APIResp:
    _guard_stale_tasks_for_user(db, user_id=user.id)
    row = db.get(Task, task_id)
    if not row or row.user_id != user.id:
        raise BizError(code=4041, message="任务不存在", http_status=404)
    return ok(
        data={
            "id": row.id,
            "task_type": row.task_type.value,
            "platform": row.platform,
            "source": row.source,
            "status": row.status.value,
            "source_filename": row.source_filename,
            "has_report": bool(row.report_path),
            "char_count": row.char_count,
            "cost_credits": row.cost_credits,
            "cost_fen": int(row.cost_credits or 0),
            "cost_points": int(row.cost_credits or 0),
            "refund_done": bool(row.refund_done),
            "result_json": sanitize_user_result_json(row.result_json),
            "error_message": row.error_message,
            "download_ready": bool(row.status == TaskStatus.COMPLETED and row.output_path),
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
    )


@router.get("/{task_id}/download")
def task_download(task_id: int, user: User = Depends(current_user), db: Session = Depends(db_dep)) -> FileResponse:
    row = db.get(Task, task_id)
    if not row or row.user_id != user.id:
        raise BizError(code=4041, message="任务不存在", http_status=404)
    if row.status != TaskStatus.COMPLETED or not row.output_path:
        raise BizError(code=4108, message="任务尚未完成")
    path = Path(row.output_path)
    if not path.exists():
        raise BizError(code=4109, message="输出文件不存在")
    return FileResponse(path=str(path), filename=path.name)


@router.delete("/{task_id}", response_model=APIResp)
def delete_task(task_id: int, user: User = Depends(current_user), db: Session = Depends(db_dep)) -> APIResp:
    row = db.get(Task, task_id)
    if not row or row.user_id != user.id:
        raise BizError(code=4041, message="任务不存在", http_status=404)
    if row.status == TaskStatus.RUNNING:
        raise BizError(code=4113, message="处理中任务不可删除")
    source_path = row.source_path
    report_path = row.report_path
    output_path = row.output_path
    db.delete(row)
    db.commit()
    _safe_remove_task_artifact(source_path)
    _safe_remove_task_artifact(report_path)
    _safe_remove_task_artifact(output_path)
    return ok(data={"task_id": task_id, "deleted": True})
