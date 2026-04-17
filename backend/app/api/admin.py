from datetime import date, datetime, timedelta
from copy import deepcopy
import ipaddress
import re
import secrets
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, Body, Cookie, Depends, File, Form, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.constants import DEFAULT_BILLING_PACKAGES
from app.deps import (
    admin_has_permission,
    current_admin,
    db_dep,
    get_redis,
    normalize_admin_permissions,
    require_admin_permission,
)
from app.exceptions import BizError
from app.models import (
    AdminAuditLog,
    AdminUser,
    CreditType,
    CreditTransaction,
    LLMErrorLog,
    Order,
    PromoBenefitRecord,
    PromoClassroom,
    PromoShareSubmission,
    PromoShareSubmissionStatus,
    SwitchLog,
    SystemConfig,
    SystemSwitch,
    Task,
    TaskType,
    User,
)
from app.pagination import paginate
from app.responses import ok
from app.schemas import (
    APIResp,
    AdminAdjustCreditReq,
    AdminLoginReq,
    AlgoPackageActivateReq,
    AlgoPackageUploadReq,
)
from app.security import (
    REFRESH_TOKEN_TYPE,
    auth_session_key,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    new_session_version,
    verify_password,
)
from app.services.algo_package_service import (
    activate_algorithm_package,
    deactivate_algorithm_package,
    get_active_slot_config,
    get_algorithm_package_archive_path,
    install_algorithm_package,
    list_algorithm_packages,
)
from app.services.builtin_algo_packages import (
    bootstrap_builtin_algo_packages,
    build_authoring_spec_bundle,
    build_builtin_template_package,
)
from app.services.credit_service import change_credits
from app.services.llm_service import LLM_PROVIDER_PRESETS, SUPPORTED_LLM_PROVIDERS, normalize_llm_provider
from app.money import cny_to_api, cny_sum
from app.services.payment_service import DEFAULT_PAYMENT_CONFIG, normalize_payment_provider
from app.services.promo_center_service import (
    SHARE_PLATFORM_PRESETS,
    build_admin_promo_overview,
    mark_share_reward_paid,
    review_share_submission,
)
from app.services.process_strategy_service import (
    get_process_strategy,
    list_process_strategies,
    normalize_platform,
    normalize_process_mode,
    normalize_task_type,
    update_process_strategy,
)
from app.services.user_navigation_service import default_user_navigation_config, normalize_user_navigation_config

router = APIRouter()
settings = get_settings()

DEFAULT_NOTICE_TITLE = "系统公告"
DEFAULT_NOTICE_TEXT = "平台系统持续优化中，任务提交后请在个人中心查看处理进度。"
ADMIN_ACCESS_COOKIE_NAME = "gw_admin_access"
SOURCE_BUCKETS = ("web", "miniapp", "other")
_SOURCE_WEB_ALIASES = {"web", "h5", "site"}
_SOURCE_MINIAPP_ALIASES = {"miniapp", "miniprogram", "mini_program", "wxapp", "wechat_miniprogram", "wechat_mini_program"}

CONFIG_CATEGORIES = {"llm", "payment", "billing", "login", "notice", "miniapp", "user_navigation"}
CONFIG_LABELS = {
    "llm": "大模型配置",
    "payment": "支付配置",
    "billing": "计费规则",
    "login": "登录配置",
    "notice": "公告配置",
    "miniapp": "小程序配置",
    "user_navigation": "前台导航",
}
CONFIG_FIELD_LABELS = {
    "llm": {
        "enabled": "启用状态",
        "provider": "提供商",
        "base_url": "Base URL",
        "model": "模型名",
        "api_key": "API Key",
        "timeout_seconds": "超时(秒)",
        "retry_attempts": "重试次数",
        "retry_backoff_seconds": "退避基线(秒)",
        "max_output_tokens": "最大输出 Tokens",
        "temperature": "温度",
    },
    "payment": {
        "provider": "支付通道",
        "test_mode": "联调模式",
        "app_id": "应用ID",
        "merchant_id": "商户号",
        "merchant_serial_no": "商户证书序列号",
        "merchant_private_key_pem": "商户私钥",
        "wechatpay_public_key_id": "微信支付公钥ID",
        "wechatpay_public_key": "微信支付公钥",
        "api_v3_key": "APIv3 Key",
        "notify_url": "回调地址",
        "app_private_key_pem": "应用私钥",
        "alipay_public_key": "支付宝公钥",
        "gateway_url": "支付网关",
        "callback_secret": "回调验签密钥",
    },
    "billing": {
        "aigc_rate": "AIGC单价",
        "dedup_rate": "降重单价",
        "rewrite_rate": "学术润色单价",
        "packages": "套餐配置",
    },
    "login": {
        "sms_provider": "短信服务商",
        "sms_api_key": "短信网关密钥",
        "sms_gateway_url": "短信网关地址",
        "sms_template_id": "短信模板ID",
        "sms_sign_name": "短信签名",
        "sms_sdk_app_id": "短信应用ID",
        "sms_region": "短信地域",
        "sms_aliyun_region_id": "阿里云地域",
        "sms_access_key_id": "短信AccessKeyId",
        "sms_access_key_secret": "短信AccessKeySecret",
        "debug_code_enabled": "debug验证码",
        "wechat_login_enabled": "微信登录开关",
        "wechat_app_id": "微信AppID",
        "wechat_app_secret": "微信AppSecret",
        "wechat_redirect_uri": "微信回调地址",
        "header_notice_text": "顶部公告文案",
        "wechat_miniprogram_login_enabled": "小程序登录开关",
        "wechat_miniprogram_app_id": "小程序AppID",
        "wechat_miniprogram_app_secret": "小程序AppSecret",
        "notice_enabled": "公告开关",
        "notice_title": "公告标题",
        "notice_content": "公告内容",
        "notice_level": "公告级别",
        "notice_version": "公告版本",
        "notice_updated_at": "公告更新时间",
        "new_user_initial_credits": "新用户初始积分",
        "max_code_retry": "验证码最大重试次数",
        "phone_lock_minutes": "验证码错误锁定分钟数",
        "send_code_ip_1h_limit": "发送验证码IP限流",
        "login_ip_10m_limit": "登录请求IP限流",
    },
    "notice": {
        "enabled": "公告开关",
        "title": "公告标题",
        "content": "公告内容",
        "header_text": "顶部公告文案",
        "level": "公告级别",
        "version": "公告版本",
        "updated_at": "公告更新时间",
    },
    "miniapp": {
        "enabled": "小程序开关",
        "app_id": "小程序AppID",
        "app_secret": "小程序AppSecret",
        "original_id": "小程序原始ID",
        "env_version": "版本环境",
        "api_base_url": "后端API地址",
        "web_base_url": "官网地址",
        "request_domain": "request合法域名",
        "upload_domain": "uploadFile合法域名",
        "download_domain": "downloadFile合法域名",
        "ws_domain": "WebSocket合法域名",
        "business_domain": "业务域名",
        "icp_filing_no": "备案号",
        "contact_phone": "客服电话",
        "contact_email": "联系邮箱",
        "publish_note": "上线备注",
        "wechat_miniprogram_login_enabled": "小程序登录开关",
        "wechat_miniprogram_app_id": "小程序登录AppID",
        "wechat_miniprogram_app_secret": "小程序登录AppSecret",
        "wechat_miniprogram_payment_enabled": "小程序支付开关",
        "payment_notify_url": "支付回调地址",
    },
    "user_navigation": {
        "items": "前台导航编排",
    },
}
CONFIG_DEFAULTS = {
    "llm": {
        "enabled": False,
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "api_key": "",
        "timeout_seconds": 25,
        "retry_attempts": 3,
        "retry_backoff_seconds": 0.8,
        "max_output_tokens": 2048,
        "temperature": 0.3,
    },
    "payment": dict(DEFAULT_PAYMENT_CONFIG),
    "billing": {
        "aigc_rate": 1,
        "dedup_rate": 3,
        "rewrite_rate": 2,
        "packages": deepcopy(DEFAULT_BILLING_PACKAGES),
    },
    "login": {
        "sms_provider": "custom_webhook",
        "sms_api_key": "",
        "sms_gateway_url": "",
        "sms_template_id": "",
        "sms_sign_name": "",
        "sms_sdk_app_id": "",
        "sms_region": "ap-guangzhou",
        "sms_aliyun_region_id": "cn-hangzhou",
        "sms_access_key_id": "",
        "sms_access_key_secret": "",
        "debug_code_enabled": False,
        "wechat_login_enabled": False,
        "wechat_app_id": "",
        "wechat_app_secret": "",
        "wechat_redirect_uri": "",
        "wechat_miniprogram_login_enabled": False,
        "wechat_miniprogram_app_id": "",
        "wechat_miniprogram_app_secret": "",
        "header_notice_text": DEFAULT_NOTICE_TEXT,
        "notice_enabled": True,
        "notice_title": DEFAULT_NOTICE_TITLE,
        "notice_content": DEFAULT_NOTICE_TEXT,
        "notice_level": "info",
        "notice_version": 1,
        "notice_updated_at": "",
        "new_user_initial_credits": settings.initial_credits,
        "max_code_retry": settings.max_code_retry,
        "phone_lock_minutes": settings.phone_lock_minutes,
        "send_code_ip_1h_limit": settings.auth_send_code_ip_1h_limit,
        "login_ip_10m_limit": settings.auth_login_ip_10m_limit,
    },
    "notice": {
        "enabled": True,
        "title": DEFAULT_NOTICE_TITLE,
        "content": DEFAULT_NOTICE_TEXT,
        "header_text": DEFAULT_NOTICE_TEXT,
        "level": "info",
        "version": 1,
        "updated_at": "",
    },
    "miniapp": {
        "enabled": False,
        "app_id": "",
        "app_secret": "",
        "original_id": "",
        "env_version": "release",
        "api_base_url": "",
        "web_base_url": "",
        "request_domain": "",
        "upload_domain": "",
        "download_domain": "",
        "ws_domain": "",
        "business_domain": "",
        "icp_filing_no": "",
        "contact_phone": "",
        "contact_email": "",
        "publish_note": "",
        "wechat_miniprogram_login_enabled": False,
        "wechat_miniprogram_app_id": "",
        "wechat_miniprogram_app_secret": "",
        "wechat_miniprogram_payment_enabled": False,
        "payment_notify_url": "",
    },
    "user_navigation": default_user_navigation_config(),
}

_LLM_PROVIDERS = set(SUPPORTED_LLM_PROVIDERS)
_PAYMENT_PROVIDERS = {"wechat", "alipay", "mock", "wechatpay_v3"}
_SMS_PROVIDERS = {"custom_webhook", "tencent_sms", "aliyun_sms", "disabled"}
ADMIN_PERMISSION_CATALOG = [
    {"key": "dashboard:view", "label": "查看总览看板", "group": "看板"},
    {"key": "users:view", "label": "查看用户列表与详情", "group": "用户"},
    {"key": "users:manage", "label": "封禁与调整用户积分", "group": "用户"},
    {"key": "tasks:view", "label": "查看任务与结果下载", "group": "任务"},
    {"key": "orders:view", "label": "查看订单列表与详情", "group": "订单"},
    {"key": "orders:refund", "label": "执行订单退款", "group": "订单"},
    {"key": "referrals:view", "label": "查看推广统计与记录", "group": "推广"},
    {"key": "referrals:manage", "label": "修改推广规则与重试奖励", "group": "推广"},
    {"key": "logs:view", "label": "查看系统日志", "group": "日志"},
    {"key": "credits:view", "label": "查看积分流水", "group": "积分"},
    {"key": "algo:view", "label": "查看算法包列表", "group": "算法包"},
    {"key": "algo:manage", "label": "上传/启停算法包", "group": "算法包"},
    {"key": "configs:view", "label": "查看系统配置", "group": "系统配置"},
    {"key": "configs:manage", "label": "修改系统配置", "group": "系统配置"},
    {"key": "system:manage", "label": "切换系统运行模式", "group": "系统模式"},
    {"key": "admins:view", "label": "查看管理员与权限", "group": "权限管理"},
    {"key": "admins:manage", "label": "创建管理员与修改权限", "group": "权限管理"},
]
ADMIN_PERMISSION_KEYS = {item["key"] for item in ADMIN_PERMISSION_CATALOG}
DEFAULT_OPERATOR_PERMISSIONS = {
    "dashboard:view",
    "users:view",
    "users:manage",
    "tasks:view",
    "orders:view",
    "orders:refund",
    "referrals:view",
    "logs:view",
    "credits:view",
    "algo:view",
}
ADMIN_PERMISSION_TEMPLATES = [
    {
        "key": "ops_basic",
        "label": "运营基础",
        "description": "适合日常运营，覆盖用户、任务、订单与推广查看。",
        "permissions": [
            "dashboard:view",
            "users:view",
            "users:manage",
            "tasks:view",
            "orders:view",
            "orders:refund",
            "referrals:view",
            "logs:view",
            "credits:view",
        ],
    },
    {
        "key": "service_support",
        "label": "客服支持",
        "description": "聚焦用户处理与订单售后，不涉及系统配置。",
        "permissions": [
            "users:view",
            "users:manage",
            "tasks:view",
            "orders:view",
            "orders:refund",
            "credits:view",
        ],
    },
    {
        "key": "read_only_audit",
        "label": "只读审计",
        "description": "只读查看业务与日志，不允许变更。",
        "permissions": [
            "dashboard:view",
            "users:view",
            "tasks:view",
            "orders:view",
            "referrals:view",
            "logs:view",
            "credits:view",
            "algo:view",
            "configs:view",
            "admins:view",
        ],
    },
    {
        "key": "config_operator",
        "label": "配置运营",
        "description": "负责算法与系统配置维护，不含管理员权限。",
        "permissions": [
            "dashboard:view",
            "tasks:view",
            "algo:view",
            "algo:manage",
            "configs:view",
            "configs:manage",
            "system:manage",
            "logs:view",
        ],
    },
    {
        "key": "permission_admin",
        "label": "权限管理员",
        "description": "负责管理员账号、授权、启停和密码重置。",
        "permissions": [
            "dashboard:view",
            "admins:view",
            "admins:manage",
            "logs:view",
        ],
    },
]
ADMIN_USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{2,31}$")
MASKED_SECRET_VALUE = "********"
MASKED_SECRET_UPDATED_VALUE = "********(updated)"
ADMIN_LOGIN_WINDOW_SECONDS = 10 * 60
SENSITIVE_CONFIG_FIELDS = {
    "llm": {"api_key"},
    "payment": {"merchant_private_key_pem", "api_v3_key", "app_private_key_pem", "api_key", "callback_secret"},
    "login": {"sms_api_key", "sms_access_key_secret", "wechat_app_secret", "wechat_miniprogram_app_secret"},
    "miniapp": {"app_secret", "wechat_miniprogram_app_secret"},
}


def _effective_admin_permissions(admin: AdminUser) -> list[str]:
    if admin.role == "super_admin":
        return ["*"]
    permissions = normalize_admin_permissions(admin.permissions_json)
    if not permissions:
        permissions = set(DEFAULT_OPERATOR_PERMISSIONS)
    return sorted(permissions)


def _admin_payload(admin: AdminUser) -> dict:
    return {
        "id": admin.id,
        "username": admin.username,
        "role": admin.role,
        "is_active": bool(getattr(admin, "is_active", True)),
        "permissions": _effective_admin_permissions(admin),
        "last_login": admin.last_login,
        "created_at": admin.created_at,
        "updated_at": admin.updated_at,
    }


def _normalize_permission_list(raw) -> list[str]:
    values = normalize_admin_permissions(raw)
    expanded = set(values)
    for item in list(values):
        if ":" not in item:
            continue
        scope, action = item.split(":", 1)
        if action != "manage":
            continue
        implied_view = f"{scope}:view"
        if implied_view in ADMIN_PERMISSION_KEYS:
            expanded.add(implied_view)
    values = expanded
    unsupported = sorted(values - ADMIN_PERMISSION_KEYS)
    if unsupported:
        raise BizError(code=4308, message=f"存在不支持的权限: {','.join(unsupported)}")
    return sorted(values)


def _permission_templates_payload() -> list[dict]:
    result = []
    for item in ADMIN_PERMISSION_TEMPLATES:
        permissions = _normalize_permission_list(item.get("permissions", []))
        result.append(
            {
                "key": item.get("key"),
                "label": item.get("label"),
                "description": item.get("description", ""),
                "permissions": permissions,
            }
        )
    return result


def _assert_actor_can_assign_permissions(actor: AdminUser, permissions: list[str]) -> None:
    if actor.role == "super_admin":
        return
    denied = [perm for perm in permissions if not admin_has_permission(actor, perm)]
    if denied:
        raise BizError(code=4315, message=f"不可分配超出自身范围的权限: {','.join(denied)}")


def _generate_admin_password(length: int = 14) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%&*"
    if length < 12:
        length = 12
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _assert_category(category: str) -> str:
    c = (category or "").strip().lower()
    if c not in CONFIG_CATEGORIES:
        raise BizError(code=4340, message=f"不支持的配置分类:{c}")
    return c


def _as_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        raw = value.strip().lower()
        if raw in {"1", "true", "yes", "on", "y"}:
            return True
        if raw in {"0", "false", "no", "off", "n", ""}:
            return False
    return default


def _as_int(value, *, default: int, min_value: int | None = None, max_value: int | None = None, field: str = "") -> int:
    try:
        num = int(value)
    except Exception as exc:
        raise BizError(code=4341, message=f"{field} 必须是整数") from exc
    if min_value is not None and num < min_value:
        raise BizError(code=4341, message=f"{field} 不能小于 {min_value}")
    if max_value is not None and num > max_value:
        raise BizError(code=4341, message=f"{field} 不能大于 {max_value}")
    return num


def _as_float(
    value,
    *,
    default: float,
    min_value: float | None = None,
    max_value: float | None = None,
    field: str = "",
) -> float:
    try:
        num = float(value)
    except Exception as exc:
        raise BizError(code=4341, message=f"{field} 必须是数字") from exc
    if min_value is not None and num < min_value:
        raise BizError(code=4341, message=f"{field} 不能小于 {min_value}")
    if max_value is not None and num > max_value:
        raise BizError(code=4341, message=f"{field} 不能大于 {max_value}")
    return num


def _as_text(value, *, default: str = "", max_len: int = 256) -> str:
    if value is None:
        return default
    return str(value).strip()[:max_len]


def _is_sensitive_config_field(category: str, field: str) -> bool:
    return field in SENSITIVE_CONFIG_FIELDS.get(category, set())


def _is_masked_secret_placeholder(value) -> bool:
    return str(value or "").strip() in {MASKED_SECRET_VALUE, MASKED_SECRET_UPDATED_VALUE}


def _mask_secret_value(value) -> str:
    return MASKED_SECRET_VALUE if str(value or "").strip() else ""


def _redact_config_view(category: str, value: dict | None) -> dict:
    payload = deepcopy(value) if isinstance(value, dict) else {}
    for field in SENSITIVE_CONFIG_FIELDS.get(category, set()):
        if field in payload:
            payload[field] = _mask_secret_value(payload.get(field))
    return payload


def _merge_masked_config_payload(category: str, payload: dict, current_value: dict) -> dict:
    merged = dict(payload)
    for field in SENSITIVE_CONFIG_FIELDS.get(category, set()):
        if field not in merged:
            continue
        if _is_masked_secret_placeholder(merged.get(field)):
            merged[field] = current_value.get(field, "")
    if category == "payment":
        raw_api_key = merged.get("api_key")
        raw_private_key = merged.get("app_private_key_pem")
        if "api_key" in merged and raw_api_key == "":
            merged["app_private_key_pem"] = ""
        if "app_private_key_pem" in merged and raw_private_key == "":
            merged["api_key"] = ""
    return merged


def _redact_config_audit_pair(category: str, before: dict | None, after: dict | None) -> tuple[dict | None, dict | None]:
    before_payload = deepcopy(before) if isinstance(before, dict) else None
    after_payload = deepcopy(after) if isinstance(after, dict) else None

    for field in SENSITIVE_CONFIG_FIELDS.get(category, set()):
        before_raw = str((before or {}).get(field, "")).strip() if isinstance(before, dict) else ""
        after_raw = str((after or {}).get(field, "")).strip() if isinstance(after, dict) else ""
        before_marker = _mask_secret_value(before_raw)
        after_marker = _mask_secret_value(after_raw)
        if before_raw and after_raw and before_raw != after_raw:
            after_marker = MASKED_SECRET_UPDATED_VALUE
        if before_payload is not None and field in before_payload:
            before_payload[field] = before_marker
        if after_payload is not None and field in after_payload:
            after_payload[field] = after_marker
    return before_payload, after_payload


def _request_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded[:64]
    if request.client is None:
        return ""
    return (request.client.host or "")[:64]


def _cookie_samesite() -> str:
    value = str(settings.auth_cookie_samesite or "lax").strip().lower()
    if value not in {"lax", "strict", "none"}:
        return "lax"
    return value


def _auth_session_ttl_seconds() -> int:
    return max(int(settings.refresh_token_expire_days) * 24 * 3600, int(settings.jwt_expire_minutes) * 60)


def _store_admin_session(redis_client, *, admin_id: int, session_version: str) -> None:
    redis_client.setex(auth_session_key("admin", str(admin_id)), _auth_session_ttl_seconds(), session_version)


def _load_admin_session(redis_client, *, admin_id: int) -> str:
    return str(redis_client.get(auth_session_key("admin", str(admin_id))) or "").strip()


def _clear_admin_session(redis_client, *, admin_id: int) -> None:
    redis_client.delete(auth_session_key("admin", str(admin_id)))


def _apply_admin_auth_cookies(response: Response, *, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        key=ADMIN_ACCESS_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=settings.auth_cookie_secure_enabled,
        samesite=_cookie_samesite(),
        max_age=int(settings.jwt_expire_minutes) * 60,
        path="/",
    )
    response.set_cookie(
        key=settings.admin_refresh_cookie_name,
        value=refresh_token,
        httponly=True,
        secure=settings.auth_cookie_secure_enabled,
        samesite=_cookie_samesite(),
        max_age=int(settings.refresh_token_expire_days) * 24 * 3600,
        path="/api/v1/admin/auth",
    )


def _issue_admin_auth(redis_client, response: Response | None, admin: AdminUser) -> tuple[str, str]:
    session_version = new_session_version()
    _store_admin_session(redis_client, admin_id=admin.id, session_version=session_version)
    access_token = create_access_token(subject=str(admin.id), scope="admin", session_version=session_version)
    refresh_token = create_refresh_token(subject=str(admin.id), scope="admin", session_version=session_version)
    if response is not None:
        _apply_admin_auth_cookies(response, access_token=access_token, refresh_token=refresh_token)
    return access_token, refresh_token


def _assert_admin_ip_allowed(request: Request) -> None:
    allowlist = settings.admin_login_ip_allowlist_set
    if not allowlist:
        return
    if _request_client_ip(request) not in allowlist:
        raise BizError(code=4310, message="当前 IP 不允许登录管理后台", http_status=403)


def _admin_login_attempt_key(kind: str, value: str) -> str:
    return f"admin:auth:{kind}:{value}"


def _enforce_admin_login_rate_limit(redis_client, *, ip: str, username: str) -> None:
    if ip and settings.admin_login_ip_10m_limit > 0:
        ip_key = _admin_login_attempt_key("ip", ip)
        ip_count = redis_client.incr(ip_key)
        if ip_count == 1:
            redis_client.expire(ip_key, ADMIN_LOGIN_WINDOW_SECONDS)
        if ip_count > settings.admin_login_ip_10m_limit:
            raise BizError(code=4317, message="管理员登录请求过于频繁，请稍后重试", http_status=429)

    username_limit = int(settings.admin_login_user_10m_limit or 0)
    if username_limit <= 0:
        return
    username_key = _admin_login_attempt_key("user_fail", username.lower())
    if redis_client.ttl(username_key) > 0:
        fail_count = int(redis_client.get(username_key) or 0)
        if fail_count >= username_limit:
            raise BizError(code=4318, message="管理员账号已临时锁定，请稍后重试", http_status=429)


def _record_admin_login_failure(redis_client, *, username: str) -> None:
    if int(settings.admin_login_user_10m_limit or 0) <= 0:
        return
    username_key = _admin_login_attempt_key("user_fail", username.lower())
    fail_count = redis_client.incr(username_key)
    if fail_count == 1:
        redis_client.expire(username_key, ADMIN_LOGIN_WINDOW_SECONDS)


def _clear_admin_login_failures(redis_client, *, username: str) -> None:
    redis_client.delete(_admin_login_attempt_key("user_fail", username.lower()))


def _is_http_url(value: str) -> bool:
    return bool(value) and value.startswith(("http://", "https://"))


def _is_https_url(value: str) -> bool:
    return bool(value) and value.startswith("https://")


def _has_query_or_fragment(value: str) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    return bool(parsed.query or parsed.fragment)


def _default_debug_code_enabled() -> bool:
    return bool(settings.auth_return_debug_code or settings.app_env != "prod")


def _normalize_notice_level(value) -> str:
    level = _as_text(value, default="info", max_len=32).lower()
    if level not in {"info", "important", "warning", "success"}:
        return "info"
    return level


def _normalize_source_bucket(value) -> str:
    raw = _as_text(value, default="", max_len=64).lower().replace("-", "_")
    if raw in _SOURCE_WEB_ALIASES:
        return "web"
    if raw in _SOURCE_MINIAPP_ALIASES:
        return "miniapp"
    return "other"


def _normalize_source_filter(value) -> str:
    raw = _as_text(value, default="", max_len=64).lower().replace("-", "_")
    if not raw or raw in {"all", "*"}:
        return ""
    if raw in _SOURCE_WEB_ALIASES:
        return "web"
    if raw in _SOURCE_MINIAPP_ALIASES:
        return "miniapp"
    if raw == "other":
        return "other"
    raise BizError(code=4348, message="source 不支持，仅允许 web / miniapp / other")


def _apply_source_filter(query, source_column, source_filter: str):
    if not source_filter:
        return query
    source_expr = func.lower(func.coalesce(source_column, ""))
    if source_filter == "web":
        return query.filter(source_expr.in_(tuple(sorted(_SOURCE_WEB_ALIASES))))
    if source_filter == "miniapp":
        return query.filter(source_expr.in_(tuple(sorted(_SOURCE_MINIAPP_ALIASES))))
    known = tuple(sorted(_SOURCE_WEB_ALIASES | _SOURCE_MINIAPP_ALIASES))
    return query.filter(~source_expr.in_(known))


def _apply_phone_filter(query, query_text: str | None):
    raw = str(query_text or "").strip()
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        return query
    if len(digits) == 11:
        return query.filter(User.phone == digits)
    if len(digits) >= 4:
        return query.filter(User.phone_last4 == digits[-4:])
    return query


def _build_source_stats(rows, *, as_float: bool = False) -> dict:
    stats: dict[str, int | float] = {bucket: 0.0 if as_float else 0 for bucket in SOURCE_BUCKETS}
    stats["total"] = 0.0 if as_float else 0
    for source, amount in rows:
        bucket = _normalize_source_bucket(source)
        if as_float:
            value = float(amount or 0)
            stats[bucket] = float(stats[bucket]) + value
            stats["total"] = float(stats["total"]) + value
        else:
            value = int(amount or 0)
            stats[bucket] = int(stats[bucket]) + value
            stats["total"] = int(stats["total"]) + value
    if as_float:
        return {key: round(float(val), 2) for key, val in stats.items()}
    return {key: int(val) for key, val in stats.items()}


def _read_system_config_raw(db: Session, key: str) -> dict:
    row = (
        db.query(SystemConfig)
        .filter(SystemConfig.category == "system", SystemConfig.config_key == key)
        .first()
    )
    if row is None or not isinstance(row.config_value, dict):
        return {}
    return row.config_value


def _upsert_system_config_raw(db: Session, *, key: str, value: dict, updated_by: int | None) -> None:
    row = (
        db.query(SystemConfig)
        .filter(SystemConfig.category == "system", SystemConfig.config_key == key)
        .first()
    )
    if row is None:
        db.add(
            SystemConfig(
                category="system",
                config_key=key,
                config_value=value,
                updated_by=updated_by,
            )
        )
        return
    row.config_value = value
    row.updated_by = updated_by


def _extract_notice_payload(raw: dict | None) -> dict:
    src = raw if isinstance(raw, dict) else {}
    content = _as_text(
        src.get("content", src.get("notice_content", src.get("header_notice_text", DEFAULT_NOTICE_TEXT))),
        default=DEFAULT_NOTICE_TEXT,
        max_len=2000,
    )
    if not content:
        content = DEFAULT_NOTICE_TEXT
    header_text = _as_text(
        src.get("header_text", src.get("header_notice_text", content)),
        default=content[:140],
        max_len=140,
    )
    if not header_text:
        header_text = content[:140]
    title = _as_text(src.get("title", src.get("notice_title", DEFAULT_NOTICE_TITLE)), default=DEFAULT_NOTICE_TITLE, max_len=32)
    if not title:
        title = DEFAULT_NOTICE_TITLE
    try:
        version = int(src.get("version", src.get("notice_version", 1)) or 1)
    except Exception:
        version = 1
    if version < 1:
        version = 1
    return {
        "enabled": _as_bool(src.get("enabled", src.get("notice_enabled", True)), default=True),
        "title": title,
        "content": content,
        "header_text": header_text,
        "level": _normalize_notice_level(src.get("level", src.get("notice_level", "info"))),
        "version": version,
        "updated_at": _as_text(src.get("updated_at", src.get("notice_updated_at", "")), default="", max_len=64),
    }


def _notice_to_login_fields(notice_payload: dict) -> dict:
    notice = _extract_notice_payload(notice_payload)
    return {
        "header_notice_text": notice["header_text"],
        "notice_enabled": notice["enabled"],
        "notice_title": notice["title"],
        "notice_content": notice["content"],
        "notice_level": notice["level"],
        "notice_version": notice["version"],
        "notice_updated_at": notice["updated_at"],
    }


def _notice_to_notice_fields(notice_payload: dict) -> dict:
    notice = _extract_notice_payload(notice_payload)
    return {
        "enabled": notice["enabled"],
        "title": notice["title"],
        "content": notice["content"],
        "header_text": notice["header_text"],
        "level": notice["level"],
        "version": notice["version"],
        "updated_at": notice["updated_at"],
    }


def _extract_miniapp_payload(raw: dict | None) -> dict:
    src = raw if isinstance(raw, dict) else {}
    payload = deepcopy(CONFIG_DEFAULTS["miniapp"])
    payload["enabled"] = _as_bool(src.get("enabled", src.get("wechat_miniprogram_login_enabled", payload["enabled"])), default=payload["enabled"])
    payload["app_id"] = _as_text(src.get("app_id", src.get("wechat_miniprogram_app_id", src.get("wechat_app_id", payload["app_id"]))), default="", max_len=128)
    payload["app_secret"] = _as_text(src.get("app_secret", src.get("wechat_miniprogram_app_secret", src.get("wechat_app_secret", payload["app_secret"]))), default="", max_len=256)
    payload["original_id"] = _as_text(src.get("original_id", payload["original_id"]), default="", max_len=128)
    payload["env_version"] = _as_text(src.get("env_version", payload["env_version"]), default="release", max_len=32).lower()
    if payload["env_version"] not in {"develop", "trial", "release"}:
        payload["env_version"] = "release"
    payload["api_base_url"] = _as_text(src.get("api_base_url", payload["api_base_url"]), default="", max_len=256)
    payload["web_base_url"] = _as_text(src.get("web_base_url", payload["web_base_url"]), default="", max_len=256)
    payload["request_domain"] = _as_text(src.get("request_domain", payload["request_domain"]), default="", max_len=256)
    payload["upload_domain"] = _as_text(src.get("upload_domain", payload["upload_domain"]), default="", max_len=256)
    payload["download_domain"] = _as_text(src.get("download_domain", payload["download_domain"]), default="", max_len=256)
    payload["ws_domain"] = _as_text(src.get("ws_domain", payload["ws_domain"]), default="", max_len=256)
    payload["business_domain"] = _as_text(src.get("business_domain", payload["business_domain"]), default="", max_len=256)
    payload["icp_filing_no"] = _as_text(src.get("icp_filing_no", payload["icp_filing_no"]), default="", max_len=128)
    payload["contact_phone"] = _as_text(src.get("contact_phone", payload["contact_phone"]), default="", max_len=32)
    payload["contact_email"] = _as_text(src.get("contact_email", payload["contact_email"]), default="", max_len=128)
    payload["publish_note"] = _as_text(src.get("publish_note", payload["publish_note"]), default="", max_len=500)
    payload["wechat_miniprogram_login_enabled"] = _as_bool(
        src.get("wechat_miniprogram_login_enabled", payload["enabled"]),
        default=payload["enabled"],
    )
    payload["wechat_miniprogram_app_id"] = _as_text(
        src.get("wechat_miniprogram_app_id", payload["app_id"]),
        default=payload["app_id"],
        max_len=128,
    )
    payload["wechat_miniprogram_app_secret"] = _as_text(
        src.get("wechat_miniprogram_app_secret", payload["app_secret"]),
        default=payload["app_secret"],
        max_len=256,
    )
    payload["wechat_miniprogram_payment_enabled"] = _as_bool(
        src.get("wechat_miniprogram_payment_enabled", payload["wechat_miniprogram_payment_enabled"]),
        default=payload["wechat_miniprogram_payment_enabled"],
    )
    payload["payment_notify_url"] = _as_text(src.get("payment_notify_url", payload["payment_notify_url"]), default="", max_len=256)
    return payload


def _miniapp_to_login_fields(miniapp_payload: dict) -> dict:
    mini = _extract_miniapp_payload(miniapp_payload)
    return {
        "wechat_miniprogram_login_enabled": mini["wechat_miniprogram_login_enabled"],
        "wechat_miniprogram_app_id": mini["wechat_miniprogram_app_id"],
        "wechat_miniprogram_app_secret": mini["wechat_miniprogram_app_secret"],
    }


def _apply_notice_versioning(before_payload: dict, after_payload: dict) -> dict:
    before_notice = _extract_notice_payload(before_payload)
    after_notice = _extract_notice_payload(after_payload)
    changed = (
        before_notice["enabled"] != after_notice["enabled"]
        or before_notice["title"] != after_notice["title"]
        or before_notice["content"] != after_notice["content"]
        or before_notice["header_text"] != after_notice["header_text"]
        or before_notice["level"] != after_notice["level"]
    )
    prev_version = int(before_notice.get("version") or 1)
    if prev_version < 1:
        prev_version = 1
    if changed:
        after_notice["version"] = prev_version + 1
        after_notice["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")
        return after_notice

    current_version = int(after_notice.get("version") or prev_version)
    if current_version < prev_version:
        current_version = prev_version
    after_notice["version"] = current_version
    if not after_notice.get("updated_at"):
        after_notice["updated_at"] = before_notice.get("updated_at", "")
    return after_notice


def _is_private_or_loopback_host(host: str) -> bool:
    normalized = (host or "").strip().lower().strip(".")
    if not normalized:
        return True
    if normalized in {"localhost", "localhost.localdomain"}:
        return True
    if normalized.endswith((".local", ".lan", ".internal", ".home.arpa")):
        return True
    try:
        ip = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    return (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _is_public_https_url(value: str) -> bool:
    if not _is_https_url(value):
        return False
    parsed = urlparse(value)
    return bool(parsed.hostname) and (not _is_private_or_loopback_host(parsed.hostname))


def _normalize_billing_packages(value) -> list[dict]:
    packages = value if isinstance(value, list) else []
    normalized: list[dict] = []
    names: set[str] = set()
    if not packages:
        packages = deepcopy(DEFAULT_BILLING_PACKAGES)
    if len(packages) > 12:
        raise BizError(code=4341, message="套餐数量不能超过 12 个")

    for index, item in enumerate(packages, start=1):
        if not isinstance(item, dict):
            raise BizError(code=4341, message=f"套餐第 {index} 项格式错误")
        name = _as_text(item.get("name"), default="", max_len=32)
        if not name:
            raise BizError(code=4341, message=f"套餐第 {index} 项名称不能为空")
        if name in names:
            raise BizError(code=4341, message=f"套餐名称重复: {name}")
        names.add(name)
        price = round(
            _as_float(
                item.get("price", 0),
                default=0,
                min_value=0.01,
                max_value=100000,
                field=f"{name}.price",
            ),
            2,
        )
        credits = _as_int(
            item.get("credits", 0),
            default=0,
            min_value=1,
            max_value=100_000_000,
            field=f"{name}.credits",
        )
        normalized.append(
            {
                "name": name,
                "price": price,
                "credits": credits,
                "description": _as_text(item.get("description"), default="", max_len=120),
                "badge": _as_text(item.get("badge"), default="", max_len=20),
                "enabled": _as_bool(item.get("enabled", True), default=True),
            }
        )
    if not normalized:
        raise BizError(code=4341, message="至少需要配置 1 个套餐")
    if not any(bool(item.get("enabled", False)) for item in normalized):
        raise BizError(code=4341, message="至少需要启用 1 个套餐")
    return normalized


def _normalize_category_payload(category: str, payload: dict) -> dict:
    base = deepcopy(CONFIG_DEFAULTS[category])
    raw = payload if isinstance(payload, dict) else {}

    if category == "billing":
        base["aigc_rate"] = _as_int(raw.get("aigc_rate", base["aigc_rate"]), default=1, min_value=1, max_value=1000, field="aigc_rate")
        base["dedup_rate"] = _as_int(raw.get("dedup_rate", base["dedup_rate"]), default=3, min_value=1, max_value=1000, field="dedup_rate")
        base["rewrite_rate"] = _as_int(
            raw.get("rewrite_rate", base["rewrite_rate"]),
            default=2,
            min_value=1,
            max_value=1000,
            field="rewrite_rate",
        )
        base["packages"] = _normalize_billing_packages(raw.get("packages", base.get("packages", [])))
        return base

    if category == "user_navigation":
        return normalize_user_navigation_config(raw)

    if category == "llm":
        base["enabled"] = _as_bool(raw.get("enabled", base["enabled"]), default=False)
        provider = normalize_llm_provider(_as_text(raw.get("provider", base["provider"]), default="openai", max_len=64))
        preset = LLM_PROVIDER_PRESETS[provider]
        base["provider"] = provider
        base["base_url"] = _as_text(raw.get("base_url") or preset["base_url"], default=preset["base_url"], max_len=256)
        base["model"] = _as_text(raw.get("model") or preset["model"], default=preset["model"], max_len=128)
        base["api_key"] = _as_text(raw.get("api_key", base["api_key"]), default="", max_len=512)
        base["timeout_seconds"] = _as_int(
            raw.get("timeout_seconds", base["timeout_seconds"]),
            default=25,
            min_value=5,
            max_value=180,
            field="timeout_seconds",
        )
        base["retry_attempts"] = _as_int(
            raw.get("retry_attempts", base["retry_attempts"]),
            default=3,
            min_value=1,
            max_value=5,
            field="retry_attempts",
        )
        base["retry_backoff_seconds"] = round(
            _as_float(
                raw.get("retry_backoff_seconds", base["retry_backoff_seconds"]),
                default=0.8,
                min_value=0.1,
                max_value=5,
                field="retry_backoff_seconds",
            ),
            2,
        )
        base["max_output_tokens"] = _as_int(
            raw.get("max_output_tokens", base["max_output_tokens"]),
            default=2048,
            min_value=128,
            max_value=8192,
            field="max_output_tokens",
        )
        base["temperature"] = round(
            _as_float(raw.get("temperature", base["temperature"]), default=0.3, min_value=0, max_value=2, field="temperature"),
            2,
        )
        if base["enabled"]:
            if not _is_http_url(base["base_url"]):
                raise BizError(code=4341, message="LLM base_url 必须以 http:// 或 https:// 开头")
            if not base["model"]:
                raise BizError(code=4341, message="启用 LLM 时必须填写 model")
            api_key_required = base["provider"] != "local_mock"
            if api_key_required and (not base["api_key"]):
                raise BizError(code=4341, message="启用 LLM 时必须填写 api_key")
        return base

    if category == "payment":
        provider = normalize_payment_provider(_as_text(raw.get("provider", base["provider"]), default="wechatpay_v3", max_len=64))
        if provider and provider not in _PAYMENT_PROVIDERS:
            raise BizError(code=4341, message=f"payment.provider 不支持: {provider}")
        base["provider"] = provider or "wechatpay_v3"
        base["test_mode"] = _as_bool(raw.get("test_mode", base.get("test_mode", settings.payment_test_mode)), default=settings.payment_test_mode)
        base["app_id"] = _as_text(raw.get("app_id", base["app_id"]), default="", max_len=128)
        base["merchant_id"] = _as_text(raw.get("merchant_id", base["merchant_id"]), default="", max_len=128)
        base["merchant_serial_no"] = _as_text(raw.get("merchant_serial_no", base["merchant_serial_no"]), default="", max_len=128)
        base["merchant_private_key_pem"] = _as_text(raw.get("merchant_private_key_pem", base["merchant_private_key_pem"]), default="", max_len=8192)
        base["wechatpay_public_key_id"] = _as_text(raw.get("wechatpay_public_key_id", base["wechatpay_public_key_id"]), default="", max_len=128)
        base["wechatpay_public_key"] = _as_text(raw.get("wechatpay_public_key", base["wechatpay_public_key"]), default="", max_len=8192)
        base["api_v3_key"] = _as_text(raw.get("api_v3_key", base["api_v3_key"]), default="", max_len=64)
        base["notify_url"] = _as_text(raw.get("notify_url", base["notify_url"]), default="", max_len=256)
        base["app_private_key_pem"] = _as_text(raw.get("app_private_key_pem", raw.get("api_key", "")), default="", max_len=8192)
        base["alipay_public_key"] = _as_text(raw.get("alipay_public_key", base.get("alipay_public_key", "")), default="", max_len=8192)
        base["gateway_url"] = _as_text(raw.get("gateway_url", base.get("gateway_url", "")), default="", max_len=256)
        base["api_key"] = _as_text(raw.get("api_key") or raw.get("app_private_key_pem") or base.get("api_key", ""), default="", max_len=8192)
        base["callback_secret"] = _as_text(raw.get("callback_secret", base["callback_secret"]), default="", max_len=512)
        app_private_key = base["app_private_key_pem"] or base["api_key"]
        base["app_private_key_pem"] = app_private_key
        base["api_key"] = app_private_key

        if base["notify_url"] and not _is_http_url(base["notify_url"]):
            raise BizError(code=4341, message="payment.notify_url 必须以 http:// 或 https:// 开头")
        if _has_query_or_fragment(base["notify_url"]):
            raise BizError(code=4341, message="payment.notify_url 不能包含 query 或 fragment")

        if base["gateway_url"] and not _is_http_url(base["gateway_url"]):
            raise BizError(code=4341, message="payment.gateway_url 必须以 http:// 或 https:// 开头")

        if base["provider"] == "mock" and (not base["test_mode"]):
            raise BizError(code=4341, message="payment.provider=mock 仅允许在测试模式下启用")

        if base["provider"] in {"wechat", "wechatpay_v3"}:
            if (not base["test_mode"]) and (not _is_public_https_url(base["notify_url"])):
                raise BizError(code=4341, message="正式微信支付要求 payment.notify_url 为公网 HTTPS 地址")
            required_fields = (
                "app_id",
                "merchant_id",
                "merchant_serial_no",
                "merchant_private_key_pem",
                "api_v3_key",
                "notify_url",
            )
            missing = [field for field in required_fields if not base.get(field)]
            if missing and (not base["test_mode"]):
                raise BizError(code=4341, message=f"微信支付V3缺少必填字段: {','.join(missing)}")
            if base["api_v3_key"] and len(base["api_v3_key"]) != 32:
                raise BizError(code=4341, message="payment.api_v3_key 必须是 32 位字符串")
            if base["merchant_private_key_pem"] and "BEGIN PRIVATE KEY" not in base["merchant_private_key_pem"]:
                raise BizError(code=4341, message="payment.merchant_private_key_pem 格式不正确")
            if bool(base["wechatpay_public_key_id"]) ^ bool(base["wechatpay_public_key"]):
                raise BizError(code=4341, message="wechatpay_public_key_id 和 wechatpay_public_key 必须同时填写")
            if base["wechatpay_public_key"] and "BEGIN PUBLIC KEY" not in base["wechatpay_public_key"]:
                raise BizError(code=4341, message="payment.wechatpay_public_key 格式不正确")

        if base["provider"] in {"custom", "gateway_proxy"} and not base["notify_url"]:
            raise BizError(code=4341, message="网关代理模式必须填写 notify_url")
        if base["provider"] in {"custom", "gateway_proxy"} and (not base["test_mode"]) and (not _is_public_https_url(base["notify_url"])):
            raise BizError(code=4341, message="正式网关代理模式要求 notify_url 为公网 HTTPS 地址")

        if base["provider"] == "alipay" and (not base["test_mode"]) and (
            (not base["app_id"]) or (not base["app_private_key_pem"]) or (not base["alipay_public_key"]) or (not base["notify_url"])
        ):
            raise BizError(code=4341, message="支付宝模式需填写 app_id、app_private_key_pem、alipay_public_key、notify_url")
        if base["provider"] == "alipay" and base["app_private_key_pem"] and ("PRIVATE KEY" not in base.get("app_private_key_pem", "")):
            raise BizError(code=4341, message="payment.app_private_key_pem 格式不正确")
        if base["provider"] == "alipay" and base["alipay_public_key"] and ("PUBLIC KEY" not in base.get("alipay_public_key", "")):
            raise BizError(code=4341, message="payment.alipay_public_key 格式不正确")
        if base["provider"] == "alipay" and (not base["test_mode"]) and (not _is_public_https_url(base["notify_url"])):
            raise BizError(code=4341, message="正式支付宝要求 payment.notify_url 为公网 HTTPS 地址")
        return base

    if category == "notice":
        notice = _extract_notice_payload(raw)
        return _notice_to_notice_fields(notice)

    if category == "miniapp":
        miniapp = _extract_miniapp_payload(raw)
        if miniapp["api_base_url"] and (not _is_http_url(miniapp["api_base_url"])):
            raise BizError(code=4341, message="miniapp.api_base_url 必须以 http:// 或 https:// 开头")
        if miniapp["web_base_url"] and (not _is_http_url(miniapp["web_base_url"])):
            raise BizError(code=4341, message="miniapp.web_base_url 必须以 http:// 或 https:// 开头")
        if miniapp["payment_notify_url"] and (not _is_http_url(miniapp["payment_notify_url"])):
            raise BizError(code=4341, message="miniapp.payment_notify_url 必须以 http:// 或 https:// 开头")
        if miniapp["enabled"] and miniapp["wechat_miniprogram_login_enabled"]:
            if (not miniapp["wechat_miniprogram_app_id"]) or (not miniapp["wechat_miniprogram_app_secret"]):
                raise BizError(code=4341, message="启用小程序登录时必须填写小程序 AppID 与 AppSecret")
        return miniapp

    if category == "login":
        sms_provider = _as_text(raw.get("sms_provider", base["sms_provider"]), default="custom_webhook", max_len=64).lower()
        if sms_provider not in _SMS_PROVIDERS:
            raise BizError(code=4341, message=f"sms_provider 不支持: {sms_provider}")
        base["sms_provider"] = sms_provider
        base["sms_api_key"] = _as_text(raw.get("sms_api_key", base["sms_api_key"]), default="", max_len=512)
        base["sms_gateway_url"] = _as_text(raw.get("sms_gateway_url", base["sms_gateway_url"]), default="", max_len=256)
        base["sms_template_id"] = _as_text(raw.get("sms_template_id", base["sms_template_id"]), default="", max_len=128)
        base["sms_sign_name"] = _as_text(raw.get("sms_sign_name", base["sms_sign_name"]), default="", max_len=128)
        base["sms_sdk_app_id"] = _as_text(raw.get("sms_sdk_app_id", base["sms_sdk_app_id"]), default="", max_len=128)
        base["sms_region"] = _as_text(raw.get("sms_region", base["sms_region"]), default="ap-guangzhou", max_len=64)
        base["sms_aliyun_region_id"] = _as_text(raw.get("sms_aliyun_region_id", base["sms_aliyun_region_id"]), default="cn-hangzhou", max_len=64)
        base["sms_access_key_id"] = _as_text(raw.get("sms_access_key_id", base["sms_access_key_id"]), default="", max_len=256)
        base["sms_access_key_secret"] = _as_text(raw.get("sms_access_key_secret", base["sms_access_key_secret"]), default="", max_len=256)
        base["debug_code_enabled"] = _as_bool(
            raw.get("debug_code_enabled", base["debug_code_enabled"]),
            default=_default_debug_code_enabled(),
        )
        base["wechat_login_enabled"] = _as_bool(raw.get("wechat_login_enabled", base["wechat_login_enabled"]), default=False)
        base["wechat_app_id"] = _as_text(raw.get("wechat_app_id", base["wechat_app_id"]), default="", max_len=128)
        base["wechat_app_secret"] = _as_text(raw.get("wechat_app_secret", base["wechat_app_secret"]), default="", max_len=256)
        base["wechat_redirect_uri"] = _as_text(raw.get("wechat_redirect_uri", base["wechat_redirect_uri"]), default="", max_len=256)
        base["wechat_miniprogram_login_enabled"] = _as_bool(
            raw.get("wechat_miniprogram_login_enabled", base.get("wechat_miniprogram_login_enabled", False)),
            default=False,
        )
        base["wechat_miniprogram_app_id"] = _as_text(
            raw.get("wechat_miniprogram_app_id", base.get("wechat_miniprogram_app_id", "")),
            default="",
            max_len=128,
        )
        base["wechat_miniprogram_app_secret"] = _as_text(
            raw.get("wechat_miniprogram_app_secret", base.get("wechat_miniprogram_app_secret", "")),
            default="",
            max_len=256,
        )
        notice = _extract_notice_payload(raw)
        base.update(_notice_to_login_fields(notice))
        base["new_user_initial_credits"] = _as_int(
            raw.get("new_user_initial_credits", base["new_user_initial_credits"]),
            default=settings.initial_credits,
            min_value=0,
            max_value=1_000_000,
            field="new_user_initial_credits",
        )
        base["max_code_retry"] = _as_int(
            raw.get("max_code_retry", base["max_code_retry"]),
            default=settings.max_code_retry,
            min_value=1,
            max_value=20,
            field="max_code_retry",
        )
        base["phone_lock_minutes"] = _as_int(
            raw.get("phone_lock_minutes", base["phone_lock_minutes"]),
            default=settings.phone_lock_minutes,
            min_value=1,
            max_value=120,
            field="phone_lock_minutes",
        )
        base["send_code_ip_1h_limit"] = _as_int(
            raw.get("send_code_ip_1h_limit", base["send_code_ip_1h_limit"]),
            default=settings.auth_send_code_ip_1h_limit,
            min_value=1,
            max_value=10_000,
            field="send_code_ip_1h_limit",
        )
        base["login_ip_10m_limit"] = _as_int(
            raw.get("login_ip_10m_limit", base["login_ip_10m_limit"]),
            default=settings.auth_login_ip_10m_limit,
            min_value=1,
            max_value=10_000,
            field="login_ip_10m_limit",
        )

        if base["sms_gateway_url"] and (not _is_http_url(base["sms_gateway_url"])):
            raise BizError(code=4341, message="sms_gateway_url 必须以 http:// 或 https:// 开头")
        if base["wechat_redirect_uri"] and (not _is_https_url(base["wechat_redirect_uri"])):
            raise BizError(code=4341, message="wechat_redirect_uri 必须以 https:// 开头")

        if base["wechat_login_enabled"] and (
            (not base["wechat_app_id"]) or (not base["wechat_app_secret"]) or (not base["wechat_redirect_uri"])
        ):
            raise BizError(code=4341, message="启用微信登录时必须填写 app_id、app_secret、redirect_uri")
        if base["wechat_miniprogram_login_enabled"] and (
            (not (base["wechat_miniprogram_app_id"] or base["wechat_app_id"]))
            or (not (base["wechat_miniprogram_app_secret"] or base["wechat_app_secret"]))
        ):
            raise BizError(code=4341, message="启用小程序登录时必须填写小程序 AppID 与 AppSecret（可复用微信登录配置）")

        if base["sms_provider"] == "custom_webhook":
            if (not base["debug_code_enabled"]) and (not base["sms_gateway_url"]) and (not base["wechat_login_enabled"]):
                raise BizError(code=4341, message="登录配置至少需可用一种方式：短信网关、微信登录或debug_code")

        if base["sms_provider"] == "tencent_sms":
            required_fields = ("sms_sdk_app_id", "sms_sign_name", "sms_template_id", "sms_access_key_id", "sms_access_key_secret")
            missing = [field for field in required_fields if not base.get(field)]
            if missing and (not base["debug_code_enabled"]) and (not base["wechat_login_enabled"]):
                raise BizError(code=4341, message=f"腾讯云短信缺少字段: {','.join(missing)}")

        if base["sms_provider"] == "aliyun_sms":
            required_fields = ("sms_sign_name", "sms_template_id", "sms_access_key_id", "sms_access_key_secret")
            missing = [field for field in required_fields if not base.get(field)]
            if missing and (not base["debug_code_enabled"]) and (not base["wechat_login_enabled"]):
                raise BizError(code=4341, message=f"阿里云短信缺少字段: {','.join(missing)}")

        if base["sms_provider"] == "disabled" and (not base["debug_code_enabled"]) and (not base["wechat_login_enabled"]):
            raise BizError(code=4341, message="短信关闭后必须启用微信登录或 debug_code")
        return base

    return base


def _category_readiness(category: str, value: dict) -> dict:
    if category == "billing":
        rate_ok = all(int(value.get(k, 0)) > 0 for k in ("aigc_rate", "dedup_rate", "rewrite_rate"))
        packages = value.get("packages") if isinstance(value.get("packages"), list) else []
        enabled_count = sum(1 for item in packages if isinstance(item, dict) and bool(item.get("enabled")))
        pkg_ok = enabled_count >= 1
        ok = rate_ok and pkg_ok
        if not rate_ok:
            message = "计费单价配置异常"
        elif not pkg_ok:
            message = "至少需启用 1 个充值套餐"
        else:
            message = f"计费与套餐已就绪（启用 {enabled_count} 个套餐）"
        return {"category": category, "status": "ready" if ok else "error", "message": message}
    if category == "user_navigation":
        navigation = normalize_user_navigation_config(value)
        items = navigation.get("items", [])
        visible_count = sum(1 for item in items if item.get("visible"))
        if visible_count <= 0:
            return {"category": category, "status": "error", "message": "前台导航至少需展示 1 个功能"}
        return {"category": category, "status": "ready", "message": f"前台导航已编排（展示 {visible_count} 个功能）"}
    if category == "llm":
        enabled = bool(value.get("enabled"))
        if not enabled:
            return {"category": category, "status": "warning", "message": "LLM 未启用（系统会走算法模式）"}
        provider = normalize_llm_provider(_as_text(value.get("provider"), default="openai", max_len=64))
        api_key_ok = bool(value.get("api_key")) or provider == "local_mock"
        fields_ok = bool(value.get("base_url")) and bool(value.get("model")) and api_key_ok
        return {"category": category, "status": "ready" if fields_ok else "error", "message": "LLM 已就绪" if fields_ok else "LLM 关键字段未填全"}
    if category == "payment":
        provider = normalize_payment_provider(str(value.get("provider", "wechatpay_v3")).lower())
        test_mode = bool(value.get("test_mode", settings.payment_test_mode))
        if provider not in _PAYMENT_PROVIDERS:
            return {"category": category, "status": "error", "message": f"支付通道不支持: {provider or 'unknown'}"}
        if test_mode:
            return {"category": category, "status": "warning", "message": "支付处于联调模式（仅开放 mock 支付）"}
        if provider == "mock":
            return {"category": category, "status": "error", "message": "已关闭测试模式，不可使用 mock 支付"}
        if provider in {"wechat", "wechatpay_v3"}:
            required_fields = (
                "app_id",
                "merchant_id",
                "merchant_serial_no",
                "merchant_private_key_pem",
                "api_v3_key",
                "notify_url",
            )
            missing = [field for field in required_fields if not value.get(field)]
            if missing:
                return {"category": category, "status": "error", "message": f"微信支付V3缺少字段: {','.join(missing)}"}
            if len(str(value.get("api_v3_key", ""))) != 32:
                return {"category": category, "status": "error", "message": "api_v3_key 必须是 32 位"}
            if not _is_public_https_url(str(value.get("notify_url", ""))):
                return {"category": category, "status": "error", "message": "微信支付 notify_url 必须是公网 HTTPS 地址"}
            if "BEGIN PRIVATE KEY" not in str(value.get("merchant_private_key_pem", "")):
                return {"category": category, "status": "error", "message": "merchant_private_key_pem 格式不正确"}
            return {"category": category, "status": "ready", "message": "微信支付V3配置已就绪"}
        if provider in {"custom", "gateway_proxy"}:
            if value.get("notify_url") and _is_public_https_url(str(value.get("notify_url", ""))):
                return {"category": category, "status": "warning", "message": "网关代理仅用于外部网关回调，本平台不直连下单"}
            return {"category": category, "status": "error", "message": "网关代理模式缺少 notify_url"}
        if provider == "alipay":
            private_key = str(value.get("app_private_key_pem") or value.get("api_key") or "")
            if (
                value.get("app_id")
                and private_key
                and value.get("alipay_public_key")
                and value.get("notify_url")
                and _is_public_https_url(str(value.get("notify_url", "")))
                and ("PRIVATE KEY" in private_key)
                and ("PUBLIC KEY" in str(value.get("alipay_public_key", "")))
            ):
                return {"category": category, "status": "ready", "message": "支付宝配置已就绪"}
            return {"category": category, "status": "error", "message": "支付宝缺少 app_id / app_private_key_pem / alipay_public_key / notify_url"}
        return {"category": category, "status": "warning", "message": "支付配置待确认"}
    if category == "notice":
        notice = _extract_notice_payload(value)
        if not notice["enabled"]:
            return {"category": category, "status": "warning", "message": "公告已关闭"}
        if not notice["title"] or not notice["content"]:
            return {"category": category, "status": "error", "message": "公告标题或内容为空"}
        return {"category": category, "status": "ready", "message": f"公告已发布（v{notice['version']}）"}
    if category == "miniapp":
        miniapp = _extract_miniapp_payload(value)
        if not miniapp["enabled"]:
            return {"category": category, "status": "warning", "message": "小程序配置未启用"}
        login_enabled = bool(miniapp.get("wechat_miniprogram_login_enabled"))
        app_id = str(miniapp.get("wechat_miniprogram_app_id") or miniapp.get("app_id") or "")
        app_secret = str(miniapp.get("wechat_miniprogram_app_secret") or miniapp.get("app_secret") or "")
        if login_enabled and (not app_id or not app_secret):
            return {"category": category, "status": "error", "message": "小程序登录已启用但 AppID/AppSecret 未填写完整"}
        if miniapp.get("api_base_url") and not _is_http_url(str(miniapp.get("api_base_url", ""))):
            return {"category": category, "status": "error", "message": "小程序 API 地址格式错误"}
        if miniapp.get("request_domain") and (not _is_https_url(str(miniapp.get("request_domain", "")))):
            return {"category": category, "status": "warning", "message": "request 域名建议使用 HTTPS"}
        return {"category": category, "status": "ready", "message": "小程序配置已就绪"}
    if category == "login":
        debug_enabled = bool(value.get("debug_code_enabled"))
        debug_runtime_enabled = debug_enabled and settings.app_env != "prod"
        sms_provider = str(value.get("sms_provider", "custom_webhook")).lower()
        wechat_enabled = bool(value.get("wechat_login_enabled"))
        sms_ok = False
        wechat_ok = False
        warnings: list[str] = []
        if debug_enabled and settings.app_env == "prod":
            warnings.append("生产环境不会返回 debug_code")

        if sms_provider == "custom_webhook":
            sms_ok = bool(value.get("sms_gateway_url"))
            if not sms_ok:
                warnings.append("未配置短信网关")
        elif sms_provider == "tencent_sms":
            sms_ok = all(
                bool(value.get(field))
                for field in ("sms_sdk_app_id", "sms_sign_name", "sms_template_id", "sms_access_key_id", "sms_access_key_secret")
            )
            if not sms_ok:
                warnings.append("腾讯云短信字段不完整")
        elif sms_provider == "aliyun_sms":
            sms_ok = all(bool(value.get(field)) for field in ("sms_sign_name", "sms_template_id", "sms_access_key_id", "sms_access_key_secret"))
            if not sms_ok:
                warnings.append("阿里云短信字段不完整")
            else:
                warnings.append("请确认阿里云账号已具备目标地区短信发送资质")
        elif sms_provider == "disabled":
            warnings.append("短信登录已关闭")

        if wechat_enabled:
            wechat_ok = all(bool(value.get(field)) for field in ("wechat_app_id", "wechat_app_secret", "wechat_redirect_uri"))
            if not wechat_ok:
                warnings.append("微信登录字段不完整")
            elif not _is_public_https_url(str(value.get("wechat_redirect_uri", ""))):
                warnings.append("微信回调地址需为公网 HTTPS")

        miniapp_enabled = bool(value.get("wechat_miniprogram_login_enabled"))
        miniapp_ok = False
        if miniapp_enabled:
            miniapp_ok = bool(value.get("wechat_miniprogram_app_id") or value.get("wechat_app_id")) and bool(
                value.get("wechat_miniprogram_app_secret") or value.get("wechat_app_secret")
            )
            if not miniapp_ok:
                warnings.append("小程序登录字段不完整")

        any_login_path = debug_runtime_enabled or sms_ok or wechat_ok or miniapp_ok
        if not any_login_path:
            return {"category": category, "status": "error", "message": "登录配置不可用：请至少启用一种登录路径"}
        if warnings:
            return {"category": category, "status": "warning", "message": "；".join(warnings)}
        return {"category": category, "status": "ready", "message": "短信与微信登录配置已就绪"}
    return {"category": category, "status": "warning", "message": "未知分类"}


def _get_category_config(db: Session, category: str, *, redact: bool = False) -> dict:
    source = _read_system_config_raw(db, category)
    if category == "user_navigation":
        return normalize_user_navigation_config(source)
    if category == "notice" and (not source):
        source = _notice_to_notice_fields(_extract_notice_payload(_read_system_config_raw(db, "login")))
    if category == "miniapp" and (not source):
        source = _extract_miniapp_payload(_read_system_config_raw(db, "login"))
    merged = deepcopy(CONFIG_DEFAULTS[category])
    if category == "login" and "debug_code_enabled" not in source:
        merged["debug_code_enabled"] = _default_debug_code_enabled()
    merged.update(source)
    if category == "llm":
        provider = normalize_llm_provider(merged.get("provider"))
        preset = LLM_PROVIDER_PRESETS[provider]
        merged["provider"] = provider
        merged["base_url"] = merged.get("base_url") or preset["base_url"]
        merged["model"] = merged.get("model") or preset["model"]
    if category == "payment":
        merged["provider"] = normalize_payment_provider(merged.get("provider"))
        merged["gateway_url"] = _as_text(
            merged.get("gateway_url", DEFAULT_PAYMENT_CONFIG.get("gateway_url", "")),
            default=DEFAULT_PAYMENT_CONFIG.get("gateway_url", ""),
            max_len=256,
        )
        merged["app_private_key_pem"] = _as_text(
            merged.get("app_private_key_pem") or merged.get("api_key"),
            default="",
            max_len=8192,
        )
        merged["api_key"] = _as_text(merged.get("api_key") or merged.get("app_private_key_pem"), default="", max_len=8192)
    if category == "billing":
        try:
            merged["packages"] = _normalize_billing_packages(merged.get("packages"))
        except BizError:
            merged["packages"] = deepcopy(DEFAULT_BILLING_PACKAGES)
    if category == "notice":
        return _notice_to_notice_fields(_extract_notice_payload(merged))
    if category == "miniapp":
        return _extract_miniapp_payload(merged)
    if category == "login":
        notice_cfg = _read_system_config_raw(db, "notice")
        if notice_cfg:
            merged.update(_notice_to_login_fields(notice_cfg))
        miniapp_cfg = _read_system_config_raw(db, "miniapp")
        if miniapp_cfg:
            mini_login_fields = _miniapp_to_login_fields(miniapp_cfg)
            merged.update(mini_login_fields)
            if not merged.get("wechat_miniprogram_app_id"):
                merged["wechat_miniprogram_app_id"] = _as_text(miniapp_cfg.get("app_id"), default="", max_len=128)
            if not merged.get("wechat_miniprogram_app_secret"):
                merged["wechat_miniprogram_app_secret"] = _as_text(miniapp_cfg.get("app_secret"), default="", max_len=256)

        merged["sms_provider"] = _as_text(merged.get("sms_provider", "custom_webhook"), default="custom_webhook", max_len=64).lower()
        merged["wechat_miniprogram_login_enabled"] = _as_bool(
            merged.get("wechat_miniprogram_login_enabled", False),
            default=False,
        )
        merged["wechat_miniprogram_app_id"] = _as_text(merged.get("wechat_miniprogram_app_id", ""), default="", max_len=128)
        merged["wechat_miniprogram_app_secret"] = _as_text(merged.get("wechat_miniprogram_app_secret", ""), default="", max_len=256)
        merged.update(_notice_to_login_fields(merged))
        merged["new_user_initial_credits"] = _as_int(
            merged.get("new_user_initial_credits", settings.initial_credits),
            default=settings.initial_credits,
            min_value=0,
            max_value=1_000_000,
            field="new_user_initial_credits",
        )
        merged["max_code_retry"] = _as_int(
            merged.get("max_code_retry", settings.max_code_retry),
            default=settings.max_code_retry,
            min_value=1,
            max_value=20,
            field="max_code_retry",
        )
        merged["phone_lock_minutes"] = _as_int(
            merged.get("phone_lock_minutes", settings.phone_lock_minutes),
            default=settings.phone_lock_minutes,
            min_value=1,
            max_value=120,
            field="phone_lock_minutes",
        )
        merged["send_code_ip_1h_limit"] = _as_int(
            merged.get("send_code_ip_1h_limit", settings.auth_send_code_ip_1h_limit),
            default=settings.auth_send_code_ip_1h_limit,
            min_value=1,
            max_value=10_000,
            field="send_code_ip_1h_limit",
        )
        merged["login_ip_10m_limit"] = _as_int(
            merged.get("login_ip_10m_limit", settings.auth_login_ip_10m_limit),
            default=settings.auth_login_ip_10m_limit,
            min_value=1,
            max_value=10_000,
            field="login_ip_10m_limit",
        )
    if redact:
        return _redact_config_view(category, merged)
    return merged


def _config_label(category: str) -> str:
    return CONFIG_LABELS.get(category, category)


def _config_field_label(category: str, field: str) -> str:
    category_labels = CONFIG_FIELD_LABELS.get(category, {})
    return category_labels.get(field, field)


def _changed_config_fields(before: dict | None, after: dict | None) -> list[str]:
    before_map = before if isinstance(before, dict) else {}
    after_map = after if isinstance(after, dict) else {}
    all_keys = sorted(set(before_map.keys()) | set(after_map.keys()))
    return [key for key in all_keys if before_map.get(key) != after_map.get(key)]


def _config_change_summary(category: str, changed_fields: list[str]) -> str:
    label = _config_label(category)
    if not changed_fields:
        return f"{label} 已重新保存"
    preview = "、".join(_config_field_label(category, field) for field in changed_fields[:3])
    if len(changed_fields) > 3:
        preview = f"{preview} 等 {len(changed_fields)} 项"
    return f"{label} 更新了 {preview}"


def _save_category_config(db: Session, category: str, value: dict, admin: AdminUser) -> dict:
    row = (
        db.query(SystemConfig)
        .filter(SystemConfig.category == "system", SystemConfig.config_key == category)
        .first()
    )
    before = deepcopy(CONFIG_DEFAULTS[category])
    if row is not None and isinstance(row.config_value, dict):
        before = row.config_value

    notice_sync_payload: dict | None = None
    miniapp_sync_payload: dict | None = None
    if category == "notice":
        next_notice = _apply_notice_versioning(before, value)
        value = _notice_to_notice_fields(next_notice)
        notice_sync_payload = value
    elif category == "miniapp":
        value = _extract_miniapp_payload(value)
        miniapp_sync_payload = value
    elif category == "login":
        notice_before = _read_system_config_raw(db, "notice")
        if not notice_before:
            notice_before = _extract_notice_payload(before)
        notice_after = _apply_notice_versioning(notice_before, value)
        notice_sync_payload = _notice_to_notice_fields(notice_after)
        value.update(_notice_to_login_fields(notice_after))
        miniapp_sync_payload = _extract_miniapp_payload(value)

    if row is None:
        row = SystemConfig(
            category="system",
            config_key=category,
            config_value=value,
            updated_by=admin.id,
        )
        db.add(row)
    else:
        row.config_value = value
        row.updated_by = admin.id

    audit_before, audit_after = _redact_config_audit_pair(category, before, value)
    db.add(
        AdminAuditLog(
            admin_id=admin.id,
            action="config_update",
            target_type=category,
            target_id=category,
            before_json=audit_before,
            after_json=audit_after,
        )
    )

    if category == "notice" and notice_sync_payload is not None:
        login_existing = _read_system_config_raw(db, "login")
        login_value = deepcopy(CONFIG_DEFAULTS["login"])
        login_value.update(login_existing)
        login_value.update(_notice_to_login_fields(notice_sync_payload))
        _upsert_system_config_raw(db, key="login", value=login_value, updated_by=admin.id)

    if category == "miniapp" and miniapp_sync_payload is not None:
        login_existing = _read_system_config_raw(db, "login")
        login_value = deepcopy(CONFIG_DEFAULTS["login"])
        login_value.update(login_existing)
        login_value.update(_miniapp_to_login_fields(miniapp_sync_payload))
        _upsert_system_config_raw(db, key="login", value=login_value, updated_by=admin.id)

    if category == "login":
        if notice_sync_payload is not None:
            _upsert_system_config_raw(db, key="notice", value=notice_sync_payload, updated_by=admin.id)
        if miniapp_sync_payload is not None:
            _upsert_system_config_raw(db, key="miniapp", value=miniapp_sync_payload, updated_by=admin.id)

    db.flush()
    return value


def _platform_label(platform: str) -> str:
    mapping = {
        "cnki": "知网",
        "vip": "维普",
        "paperpass": "PaperPass",
    }
    return mapping.get(platform, platform)


def _task_type_label(task_type: str) -> str:
    mapping = {
        "aigc_detect": "AIGC检测",
        "rewrite": "学术润色",
        "dedup": "降重复率",
    }
    return mapping.get(task_type, task_type)


@router.post("/auth/login", response_model=APIResp)
def admin_login(
    req: AdminLoginReq,
    request: Request,
    response: Response,
    db: Session = Depends(db_dep),
    redis_client=Depends(get_redis),
) -> APIResp:
    _assert_admin_ip_allowed(request)
    username = str(req.username or "").strip()
    _enforce_admin_login_rate_limit(
        redis_client,
        ip=_request_client_ip(request),
        username=username,
    )
    admin = db.query(AdminUser).filter(AdminUser.username == username).first()
    if admin is None or not verify_password(req.password, admin.password_hash):
        _record_admin_login_failure(redis_client, username=username)
        raise BizError(code=4301, message="管理员账号或密码错误")
    if not bool(getattr(admin, "is_active", True)):
        raise BizError(code=4309, message="管理员账号已停用，请联系超级管理员")
    _clear_admin_login_failures(redis_client, username=username)
    admin.last_login = datetime.utcnow()
    db.commit()
    token, refresh_token = _issue_admin_auth(redis_client, response, admin)
    return ok(
        data={
            "token": token,
            "refresh_token": refresh_token,
            "admin": _admin_payload(admin),
            "permission_catalog": ADMIN_PERMISSION_CATALOG,
            "permission_templates": _permission_templates_payload(),
        }
    )


@router.post("/auth/refresh", response_model=APIResp)
def admin_refresh(
    response: Response,
    payload: dict | None = Body(default=None),
    refresh_cookie: str | None = Cookie(default=None, alias=settings.admin_refresh_cookie_name),
    db: Session = Depends(db_dep),
    redis_client=Depends(get_redis),
) -> APIResp:
    refresh_token = str((payload or {}).get("refresh_token") or refresh_cookie or "").strip()
    if not refresh_token:
        raise BizError(code=4311, message="refresh token missing", http_status=401)
    try:
        decoded = decode_token(refresh_token)
    except ValueError as exc:
        raise BizError(code=4312, message="refresh token invalid", http_status=401) from exc
    if decoded.get("scope") != "admin" or str(decoded.get("typ") or "").strip().lower() != REFRESH_TOKEN_TYPE:
        raise BizError(code=4312, message="refresh token invalid", http_status=401)
    admin = db.get(AdminUser, int(decoded["sub"]))
    if admin is None or not bool(getattr(admin, "is_active", True)):
        raise BizError(code=4309, message="管理员账号已停用，请联系超级管理员", http_status=401)
    session_version = str(decoded.get("sv") or "").strip()
    current_version = _load_admin_session(redis_client, admin_id=admin.id)
    if not session_version or not current_version or session_version != current_version:
        raise BizError(code=4312, message="refresh token revoked", http_status=401)
    token, next_refresh_token = _issue_admin_auth(redis_client, response, admin)
    return ok(
        data={
            "token": token,
            "refresh_token": next_refresh_token,
            "admin": _admin_payload(admin),
            "permission_catalog": ADMIN_PERMISSION_CATALOG,
            "permission_templates": _permission_templates_payload(),
        }
    )


@router.post("/auth/logout", response_model=APIResp)
def admin_logout(
    response: Response,
    admin: AdminUser = Depends(current_admin),
    redis_client=Depends(get_redis),
) -> APIResp:
    _clear_admin_session(redis_client, admin_id=admin.id)
    response.delete_cookie(ADMIN_ACCESS_COOKIE_NAME, path="/")
    response.delete_cookie(settings.admin_refresh_cookie_name, path="/api/v1/admin/auth")
    return ok(data={"logged_out": True})


@router.get("/admin-users", response_model=APIResp)
def list_admin_users(
    keyword: str | None = Query(default=None),
    role: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    _: AdminUser = Depends(require_admin_permission("admins:view")),
    db: Session = Depends(db_dep),
) -> APIResp:
    query = db.query(AdminUser)
    if keyword:
        raw = str(keyword).strip()
        if raw:
            query = query.filter(AdminUser.username.like(f"%{raw}%"))
    if role:
        role_val = str(role).strip().lower()
        if role_val in {"super_admin", "operator"}:
            query = query.filter(AdminUser.role == role_val)
    if is_active is not None:
        query = query.filter(AdminUser.is_active == bool(is_active))

    rows = query.order_by(desc(AdminUser.created_at)).all()
    total_count = db.query(func.count(AdminUser.id)).scalar() or 0
    active_count = db.query(func.count(AdminUser.id)).filter(AdminUser.is_active == True).scalar() or 0  # noqa: E712
    inactive_count = max(int(total_count) - int(active_count), 0)
    return ok(
        data={
            "items": [_admin_payload(row) for row in rows],
            "permission_catalog": ADMIN_PERMISSION_CATALOG,
            "permission_templates": _permission_templates_payload(),
            "summary": {
                "total": int(total_count),
                "active": int(active_count),
                "inactive": int(inactive_count),
            },
        }
    )


@router.post("/admin-users", response_model=APIResp)
def create_admin_user(
    payload: dict,
    actor: AdminUser = Depends(require_admin_permission("admins:manage")),
    db: Session = Depends(db_dep),
) -> APIResp:
    if not isinstance(payload, dict):
        raise BizError(code=4302, message="请求体必须为 JSON 对象")
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", "")).strip()
    role = str(payload.get("role", "operator")).strip().lower() or "operator"
    is_active = bool(payload.get("is_active", True))
    if len(username) < 3:
        raise BizError(code=4303, message="管理员用户名至少 3 位")
    if not ADMIN_USERNAME_RE.fullmatch(username):
        raise BizError(code=4312, message="用户名仅支持字母开头，且只能包含字母/数字/._-（3~32 位）")
    if len(password) < 8:
        raise BizError(code=4304, message="管理员密码至少 8 位")
    if role == "super_admin":
        raise BizError(code=4305, message="禁止通过该接口创建超级管理员")
    if db.query(AdminUser.id).filter(func.lower(AdminUser.username) == username.lower()).first():
        raise BizError(code=4306, message="管理员用户名已存在")

    permissions = payload.get("permissions")
    if permissions is None:
        normalized_permissions = sorted(DEFAULT_OPERATOR_PERMISSIONS)
    else:
        normalized_permissions = _normalize_permission_list(permissions)
        if not normalized_permissions:
            raise BizError(code=4313, message="至少需要分配 1 项权限")
    _assert_actor_can_assign_permissions(actor, normalized_permissions)

    row = AdminUser(
        username=username,
        password_hash=hash_password(password),
        role=role,
        is_active=is_active,
        permissions_json=normalized_permissions,
    )
    db.add(row)
    db.flush()
    db.add(
        AdminAuditLog(
            admin_id=actor.id,
            action="admin_create",
            target_type="admin_user",
            target_id=str(row.id),
            before_json=None,
            after_json={
                "username": row.username,
                "role": row.role,
                "is_active": row.is_active,
                "permissions": normalized_permissions,
            },
        )
    )
    db.commit()
    db.refresh(row)
    return ok(data={"admin": _admin_payload(row)})


@router.post("/admin-users/{admin_id}/permissions", response_model=APIResp)
def update_admin_permissions(
    admin_id: int,
    payload: dict,
    actor: AdminUser = Depends(require_admin_permission("admins:manage")),
    db: Session = Depends(db_dep),
) -> APIResp:
    if not isinstance(payload, dict):
        raise BizError(code=4302, message="请求体必须为 JSON 对象")
    target = db.get(AdminUser, admin_id)
    if target is None:
        raise BizError(code=4307, message="管理员不存在", http_status=404)
    if actor.role != "super_admin" and target.role == "super_admin":
        raise BizError(code=4316, message="仅超级管理员可修改超级管理员账号")
    if target.role == "super_admin":
        raise BizError(code=4310, message="超级管理员权限固定为全量权限")
    permissions = _normalize_permission_list(payload.get("permissions", []))
    if not permissions:
        raise BizError(code=4313, message="至少需要分配 1 项权限")
    _assert_actor_can_assign_permissions(actor, permissions)
    before = _effective_admin_permissions(target)
    target.permissions_json = permissions
    db.add(
        AdminAuditLog(
            admin_id=actor.id,
            action="admin_permissions_update",
            target_type="admin_user",
            target_id=str(target.id),
            before_json={"permissions": before},
            after_json={"permissions": permissions},
        )
    )
    db.commit()
    db.refresh(target)
    return ok(data={"admin": _admin_payload(target)})


@router.post("/admin-users/{admin_id}/password", response_model=APIResp)
def reset_admin_password(
    admin_id: int,
    payload: dict,
    actor: AdminUser = Depends(require_admin_permission("admins:manage")),
    db: Session = Depends(db_dep),
) -> APIResp:
    if not isinstance(payload, dict):
        raise BizError(code=4302, message="请求体必须为 JSON 对象")
    auto_generate = bool(payload.get("auto_generate", False))
    password = str(payload.get("password", "")).strip()
    if not password and auto_generate:
        password = _generate_admin_password()
    if len(password) < 8:
        raise BizError(code=4304, message="管理员密码至少 8 位")
    target = db.get(AdminUser, admin_id)
    if target is None:
        raise BizError(code=4307, message="管理员不存在", http_status=404)
    if actor.role != "super_admin" and target.role == "super_admin":
        raise BizError(code=4316, message="仅超级管理员可修改超级管理员账号")
    target.password_hash = hash_password(password)
    db.add(
        AdminAuditLog(
            admin_id=actor.id,
            action="admin_password_reset",
            target_type="admin_user",
            target_id=str(target.id),
            before_json=None,
            after_json={"password_reset": True},
        )
    )
    db.commit()
    db.refresh(target)
    return ok(
        data={
            "admin": _admin_payload(target),
            "generated_password": password if auto_generate else None,
        }
    )


@router.post("/admin-users/{admin_id}/status", response_model=APIResp)
def update_admin_status(
    admin_id: int,
    payload: dict,
    actor: AdminUser = Depends(require_admin_permission("admins:manage")),
    db: Session = Depends(db_dep),
) -> APIResp:
    if not isinstance(payload, dict):
        raise BizError(code=4302, message="请求体必须为 JSON 对象")
    target = db.get(AdminUser, admin_id)
    if target is None:
        raise BizError(code=4307, message="管理员不存在", http_status=404)
    if actor.role != "super_admin" and target.role == "super_admin":
        raise BizError(code=4316, message="仅超级管理员可修改超级管理员账号")
    next_status = bool(payload.get("is_active", True))
    if actor.id == target.id and not next_status:
        raise BizError(code=4314, message="当前登录管理员账号不可自行停用")
    if target.role == "super_admin" and not next_status:
        raise BizError(code=4311, message="超级管理员账号不可停用")
    before = bool(getattr(target, "is_active", True))
    target.is_active = next_status
    db.add(
        AdminAuditLog(
            admin_id=actor.id,
            action="admin_status_update",
            target_type="admin_user",
            target_id=str(target.id),
            before_json={"is_active": before},
            after_json={"is_active": next_status},
        )
    )
    db.commit()
    db.refresh(target)
    return ok(data={"admin": _admin_payload(target)})


@router.get("/dashboard", response_model=APIResp)
def dashboard(_: AdminUser = Depends(require_admin_permission("dashboard:view")), db: Session = Depends(db_dep)) -> APIResp:
    total_users = db.query(User).count()
    total_tasks = db.query(Task).count()
    total_orders = db.query(Order).filter(Order.status == "paid").count()
    total_revenue = db.query(func.coalesce(func.sum(Order.amount_cny), 0)).filter(Order.status == "paid").scalar() or 0
    users_by_source = db.query(User.source, func.count(User.id)).group_by(User.source).all()
    tasks_by_source = db.query(Task.source, func.count(Task.id)).group_by(Task.source).all()
    paid_orders_by_source = (
        db.query(Order.source, func.count(Order.id))
        .filter(Order.status == "paid")
        .group_by(Order.source)
        .all()
    )
    paid_revenue_by_source = (
        db.query(Order.source, func.coalesce(func.sum(Order.amount_cny), 0))
        .filter(Order.status == "paid")
        .group_by(Order.source)
        .all()
    )

    start_date = date.today() - timedelta(days=29)
    task_rows = (
        db.query(func.date(Task.created_at).label("d"), func.count(Task.id))
        .filter(Task.created_at >= start_date)
        .group_by(func.date(Task.created_at))
        .all()
    )
    revenue_rows = (
        db.query(func.date(Order.created_at).label("d"), func.coalesce(func.sum(Order.amount_cny), 0))
        .filter(Order.status == "paid", Order.created_at >= start_date)
        .group_by(func.date(Order.created_at))
        .all()
    )
    task_map = {str(d): int(v) for d, v in task_rows}
    revenue_map = {str(d): cny_to_api(v) for d, v in revenue_rows}
    trend = []
    for i in range(30):
        d = start_date + timedelta(days=i)
        ds = d.isoformat()
        trend.append({"date": ds, "tasks": task_map.get(ds, 0), "revenue": revenue_map.get(ds, 0.0)})

    by_type = (
        db.query(Task.task_type, func.count(Task.id))
        .group_by(Task.task_type)
        .all()
    )
    type_dist = [{"task_type": t.value if isinstance(t, TaskType) else str(t), "count": int(c)} for t, c in by_type]
    platform_dist = (
        db.query(Task.platform, func.count(Task.id))
        .group_by(Task.platform)
        .all()
    )
    platform_items = [{"platform": p, "count": int(c)} for p, c in platform_dist]
    funnel = {
        "visitors": total_users * 3,
        "registered": total_users,
        "paid_users": db.query(Order.user_id).filter(Order.status == "paid").distinct().count(),
        "task_users": db.query(Task.user_id).distinct().count(),
    }
    switch = db.query(SystemSwitch).first()
    last_switch_log = db.query(SwitchLog).order_by(desc(SwitchLog.created_at)).first()
    return ok(
        data={
            "overview": {
                "total_users": total_users,
                "total_tasks": total_tasks,
                "total_orders": total_orders,
                "total_revenue": cny_to_api(total_revenue),
            },
            "trend_30d": trend,
            "task_type_dist": type_dist,
            "platform_dist": platform_items,
            "funnel": funnel,
            "source_stats": {
                "users": _build_source_stats(users_by_source, as_float=False),
                "tasks": _build_source_stats(tasks_by_source, as_float=False),
                "paid_orders": _build_source_stats(paid_orders_by_source, as_float=False),
                "revenue": _build_source_stats(paid_revenue_by_source, as_float=True),
            },
            "switch_status": {
                "current_mode": switch.current_mode if switch else "LLM_PLUS_ALGO",
                "llm_fail_count": switch.llm_fail_count if switch else 0,
                "llm_fail_threshold": switch.llm_fail_threshold if switch else 3,
                "last_switch_time": last_switch_log.created_at if last_switch_log else None,
                "last_switch_reason": last_switch_log.reason if last_switch_log else "",
            },
        }
    )


@router.get("/switch/current", response_model=APIResp)
def switch_current(_: AdminUser = Depends(require_admin_permission("dashboard:view")), db: Session = Depends(db_dep)) -> APIResp:
    switch = db.query(SystemSwitch).first()
    if switch is None:
        switch = SystemSwitch(
            current_mode="LLM_PLUS_ALGO",
            llm_enabled=True,
            llm_fail_count=0,
            llm_fail_threshold=3,
        )
        db.add(switch)
        db.commit()
    return ok(
        data={
            "current_mode": switch.current_mode,
            "llm_enabled": switch.llm_enabled,
            "llm_fail_count": switch.llm_fail_count,
            "llm_fail_threshold": switch.llm_fail_threshold,
            "updated_at": switch.updated_at,
        }
    )


@router.post("/switch/mode", response_model=APIResp)
def switch_mode(
    payload: dict,
    admin: AdminUser = Depends(require_admin_permission("system:manage")),
    db: Session = Depends(db_dep),
) -> APIResp:
    mode = str(payload.get("mode", "")).strip().upper()
    if mode not in {"LLM_PLUS_ALGO", "ALGO_ONLY"}:
        raise BizError(code=4342, message="mode 必须为 LLM_PLUS_ALGO 或 ALGO_ONLY")
    switch = db.query(SystemSwitch).first()
    if switch is None:
        switch = SystemSwitch(
            current_mode=mode,
            llm_enabled=True,
            llm_fail_count=0,
            llm_fail_threshold=3,
        )
        db.add(switch)
        db.flush()
    from_mode = switch.current_mode
    switch.current_mode = mode
    if mode == "LLM_PLUS_ALGO":
        switch.llm_fail_count = 0
    db.add(
        SwitchLog(
            from_mode=from_mode,
            to_mode=mode,
            reason=f"manual_switch_by:{admin.username}",
        )
    )
    db.commit()
    return ok(data={"current_mode": switch.current_mode})


@router.get("/switch/logs", response_model=APIResp)
def switch_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: AdminUser = Depends(require_admin_permission("logs:view")),
    db: Session = Depends(db_dep),
) -> APIResp:
    base_query = db.query(SwitchLog)
    total = base_query.count()
    rows = (
        base_query.order_by(desc(SwitchLog.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        {
            "id": row.id,
            "from_mode": row.from_mode,
            "to_mode": row.to_mode,
            "reason": row.reason,
            "created_at": row.created_at,
        }
        for row in rows
    ]
    return ok(data={"items": items, "pagination": paginate(total, page, page_size)})


@router.get("/llm-error-logs", response_model=APIResp)
def llm_error_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    error_type: str | None = Query(default=None),
    _: AdminUser = Depends(require_admin_permission("logs:view")),
    db: Session = Depends(db_dep),
) -> APIResp:
    base_query = db.query(LLMErrorLog)
    if error_type:
        base_query = base_query.filter(LLMErrorLog.error_type == error_type.strip())
    total = base_query.count()
    rows = (
        base_query.order_by(desc(LLMErrorLog.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        {
            "id": row.id,
            "task_id": row.task_id,
            "error_type": row.error_type,
            "error_detail": row.error_detail,
            "trigger_downgrade": row.trigger_downgrade,
            "created_at": row.created_at,
        }
        for row in rows
    ]
    return ok(data={"items": items, "pagination": paginate(total, page, page_size)})


@router.get("/users", response_model=APIResp)
def admin_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None),
    source: str | None = Query(default=None),
    _: AdminUser = Depends(require_admin_permission("users:view")),
    db: Session = Depends(db_dep),
) -> APIResp:
    base_query = db.query(User)
    if q:
        base_query = _apply_phone_filter(base_query, q)
    source_filter = _normalize_source_filter(source)
    base_query = _apply_source_filter(base_query, User.source, source_filter)
    source_rows = base_query.with_entities(User.source, func.count(User.id)).group_by(User.source).all()
    total = base_query.count()
    rows = (
        base_query.order_by(desc(User.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        {
            "id": u.id,
            "phone": u.phone,
            "nickname": u.nickname,
            "credits": u.credits,
            "is_banned": u.is_banned,
            "source": _normalize_source_bucket(u.source),
            "created_at": u.created_at,
        }
        for u in rows
    ]
    return ok(
        data={
            "items": items,
            "pagination": paginate(total, page, page_size),
            "source_filter": source_filter or "all",
            "source_stats": _build_source_stats(source_rows, as_float=False),
        }
    )


@router.post("/users/{user_id}/adjust-credits", response_model=APIResp)
def adjust_user_credits(
    user_id: int,
    req: AdminAdjustCreditReq,
    admin: AdminUser = Depends(require_admin_permission("users:manage")),
    db: Session = Depends(db_dep),
) -> APIResp:
    user = db.get(User, user_id)
    if user is None:
        raise BizError(code=4040, message="用户不存在", http_status=404)
    if req.delta == 0:
        raise BizError(code=4302, message="调整值不能为0")
    before_credits = int(user.credits)
    change_credits(
        db,
        user,
        tx_type=CreditType.ADMIN_ADJUST,
        delta=req.delta,
        reason=f"管理员[{admin.username}]调整积分:{req.reason}",
        related_id=f"admin_adjust:{admin.id}:{datetime.utcnow().timestamp()}",
        source="admin",
    )
    db.add(
        AdminAuditLog(
            admin_id=admin.id,
            action="user_credit_adjust",
            target_type="user",
            target_id=str(user.id),
            before_json={"credits": before_credits, "delta": req.delta},
            after_json={"credits": int(user.credits), "delta": req.delta, "reason": req.reason},
        )
    )
    db.commit()
    return ok(data={"user_id": user.id, "credits": user.credits})


@router.post("/users/{user_id}/ban", response_model=APIResp)
def ban_or_unban_user(
    user_id: int,
    payload: dict,
    admin: AdminUser = Depends(require_admin_permission("users:manage")),
    db: Session = Depends(db_dep),
) -> APIResp:
    user = db.get(User, user_id)
    if user is None:
        raise BizError(code=4040, message="用户不存在", http_status=404)
    is_banned = bool(payload.get("is_banned", True))
    user.is_banned = is_banned
    db.add(
        AdminAuditLog(
            admin_id=admin.id,
            action="user_ban_toggle",
            target_type="user",
            target_id=str(user.id),
            before_json={"is_banned": (not is_banned)},
            after_json={"is_banned": is_banned},
        )
    )
    db.commit()
    return ok(data={"user_id": user.id, "is_banned": user.is_banned})


@router.get("/users/{user_id}/detail", response_model=APIResp)
def user_detail(
    user_id: int,
    _: AdminUser = Depends(require_admin_permission("users:view")),
    db: Session = Depends(db_dep),
) -> APIResp:
    user = db.get(User, user_id)
    if user is None:
        raise BizError(code=4040, message="用户不存在", http_status=404)

    tx_rows = (
        db.query(CreditTransaction)
        .filter(CreditTransaction.user_id == user.id)
        .order_by(desc(CreditTransaction.id))
        .limit(20)
        .all()
    )
    task_rows = (
        db.query(Task)
        .filter(Task.user_id == user.id)
        .order_by(desc(Task.id))
        .limit(20)
        .all()
    )
    orders = db.query(Order).filter(Order.user_id == user.id, Order.status == "paid").all()
    total_paid_cny = cny_to_api(cny_sum(o.amount_cny for o in orders))
    total_paid_credits = int(sum(int(o.credits) for o in orders))
    total_task_cost = int(
        db.query(func.coalesce(func.sum(Task.cost_credits), 0))
        .filter(Task.user_id == user.id)
        .scalar()
        or 0
    )
    return ok(
        data={
            "user": {
                "id": user.id,
                "phone": user.phone,
                "nickname": user.nickname,
                "credits": user.credits,
                "is_banned": user.is_banned,
                "source": _normalize_source_bucket(user.source),
                "created_at": user.created_at,
            },
            "summary": {
                "total_paid_cny": total_paid_cny,
                "total_paid_credits": total_paid_credits,
                "total_task_cost_credits": total_task_cost,
            },
            "credit_transactions": [
                {
                    "id": tx.id,
                    "tx_type": tx.tx_type.value,
                    "delta": tx.delta,
                    "balance_before": tx.balance_before,
                    "balance_after": tx.balance_after,
                    "reason": tx.reason,
                    "created_at": tx.created_at,
                }
                for tx in tx_rows
            ],
            "tasks": [
                {
                    "id": t.id,
                    "task_type": t.task_type.value,
                    "platform": t.platform,
                    "status": t.status.value,
                    "char_count": t.char_count,
                    "cost_credits": t.cost_credits,
                    "source_filename": t.source_filename,
                    "report_path": t.report_path,
                    "output_path": t.output_path,
                    "error_message": t.error_message,
                    "result_json": t.result_json,
                    "created_at": t.created_at,
                    "updated_at": t.updated_at,
                }
                for t in task_rows
            ],
        }
    )


@router.get("/tasks", response_model=APIResp)
def admin_tasks(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q_phone: str | None = Query(default=None),
    source: str | None = Query(default=None),
    task_type: str | None = Query(default=None),
    platform: str | None = Query(default=None),
    status: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    _: AdminUser = Depends(require_admin_permission("tasks:view")),
    db: Session = Depends(db_dep),
) -> APIResp:
    base_query = db.query(Task).join(User, User.id == Task.user_id)
    source_filter = _normalize_source_filter(source)
    if q_phone:
        base_query = _apply_phone_filter(base_query, q_phone)
    if source_filter:
        base_query = _apply_source_filter(base_query, Task.source, source_filter)
    if task_type:
        try:
            base_query = base_query.filter(Task.task_type == TaskType(task_type))
        except Exception:
            raise BizError(code=4343, message="task_type 不支持")
    if platform:
        base_query = base_query.filter(Task.platform == platform.strip().lower())
    if status:
        try:
            from app.models import TaskStatus

            base_query = base_query.filter(Task.status == TaskStatus(status.strip().lower()))
        except Exception:
            raise BizError(code=4346, message="status 不支持")
    if start_date:
        try:
            dt = datetime.strptime(start_date, "%Y-%m-%d")
            base_query = base_query.filter(Task.created_at >= dt)
        except Exception:
            raise BizError(code=4344, message="start_date 格式应为YYYY-MM-DD")
    if end_date:
        try:
            dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            base_query = base_query.filter(Task.created_at <= dt)
        except Exception:
            raise BizError(code=4345, message="end_date 格式应为YYYY-MM-DD")
    source_rows = base_query.with_entities(Task.source, func.count(Task.id)).group_by(Task.source).all()
    total = base_query.count()
    rows = (
        base_query.order_by(desc(Task.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        {
            "id": t.id,
            "user_id": t.user_id,
            "task_type": t.task_type.value,
            "platform": t.platform,
            "processing_mode": t.processing_mode,
            "status": t.status.value,
            "source": _normalize_source_bucket(t.source),
            "char_count": t.char_count,
            "cost_credits": t.cost_credits,
            "created_at": t.created_at,
        }
        for t in rows
    ]
    return ok(
        data={
            "items": items,
            "pagination": paginate(total, page, page_size),
            "source_filter": source_filter or "all",
            "source_stats": _build_source_stats(source_rows, as_float=False),
        }
    )


@router.get("/tasks/{task_id}/detail", response_model=APIResp)
def admin_task_detail(
    task_id: int,
    _: AdminUser = Depends(require_admin_permission("tasks:view")),
    db: Session = Depends(db_dep),
) -> APIResp:
    row = db.get(Task, task_id)
    if row is None:
        raise BizError(code=4041, message="任务不存在", http_status=404)
    user = db.get(User, row.user_id)
    return ok(
        data={
            "id": row.id,
            "user_id": row.user_id,
            "user_phone": user.phone if user else "",
            "task_type": row.task_type.value,
            "platform": row.platform,
            "processing_mode": row.processing_mode,
            "source": _normalize_source_bucket(row.source),
            "status": row.status.value,
            "char_count": row.char_count,
            "cost_credits": row.cost_credits,
            "source_filename": row.source_filename,
            "source_path": row.source_path,
            "report_path": row.report_path,
            "output_path": row.output_path,
            "error_message": row.error_message,
            "result_json": row.result_json,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
    )


@router.get("/tasks/{task_id}/download")
def admin_task_download(
    task_id: int,
    _: AdminUser = Depends(require_admin_permission("tasks:view")),
    db: Session = Depends(db_dep),
) -> FileResponse:
    row = db.get(Task, task_id)
    if row is None:
        raise BizError(code=4041, message="任务不存在", http_status=404)
    if row.status.value != "completed" or not row.output_path:
        raise BizError(code=4108, message="任务尚未完成")
    path = Path(row.output_path)
    if not path.exists():
        raise BizError(code=4109, message="输出文件不存在")
    return FileResponse(path=str(path), filename=path.name)


@router.get("/orders", response_model=APIResp)
def admin_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q_phone: str | None = Query(default=None),
    source: str | None = Query(default=None),
    order_no: str | None = Query(default=None),
    status: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    _: AdminUser = Depends(require_admin_permission("orders:view")),
    db: Session = Depends(db_dep),
) -> APIResp:
    base_query = db.query(Order).join(User, User.id == Order.user_id)
    source_filter = _normalize_source_filter(source)
    if q_phone:
        base_query = _apply_phone_filter(base_query, q_phone)
    if source_filter:
        base_query = _apply_source_filter(base_query, Order.source, source_filter)
    if order_no:
        base_query = base_query.filter(Order.order_no.like(f"%{order_no}%"))
    if status:
        base_query = base_query.filter(Order.status == status.strip().lower())
    if provider:
        base_query = base_query.filter(Order.provider == provider.strip().lower())
    source_count_rows = base_query.with_entities(Order.source, func.count(Order.id)).group_by(Order.source).all()
    source_revenue_rows = base_query.with_entities(Order.source, func.coalesce(func.sum(Order.amount_cny), 0)).group_by(Order.source).all()
    total = base_query.count()
    rows = (
        base_query.order_by(desc(Order.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        {
            "order_no": o.order_no,
            "user_id": o.user_id,
            "amount_cny": cny_to_api(o.amount_cny),
            "credits": o.credits,
            "status": o.status,
            "source": _normalize_source_bucket(o.source),
            "is_first_pay": o.is_first_pay,
            "created_at": o.created_at,
        }
        for o in rows
    ]
    return ok(
        data={
            "items": items,
            "pagination": paginate(total, page, page_size),
            "source_filter": source_filter or "all",
            "source_stats": {
                "orders": _build_source_stats(source_count_rows, as_float=False),
                "revenue": _build_source_stats(source_revenue_rows, as_float=True),
            },
        }
    )


@router.get("/orders/{order_no}/detail", response_model=APIResp)
def order_detail(order_no: str, _: AdminUser = Depends(require_admin_permission("orders:view")), db: Session = Depends(db_dep)) -> APIResp:
    row = db.query(Order).filter(Order.order_no == order_no).first()
    if row is None:
        raise BizError(code=4044, message="订单不存在", http_status=404)
    user = db.get(User, row.user_id)
    return ok(
        data={
            "order_no": row.order_no,
            "user_id": row.user_id,
            "user_phone": user.phone if user else "",
            "amount_cny": cny_to_api(row.amount_cny),
            "credits": row.credits,
            "status": row.status,
            "provider": row.provider,
            "source": _normalize_source_bucket(row.source),
            "is_first_pay": row.is_first_pay,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
    )


@router.post("/orders/{order_no}/refund", response_model=APIResp)
def refund_order(
    order_no: str,
    admin: AdminUser = Depends(require_admin_permission("orders:refund")),
    db: Session = Depends(db_dep),
) -> APIResp:
    order = db.query(Order).filter(Order.order_no == order_no).with_for_update().first()
    if order is None:
        raise BizError(code=4044, message="订单不存在", http_status=404)
    if order.status == "refunded":
        return ok(data={"order_no": order.order_no, "status": order.status, "idempotent": True})
    if order.status != "paid":
        raise BizError(code=4347, message="仅已支付订单可退款")
    user = db.query(User).filter(User.id == order.user_id).with_for_update().first()
    if user is None:
        raise BizError(code=4040, message="用户不存在", http_status=404)
    if user.credits < int(order.credits):
        raise BizError(code=4348, message="用户已消耗部分权益，当前订单不可直接退款")
    change_credits(
        db,
        user,
        tx_type=CreditType.ADMIN_ADJUST,
        delta=-int(order.credits),
        reason=f"管理员[{admin.username}]订单退款:{order.order_no}",
        related_id=f"refund:{order.order_no}",
        source="admin",
    )
    order.status = "refunded"
    db.add(
        AdminAuditLog(
            admin_id=admin.id,
            action="order_refund",
            target_type="order",
            target_id=order.order_no,
            before_json={"status": "paid"},
            after_json={"status": "refunded"},
        )
    )
    db.commit()
    return ok(data={"order_no": order.order_no, "status": order.status, "idempotent": False})


@router.get("/referrals/stats", response_model=APIResp)
def referral_stats(_: AdminUser = Depends(require_admin_permission("referrals:view")), db: Session = Depends(db_dep)) -> APIResp:
    return ok(data=build_admin_promo_overview(db))


@router.get("/referrals/rewards", response_model=APIResp)
def referral_rewards(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: AdminUser = Depends(require_admin_permission("referrals:view")),
    db: Session = Depends(db_dep),
) -> APIResp:
    base_query = db.query(PromoShareSubmission)
    total = base_query.count()
    rows = (
        base_query.order_by(desc(PromoShareSubmission.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        {
            "id": row.id,
            "user_id": row.user_id,
            "platform": row.platform,
            "platform_label": SHARE_PLATFORM_PRESETS.get(row.platform, {}).get("label", row.platform),
            "tier_key": row.tier_key,
            "share_link": row.share_link,
            "payout_account": row.payout_account,
            "payout_name": row.payout_name,
            "note": row.note,
            "status": row.status.value,
            "reward_credits": row.reward_credits,
            "reward_amount_cny": float(row.reward_amount_cny or 0),
            "coupon_name": row.coupon_name,
            "coupon_count": row.coupon_count,
            "review_note": row.review_note,
            "created_at": row.created_at,
            "reviewed_at": row.reviewed_at,
        }
        for row in rows
    ]
    return ok(data={"items": items, "pagination": paginate(total, page, page_size)})


@router.get("/referrals/suspicious", response_model=APIResp)
def suspicious_accounts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: AdminUser = Depends(require_admin_permission("referrals:view")),
    db: Session = Depends(db_dep),
) -> APIResp:
    rows = (
        db.query(PromoClassroom)
        .filter(PromoClassroom.status == "active")
        .order_by(desc(PromoClassroom.activity_score), desc(PromoClassroom.member_count))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    total = db.query(func.count(PromoClassroom.id)).filter(PromoClassroom.status == "active").scalar() or 0
    items = [
        {
            "id": row.id,
            "owner_user_id": row.owner_user_id,
            "name": row.name,
            "invite_code": row.invite_code,
            "level": row.level,
            "member_count": row.member_count,
            "activity_score": row.activity_score,
            "created_at": row.created_at,
        }
        for row in rows
    ]
    return ok(data={"items": items, "pagination": paginate(total, page, page_size)})


@router.post("/referrals/config", response_model=APIResp)
def update_referral_config(
    payload: dict,
    admin: AdminUser = Depends(require_admin_permission("referrals:manage")),
    db: Session = Depends(db_dep),
) -> APIResp:
    raise BizError(code=4419, message="分享红包活动当前采用固定规则，暂不支持后台改动奖励配置")


@router.get("/referrals/config", response_model=APIResp)
def get_referral_config(_: AdminUser = Depends(require_admin_permission("referrals:manage")), db: Session = Depends(db_dep)) -> APIResp:
    return ok(data={"mode": "promo_center", "reward_policy": "现金红包人工审核"})


@router.get("/configs/audit-logs", response_model=APIResp)
def config_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: AdminUser = Depends(require_admin_permission("configs:view")),
    db: Session = Depends(db_dep),
) -> APIResp:
    base_query = db.query(AdminAuditLog).filter(AdminAuditLog.action == "config_update")
    total = base_query.count()
    rows = (
        db.query(AdminAuditLog, AdminUser.username)
        .outerjoin(AdminUser, AdminUser.id == AdminAuditLog.admin_id)
        .filter(AdminAuditLog.action == "config_update")
        .order_by(desc(AdminAuditLog.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = []
    for row, admin_username in rows:
        changed_fields = _changed_config_fields(row.before_json, row.after_json)
        changed_field_labels = [_config_field_label(row.target_type, field) for field in changed_fields]
        items.append(
            {
                "id": row.id,
                "admin_id": row.admin_id,
                "admin_username": admin_username or f"admin#{row.admin_id}",
                "target_type": row.target_type,
                "target_type_label": _config_label(row.target_type),
                "target_id": row.target_id,
                "changed_fields": changed_fields,
                "changed_field_labels": changed_field_labels,
                "changed_count": len(changed_fields),
                "summary": _config_change_summary(row.target_type, changed_fields),
                "created_at": row.created_at,
            }
        )
    return ok(data={"items": items, "pagination": paginate(total, page, page_size)})


@router.get("/configs/readiness", response_model=APIResp)
def get_config_readiness(
    _: AdminUser = Depends(require_admin_permission("configs:view")),
    db: Session = Depends(db_dep),
) -> APIResp:
    items = []
    for c in ("llm", "payment", "billing", "login", "notice", "miniapp", "user_navigation"):
        value = _get_category_config(db, c)
        items.append(_category_readiness(c, value))
    return ok(data={"items": items})


@router.get("/configs/{category}", response_model=APIResp)
def get_config(
    category: str,
    _: AdminUser = Depends(require_admin_permission("configs:view")),
    db: Session = Depends(db_dep),
) -> APIResp:
    c = _assert_category(category)
    return ok(data={"category": c, "value": _get_category_config(db, c, redact=True)})


@router.post("/configs/{category}", response_model=APIResp)
def update_config(
    category: str,
    payload: dict,
    admin: AdminUser = Depends(require_admin_permission("configs:manage")),
    db: Session = Depends(db_dep),
) -> APIResp:
    c = _assert_category(category)
    if not isinstance(payload, dict):
        raise BizError(code=4341, message="配置内容必须为 JSON 对象")
    effective_payload = payload
    if c in CONFIG_DEFAULTS:
        current_value = _get_category_config(db, c, redact=False)
        if isinstance(current_value, dict):
            effective_payload = dict(current_value)
            effective_payload.update(_merge_masked_config_payload(c, payload, current_value))
    normalized = _normalize_category_payload(c, effective_payload)
    try:
        value = _save_category_config(db, c, normalized, admin)
        db.commit()
        return ok(data={"category": c, "value": _redact_config_view(c, value)})
    except Exception:
        db.rollback()
        raise


@router.post("/referrals/rewards/{reward_id}/retry", response_model=APIResp)
def retry_referral_reward(
    reward_id: int,
    _: AdminUser = Depends(require_admin_permission("referrals:manage")),
    db: Session = Depends(db_dep),
) -> APIResp:
    raise BizError(code=4419, message="当前活动中心红包发放为人工处理，不支持自动重试")


@router.get("/referrals/share-tasks", response_model=APIResp)
def referral_share_tasks(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    platform: str | None = Query(default=None),
    q_phone: str | None = Query(default=None),
    _: AdminUser = Depends(require_admin_permission("referrals:view")),
    db: Session = Depends(db_dep),
) -> APIResp:
    base_query = db.query(PromoShareSubmission)
    if status:
        try:
            normalized_status = PromoShareSubmissionStatus(str(status).strip().lower())
            base_query = base_query.filter(PromoShareSubmission.status == normalized_status)
        except Exception:
            raise BizError(code=4348, message="share submission status 不支持")
    if platform:
        base_query = base_query.filter(PromoShareSubmission.platform == str(platform).strip().lower())
    total = base_query.count()
    rows = (
        base_query.order_by(desc(PromoShareSubmission.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    user_ids = {row.user_id for row in rows}
    benefit_map = {}
    if user_ids:
        benefit_rows = (
            db.query(PromoBenefitRecord)
            .filter(PromoBenefitRecord.scene == "share_center", PromoBenefitRecord.user_id.in_(user_ids))
            .all()
        )
        benefit_map = {(row.user_id, row.benefit_code): row for row in benefit_rows}
    items = [
        {
            "id": row.id,
            "user_id": row.user_id,
            "platform": row.platform,
            "platform_label": SHARE_PLATFORM_PRESETS.get(row.platform, {}).get("label", row.platform),
            "label": SHARE_PLATFORM_PRESETS.get(row.platform, {}).get("label", row.platform),
            "tier_key": row.tier_key,
            "share_link": row.share_link,
            "payout_account": row.payout_account,
            "payout_name": row.payout_name,
            "note": row.note,
            "status": row.status.value,
            "payout_status": (
                benefit_map[(row.user_id, f"{row.platform}:{row.tier_key}")].payout_status
                if (row.user_id, f"{row.platform}:{row.tier_key}") in benefit_map
                else "none"
            ),
            "reward_credits": row.reward_credits,
            "reward_amount_cny": float(row.reward_amount_cny or 0),
            "coupon_name": row.coupon_name,
            "coupon_count": row.coupon_count,
            "review_note": row.review_note,
            "created_at": row.created_at,
            "reviewed_at": row.reviewed_at,
            "paid_at": (
                benefit_map[(row.user_id, f"{row.platform}:{row.tier_key}")].paid_at
                if (row.user_id, f"{row.platform}:{row.tier_key}") in benefit_map
                else None
            ),
        }
        for row in rows
    ]
    return ok(data={"items": items, "pagination": paginate(total, page, page_size)})


@router.get("/referrals/share-tasks/{submission_id}/screenshot")
def download_referral_share_task_screenshot(
    submission_id: int,
    _: AdminUser = Depends(require_admin_permission("referrals:view")),
    db: Session = Depends(db_dep),
) -> FileResponse:
    raise BizError(code=4419, message="新版分享任务改为链接审核，暂不下载截图")


@router.post("/referrals/share-tasks/{submission_id}/review", response_model=APIResp)
def review_referral_share_task(
    submission_id: int,
    payload: dict,
    admin: AdminUser = Depends(require_admin_permission("referrals:manage")),
    db: Session = Depends(db_dep),
) -> APIResp:
    row = db.query(PromoShareSubmission).filter(PromoShareSubmission.id == submission_id).with_for_update().first()
    if row is None:
        raise BizError(code=4046, message="分享任务不存在", http_status=404)
    target_status = str(payload.get("status", "")).strip().lower()
    review_note = str(payload.get("review_note", "")).strip()[:255]
    if target_status not in {PromoShareSubmissionStatus.APPROVED.value, PromoShareSubmissionStatus.REJECTED.value}:
        raise BizError(code=4349, message="审核状态仅支持 approved / rejected")
    updated, idempotent = review_share_submission(
        db,
        submission=row,
        admin_id=admin.id,
        approved=target_status == PromoShareSubmissionStatus.APPROVED.value,
        review_note=review_note,
    )
    db.commit()
    return ok(
        data={
            "id": updated.id,
            "status": updated.status.value,
            "review_note": updated.review_note or "",
            "idempotent": idempotent,
        }
    )


@router.post("/referrals/share-tasks/{submission_id}/payout", response_model=APIResp)
def payout_referral_share_task(
    submission_id: int,
    payload: dict,
    admin: AdminUser = Depends(require_admin_permission("referrals:manage")),
    db: Session = Depends(db_dep),
) -> APIResp:
    row = db.query(PromoShareSubmission).filter(PromoShareSubmission.id == submission_id).with_for_update().first()
    if row is None:
        raise BizError(code=4047, message="分享任务不存在", http_status=404)
    payout_note = str(payload.get("payout_note", "")).strip()[:255]
    try:
        benefit, idempotent = mark_share_reward_paid(
            db,
            submission=row,
            admin_id=admin.id,
            payout_note=payout_note,
        )
    except ValueError as exc:
        if str(exc) == "share_submission_not_approved":
            raise BizError(code=4350, message="仅审核通过的分享任务才能标记打款", http_status=422)
        raise BizError(code=4351, message="未找到待发放红包记录", http_status=404)
    db.commit()
    return ok(
        data={
            "submission_id": row.id,
            "payout_status": benefit.payout_status,
            "paid_at": benefit.paid_at,
            "idempotent": idempotent,
        }
    )


@router.get("/strategies", response_model=APIResp)
def admin_process_strategies(
    _: AdminUser = Depends(require_admin_permission("algo:view")),
    db: Session = Depends(db_dep),
) -> APIResp:
    data = list_process_strategies(db)
    items = []
    for row in data.get("items", []):
        platform = str(row.get("platform", ""))
        task_type = str(row.get("task_type", ""))
        active_slot = get_active_slot_config(db, platform=platform, function_type=task_type)
        item = dict(row)
        item["platform_label"] = _platform_label(platform)
        item["task_type_label"] = _task_type_label(task_type)
        item["active_package"] = (
            {
                "name": active_slot.get("name"),
                "version": active_slot.get("version"),
                "entry": active_slot.get("entry"),
            }
            if isinstance(active_slot, dict)
            else None
        )
        items.append(item)
    return ok(
        data={
            "task_types": data.get("task_types", []),
            "platforms": data.get("platforms", []),
            "items": items,
        }
    )


@router.put("/strategies/{task_type}/{platform}", response_model=APIResp)
def admin_update_process_strategy(
    task_type: str,
    platform: str,
    payload: dict,
    admin: AdminUser = Depends(require_admin_permission("algo:manage")),
    db: Session = Depends(db_dep),
) -> APIResp:
    if not isinstance(payload, dict):
        raise BizError(code=4302, message="请求体必须为 JSON 对象")
    if not any(key in payload for key in ("process_mode", "is_enabled", "timeout_sec")):
        raise BizError(code=4341, message="至少需要提供 process_mode / is_enabled / timeout_sec 其中之一")

    normalized_task_type = normalize_task_type(task_type)
    normalized_platform = normalize_platform(platform)
    before = get_process_strategy(db, task_type=normalized_task_type, platform=normalized_platform)

    process_mode = payload.get("process_mode") if "process_mode" in payload else None
    if process_mode is not None:
        process_mode = normalize_process_mode(process_mode)
    is_enabled = _as_bool(payload.get("is_enabled"), default=False) if "is_enabled" in payload else None
    timeout_sec = payload.get("timeout_sec") if "timeout_sec" in payload else None

    if is_enabled:
        active_slot = get_active_slot_config(
            db,
            platform=normalized_platform,
            function_type=normalized_task_type.value,
        )
        if not active_slot:
            raise BizError(code=4118, message="该平台功能尚未激活算法包，无法启用")

    try:
        result = update_process_strategy(
            db,
            task_type=normalized_task_type,
            platform=normalized_platform,
            process_mode=process_mode,
            is_enabled=is_enabled,
            timeout_sec=timeout_sec,
            updated_by=admin.id,
        )
        db.add(
            AdminAuditLog(
                admin_id=admin.id,
                action="strategy_update",
                target_type="process_strategy",
                target_id=f"{normalized_task_type.value}:{normalized_platform}",
                before_json=before,
                after_json=result,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    active_slot = get_active_slot_config(db, platform=normalized_platform, function_type=normalized_task_type.value)
    result_payload = dict(result)
    result_payload["platform_label"] = _platform_label(normalized_platform)
    result_payload["task_type_label"] = _task_type_label(normalized_task_type.value)
    result_payload["active_package"] = (
        {
            "name": active_slot.get("name"),
            "version": active_slot.get("version"),
            "entry": active_slot.get("entry"),
        }
        if isinstance(active_slot, dict)
        else None
    )
    return ok(data=result_payload)


@router.get("/credit-transactions", response_model=APIResp)
def credit_transactions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: AdminUser = Depends(require_admin_permission("credits:view")),
    db: Session = Depends(db_dep),
) -> APIResp:
    base_query = db.query(CreditTransaction)
    total = base_query.count()
    rows = (
        base_query.order_by(desc(CreditTransaction.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        {
            "id": tx.id,
            "user_id": tx.user_id,
            "tx_type": tx.tx_type.value,
            "delta": tx.delta,
            "balance_before": tx.balance_before,
            "balance_after": tx.balance_after,
            "reason": tx.reason,
            "related_id": tx.related_id,
            "created_at": tx.created_at,
        }
        for tx in rows
    ]
    return ok(data={"items": items, "pagination": paginate(total, page, page_size)})


@router.get("/algo-packages", response_model=APIResp)
def get_algo_packages(_: AdminUser = Depends(require_admin_permission("algo:view")), db: Session = Depends(db_dep)) -> APIResp:
    data = list_algorithm_packages(db)
    return ok(data=data)


@router.get("/algo-packages/guide")
@router.get("/algo-package-guide")
def download_algo_package_guide(_: AdminUser = Depends(require_admin_permission("algo:view"))) -> Response:
    guide_path = Path(__file__).resolve().parents[2] / "docs" / "ALGO_PACKAGE_AUTHORING_GUIDE.md"
    if not guide_path.exists():
        raise BizError(code=4501, message="算法包撰写说明不存在", http_status=404)
    return FileResponse(
        path=guide_path,
        filename=guide_path.name,
        media_type="application/octet-stream",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/algo-packages/authoring-bundle")
def download_algo_package_authoring_bundle(_: AdminUser = Depends(require_admin_permission("algo:view"))) -> Response:
    filename, content = build_authoring_spec_bundle()
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"; filename*=UTF-8\'\'{filename}',
        "Cache-Control": "no-store",
    }
    return Response(content=content, media_type="application/zip", headers=headers)


@router.get("/algo-packages/template")
def download_algo_package_template(
    platform: str = Query(...),
    function_type: str = Query(...),
    _: AdminUser = Depends(require_admin_permission("algo:view")),
) -> Response:
    filename, content = build_builtin_template_package(platform=platform, function_type=function_type)
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"; filename*=UTF-8\'\'{filename}',
        "Cache-Control": "no-store",
    }
    return Response(content=content, media_type="application/zip", headers=headers)


@router.get("/algo-packages/download")
def download_algo_package_archive(
    platform: str = Query(...),
    function_type: str = Query(...),
    version: str = Query(...),
    _: AdminUser = Depends(require_admin_permission("algo:view")),
) -> Response:
    package_path = get_algorithm_package_archive_path(
        platform=platform,
        function_type=function_type,
        version=version,
    )
    filename = f"algo_package_{platform}_{function_type}_{version}.zip"
    return FileResponse(
        path=package_path,
        filename=filename,
        media_type="application/zip",
        headers={"Cache-Control": "no-store"},
    )


@router.post("/algo-packages/bootstrap", response_model=APIResp)
def bootstrap_algo_packages(
    activate: bool = Query(default=True),
    admin: AdminUser = Depends(require_admin_permission("algo:manage")),
    db: Session = Depends(db_dep),
) -> APIResp:
    try:
        data = bootstrap_builtin_algo_packages(
            db,
            uploaded_by=admin.id,
            activate_after_upload=activate,
        )
        db.commit()
        return ok(data=data)
    except Exception:
        db.rollback()
        raise


@router.post("/algo-packages/upload", response_model=APIResp)
def upload_algo_package(
    platform: str = Form(...),
    function_type: str = Form(...),
    activate: bool = Form(default=True),
    admin: AdminUser = Depends(require_admin_permission("algo:manage")),
    db: Session = Depends(db_dep),
    file: UploadFile = File(...),
) -> APIResp:
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise BizError(code=4500, message="仅支持 zip 文件")

    def _read_limited_upload_bytes(upload: UploadFile, *, max_bytes: int) -> bytes:
        total = 0
        chunks: list[bytes] = []
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise BizError(code=4502, message=f"算法包大小超过{settings.algorithm_package_max_mb}MB")
            chunks.append(chunk)
        if total <= 0:
            raise BizError(code=4501, message="算法包文件为空")
        data = b"".join(chunks)
        if not data.startswith(b"PK\x03\x04"):
            raise BizError(code=4513, message="上传文件不是有效 zip")
        content_type = str(upload.content_type or "").split(";")[0].strip().lower()
        if content_type not in {"application/zip", "application/x-zip-compressed", "application/octet-stream"}:
            raise BizError(code=4500, message="zip 文件 MIME 类型不支持")
        return data

    file_bytes = _read_limited_upload_bytes(
        file,
        max_bytes=int(settings.algorithm_package_max_mb) * 1024 * 1024,
    )
    req = AlgoPackageUploadReq(platform=platform, function_type=function_type)
    try:
        result = install_algorithm_package(
            db,
            file_bytes=file_bytes,
            platform=req.platform,
            function_type=req.function_type,
            uploaded_by=admin.id,
            activate_after_upload=activate,
        )
        db.commit()
        return ok(data=result)
    except Exception:
        db.rollback()
        raise


@router.post("/algo-packages/activate", response_model=APIResp)
def activate_algo_package(
    req: AlgoPackageActivateReq,
    admin: AdminUser = Depends(require_admin_permission("algo:manage")),
    db: Session = Depends(db_dep),
) -> APIResp:
    try:
        result = activate_algorithm_package(
            db,
            platform=req.platform,
            function_type=req.function_type,
            version=req.version,
            updated_by=admin.id,
        )
        db.commit()
        return ok(data=result)
    except Exception:
        db.rollback()
        raise


@router.post("/algo-packages/deactivate", response_model=APIResp)
def deactivate_algo_package_slot(
    req: AlgoPackageUploadReq,
    admin: AdminUser = Depends(require_admin_permission("algo:manage")),
    db: Session = Depends(db_dep),
) -> APIResp:
    try:
        result = deactivate_algorithm_package(
            db,
            platform=req.platform,
            function_type=req.function_type,
            updated_by=admin.id,
        )
        db.commit()
        return ok(data=result)
    except Exception:
        db.rollback()
        raise



