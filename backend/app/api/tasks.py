from datetime import datetime
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.client_source import MINIPROGRAM_CLIENT_SOURCE
from app.config import get_settings
from app.constants import ALLOWED_EXTENSIONS, MAX_FILE_SIZE_MB
from app.deps import client_source_dep, current_user, db_dep, get_redis
from app.exceptions import BizError
from app.models import CreditType, Task, TaskStatus, TaskType, User
from app.responses import ok
from app.schemas import APIResp
from app.services.billing_rules_service import build_task_rate_payload
from app.services.credit_service import change_credits
from app.services.process_strategy_service import (
    normalize_platform,
    resolve_task_processing_mode,
)
from app.services.task_query_actions import (
    delete_user_task,
    get_user_task_detail,
    get_user_task_download_path,
    list_user_tasks,
)
from app.services.task_artifacts import (
    build_storage_name,
    remove_uploads,
    serialize_task_artifact_path,
    safe_remove_task_artifact,
    save_upload_to,
)
from app.services.task_submission_prepare import (
    initial_billing_payload,
    prepare_task_for_processing,
    validate_report_content,
)
from app.services.partner_rebate_service import record_task_refund_rebate
from app.services.task_response_builder import (
    build_recover_payload,
    build_submit_payload,
)
from app.services.task_filename import build_task_result_filename
from app.services.task_download_response import build_download_media_type
from app.services.task_submission_guards import (
    acquire_submit_backlog,
    build_idempotency_key,
    check_submit_limits,
    decrement_submit_backlog,
    increment_submit_backlog,
    request_client_ip,
    submit_backlog_keys,
)
from app.utils import detect_file_magic, safe_display_filename, safe_filename

router = APIRouter()
settings = get_settings()
logger = logging.getLogger("app.api.tasks")
TASK_CHAIN_GUARD_TIMEOUT_MESSAGE = "任务链路保护触发：处理超时未完成，请重试"

TASK_PAPER_EXTENSIONS: dict[TaskType, set[str]] = {
    TaskType.AIGC_DETECT: {".doc", ".docx", ".pdf", ".txt"},
    TaskType.DEDUP: {".doc", ".docx"},
    TaskType.REWRITE: {".doc", ".docx"},
}
TASK_REPORT_EXTENSIONS: dict[TaskType, set[str]] = {
    TaskType.AIGC_DETECT: set(),
    TaskType.DEDUP: {".doc", ".docx", ".pdf"},
    TaskType.REWRITE: {".doc", ".docx", ".pdf"},
}
TASK_PAPER_MIME_TYPES: dict[TaskType, set[str]] = {
    TaskType.AIGC_DETECT: {
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/pdf",
        "text/plain",
        "application/octet-stream",
    },
    TaskType.DEDUP: {
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    },
    TaskType.REWRITE: {
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    },
}
TASK_REPORT_MIME_TYPES: dict[TaskType, set[str]] = {
    TaskType.AIGC_DETECT: set(),
    TaskType.DEDUP: {
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/pdf",
        "application/octet-stream",
    },
    TaskType.REWRITE: {
        "application/msword",
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
                    record_task_refund_rebate(db, task_id=row.id, operator="task_chain_guard")
                    row.refund_done = True
                    refund_count += 1
                except Exception:
                    logger.exception("task_chain_guard_refund_failed", extra={"task_id": row.id, "user_id": user_id})
                    raise
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
    save_upload_to(path, upload, max_bytes)


def _build_storage_name(name: str, fallback_name: str) -> tuple[str, str]:
    return build_storage_name(name, fallback_name)


def _remove_uploads(*paths: Path | None) -> None:
    remove_uploads(*paths)


def _clean_form_text(value: str, *, max_len: int) -> str:
    return str(value or "").strip()[:max_len]


def _clean_form_multiline_text(value: str, *, max_len: int) -> str:
    raw = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    return raw[:max_len].strip()


def _format_exts(exts: set[str]) -> str:
    return " / ".join(sorted(exts))


def _validate_paper_extension(task_type: TaskType, ext: str) -> None:
    allowed = TASK_PAPER_EXTENSIONS[task_type]
    if ext not in allowed:
        if task_type in {TaskType.DEDUP, TaskType.REWRITE}:
            raise BizError(code=4104, message="仅支持 Word 文档（.doc / .docx）")
        raise BizError(code=4104, message=f"文件格式不支持，仅支持{_format_exts(allowed)}")


def _validate_report_extension(task_type: TaskType, ext: str) -> None:
    allowed = TASK_REPORT_EXTENSIONS[task_type]
    if not allowed:
        raise BizError(code=4106, message="当前任务不支持上传辅助报告")
    if ext not in allowed:
        raise BizError(code=4106, message=f"报告文件格式不支持，仅支持{_format_exts(allowed)}")


def _resolve_upload_filename(upload: UploadFile | None, *, provided_name: str = "", fallback_name: str = "unnamed") -> str:
    normalized_provided = safe_display_filename(provided_name) if provided_name else ""
    normalized_upload_name = safe_display_filename(upload.filename) if upload and upload.filename else ""
    if normalized_provided:
        if Path(normalized_provided).suffix:
            return normalized_provided
        upload_ext = Path(normalized_upload_name).suffix.lower()
        return f"{normalized_provided}{upload_ext}" if upload_ext else normalized_provided
    return normalized_upload_name or safe_display_filename(fallback_name)


def _validate_upload_content_type(
    upload: UploadFile,
    *,
    allowed: set[str],
    label: str,
    code: int,
    client_source: str = "",
) -> None:
    content_type = str(upload.content_type or "").split(";")[0].strip().lower()
    if content_type and content_type in allowed:
        return
    if client_source == MINIPROGRAM_CLIENT_SOURCE:
        return
    raise BizError(code=code, message=f"{label} MIME 类型不支持")


def _validate_report_content(task_type: TaskType, path: Path) -> None:
    validate_report_content(task_type, path)


def _request_client_ip(request: Request) -> str:
    return request_client_ip(request)


def _check_submit_limits(redis_conn, *, user_id: int, client_ip: str) -> None:
    check_submit_limits(redis_conn, user_id=user_id, client_ip=client_ip)


def _submit_backlog_keys(user_id: int) -> tuple[str, str]:
    return submit_backlog_keys(user_id)


def _acquire_submit_backlog(redis_conn, *, user_id: int) -> bool:
    return acquire_submit_backlog(redis_conn, user_id=user_id)


def _increment_submit_backlog(redis_conn, *, user_id: int) -> None:
    increment_submit_backlog(redis_conn, user_id=user_id)


def _decrement_submit_backlog(redis_conn, *, user_id: int) -> None:
    decrement_submit_backlog(redis_conn, user_id=user_id)


def _safe_remove_task_artifact(raw_path: str | None) -> None:
    safe_remove_task_artifact(raw_path)


def _build_idempotency_key(request: Request, *, user_id: int, task_type: TaskType, platform: str, filename: str) -> str | None:
    return build_idempotency_key(
        request,
        user_id=user_id,
        task_type=task_type,
        platform=platform,
        filename=filename,
    )


def _prepare_task_for_processing(db: Session, *, task: Task) -> dict:
    return prepare_task_for_processing(db, task=task)


def _initial_billing_payload(db: Session, *, user_id: int, task_type: TaskType) -> dict:
    return initial_billing_payload(db, user_id=user_id, task_type=task_type)


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
    return build_submit_payload(
        db,
        task=task,
        strategy=strategy,
        billing_payload=billing_payload,
        idempotent=idempotent,
        dispatch_mode=dispatch_mode,
        balance_after=balance_after,
    )


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
    pasted_text: str = Form(""),
    source_filename: str = Form(""),
    paper: UploadFile | None = File(default=None),
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
    if t != TaskType.AIGC_DETECT and int(user.credits or 0) <= 0:
        raise BizError(code=4006, message="通用点数不足，请先充值")
    internal_processing_mode, strategy = resolve_task_processing_mode(db, task_type=t, platform=normalized_platform)
    paper_upload = paper if paper and paper.filename else None
    normalized_pasted_text = _clean_form_multiline_text(pasted_text, max_len=300000)
    if paper_upload is None and not normalized_pasted_text:
        raise BizError(code=4104, message="请上传文件或粘贴文本")

    if paper_upload is not None:
        upload_name = _resolve_upload_filename(
            paper_upload,
            provided_name=source_filename,
            fallback_name=f"source{Path(paper_upload.filename or '').suffix.lower() or '.tmp'}",
        )
        ext = Path(upload_name).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise BizError(code=4104, message="文件格式不支持")
        _validate_paper_extension(t, ext)
        _validate_upload_content_type(
            paper_upload,
            allowed=TASK_PAPER_MIME_TYPES[t],
            label="主文稿",
            code=4104,
            client_source=client_source,
        )
        src_name, src_storage_name = _build_storage_name(upload_name, f"source{ext}")
    else:
        if t not in {TaskType.DEDUP, TaskType.REWRITE}:
            raise BizError(code=4104, message="当前任务仅支持上传文件")
        if len(normalized_pasted_text) < 10:
            raise BizError(code=4104, message="粘贴文本过短，请至少输入10个字符")
        raw_name = safe_display_filename(source_filename) if source_filename else ""
        normalized_name = raw_name or "pasted_text.txt"
        if not normalized_name.lower().endswith(".txt"):
            normalized_name = f"{normalized_name}.txt"
        ext = ".txt"
        src_name, src_storage_name = _build_storage_name(normalized_name, "source.txt")
        if report is not None and report.filename:
            raise BizError(code=4106, message="粘贴文本模式不支持上传辅助报告")

    upload_dir = settings.upload_dir / str(user.id)
    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
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
            "input_mode": "file_upload" if paper_upload is not None else "pasted_text",
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
        if paper_upload is not None:
            _save_upload_to(src_path, paper_upload, max_bytes)
        else:
            src_path.parent.mkdir(parents=True, exist_ok=True)
            src_path.write_text(normalized_pasted_text, encoding="utf-8")

        magic = detect_file_magic(src_path)
        if magic != ext:
            raise BizError(code=4105, message="文件内容与扩展名不匹配")

        if report is not None and report.filename:
            rpt_ext = Path(report.filename).suffix.lower()
            if rpt_ext not in ALLOWED_EXTENSIONS:
                raise BizError(code=4106, message="报告文件格式不支持")
            _validate_report_extension(t, rpt_ext)
            _validate_upload_content_type(
                report,
                allowed=TASK_REPORT_MIME_TYPES[t],
                label="辅助报告",
                code=4106,
                client_source=client_source,
            )
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
        submission_meta["input_mode"] = "file_upload" if paper_upload is not None else "pasted_text"

        task = Task(
            user_id=user.id,
            task_type=t,
            platform=normalized_platform,
            processing_mode=internal_processing_mode,
            source=client_source,
            status=TaskStatus.PREPROCESSING if settings.app_env != "test" else TaskStatus.PENDING,
            source_filename=src_name,
            source_path=serialize_task_artifact_path(src_path) or str(src_path),
            report_path=serialize_task_artifact_path(report_file_path) if report_file_path else report_path,
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
    source_filename = safe_display_filename(str(payload.get("source_filename", "")).strip())
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
    return ok(data=build_recover_payload(row))


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
    return ok(
        data=list_user_tasks(
            db,
            user_id=user.id,
            page=page,
            page_size=page_size,
            task_type=task_type,
            platform=platform,
            status=status,
            start_date=start_date,
            end_date=end_date,
        )
    )


@router.get("/{task_id}", response_model=APIResp)
def task_detail(task_id: int, user: User = Depends(current_user), db: Session = Depends(db_dep)) -> APIResp:
    _guard_stale_tasks_for_user(db, user_id=user.id)
    return ok(data=get_user_task_detail(db, user_id=user.id, task_id=task_id))


@router.get("/{task_id}/download")
def task_download(task_id: int, user: User = Depends(current_user), db: Session = Depends(db_dep)) -> FileResponse:
    path = get_user_task_download_path(db, user_id=user.id, task_id=task_id)
    row = db.get(Task, task_id)
    download_name = (
        build_task_result_filename(row.task_type, row.source_filename, path)
        if row is not None
        else path.name
    )
    return FileResponse(
        path=str(path),
        filename=download_name,
        media_type=build_download_media_type(path),
    )


@router.delete("/{task_id}", response_model=APIResp)
def delete_task(task_id: int, user: User = Depends(current_user), db: Session = Depends(db_dep)) -> APIResp:
    return ok(data=delete_user_task(db, user_id=user.id, task_id=task_id))
