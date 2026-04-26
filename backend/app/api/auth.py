import base64
import hmac
import hashlib
import json
from datetime import datetime
from io import BytesIO
import logging
from urllib.parse import quote
import uuid

from fastapi import APIRouter, Body, Cookie, Depends, Request, Response
from fastapi.responses import HTMLResponse
import httpx
from sqlalchemy.orm import Session

from app.client_source import DEFAULT_CLIENT_SOURCE, get_client_source
from app.config import get_settings
from app.deps import current_user, db_dep, get_redis
from app.exceptions import BizError
from app.money import cny_to_api, fen_to_cny
from app.models import CreditType, RegistrationRiskLog, SystemConfig, User
from app.responses import ok
from app.schemas import APIResp, LoginReq, MiniProgramLoginReq, MiniProgramPhoneLoginReq, SendCodeReq
from app.security import (
    REFRESH_TOKEN_TYPE,
    auth_session_key,
    create_access_token,
    create_refresh_token,
    decode_token,
    new_session_version,
)
from app.services.credit_service import change_credits
from app.services.user_navigation_service import default_user_navigation_config, normalize_user_navigation_config
from app.utils import gen_code, is_phone_valid
from app.utils_qrcode import build_qrcode_data_url

router = APIRouter()
settings = get_settings()
logger = logging.getLogger("app.api.auth")
WX_LOGIN_TTL_SECONDS = 120
DEFAULT_NOTICE_TITLE = "系统公告"
DEFAULT_HEADER_NOTICE_TEXT = "平台系统持续优化中，任务提交后请在个人中心查看处理进度。"
USER_ACCESS_COOKIE_NAME = "gw_user_access"
_LOGIN_CONFIG_DEFAULTS = {
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
    "header_notice_text": DEFAULT_HEADER_NOTICE_TEXT,
    "notice_enabled": True,
    "notice_title": DEFAULT_NOTICE_TITLE,
    "notice_content": DEFAULT_HEADER_NOTICE_TEXT,
    "notice_level": "info",
    "notice_version": 1,
    "notice_updated_at": "",
    "new_user_initial_credits": 5000,
    "max_code_retry": 3,
    "phone_lock_minutes": 5,
    "send_code_ip_1h_limit": 30,
    "login_ip_10m_limit": 120,
}


def _cookie_samesite() -> str:
    value = str(settings.auth_cookie_samesite or "lax").strip().lower()
    if value not in {"lax", "strict", "none"}:
        return "lax"
    return value


def _auth_session_ttl_seconds() -> int:
    return max(int(settings.refresh_token_expire_days) * 24 * 3600, int(settings.jwt_expire_minutes) * 60)


def _store_auth_session(redis_client, *, scope: str, subject: str, session_version: str) -> None:
    redis_client.setex(auth_session_key(scope, subject), _auth_session_ttl_seconds(), session_version)


def _load_auth_session(redis_client, *, scope: str, subject: str) -> str:
    return str(redis_client.get(auth_session_key(scope, subject)) or "").strip()


def _clear_auth_session(redis_client, *, scope: str, subject: str) -> None:
    redis_client.delete(auth_session_key(scope, subject))


def _apply_user_auth_cookies(response: Response, *, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        key=USER_ACCESS_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=settings.auth_cookie_secure_enabled,
        samesite=_cookie_samesite(),
        max_age=int(settings.jwt_expire_minutes) * 60,
        path="/",
    )
    response.set_cookie(
        key=settings.user_refresh_cookie_name,
        value=refresh_token,
        httponly=True,
        secure=settings.auth_cookie_secure_enabled,
        samesite=_cookie_samesite(),
        max_age=int(settings.refresh_token_expire_days) * 24 * 3600,
        path="/api/v1/auth",
    )


def _issue_user_auth(redis_client, response: Response | None, user: User) -> tuple[str, str]:
    session_version = new_session_version()
    _store_auth_session(redis_client, scope="user", subject=str(user.id), session_version=session_version)
    access_token = create_access_token(subject=str(user.id), scope="user", session_version=session_version)
    refresh_token = create_refresh_token(subject=str(user.id), scope="user", session_version=session_version)
    if response is not None:
        _apply_user_auth_cookies(response, access_token=access_token, refresh_token=refresh_token)
    return access_token, refresh_token


def _default_debug_code_enabled() -> bool:
    return bool(settings.auth_return_debug_code or settings.app_env != "prod")


def _redis_key(phone: str, kind: str) -> str:
    return f"auth:phone:{kind}:{phone}"


def _get_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded[:64]
    if request.client is None:
        return ""
    return (request.client.host or "")[:64]


def _get_ua(request: Request) -> str:
    return request.headers.get("user-agent", "")[:280]


def _get_device_fingerprint(request: Request, payload_fp: str | None) -> str:
    # 浠?IP+UA 浣滀负涓绘寚绾癸紝鍓嶇 UUID 浠呭湪鏋佺鍦烘櫙浣滀负鍏滃簳
    primary = f"{_get_ip(request)}|{_get_ua(request)}".strip("|")[:128]
    if primary:
        return primary
    direct = (payload_fp or "").strip()[:128]
    if direct:
        return direct
    header_fp = request.headers.get("x-device-fingerprint", "").strip()[:128]
    if header_fp:
        return header_fp
    return "unknown"


def _enforce_ip_limit(
    redis_client,
    *,
    ip: str,
    action: str,
    limit: int,
    window_seconds: int,
    error_code: int,
    error_message: str,
) -> None:
    if not ip or limit <= 0:
        return
    key = f"risk:ip_limit:{action}:{ip}"
    count = redis_client.incr(key)
    if count == 1:
        redis_client.expire(key, window_seconds)
    if count > limit:
        raise BizError(code=error_code, message=error_message)


def _user_payload(user: User) -> dict:
    phone = str(user.phone or "").strip()
    masked_phone = f"{phone[:3]}****{phone[-4:]}" if len(phone) == 11 else phone
    balance_fen = int(user.credits or 0)
    balance_cny = cny_to_api(fen_to_cny(balance_fen) or 0)
    return {
        "id": user.id,
        "phone": masked_phone,
        "nickname": user.nickname,
        "balance_fen": balance_fen,
        "balance_cny": balance_cny,
        "credits": user.credits,
        "source": user.source,
        "created_at": user.created_at,
    }


def _read_system_config_raw(db: Session, key: str) -> dict:
    row = (
        db.query(SystemConfig)
        .filter(SystemConfig.category == "system", SystemConfig.config_key == key)
        .first()
    )
    if row is None or not isinstance(row.config_value, dict):
        return {}
    return row.config_value


def _get_login_config(db: Session) -> dict:
    login_value = _read_system_config_raw(db, "login")
    notice_value = _read_system_config_raw(db, "notice")
    miniapp_value = _read_system_config_raw(db, "miniapp")
    merged = dict(_LOGIN_CONFIG_DEFAULTS)
    merged["debug_code_enabled"] = _default_debug_code_enabled()
    merged["new_user_initial_credits"] = int(settings.initial_credits)
    merged["max_code_retry"] = int(settings.max_code_retry)
    merged["phone_lock_minutes"] = int(settings.phone_lock_minutes)
    merged["send_code_ip_1h_limit"] = int(settings.auth_send_code_ip_1h_limit)
    merged["login_ip_10m_limit"] = int(settings.auth_login_ip_10m_limit)
    merged.update(login_value)

    if notice_value:
        content = str(notice_value.get("content") or notice_value.get("header_text") or DEFAULT_HEADER_NOTICE_TEXT).strip() or DEFAULT_HEADER_NOTICE_TEXT
        header_text = str(notice_value.get("header_text") or content).strip() or DEFAULT_HEADER_NOTICE_TEXT
        title = str(notice_value.get("title") or DEFAULT_NOTICE_TITLE).strip()[:32] or DEFAULT_NOTICE_TITLE
        try:
            version = int(notice_value.get("version") or 1)
        except Exception:
            version = 1
        if version < 1:
            version = 1
        merged.update(
            {
                "notice_enabled": bool(notice_value.get("enabled", True)),
                "notice_title": title,
                "notice_content": content[:2000],
                "notice_level": str(notice_value.get("level", "info")).strip().lower() or "info",
                "notice_version": version,
                "notice_updated_at": str(notice_value.get("updated_at", "") or "").strip(),
                "header_notice_text": header_text[:140],
            }
        )

    if miniapp_value:
        mini_enabled = bool(miniapp_value.get("wechat_miniprogram_login_enabled", miniapp_value.get("enabled", False)))
        mini_app_id = str(miniapp_value.get("wechat_miniprogram_app_id") or miniapp_value.get("app_id") or "").strip()
        mini_app_secret = str(miniapp_value.get("wechat_miniprogram_app_secret") or miniapp_value.get("app_secret") or "").strip()
        merged["wechat_miniprogram_login_enabled"] = mini_enabled
        if mini_app_id:
            merged["wechat_miniprogram_app_id"] = mini_app_id[:128]
        if mini_app_secret:
            merged["wechat_miniprogram_app_secret"] = mini_app_secret[:256]
    return merged


def _public_site_filing_payload(db: Session) -> dict:
    miniapp_value = _read_system_config_raw(db, "miniapp")
    icp_filing_no = str(miniapp_value.get("icp_filing_no") or "").strip()
    police_filing_no = str(miniapp_value.get("police_filing_no") or "").strip()
    police_filing_url = str(miniapp_value.get("police_filing_url") or "").strip() or "https://beian.mps.gov.cn/#/query/webSearch"
    return {
        "icp_filing_no": icp_filing_no[:128],
        "icp_filing_url": "https://beian.miit.gov.cn",
        "police_filing_no": police_filing_no[:128],
        "police_filing_url": police_filing_url[:256],
    }


def _get_user_navigation_config(db: Session) -> dict:
    raw = _read_system_config_raw(db, "user_navigation")
    if not raw:
        return default_user_navigation_config()
    return normalize_user_navigation_config(raw)


def _get_promo_center_config(db: Session) -> dict:
    raw = _read_system_config_raw(db, "promo_center")
    defaults = {
        "enabled": True,
        "schema_version": 2,
        "invite_reward_points": 2000,
        "updated_by": "",
        "updated_at": "",
        "contacts": {
            "phone": [],
            "wechat": [],
            "email": [],
        },
        "nav_cards": [
            {
                "key": "invite",
                "title": "邀请有奖",
                "badge": "绑定即得点数",
                "description": "邀请好友完成手机号与微信绑定，双方都能拿点数。",
                "sort_order": 1,
                "enabled": True,
            },
            {
                "key": "like",
                "title": "集赞有奖",
                "badge": "截图审核",
                "description": "转发活动素材集赞后提交截图，审核通过发放点数。",
                "sort_order": 2,
                "enabled": True,
            },
            {
                "key": "create",
                "title": "创作有奖",
                "badge": "最高 20000 点",
                "description": "发布指定平台内容，按点赞阶梯领取点数奖励。",
                "sort_order": 3,
                "enabled": True,
            },
            {
                "key": "partner",
                "title": "机构合作",
                "badge": "校园 / 机构",
                "description": "校园大使、机构合作与企业服务统一从这里接入。",
                "sort_order": 4,
                "enabled": True,
            },
        ],
        "pages": {
            "invite": {
                "enabled": True,
                "title": "邀请有奖",
                "subtitle": "邀请好友完成手机号与微信绑定，双方按规则获得点数奖励。",
                "rule_lines": [
                    "被邀请者完成手机号与微信绑定后，可获得 2000 点数。",
                    "邀请者每产生 1 个有效邀请，可获得 1000 点数。",
                    "支持配置里程碑加奖，全部奖励均以点数发放。",
                ],
                "quick_actions_title": "快捷操作区",
                "bind_code_label": "填写邀请码",
                "bind_code_placeholder": "请输入好友邀请码",
                "bind_code_button_text": "确认填写",
                "share_copy_title": "分享文案",
                "share_copy_text": "我正在参加格物推广活动，注册并完成绑定即可拿点数，欢迎通过我的邀请码加入。",
                "miniapp_guide_title": "小程序 3 步邀请指引",
                "miniapp_steps": [
                    "保存二维码或邀请链接，发送给好友。",
                    "好友注册后先完成手机号绑定，再完成微信绑定。",
                    "达到有效邀请条件后，点数奖励按规则发放。",
                ],
                "bind_code_notice": "邀请码在线填写入口待后端接口开放后启用。",
            },
            "like": {
                "enabled": True,
                "title": "集赞有奖",
                "subtitle": "扫码转发活动素材集赞，提交截图后由运营审核发放点数。",
                "rule_lines": [
                    "10 赞可得 10000 点数。",
                    "20 赞可得 20000 点数。",
                    "活动时间、审核时效与违规处理均支持后台调整。",
                ],
                "qrcode_title": "活动二维码",
                "review_notice": "截图需清晰完整，默认 1-3 个工作日内完成审核。",
                "other_entries_title": "其他活动入口",
                "other_entries": [],
            },
            "create": {
                "enabled": True,
                "title": "创作有奖",
                "subtitle": "按平台规则发布指定内容，审核通过后按点赞阶梯发放点数。",
                "rule_lines": [
                    "发帖即送 5000 点数。",
                    "点赞达到 10+ 可得 10000 点数。",
                    "点赞达到 20+ 可得 20000 点数，单次活动封顶。",
                ],
                "platforms": [
                    {"key": "douyin", "label": "抖音", "status_text": "可参加", "enabled": True},
                    {"key": "xiaohongshu", "label": "小红书", "status_text": "可参加", "enabled": True},
                    {"key": "kuaishou", "label": "快手", "status_text": "可参加", "enabled": True},
                    {"key": "weibo", "label": "微博", "status_text": "可参加", "enabled": True},
                    {"key": "moments", "label": "朋友圈", "status_text": "可参加", "enabled": True},
                ],
                "template_title": "推荐文案模板",
                "templates": [
                    "我在用格物做论文处理，流程顺、反馈快，做完绑定和任务后还能参加创作活动拿点数。",
                    "毕业季论文处理别乱找渠道，我最近在格物做检测和改写，活动期还有点赞点数奖励。",
                ],
                "submit_placeholder": "请输入作品链接",
                "submit_button_text": "提交链接",
                "history_button_text": "查看记录",
            },
            "partner": {
                "enabled": True,
                "title": "机构合作",
                "subtitle": "校园大使、机构合作、社群联名与企业服务统一接入。",
                "description": "支持校园活动合作、机构代充、批量服务采购与品牌联动推广。",
                "benefits": [
                    "支持校园大使、社群团长与机构代理合作模式。",
                    "支持批量采购、统一对账与定制化服务方案。",
                    "支持微信二维码、微信号与合作文案按活动实时替换。",
                ],
                "contacts": [
                    {
                        "title": "机构合作顾问",
                        "description": "院校、机构、企业合作优先对接。",
                        "wechat_id": "",
                        "qrcode_url": "/promo-contact-qr-1.jpg",
                        "enabled": True,
                    },
                    {
                        "title": "专属客服",
                        "description": "处理账号、订单与日常服务咨询。",
                        "wechat_id": "",
                        "qrcode_url": "/promo-contact-qr-2.png",
                        "enabled": True,
                    },
                ],
            },
        },
        "reward_rules": {
            "invite": {
                "invitee_bind_reward_points": 2000,
                "inviter_valid_invite_reward_points": 1000,
                "audit_mode": "manual",
                "auto_grant": False,
                "milestones": [
                    {"threshold": 5, "reward_points": 3000, "label": "邀请满 5 人"},
                    {"threshold": 20, "reward_points": 10000, "label": "邀请满 20 人"},
                    {"threshold": 50, "reward_points": 30000, "label": "邀请满 50 人"},
                ],
            },
            "like": {
                "audit_mode": "manual",
                "auto_grant": False,
                "tiers": [
                    {"threshold": 10, "reward_points": 10000, "label": "10 赞"},
                    {"threshold": 20, "reward_points": 20000, "label": "20 赞"},
                ],
            },
            "create": {
                "audit_mode": "manual",
                "auto_grant": False,
                "tiers": [
                    {"threshold": 0, "reward_points": 5000, "label": "发帖即送"},
                    {"threshold": 10, "reward_points": 10000, "label": "10+ 赞"},
                    {"threshold": 20, "reward_points": 20000, "label": "20+ 赞"},
                ],
            },
        },
        "assets": {
            "like_qrcode_url": "",
            "invite_example_image_url": "",
            "partner_primary_qrcode_url": "/promo-contact-qr-1.jpg",
            "partner_secondary_qrcode_url": "/promo-contact-qr-2.png",
        },
    }
    merged = dict(defaults)
    merged["enabled"] = bool(raw.get("enabled", defaults["enabled"])) if isinstance(raw, dict) else defaults["enabled"]
    if not isinstance(raw, dict):
        return merged

    def _safe_int(value, default: int, *, min_value: int | None = None, max_value: int | None = None) -> int:
        try:
            parsed = int(value)
        except Exception:
            parsed = int(default)
        if min_value is not None:
            parsed = max(min_value, parsed)
        if max_value is not None:
            parsed = min(max_value, parsed)
        return parsed

    merged["schema_version"] = _safe_int(
        raw.get("schema_version", defaults["schema_version"]) or defaults["schema_version"],
        defaults["schema_version"],
        min_value=1,
        max_value=99,
    )
    merged["updated_by"] = str(raw.get("updated_by", defaults["updated_by"]) or "")[:64]
    merged["updated_at"] = str(raw.get("updated_at", defaults["updated_at"]) or "")[:64]
    merged["invite_reward_points"] = _safe_int(
        raw.get("invite_reward_points", defaults["invite_reward_points"]),
        defaults["invite_reward_points"],
        min_value=0,
        max_value=100_000,
    )

    raw_contacts = raw.get("contacts") if isinstance(raw.get("contacts"), dict) else {}
    contacts: dict[str, list[str]] = {"phone": [], "wechat": [], "email": []}
    for key in ("phone", "wechat", "email"):
        values = raw_contacts.get(key)
        if not isinstance(values, list):
            values = []
        normalized = []
        seen = set()
        for item in values:
            text = str(item or "").strip()
            if not text:
                continue
            dedup_key = text.lower()
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            normalized.append(text[:128])
            if len(normalized) >= 20:
                break
        contacts[key] = normalized
    merged["contacts"] = contacts

    assets_raw = raw.get("assets") if isinstance(raw.get("assets"), dict) else {}
    merged["assets"] = {
        "like_qrcode_url": str(assets_raw.get("like_qrcode_url", defaults["assets"]["like_qrcode_url"]) or "")[:256],
        "invite_example_image_url": str(assets_raw.get("invite_example_image_url", defaults["assets"]["invite_example_image_url"]) or "")[:256],
        "partner_primary_qrcode_url": str(assets_raw.get("partner_primary_qrcode_url", defaults["assets"]["partner_primary_qrcode_url"]) or "")[:256],
        "partner_secondary_qrcode_url": str(assets_raw.get("partner_secondary_qrcode_url", defaults["assets"]["partner_secondary_qrcode_url"]) or "")[:256],
    }

    raw_cards = raw.get("nav_cards") if isinstance(raw.get("nav_cards"), list) else []
    card_map = {}
    for item in raw_cards:
        if isinstance(item, dict):
            key = str(item.get("key") or "").strip().lower()
            if key:
                card_map[key] = item
    cards = []
    for index, default_card in enumerate(defaults["nav_cards"]):
        source = card_map.get(default_card["key"], {})
        cards.append(
            {
                "key": default_card["key"],
                "title": str(source.get("title", default_card["title"]) or "")[:32] or default_card["title"],
                "badge": str(source.get("badge", default_card["badge"]) or "")[:32],
                "description": str(source.get("description", default_card["description"]) or "")[:120],
                "sort_order": _safe_int(
                    source.get("sort_order", default_card["sort_order"]) or default_card["sort_order"],
                    default_card["sort_order"],
                    min_value=1,
                    max_value=99,
                ),
                "enabled": bool(source.get("enabled", default_card["enabled"])),
            }
        )
    cards.sort(key=lambda item: (item["sort_order"], item["key"]))
    merged["nav_cards"] = cards

    reward_rules = defaults["reward_rules"]
    raw_reward_rules = raw.get("reward_rules") if isinstance(raw.get("reward_rules"), dict) else {}
    invite_rules = raw_reward_rules.get("invite") if isinstance(raw_reward_rules.get("invite"), dict) else {}
    like_rules = raw_reward_rules.get("like") if isinstance(raw_reward_rules.get("like"), dict) else {}
    create_rules = raw_reward_rules.get("create") if isinstance(raw_reward_rules.get("create"), dict) else {}
    legacy_inviter_reward = merged["invite_reward_points"] if ("invite_reward_points" in raw and not invite_rules) else max(0, merged["invite_reward_points"] // 2)

    def _normalize_reward_list(values, default_items):
        if not isinstance(values, list):
            return list(default_items)
        items = []
        for item in values:
            if not isinstance(item, dict):
                continue
            try:
                threshold = int(item.get("threshold", 0) or 0)
                reward_points = int(item.get("reward_points", 0) or 0)
            except Exception:
                continue
            if reward_points <= 0:
                continue
            items.append(
                {
                    "threshold": max(0, min(threshold, 100000)),
                    "reward_points": max(0, min(reward_points, 1000000)),
                    "label": str(item.get("label", "") or "")[:48],
                }
            )
            if len(items) >= 12:
                break
        if not items:
            return list(default_items)
        items.sort(key=lambda item: (item["threshold"], item["reward_points"]))
        return items

    merged["reward_rules"] = {
        "invite": {
            "invitee_bind_reward_points": _safe_int(
                invite_rules.get("invitee_bind_reward_points", merged["invite_reward_points"]) or merged["invite_reward_points"],
                merged["invite_reward_points"],
                min_value=0,
                max_value=1_000_000,
            ),
            "inviter_valid_invite_reward_points": _safe_int(
                invite_rules.get("inviter_valid_invite_reward_points", legacy_inviter_reward) or legacy_inviter_reward,
                legacy_inviter_reward,
                min_value=0,
                max_value=1_000_000,
            ),
            "audit_mode": str(invite_rules.get("audit_mode", reward_rules["invite"]["audit_mode"]) or "manual")[:32],
            "auto_grant": bool(invite_rules.get("auto_grant", reward_rules["invite"]["auto_grant"])),
            "milestones": _normalize_reward_list(invite_rules.get("milestones"), reward_rules["invite"]["milestones"]),
        },
        "like": {
            "audit_mode": str(like_rules.get("audit_mode", reward_rules["like"]["audit_mode"]) or "manual")[:32],
            "auto_grant": bool(like_rules.get("auto_grant", reward_rules["like"]["auto_grant"])),
            "tiers": _normalize_reward_list(like_rules.get("tiers"), reward_rules["like"]["tiers"]),
        },
        "create": {
            "audit_mode": str(create_rules.get("audit_mode", reward_rules["create"]["audit_mode"]) or "manual")[:32],
            "auto_grant": bool(create_rules.get("auto_grant", reward_rules["create"]["auto_grant"])),
            "tiers": _normalize_reward_list(create_rules.get("tiers"), reward_rules["create"]["tiers"]),
        },
    }

    raw_pages = raw.get("pages") if isinstance(raw.get("pages"), dict) else {}
    merged_pages = {}
    for key, default_page in defaults["pages"].items():
        source = raw_pages.get(key) if isinstance(raw_pages.get(key), dict) else {}
        page = dict(default_page)
        page["enabled"] = bool(source.get("enabled", default_page.get("enabled", True)))
        page["title"] = str(source.get("title", default_page.get("title", "")) or "")[:32] or default_page.get("title", "")
        page["subtitle"] = str(source.get("subtitle", default_page.get("subtitle", "")) or "")[:180]
        if key == "invite":
            page["rule_lines"] = source.get("rule_lines") if isinstance(source.get("rule_lines"), list) else [
                f"被邀请者完成手机号与微信绑定后，可获得 {merged['reward_rules']['invite']['invitee_bind_reward_points']} 点数。",
                f"邀请者每产生 1 个有效邀请，可获得 {merged['reward_rules']['invite']['inviter_valid_invite_reward_points']} 点数。",
                "支持配置里程碑加奖，全部奖励均以点数发放。",
            ]
            page["rule_lines"] = [str(item or "").strip()[:120] for item in page["rule_lines"] if str(item or "").strip()][:6]
            page["quick_actions_title"] = str(source.get("quick_actions_title", default_page.get("quick_actions_title", "")) or "")[:32]
            page["bind_code_label"] = str(source.get("bind_code_label", default_page.get("bind_code_label", "")) or "")[:32]
            page["bind_code_placeholder"] = str(source.get("bind_code_placeholder", default_page.get("bind_code_placeholder", "")) or "")[:64]
            page["bind_code_button_text"] = str(source.get("bind_code_button_text", default_page.get("bind_code_button_text", "")) or "")[:24]
            page["share_copy_title"] = str(source.get("share_copy_title", default_page.get("share_copy_title", "")) or "")[:32]
            page["share_copy_text"] = str(source.get("share_copy_text", default_page.get("share_copy_text", "")) or "")[:300]
            page["miniapp_guide_title"] = str(source.get("miniapp_guide_title", default_page.get("miniapp_guide_title", "")) or "")[:40]
            steps = source.get("miniapp_steps") if isinstance(source.get("miniapp_steps"), list) else default_page.get("miniapp_steps", [])
            page["miniapp_steps"] = [str(item or "").strip()[:80] for item in steps if str(item or "").strip()][:5]
            page["bind_code_notice"] = str(source.get("bind_code_notice", default_page.get("bind_code_notice", "")) or "")[:120]
        elif key == "like":
            lines = source.get("rule_lines") if isinstance(source.get("rule_lines"), list) else default_page.get("rule_lines", [])
            page["rule_lines"] = [str(item or "").strip()[:120] for item in lines if str(item or "").strip()][:6]
            page["qrcode_title"] = str(source.get("qrcode_title", default_page.get("qrcode_title", "")) or "")[:32]
            page["review_notice"] = str(source.get("review_notice", default_page.get("review_notice", "")) or "")[:180]
            page["other_entries_title"] = str(source.get("other_entries_title", default_page.get("other_entries_title", "")) or "")[:32]
            entries = source.get("other_entries") if isinstance(source.get("other_entries"), list) else []
            normalized_entries = []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                normalized_entries.append(
                    {
                        "title": str(entry.get("title", "") or "")[:32],
                        "description": str(entry.get("description", "") or "")[:120],
                        "qrcode_url": str(entry.get("qrcode_url", "") or "")[:256],
                        "enabled": bool(entry.get("enabled", True)),
                    }
                )
                if len(normalized_entries) >= 8:
                    break
            page["other_entries"] = normalized_entries
        elif key == "create":
            lines = source.get("rule_lines") if isinstance(source.get("rule_lines"), list) else default_page.get("rule_lines", [])
            page["rule_lines"] = [str(item or "").strip()[:120] for item in lines if str(item or "").strip()][:6]
            default_platforms = default_page.get("platforms", [])
            raw_platforms = source.get("platforms") if isinstance(source.get("platforms"), list) else []
            platform_map = {}
            for item in raw_platforms:
                if isinstance(item, dict):
                    platform_map[str(item.get("key", "") or "").strip().lower()] = item
            page["platforms"] = []
            for item in default_platforms:
                current = platform_map.get(item["key"], {})
                page["platforms"].append(
                    {
                        "key": item["key"],
                        "label": str(current.get("label", item["label"]) or "")[:24] or item["label"],
                        "status_text": str(current.get("status_text", item["status_text"]) or "")[:32],
                        "enabled": bool(current.get("enabled", item["enabled"])),
                    }
                )
            page["template_title"] = str(source.get("template_title", default_page.get("template_title", "")) or "")[:32]
            templates = source.get("templates") if isinstance(source.get("templates"), list) else default_page.get("templates", [])
            page["templates"] = [str(item or "").strip()[:220] for item in templates if str(item or "").strip()][:8]
            page["submit_placeholder"] = str(source.get("submit_placeholder", default_page.get("submit_placeholder", "")) or "")[:64]
            page["submit_button_text"] = str(source.get("submit_button_text", default_page.get("submit_button_text", "")) or "")[:24]
            page["history_button_text"] = str(source.get("history_button_text", default_page.get("history_button_text", "")) or "")[:24]
        elif key == "partner":
            page["description"] = str(source.get("description", default_page.get("description", "")) or "")[:240]
            benefits = source.get("benefits") if isinstance(source.get("benefits"), list) else default_page.get("benefits", [])
            page["benefits"] = [str(item or "").strip()[:120] for item in benefits if str(item or "").strip()][:6]
            default_cards = default_page.get("contacts", [])
            source_cards = source.get("contacts") if isinstance(source.get("contacts"), list) else []
            partner_cards = []
            for index, item in enumerate(default_cards):
                current = source_cards[index] if index < len(source_cards) and isinstance(source_cards[index], dict) else {}
                partner_cards.append(
                    {
                        "title": str(current.get("title", item.get("title", "")) or "")[:32] or item.get("title", ""),
                        "description": str(current.get("description", item.get("description", "")) or "")[:120],
                        "wechat_id": str(current.get("wechat_id", item.get("wechat_id", "")) or "")[:64],
                        "qrcode_url": str(current.get("qrcode_url", item.get("qrcode_url", "")) or "")[:256],
                        "enabled": bool(current.get("enabled", item.get("enabled", True))),
                    }
                )
            page["contacts"] = partner_cards
        merged_pages[key] = page
    merged["pages"] = merged_pages
    return merged


def _normalize_notice_level(value) -> str:
    level = str(value or "info").strip().lower()
    if level not in {"info", "important", "success", "warning"}:
        return "info"
    return level


def _build_notice_payload(login_cfg: dict) -> dict:
    content = str(login_cfg.get("notice_content") or login_cfg.get("header_notice_text") or DEFAULT_HEADER_NOTICE_TEXT).strip()
    if not content:
        content = DEFAULT_HEADER_NOTICE_TEXT
    header_text = str(login_cfg.get("header_notice_text") or content).strip()
    if not header_text:
        header_text = DEFAULT_HEADER_NOTICE_TEXT
    title = str(login_cfg.get("notice_title") or DEFAULT_NOTICE_TITLE).strip()[:32]
    if not title:
        title = DEFAULT_NOTICE_TITLE
    try:
        version = int(login_cfg.get("notice_version") or 1)
    except Exception:
        version = 1
    if version < 1:
        version = 1
    return {
        "enabled": bool(login_cfg.get("notice_enabled", True)),
        "title": title,
        "content": content[:2000],
        "header_text": header_text[:140],
        "level": _normalize_notice_level(login_cfg.get("notice_level", "info")),
        "version": version,
        "updated_at": str(login_cfg.get("notice_updated_at", "") or "").strip(),
    }


def _int_from_login_cfg(
    login_cfg: dict,
    key: str,
    default: int,
    *,
    min_value: int = 0,
    max_value: int | None = None,
) -> int:
    try:
        value = int(login_cfg.get(key, default))
    except Exception:
        value = int(default)
    if value < min_value:
        return int(default)
    if max_value is not None and value > max_value:
        return int(default)
    return value


def _sms_provider_ready(login_cfg: dict) -> bool:
    provider = str(login_cfg.get("sms_provider", "custom_webhook")).strip().lower()
    if provider == "custom_webhook":
        return bool(str(login_cfg.get("sms_gateway_url", settings.sms_gateway_url)).strip())
    if provider == "tencent_sms":
        return all(
            bool(str(login_cfg.get(field, "")).strip())
            for field in ("sms_sdk_app_id", "sms_sign_name", "sms_template_id", "sms_access_key_id", "sms_access_key_secret")
        )
    if provider == "aliyun_sms":
        return all(
            bool(str(login_cfg.get(field, "")).strip())
            for field in ("sms_sign_name", "sms_template_id", "sms_access_key_id", "sms_access_key_secret")
        )
    return False


def _send_via_custom_gateway(phone: str, code: str, login_cfg: dict) -> bool:
    gateway_url = str(login_cfg.get("sms_gateway_url", settings.sms_gateway_url)).strip()
    if not gateway_url:
        return False
    api_key = str(login_cfg.get("sms_api_key", settings.sms_api_key)).strip()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "phone": phone,
        "code": code,
        "provider": str(login_cfg.get("sms_provider", "custom_webhook")).strip() or "custom_webhook",
        "template_id": str(login_cfg.get("sms_template_id", "")).strip(),
        "sign_name": str(login_cfg.get("sms_sign_name", "")).strip(),
        "sdk_app_id": str(login_cfg.get("sms_sdk_app_id", "")).strip(),
    }
    try:
        resp = httpx.post(gateway_url, json=payload, headers=headers, timeout=8)
        return 200 <= resp.status_code < 300
    except Exception:
        return False


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _hmac_sha256(key: bytes, text: str) -> bytes:
    return hmac.new(key, text.encode("utf-8"), hashlib.sha256).digest()


def _send_via_tencent_sms(phone: str, code: str, login_cfg: dict) -> bool:
    secret_id = str(login_cfg.get("sms_access_key_id", "")).strip()
    secret_key = str(login_cfg.get("sms_access_key_secret", "")).strip()
    sdk_app_id = str(login_cfg.get("sms_sdk_app_id", "")).strip()
    sign_name = str(login_cfg.get("sms_sign_name", "")).strip()
    template_id = str(login_cfg.get("sms_template_id", "")).strip()
    region = str(login_cfg.get("sms_region", "ap-guangzhou")).strip() or "ap-guangzhou"
    if not all([secret_id, secret_key, sdk_app_id, sign_name, template_id]):
        return False

    normalized_phone = phone if phone.startswith("+") else f"+86{phone}"
    payload = json.dumps(
        {
            "PhoneNumberSet": [normalized_phone],
            "SmsSdkAppId": sdk_app_id,
            "SignName": sign_name,
            "TemplateId": template_id,
            "TemplateParamSet": [code],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )

    host = "sms.tencentcloudapi.com"
    service = "sms"
    action = "SendSms"
    version = "2021-01-11"
    algorithm = "TC3-HMAC-SHA256"
    timestamp = int(datetime.utcnow().timestamp())
    date_str = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")
    content_type = "application/json; charset=utf-8"
    signed_headers = "content-type;host;x-tc-action"
    canonical_headers = f"content-type:{content_type}\nhost:{host}\nx-tc-action:{action.lower()}\n"
    canonical_request = "\n".join(["POST", "/", "", canonical_headers, signed_headers, _sha256_hex(payload)])
    credential_scope = f"{date_str}/{service}/tc3_request"
    string_to_sign = "\n".join([algorithm, str(timestamp), credential_scope, _sha256_hex(canonical_request)])
    secret_date = _hmac_sha256(f"TC3{secret_key}".encode("utf-8"), date_str)
    secret_service = hmac.new(secret_date, service.encode("utf-8"), hashlib.sha256).digest()
    secret_signing = hmac.new(secret_service, b"tc3_request", hashlib.sha256).digest()
    signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    authorization = (
        f"{algorithm} Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    headers = {
        "Authorization": authorization,
        "Content-Type": content_type,
        "Host": host,
        "X-TC-Action": action,
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Version": version,
        "X-TC-Region": region,
    }
    try:
        resp = httpx.post(f"https://{host}", content=payload.encode("utf-8"), headers=headers, timeout=8)
        if not (200 <= resp.status_code < 300):
            return False
        body = resp.json()
        if isinstance(body.get("Response", {}).get("Error"), dict):
            return False
        statuses = body.get("Response", {}).get("SendStatusSet", [])
        if not statuses:
            return False
        return str(statuses[0].get("Code", "")).strip().lower() == "ok"
    except Exception:
        return False


def _aliyun_percent_encode(value: str) -> str:
    return quote(value, safe="~")


def _send_via_aliyun_sms(phone: str, code: str, login_cfg: dict) -> bool:
    access_key_id = str(login_cfg.get("sms_access_key_id", "")).strip()
    access_key_secret = str(login_cfg.get("sms_access_key_secret", "")).strip()
    sign_name = str(login_cfg.get("sms_sign_name", "")).strip()
    template_code = str(login_cfg.get("sms_template_id", "")).strip()
    region_id = str(login_cfg.get("sms_aliyun_region_id", "cn-hangzhou")).strip() or "cn-hangzhou"
    endpoint = str(login_cfg.get("sms_gateway_url", "")).strip() or "https://dysmsapi.aliyuncs.com"
    if not all([access_key_id, access_key_secret, sign_name, template_code]):
        return False

    params = {
        "Action": "SendSms",
        "Version": "2017-05-25",
        "RegionId": region_id,
        "PhoneNumbers": phone,
        "SignName": sign_name,
        "TemplateCode": template_code,
        "TemplateParam": json.dumps({"code": code}, ensure_ascii=False, separators=(",", ":")),
    }
    sorted_pairs = sorted(params.items(), key=lambda item: item[0])
    canonicalized_query = "&".join([f"{_aliyun_percent_encode(str(k))}={_aliyun_percent_encode(str(v))}" for k, v in sorted_pairs])
    query_string = canonicalized_query

    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    nonce = uuid.uuid4().hex
    payload_hash = hashlib.sha256(b"").hexdigest()
    host = endpoint.replace("https://", "").replace("http://", "").strip("/")
    canonical_headers = (
        f"host:{host}\n"
        f"x-acs-action:SendSms\n"
        f"x-acs-content-sha256:{payload_hash}\n"
        f"x-acs-date:{timestamp}\n"
        f"x-acs-signature-nonce:{nonce}\n"
        f"x-acs-version:2017-05-25\n"
    )
    signed_headers = "host;x-acs-action;x-acs-content-sha256;x-acs-date;x-acs-signature-nonce;x-acs-version"
    canonical_request = "\n".join(["POST", "/", query_string, canonical_headers, signed_headers, payload_hash])
    string_to_sign = "ACS3-HMAC-SHA256\n" + hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    signature = hmac.new(access_key_secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    authorization = (
        f"ACS3-HMAC-SHA256 Credential={access_key_id},"
        f"SignedHeaders={signed_headers},Signature={signature}"
    )
    headers = {
        "Authorization": authorization,
        "host": host,
        "x-acs-action": "SendSms",
        "x-acs-version": "2017-05-25",
        "x-acs-date": timestamp,
        "x-acs-signature-nonce": nonce,
        "x-acs-content-sha256": payload_hash,
    }
    try:
        resp = httpx.post(f"{endpoint}/?{query_string}", headers=headers, timeout=8)
        if not (200 <= resp.status_code < 300):
            return False
        body = resp.json()
        return str(body.get("Code", "")).strip().upper() == "OK"
    except Exception:
        return False


def _send_sms_code(phone: str, code: str, login_cfg: dict) -> bool:
    provider = str(login_cfg.get("sms_provider", "custom_webhook")).strip().lower()
    if provider == "tencent_sms":
        return _send_via_tencent_sms(phone, code, login_cfg)
    if provider == "aliyun_sms":
        return _send_via_aliyun_sms(phone, code, login_cfg)
    if provider == "disabled":
        return False
    return _send_via_custom_gateway(phone, code, login_cfg)


def _make_virtual_phone(db: Session, openid: str) -> str:
    seed = int(hashlib.sha256(openid.encode("utf-8")).hexdigest()[:16], 16)
    for i in range(2000):
        digits = str((seed + i) % 1_000_000_000).zfill(9)
        phone = f"19{digits}"
        exists = db.query(User.id).filter(User.phone == phone).first()
        if exists is None:
            return phone
    raise BizError(code=4015, message="鏃犳硶涓哄井淇＄敤鎴峰垎閰嶆墜鏈哄彿")


def _wx_key(key: str) -> str:
    return f"auth:wx:{key}"


def _wechat_real_login_enabled(login_cfg: dict) -> bool:
    enabled = bool(login_cfg.get("wechat_login_enabled"))
    if not enabled:
        return False
    return all(
        bool(str(login_cfg.get(field, "")).strip())
        for field in ("wechat_app_id", "wechat_app_secret", "wechat_redirect_uri")
    )


def _wechat_mock_enabled() -> bool:
    return settings.app_env != "prod"


def _wechat_login_enabled(login_cfg: dict) -> bool:
    return _wechat_real_login_enabled(login_cfg) or _wechat_mock_enabled()


def _resolve_wechat_miniprogram_credentials(login_cfg: dict) -> tuple[str, str]:
    app_id = str(login_cfg.get("wechat_miniprogram_app_id") or login_cfg.get("wechat_app_id") or "").strip()
    app_secret = str(login_cfg.get("wechat_miniprogram_app_secret") or login_cfg.get("wechat_app_secret") or "").strip()
    return app_id, app_secret


def _wechat_miniprogram_real_login_enabled(login_cfg: dict) -> bool:
    if not bool(login_cfg.get("wechat_miniprogram_login_enabled")):
        return False
    app_id, app_secret = _resolve_wechat_miniprogram_credentials(login_cfg)
    return bool(app_id and app_secret)


def _wechat_miniprogram_login_enabled(login_cfg: dict) -> bool:
    return _wechat_miniprogram_real_login_enabled(login_cfg) or _wechat_mock_enabled()


def _wechat_miniprogram_phone_login_enabled(login_cfg: dict) -> bool:
    return _wechat_miniprogram_real_login_enabled(login_cfg)


def _get_wechat_miniprogram_access_token(login_cfg: dict, redis_client) -> str:
    if not _wechat_miniprogram_real_login_enabled(login_cfg):
        raise BizError(code=4016, message="miniprogram_credentials_not_ready")

    app_id, app_secret = _resolve_wechat_miniprogram_credentials(login_cfg)
    cache_key = f"auth:wxmini:access_token:{app_id}"
    cached = str(redis_client.get(cache_key) or "").strip()
    if cached:
        return cached

    try:
        token_resp = httpx.get(
            "https://api.weixin.qq.com/cgi-bin/token",
            params={
                "grant_type": "client_credential",
                "appid": app_id,
                "secret": app_secret,
            },
            timeout=8,
        )
    except Exception as exc:
        raise BizError(code=4016, message="微信小程序 access_token 获取失败") from exc

    if not (200 <= token_resp.status_code < 300):
        raise BizError(code=4016, message="微信小程序 access_token 获取失败")

    payload = token_resp.json()
    access_token = str(payload.get("access_token", "")).strip()
    if not access_token:
        raise BizError(code=4016, message="微信小程序 access_token 无效")

    expires_in = int(payload.get("expires_in") or 7200)
    redis_client.setex(cache_key, max(60, min(expires_in - 120, 7000)), access_token)
    return access_token


def _resolve_miniprogram_openid_unionid(login_cfg: dict, login_code: str) -> tuple[str, str | None]:
    if settings.app_env != "prod" and login_code.startswith("mock_"):
        openid = f"mp_{hashlib.sha256(login_code.encode('utf-8')).hexdigest()[:20]}"
        unionid = f"union_{hashlib.sha256((login_code + settings.jwt_secret).encode('utf-8')).hexdigest()[:20]}"
        return openid, unionid

    if not _wechat_miniprogram_real_login_enabled(login_cfg):
        raise BizError(code=4016, message="miniprogram_credentials_not_ready")

    app_id, app_secret = _resolve_wechat_miniprogram_credentials(login_cfg)
    try:
        session_resp = httpx.get(
            "https://api.weixin.qq.com/sns/jscode2session",
            params={
                "appid": app_id,
                "secret": app_secret,
                "js_code": login_code,
                "grant_type": "authorization_code",
            },
            timeout=8,
        )
    except Exception as exc:
        raise BizError(code=4016, message="wechat_jscode2session_request_failed") from exc
    if not (200 <= session_resp.status_code < 300):
        raise BizError(code=4016, message="wechat_jscode2session_http_error")

    payload = session_resp.json()
    openid = str(payload.get("openid", "")).strip()
    unionid = str(payload.get("unionid", "")).strip() or None
    if not openid:
        errmsg = str(payload.get("errmsg") or "openid_missing")
        raise BizError(code=4016, message=f"wechat_jscode2session_failed:{errmsg}")
    return openid, unionid


def _resolve_miniprogram_phone_number(login_cfg: dict, redis_client, phone_code: str) -> str:
    if settings.app_env != "prod" and phone_code.startswith("mock_phone_"):
        phone = str(phone_code.split("mock_phone_", 1)[1]).strip()
        if not is_phone_valid(phone):
            raise BizError(code=4001, message="手机号格式错误")
        return phone

    access_token = _get_wechat_miniprogram_access_token(login_cfg, redis_client)
    try:
        phone_resp = httpx.post(
            "https://api.weixin.qq.com/wxa/business/getuserphonenumber",
            params={"access_token": access_token},
            json={"code": phone_code},
            timeout=8,
        )
    except Exception as exc:
        raise BizError(code=4016, message="微信手机号快捷登录暂不可用，请稍后重试") from exc

    if not (200 <= phone_resp.status_code < 300):
        raise BizError(code=4016, message="微信手机号快捷登录暂不可用，请稍后重试")

    payload = phone_resp.json()
    errcode = int(payload.get("errcode") or 0)
    if errcode != 0:
        if errcode == 40029:
            raise BizError(code=4016, message="手机号授权已失效，请重新获取")
        if errcode == 40013:
            raise BizError(code=4016, message="小程序配置异常，请联系管理员")
        raise BizError(code=4016, message="手机号快捷登录失败，请改用微信一键登录")

    phone_info = payload.get("phone_info") if isinstance(payload.get("phone_info"), dict) else {}
    phone = str(phone_info.get("purePhoneNumber") or phone_info.get("phoneNumber") or "").strip()
    if not is_phone_valid(phone):
        raise BizError(code=4016, message="微信返回的手机号无效，请改用微信一键登录")
    return phone


def _wechat_authorize_url(login_cfg: dict, state: str) -> str:
    app_id = str(login_cfg.get("wechat_app_id", "")).strip()
    redirect_uri = str(login_cfg.get("wechat_redirect_uri", "")).strip()
    return (
        "https://open.weixin.qq.com/connect/qrconnect"
        f"?appid={quote(app_id, safe='')}"
        f"&redirect_uri={quote(redirect_uri, safe='')}"
        "&response_type=code"
        "&scope=snsapi_login"
        f"&state={quote(state, safe='')}"
        "#wechat_redirect"
    )


def _upsert_wechat_user(
    db: Session,
    *,
    openid: str,
    source: str = DEFAULT_CLIENT_SOURCE,
    scene: str = "web",
    unionid: str | None = None,
    initial_credits: int | None = None,
) -> tuple[User, bool]:
    is_miniprogram = scene == "miniprogram"
    openid_attr = "wechat_openid_mp" if is_miniprogram else "wechat_openid_web"
    openid_column = getattr(User, openid_attr)

    user = db.query(User).filter(openid_column == openid).with_for_update().first()
    if user is None and not is_miniprogram:
        user = db.query(User).filter(User.openid == openid).with_for_update().first()
    if user is None and unionid:
        user = db.query(User).filter(User.wechat_unionid == unionid).with_for_update().first()

    is_new_user = False
    if user and user.is_banned:
        raise BizError(code=4012, message="账号已封禁")
    if user is None:
        is_new_user = True
        phone = _make_virtual_phone(db, openid)
        user = User(
            phone=phone,
            nickname=f"寰俊鐢ㄦ埛{phone[-4:]}",
            openid=openid if not is_miniprogram else None,
            wechat_unionid=unionid,
            wechat_openid_web=openid if not is_miniprogram else None,
            wechat_openid_mp=openid if is_miniprogram else None,
            source=source,
            credits=0,
        )
        db.add(user)
        db.flush()
        change_credits(
            db,
            user,
            tx_type=CreditType.INIT,
            delta=settings.initial_credits if initial_credits is None else int(initial_credits),
            reason="微信新用户初始通用点数",
            related_id=f"wx_user_init:{user.id}",
            source=source,
        )
        return user, is_new_user

    setattr(user, openid_attr, openid)
    if not is_miniprogram and not user.openid:
        user.openid = openid
    if unionid and not user.wechat_unionid:
        user.wechat_unionid = unionid
    if not user.source:
        user.source = source
    db.flush()
    return user, is_new_user


def _upsert_miniprogram_phone_user(
    db: Session,
    *,
    phone: str,
    openid: str,
    source: str = DEFAULT_CLIENT_SOURCE,
    unionid: str | None = None,
    initial_credits: int | None = None,
) -> tuple[User, bool]:
    openid_user = db.query(User).filter(User.wechat_openid_mp == openid).with_for_update().first()
    if openid_user is None and unionid:
        openid_user = db.query(User).filter(User.wechat_unionid == unionid).with_for_update().first()
    phone_user = db.query(User).filter(User.phone == phone).with_for_update().first()

    checked: list[User] = []
    for candidate in (openid_user, phone_user):
        if candidate is None or candidate in checked:
            continue
        checked.append(candidate)
        if candidate.is_banned:
            raise BizError(code=4012, message="账号已封禁")

    if openid_user and phone_user and openid_user.id != phone_user.id:
        raise BizError(code=4016, message="当前微信与手机号已关联不同账户，请使用原登录方式")

    user = openid_user or phone_user
    is_new_user = False
    if user is None:
        is_new_user = True
        user = User(
            phone=phone,
            nickname=f"用户{phone[-4:]}",
            wechat_unionid=unionid,
            wechat_openid_mp=openid,
            source=source,
            credits=0,
        )
        db.add(user)
        db.flush()
        change_credits(
            db,
            user,
            tx_type=CreditType.INIT,
            delta=settings.initial_credits if initial_credits is None else int(initial_credits),
            reason="微信新用户初始通用点数",
            related_id=f"wx_user_init:{user.id}",
            source=source,
        )
        return user, is_new_user

    user.phone = phone
    user.wechat_openid_mp = openid
    if unionid and not user.wechat_unionid:
        user.wechat_unionid = unionid
    if not user.source:
        user.source = source
    db.flush()
    return user, is_new_user


@router.get("/options", response_model=APIResp)
def auth_options(db: Session = Depends(db_dep)) -> APIResp:
    login_cfg = _get_login_config(db)
    debug_enabled = bool(login_cfg.get("debug_code_enabled"))
    phone_login_enabled = _sms_provider_ready(login_cfg) or (settings.app_env != "prod" and debug_enabled)
    notice = _build_notice_payload(login_cfg)
    user_navigation = _get_user_navigation_config(db)
    promo_center = _get_promo_center_config(db)
    return ok(
        data={
            "wechat_login_enabled": _wechat_login_enabled(login_cfg),
            "wechat_miniprogram_login_enabled": _wechat_miniprogram_login_enabled(login_cfg),
            "wechat_miniprogram_phone_quick_login_enabled": _wechat_miniprogram_phone_login_enabled(login_cfg),
            "wechat_auth_scenes": ["web", "miniprogram"],
            "debug_code_enabled": debug_enabled,
            "sms_provider": str(login_cfg.get("sms_provider", "custom_webhook")).strip().lower() or "custom_webhook",
            "wx_mock_enabled": _wechat_mock_enabled(),
            "phone_login_enabled": phone_login_enabled,
            "new_user_initial_credits": _int_from_login_cfg(login_cfg, "new_user_initial_credits", settings.initial_credits, min_value=0, max_value=1_000_000),
            "header_notice_text": notice["header_text"],
            "notice": notice,
            "user_navigation": user_navigation,
            "promo_center": promo_center,
            "site_filing": _public_site_filing_payload(db),
        }
    )


@router.get("/announcement", response_model=APIResp)
def auth_announcement(db: Session = Depends(db_dep)) -> APIResp:
    login_cfg = _get_login_config(db)
    return ok(data=_build_notice_payload(login_cfg))


@router.post("/send-code", response_model=APIResp)
def send_code(
    req: SendCodeReq,
    request: Request,
    db: Session = Depends(db_dep),
    redis_client=Depends(get_redis),
) -> APIResp:
    login_cfg = _get_login_config(db)
    if not is_phone_valid(req.phone):
        raise BizError(code=4001, message="手机号格式错误")
    ip = _get_ip(request)
    _enforce_ip_limit(
        redis_client,
        ip=ip,
        action="send_code",
        limit=_int_from_login_cfg(login_cfg, "send_code_ip_1h_limit", settings.auth_send_code_ip_1h_limit, min_value=1, max_value=10_000),
        window_seconds=3600,
        error_code=4019,
        error_message="当前 IP 请求验证码过于频繁，请稍后重试",
    )

    lock_key = _redis_key(req.phone, "lock")
    cooldown_key = _redis_key(req.phone, "cooldown")
    code_key = _redis_key(req.phone, "code")
    attempt_key = _redis_key(req.phone, "attempt")

    if redis_client.ttl(lock_key) > 0:
        raise BizError(code=4004, message=f"鎵嬫満鍙峰凡閿佸畾锛岃绋嶅悗鍐嶈瘯({redis_client.ttl(lock_key)}s)")
    if redis_client.ttl(cooldown_key) > 0:
        raise BizError(code=4003, message=f"验证码发送过于频繁，请 {redis_client.ttl(cooldown_key)} 秒后重试")

    debug_switch = bool(login_cfg.get("debug_code_enabled"))
    sms_ready = _sms_provider_ready(login_cfg)
    if settings.app_env == "prod" and (not sms_ready):
        logger.warning("auth_send_code_sms_not_configured", extra={"ip": ip, "phone_tail": req.phone[-4:]})
        raise BizError(code=4021, message="短信服务未配置或不可用，当前环境不可发送验证码")

    code = gen_code()
    sms_sent = _send_sms_code(req.phone, code, login_cfg)
    allow_debug_fallback = settings.app_env != "prod"
    if (not sms_sent) and (not allow_debug_fallback):
        logger.warning(
            "auth_send_code_gateway_failed",
            extra={"ip": ip, "phone_tail": req.phone[-4:]},
        )
        raise BizError(code=4022, message="短信发送失败，请检查短信配置")
    if (not sms_sent) and allow_debug_fallback:
        logger.warning(
            "auth_send_code_dev_fallback",
            extra={"ip": ip, "phone_tail": req.phone[-4:]},
        )

    redis_client.setex(code_key, 300, code)
    redis_client.setex(attempt_key, 300, 0)
    redis_client.setex(cooldown_key, 60, 1)
    payload = {"phone": req.phone, "expire_seconds": 300}
    if settings.app_env != "prod" and (debug_switch or (not sms_sent)):
        payload["debug_code"] = code
    logger.info(
        "auth_send_code_success",
        extra={"ip": ip, "phone_tail": req.phone[-4:], "sms_sent": sms_sent},
    )
    return ok(data=payload)


@router.post("/login", response_model=APIResp)
def login(
    req: LoginReq,
    request: Request,
    response: Response,
    db: Session = Depends(db_dep),
    redis_client=Depends(get_redis),
) -> APIResp:
    login_cfg = _get_login_config(db)
    if not is_phone_valid(req.phone):
        raise BizError(code=4001, message="手机号格式错误")
    _enforce_ip_limit(
        redis_client,
        ip=_get_ip(request),
        action="login",
        limit=_int_from_login_cfg(login_cfg, "login_ip_10m_limit", settings.auth_login_ip_10m_limit, min_value=1, max_value=10_000),
        window_seconds=10 * 60,
        error_code=4020,
        error_message="当前 IP 登录请求过于频繁，请稍后重试",
    )

    lock_key = _redis_key(req.phone, "lock")
    cooldown_key = _redis_key(req.phone, "cooldown")
    code_key = _redis_key(req.phone, "code")
    attempt_key = _redis_key(req.phone, "attempt")

    lock_ttl = redis_client.ttl(lock_key)
    if lock_ttl > 0:
        raise BizError(code=4004, message=f"验证码错误次数过多，请 {lock_ttl} 秒后重试")

    real_code = redis_client.get(code_key)
    if not real_code:
        raise BizError(code=4002, message="验证码已过期，请重新发送")

    if req.code != real_code:
        current_retry = redis_client.incr(attempt_key)
        redis_client.expire(attempt_key, 300)
        max_code_retry = _int_from_login_cfg(login_cfg, "max_code_retry", settings.max_code_retry, min_value=1, max_value=20)
        phone_lock_minutes = _int_from_login_cfg(login_cfg, "phone_lock_minutes", settings.phone_lock_minutes, min_value=1, max_value=120)
        if current_retry >= max_code_retry:
            redis_client.setex(lock_key, phone_lock_minutes * 60, 1)
            redis_client.delete(code_key)
        raise BizError(code=4005, message="验证码错误")

    redis_client.delete(code_key, attempt_key, cooldown_key)

    ip = _get_ip(request)
    ua = _get_ua(request)
    fp = _get_device_fingerprint(request, req.device_fingerprint)
    client_source = get_client_source(request)
    is_new_user = False

    try:
        user = db.query(User).filter(User.phone == req.phone).with_for_update().first()
        if user and user.is_banned:
            db.add(
                RegistrationRiskLog(
                    phone=req.phone,
                    ip=ip,
                    user_agent=ua,
                    reason="banned_user_login_attempt",
                )
            )
            db.commit()
            raise BizError(code=4012, message="账号已封禁")

        if user is None:
            is_new_user = True
            user = User(phone=req.phone, nickname=f"鐢ㄦ埛{req.phone[-4:]}", source=client_source, credits=0)
            db.add(user)
            db.flush()
            initial_credits = _int_from_login_cfg(
                login_cfg,
                "new_user_initial_credits",
                settings.initial_credits,
                min_value=0,
                max_value=1_000_000,
            )
            change_credits(
                db,
                user,
                tx_type=CreditType.INIT,
                delta=initial_credits,
                reason="新用户初始通用点数",
                related_id=f"user_init:{user.id}",
                source=client_source,
            )
        elif not user.source:
            user.source = client_source

        redis_client.setex(f"user:fp:{user.id}", 30 * 24 * 3600, fp)
        db.commit()
    except Exception:
        db.rollback()
        raise

    token, refresh_token = _issue_user_auth(redis_client, response, user)

    logger.info(
        "auth_login_success",
        extra={"user_id": user.id, "is_new_user": is_new_user, "ip": ip},
    )
    return ok(
        data={
            "token": token,
            "refresh_token": refresh_token,
            "is_new_user": is_new_user,
            "user": _user_payload(user),
        }
    )


@router.post("/refresh", response_model=APIResp)
def refresh_user_token(
    response: Response,
    payload: dict | None = Body(default=None),
    refresh_cookie: str | None = Cookie(default=None, alias=settings.user_refresh_cookie_name),
    db: Session = Depends(db_dep),
    redis_client=Depends(get_redis),
) -> APIResp:
    refresh_token = str((payload or {}).get("refresh_token") or refresh_cookie or "").strip()
    if not refresh_token:
        raise BizError(code=4013, message="refresh token missing", http_status=401)
    try:
        decoded = decode_token(refresh_token)
    except ValueError as exc:
        raise BizError(code=4014, message="refresh token invalid", http_status=401) from exc
    if decoded.get("scope") != "user" or str(decoded.get("typ") or "").strip().lower() != REFRESH_TOKEN_TYPE:
        raise BizError(code=4014, message="refresh token invalid", http_status=401)

    user = db.get(User, int(decoded["sub"]))
    if not user or getattr(user, "is_banned", False):
        raise BizError(code=4012, message="账号不可用", http_status=401)

    session_version = str(decoded.get("sv") or "").strip()
    current_version = _load_auth_session(redis_client, scope="user", subject=str(user.id))
    if not session_version or not current_version or session_version != current_version:
        raise BizError(code=4014, message="refresh token revoked", http_status=401)

    token, next_refresh_token = _issue_user_auth(redis_client, response, user)
    return ok(data={"token": token, "refresh_token": next_refresh_token, "user": _user_payload(user)})


@router.post("/logout", response_model=APIResp)
def logout_user(
    response: Response,
    user: User = Depends(current_user),
    redis_client=Depends(get_redis),
) -> APIResp:
    _clear_auth_session(redis_client, scope="user", subject=str(user.id))
    response.delete_cookie(USER_ACCESS_COOKIE_NAME, path="/")
    response.delete_cookie(settings.user_refresh_cookie_name, path="/api/v1/auth")
    return ok(data={"logged_out": True})


@router.post("/wx/mini-login", response_model=APIResp)
def wx_mini_login(
    req: MiniProgramLoginReq,
    request: Request,
    db: Session = Depends(db_dep),
    redis_client=Depends(get_redis),
) -> APIResp:
    login_cfg = _get_login_config(db)
    if not _wechat_miniprogram_login_enabled(login_cfg):
        raise BizError(code=4016, message="wechat_miniprogram_login_not_enabled")

    js_code = str(req.code or "").strip()
    if not js_code:
        raise BizError(code=4017, message="empty_js_code")

    _enforce_ip_limit(
        redis_client,
        ip=_get_ip(request),
        action="wx_mini_login",
        limit=_int_from_login_cfg(login_cfg, "login_ip_10m_limit", settings.auth_login_ip_10m_limit, min_value=1, max_value=10_000),
        window_seconds=10 * 60,
        error_code=4020,
        error_message="ip_rate_limit_reached",
    )

    openid, unionid = _resolve_miniprogram_openid_unionid(login_cfg, js_code)

    is_new_user = False
    fp = _get_device_fingerprint(request, req.device_fingerprint)
    client_source = get_client_source(request)
    try:
        user, is_new_user = _upsert_wechat_user(
            db,
            openid=openid,
            source=client_source,
            scene="miniprogram",
            unionid=unionid,
            initial_credits=_int_from_login_cfg(
                login_cfg,
                "new_user_initial_credits",
                settings.initial_credits,
                min_value=0,
                max_value=1_000_000,
            ),
        )
        redis_client.setex(f"user:fp:{user.id}", 30 * 24 * 3600, fp)
        db.commit()
    except Exception:
        db.rollback()
        raise

    token, refresh_token = _issue_user_auth(redis_client, None, user)

    return ok(
        data={
            "token": token,
            "refresh_token": refresh_token,
            "is_new_user": is_new_user,
            "scene": "miniprogram",
            "user": _user_payload(user),
        }
    )


@router.post("/wx/mini-phone-login", response_model=APIResp)
def wx_mini_phone_login(
    req: MiniProgramPhoneLoginReq,
    request: Request,
    db: Session = Depends(db_dep),
    redis_client=Depends(get_redis),
) -> APIResp:
    login_cfg = _get_login_config(db)
    if not _wechat_miniprogram_phone_login_enabled(login_cfg):
        raise BizError(code=4016, message="wechat_miniprogram_phone_login_not_enabled")

    login_code = str(req.login_code or "").strip()
    phone_code = str(req.phone_code or "").strip()
    if not login_code:
        raise BizError(code=4017, message="empty_login_code")
    if not phone_code:
        raise BizError(code=4017, message="empty_phone_code")

    _enforce_ip_limit(
        redis_client,
        ip=_get_ip(request),
        action="wx_mini_phone_login",
        limit=_int_from_login_cfg(login_cfg, "login_ip_10m_limit", settings.auth_login_ip_10m_limit, min_value=1, max_value=10_000),
        window_seconds=10 * 60,
        error_code=4020,
        error_message="ip_rate_limit_reached",
    )

    openid, unionid = _resolve_miniprogram_openid_unionid(login_cfg, login_code)
    phone = _resolve_miniprogram_phone_number(login_cfg, redis_client, phone_code)

    fp = _get_device_fingerprint(request, req.device_fingerprint)
    client_source = get_client_source(request)
    try:
        user, is_new_user = _upsert_miniprogram_phone_user(
            db,
            phone=phone,
            openid=openid,
            source=client_source,
            unionid=unionid,
            initial_credits=_int_from_login_cfg(
                login_cfg,
                "new_user_initial_credits",
                settings.initial_credits,
                min_value=0,
                max_value=1_000_000,
            ),
        )
        redis_client.setex(f"user:fp:{user.id}", 30 * 24 * 3600, fp)
        db.commit()
    except Exception:
        db.rollback()
        raise

    token, refresh_token = _issue_user_auth(redis_client, None, user)

    return ok(
        data={
            "token": token,
            "refresh_token": refresh_token,
            "is_new_user": is_new_user,
            "scene": "miniprogram",
            "login_type": "phone_quick",
            "user": _user_payload(user),
        }
    )


@router.get("/wx/qrcode", response_model=APIResp)
def wx_qrcode(db: Session = Depends(db_dep), redis_client=Depends(get_redis)) -> APIResp:
    login_cfg = _get_login_config(db)
    if not _wechat_login_enabled(login_cfg):
        raise BizError(code=4016, message="微信登录未启用或配置不完整")

    raw = f"{datetime.utcnow().timestamp()}-{gen_code()}-{settings.jwt_secret}"
    key = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    state = f"{key}.{gen_code()}"
    data = {"status": "pending", "created_at": int(datetime.utcnow().timestamp()), "state": state}
    redis_client.setex(_wx_key(key), WX_LOGIN_TTL_SECONDS, json.dumps(data, ensure_ascii=False))

    if _wechat_real_login_enabled(login_cfg):
        qr_payload = _wechat_authorize_url(login_cfg, state)
    else:
        qr_payload = f"mock://wechat-login?state={quote(state, safe='')}"
    return ok(
        data={
            "key": key,
            "qrcode_data_url": build_qrcode_data_url(qr_payload),
            "expire_seconds": WX_LOGIN_TTL_SECONDS,
            "poll_interval_seconds": 2,
        }
    )


@router.get("/wx/callback", response_class=HTMLResponse)
def wx_callback(
    request: Request,
    code: str = "",
    state: str = "",
    db: Session = Depends(db_dep),
    redis_client=Depends(get_redis),
):
    if not code or not state:
        raise BizError(code=4017, message="寰俊鎺堟潈鍙傛暟缂哄け")
    if "." not in state:
        raise BizError(code=4017, message="无效的微信授权状态")
    key = state.split(".", 1)[0]
    raw = redis_client.get(_wx_key(key))
    if not raw:
        raise BizError(code=4018, message="浜岀淮鐮佸凡杩囨湡锛岃鍒锋柊")
    try:
        pending = json.loads(raw)
    except Exception as exc:
        raise BizError(code=4018, message="寰俊鐧诲綍浼氳瘽宸插け鏁堬紝璇峰埛鏂颁簩缁寸爜") from exc
    if str(pending.get("state", "")) != state:
        raise BizError(code=4017, message="微信授权状态校验失败")

    login_cfg = _get_login_config(db)
    if not _wechat_real_login_enabled(login_cfg):
        raise BizError(code=4016, message="微信真实登录未启用或配置不完整")

    app_id = str(login_cfg.get("wechat_app_id", "")).strip()
    app_secret = str(login_cfg.get("wechat_app_secret", "")).strip()
    token_resp = httpx.get(
        "https://api.weixin.qq.com/sns/oauth2/access_token",
        params={
            "appid": app_id,
            "secret": app_secret,
            "code": code,
            "grant_type": "authorization_code",
        },
        timeout=8,
    )
    if not (200 <= token_resp.status_code < 300):
        raise BizError(code=4016, message="寰俊鎺堟潈鎹㈠彇浠ょ墝澶辫触")
    token_data = token_resp.json()
    openid = str(token_data.get("openid", "")).strip()
    unionid = str(token_data.get("unionid", "")).strip() or None
    if not openid:
        err_msg = token_data.get("errmsg") or "寰俊杩斿洖openid涓虹┖"
        raise BizError(code=4016, message=f"寰俊鎺堟潈澶辫触: {err_msg}")

    try:
        user, is_new_user = _upsert_wechat_user(
            db,
            openid=openid,
            source=get_client_source(request),
            scene="web",
            unionid=unionid,
            initial_credits=_int_from_login_cfg(
                login_cfg,
                "new_user_initial_credits",
                settings.initial_credits,
                min_value=0,
                max_value=1_000_000,
            ),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    token, refresh_token = _issue_user_auth(redis_client, None, user)

    wx_payload = {
        "status": "authorized",
        "token": token,
        "refresh_token": refresh_token,
        "user": _user_payload(user),
        "is_new_user": is_new_user,
    }
    redis_client.setex(_wx_key(key), WX_LOGIN_TTL_SECONDS, json.dumps(wx_payload, ensure_ascii=False, default=str))
    return HTMLResponse(
        content=(
            "<html><head><meta charset='utf-8'></head><body>"
            "<div style='font-family: sans-serif;padding:24px;'>"
            "<h3>寰俊鎺堟潈鎴愬姛</h3><p>鍙繑鍥炲師椤甸潰锛岀郴缁熷皢鑷姩瀹屾垚鐧诲綍銆?/p>"
            "</div></body></html>"
        )
    )


@router.get("/wx/poll/{key}", response_model=APIResp)
def wx_poll(key: str, response: Response, redis_client=Depends(get_redis)) -> APIResp:
    raw = redis_client.get(_wx_key(key))
    if not raw:
        return ok(data={"status": "expired"})
    try:
        data = json.loads(raw)
    except Exception:
        redis_client.delete(_wx_key(key))
        return ok(data={"status": "expired"})
    status = str(data.get("status", "pending"))
    if status != "authorized":
        return ok(data={"status": "pending"})
    token = data.get("token")
    refresh_token = data.get("refresh_token")
    user_data = data.get("user")
    if not token or not refresh_token or not isinstance(user_data, dict):
        return ok(data={"status": "pending"})
    _apply_user_auth_cookies(response, access_token=str(token), refresh_token=str(refresh_token))
    redis_client.delete(_wx_key(key))
    return ok(data={"status": "authorized", "token": token, "refresh_token": refresh_token, "user": user_data})


@router.post("/wx/mock-authorize", response_model=APIResp)
def wx_mock_authorize(
    payload: dict,
    request: Request,
    db: Session = Depends(db_dep),
    redis_client=Depends(get_redis),
) -> APIResp:
    if settings.app_env == "prod":
        raise BizError(code=4016, message="鐢熶骇鐜绂佹 mock 寰俊鎺堟潈")
    key = str(payload.get("key", "")).strip()
    if not key:
        raise BizError(code=4017, message="缂哄皯寰俊鐧诲綍 key")
    raw = redis_client.get(_wx_key(key))
    if not raw:
        raise BizError(code=4018, message="浜岀淮鐮佸凡杩囨湡锛岃鍒锋柊")

    openid = str(payload.get("openid", "")).strip()
    if not openid:
        openid = f"mock_wx_{hashlib.sha256((key + settings.jwt_secret).encode('utf-8')).hexdigest()[:16]}"
    scene = str(payload.get("scene", "web")).strip().lower() or "web"
    if scene not in {"web", "miniprogram"}:
        scene = "web"
    unionid = str(payload.get("unionid", "")).strip() or None
    login_cfg = _get_login_config(db)

    try:
        user, is_new_user = _upsert_wechat_user(
            db,
            openid=openid,
            source=get_client_source(request),
            scene=scene,
            unionid=unionid,
            initial_credits=_int_from_login_cfg(
                login_cfg,
                "new_user_initial_credits",
                settings.initial_credits,
                min_value=0,
                max_value=1_000_000,
            ),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    token, refresh_token = _issue_user_auth(redis_client, None, user)

    wx_payload = {
        "status": "authorized",
        "token": token,
        "refresh_token": refresh_token,
        "user": _user_payload(user),
        "is_new_user": is_new_user,
    }
    redis_client.setex(_wx_key(key), WX_LOGIN_TTL_SECONDS, json.dumps(wx_payload, ensure_ascii=False, default=str))
    return ok(data={"status": "authorized"})

