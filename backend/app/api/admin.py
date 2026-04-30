from datetime import date, datetime, timedelta
from copy import deepcopy
import ipaddress
from pathlib import Path
import re
import secrets
from urllib.parse import urlparse

from fastapi import APIRouter, Body, Cookie, Depends, File, Form, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.constants import (
    DEFAULT_BILLING_PACKAGES,
    DEFAULT_BILLING_PACKAGE_PROFILE_VERSION,
    DEFAULT_BILLING_SCHEMA_VERSION,
    LEGACY_BUILTIN_BILLING_PACKAGE_NAMES,
    MAX_FILE_SIZE_MB,
)
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
    PromoBenefitStatus,
    PromoBenefitType,
    PromoShareSubmission,
    PromoShareSubmissionStatus,
    ShareTaskStatus,
    SwitchLog,
    SystemConfig,
    SystemSwitch,
    Task,
    TaskStatus,
    TaskType,
    User,
    UserShareTaskSubmission,
)
from app.pagination import paginate
from app.responses import ok
from app.schemas import (
    APIResp,
    AdminAdjustCreditReq,
    AdminLoginReq,
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
from app.services.credit_service import change_credits
from app.services.llm_service import LLM_PROVIDER_PRESETS, SUPPORTED_LLM_PROVIDERS, normalize_llm_provider
from app.money import cny_to_api, cny_sum, cny_to_fen, fen_to_cny, to_cny_decimal
from app.services.payment_service import DEFAULT_PAYMENT_CONFIG, normalize_payment_provider
from app.services.process_strategy_service import (
    get_process_strategy,
    is_independent_strategy_config,
    list_process_strategies,
    normalize_platform,
    normalize_process_mode,
    normalize_task_type,
    platform_label,
    update_process_strategy,
)
from app.services.platform_registry import list_platforms, upsert_platform, validate_platform_payload
from app.services.aigc_detect_strategies.config import (
    DEFAULT_AIGC_DETECT_STRATEGY_CONFIG,
    aigc_detect_strategy_readiness,
    normalize_aigc_detect_strategy_config,
)
from app.services.dedup_strategies.config import (
    DEFAULT_DEDUP_STRATEGY_CONFIG,
    dedup_strategy_readiness,
    normalize_dedup_strategy_config,
)
from app.services.rewrite_strategies.config import (
    DEFAULT_REWRITE_STRATEGY_CONFIG,
    normalize_rewrite_strategy_config,
    rewrite_strategy_readiness,
)
from app.services.task_artifacts import resolve_task_artifact_path
from app.services.task_artifacts import build_storage_name, save_upload_to, serialize_task_artifact_path
from app.services.task_filename import build_task_filename_pair, build_task_result_filename
from app.services.user_navigation_service import default_user_navigation_config, normalize_user_navigation_config
from app.services.partner_rebate_service import record_refund_order_rebate

router = APIRouter()
settings = get_settings()

DEFAULT_NOTICE_TITLE = "系统公告"
DEFAULT_NOTICE_TEXT = "平台系统持续优化中，任务提交后请在个人中心查看处理进度。"
ADMIN_ACCESS_COOKIE_NAME = "gw_admin_access"
SOURCE_BUCKETS = ("web", "miniapp", "other")
_SOURCE_WEB_ALIASES = {"web", "h5", "site"}
_SOURCE_MINIAPP_ALIASES = {"miniapp", "miniprogram", "mini_program", "wxapp", "wechat_miniprogram", "wechat_mini_program"}

CONFIG_CATEGORIES = {
    "llm",
    "payment",
    "billing",
    "login",
    "notice",
    "miniapp",
    "user_navigation",
    "promo_center",
    "aigc_detect_strategy",
    "rewrite_strategy",
    "dedup_strategy",
}
CONFIG_LABELS = {
    "llm": "大模型配置",
    "payment": "支付配置",
    "billing": "计费规则",
    "login": "登录配置",
    "notice": "公告配置",
    "miniapp": "小程序配置",
    "user_navigation": "前台导航",
    "promo_center": "推广中心",
    "aigc_detect_strategy": "AIGC检测策略",
    "rewrite_strategy": "降AIGC提示词",
    "dedup_strategy": "降重复率提示词",
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
        "aigc_points_per_char": "AIGC单价(点数/字符，整数)",
        "dedup_points_per_char": "降重单价(点数/字符，整数)",
        "rewrite_points_per_char": "降AIGC率单价(点数/字符，整数)",
        "packages": "通用点数套餐",
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
        "new_user_initial_credits": "新用户初始通用点数",
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
        "police_filing_no": "公安备案号",
        "police_filing_url": "公安备案链接",
        "contact_phone": "客服电话",
        "contact_email": "联系邮箱",
        "publish_note": "上线备注",
        "wechat_miniprogram_login_enabled": "小程序登录开关",
        "wechat_miniprogram_app_id": "小程序登录AppID",
        "wechat_miniprogram_app_secret": "小程序登录AppSecret",
        "wechat_miniprogram_payment_enabled": "小程序支付开关",
        "payment_notify_url": "支付回调地址",
        "runtime_copy": "小程序运行文案",
    },
    "user_navigation": {
        "items": "前台导航编排",
    },
    "promo_center": {
        "enabled": "推广中心开关",
        "schema_version": "配置版本",
        "invite_reward_points": "邀请奖励积分",
        "contacts": "机构合作联系方式",
        "nav_cards": "顶部活动卡片",
        "pages": "活动页面文案",
        "reward_rules": "点数奖励规则",
        "assets": "活动素材",
    },
    "aigc_detect_strategy": {
        "cnki": "知网AIGC检测策略",
        "vip": "维普AIGC检测策略",
    },
    "rewrite_strategy": {
        "cnki": "知网降AIGC率提示词",
        "vip": "维普降AIGC率提示词",
    },
    "dedup_strategy": {
        "cnki": "知网降重复率提示词",
        "vip": "维普降重复率提示词",
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
        "schema_version": DEFAULT_BILLING_SCHEMA_VERSION,
        "package_profile_version": DEFAULT_BILLING_PACKAGE_PROFILE_VERSION,
        "aigc_points_per_char": 1,
        "dedup_points_per_char": 1,
        "rewrite_points_per_char": 1,
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
        "miniapp_internal_test_login_enabled": False,
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
        "police_filing_no": "",
        "police_filing_url": "",
        "contact_phone": "",
        "contact_email": "",
        "publish_note": "",
        "wechat_miniprogram_login_enabled": False,
        "wechat_miniprogram_app_id": "",
        "wechat_miniprogram_app_secret": "",
        "wechat_miniprogram_payment_enabled": False,
        "payment_notify_url": "",
        "runtime_copy": {
            "login": {
                "brand_name": "格物学术",
                "brand_subtitle": "论文检测与处理服务",
                "agreement_text": "我已阅读并同意服务协议与隐私条款",
                "login_unavailable_title": "暂时无法完成登录",
                "login_unavailable_desc": "当前登录服务正在维护，请稍后重试或联系管理员处理。",
                "formal_mode_label": "当前为正式微信登录",
                "internal_test_mode_label": "当前为内测登录",
                "mock_mode_label": "当前为本地开发调试登录",
                "prefer_phone_title": "请使用手机号快捷登录",
                "prefer_phone_content": "为了统一 Web 端和小程序端账号、积分、订单和邀请关系，正式环境请优先使用微信手机号快捷登录。",
                "policy_required_title": "请先同意协议",
                "policy_required_content": "继续登录前，请先勾选服务协议与隐私条款。",
                "phone_auth_missing_title": "未完成授权",
            },
            "home": {
                "hero_title": "格物学术",
                "hero_subtitle": "全文检测、降AIGC、降重处理，在同一个学术工作台里完成。",
                "invite_label": "邀请好友",
                "invite_note": "好友首次登录时会自动带入邀请码，邀请关系会被记录。",
                "copy_invite_button_text": "复制邀请码",
                "share_button_text": "邀请好友",
                "share_title": "格物学术 | 检测、降AIGC与降重",
            },
            "profile": {
                "guest_subtitle": "登录后可查看账户、权益和充值进度。",
                "user_subtitle": "账户、充值、公告集中管理。",
                "guest_section_title": "登录后进入个人中心",
                "guest_section_desc": "账户信息、积分充值、订单进度和系统公告会在登录后显示。",
                "guest_login_button_text": "去登录",
                "account_section_title": "账户信息",
                "promo_section_title": "推广领积分",
                "promo_section_desc": "邀请好友、参与活动，领取积分奖励。",
                "system_section_title": "公告与操作",
            },
        },
    },
    "user_navigation": default_user_navigation_config(),
    "promo_center": {
        "enabled": True,
        "schema_version": 2,
        "updated_by": "",
        "updated_at": "",
        "invite_reward_points": 2000,
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
                    {
                        "key": "douyin",
                        "label": "抖音",
                        "status_text": "可参加",
                        "enabled": True,
                    },
                    {
                        "key": "xiaohongshu",
                        "label": "小红书",
                        "status_text": "可参加",
                        "enabled": True,
                    },
                    {
                        "key": "kuaishou",
                        "label": "快手",
                        "status_text": "可参加",
                        "enabled": True,
                    },
                    {
                        "key": "weibo",
                        "label": "微博",
                        "status_text": "可参加",
                        "enabled": True,
                    },
                    {
                        "key": "moments",
                        "label": "朋友圈",
                        "status_text": "可参加",
                        "enabled": True,
                    },
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
            "platform_douyin_qrcode_url": "/promo-qr-douyin.jpg",
            "platform_xiaohongshu_qrcode_url": "/promo-qr-xiaohongshu.jpg",
            "platform_bilibili_qrcode_url": "/promo-qr-bilibili.jpg",
            "platform_wechat_qrcode_url": "/promo-qr-wechat.jpg",
        },
    },
    "aigc_detect_strategy": deepcopy(DEFAULT_AIGC_DETECT_STRATEGY_CONFIG),
    "rewrite_strategy": deepcopy(DEFAULT_REWRITE_STRATEGY_CONFIG),
    "dedup_strategy": deepcopy(DEFAULT_DEDUP_STRATEGY_CONFIG),
}

PROMO_CENTER_PAGE_KEYS = ("invite", "like", "create", "partner")
PROMO_CENTER_CARD_KEYS = ("invite", "like", "create", "partner")
PROMO_CENTER_UPLOAD_ASSET_KEYS = {
    "like_qrcode_url",
    "platform_douyin_qrcode_url",
    "platform_xiaohongshu_qrcode_url",
    "platform_bilibili_qrcode_url",
    "platform_wechat_qrcode_url",
}

_LLM_PROVIDERS = set(SUPPORTED_LLM_PROVIDERS)
_PAYMENT_PROVIDERS = {"wechat", "alipay", "mock", "wechatpay_v3"}
_SMS_PROVIDERS = {"custom_webhook", "tencent_sms", "aliyun_sms", "disabled"}
ADMIN_PERMISSION_CATALOG = [
    {"key": "dashboard:view", "label": "查看总览看板", "group": "看板"},
    {"key": "users:view", "label": "查看用户列表与详情", "group": "用户"},
    {"key": "users:manage", "label": "封禁与调整用户通用点数", "group": "用户"},
    {"key": "tasks:view", "label": "查看任务与结果下载", "group": "任务"},
    {"key": "orders:view", "label": "查看订单列表与详情", "group": "订单"},
    {"key": "orders:refund", "label": "执行订单退款", "group": "订单"},
    {"key": "logs:view", "label": "查看系统日志", "group": "日志"},
    {"key": "credits:view", "label": "查看点数流水", "group": "点数"},
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
    "logs:view",
    "credits:view",
}
ADMIN_PERMISSION_TEMPLATES = [
    {
        "key": "ops_basic",
        "label": "运营基础",
        "description": "适合日常运营，覆盖用户、任务、订单与点数处理。",
        "permissions": [
            "dashboard:view",
            "users:view",
            "users:manage",
            "tasks:view",
            "orders:view",
            "orders:refund",
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
            "logs:view",
            "credits:view",
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
    if isinstance(value, float) and not value.is_integer():
        raise BizError(code=4341, message=f"{field} 必须是整数")
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


def _fen_to_cny_api(value_fen: int) -> float:
    amount = fen_to_cny(int(value_fen or 0))
    return cny_to_api(amount or 0)


def _resolve_admin_adjust_delta_fen(req: AdminAdjustCreditReq) -> int:
    if req.delta_cny is not None:
        amount = to_cny_decimal(req.delta_cny)
        return cny_to_fen(amount)
    if req.delta_fen is not None:
        return int(req.delta_fen)
    if req.delta is not None:
        return int(req.delta)
    raise BizError(code=4302, message="调整值不能为空")


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


def _order_package_snapshot(order: Order) -> dict:
    snapshot = order.package_snapshot if isinstance(order.package_snapshot, dict) else {}
    credits = int(snapshot.get("credits") or order.credits or 0)
    amount_cny = round(float(snapshot.get("price") or cny_to_api(order.amount_cny)), 2)
    price_per_kchar = round(amount_cny / (credits / 1000.0), 2) if credits > 0 else 0.0
    return {
        "name": str(snapshot.get("name", "")).strip(),
        "price": amount_cny,
        "credits": credits,
        "processable_chars": int(snapshot.get("processable_chars") or credits),
        "price_per_kchar": price_per_kchar,
        "price_per_kchar_label": f"{price_per_kchar:.2f} 元/千字",
        "badge": str(snapshot.get("badge", "")).strip(),
        "description": str(snapshot.get("description", "")).strip(),
        "audience": str(snapshot.get("audience", "")).strip(),
        "discount_note": str(snapshot.get("discount_note", "")).strip(),
        "sort_order": int(snapshot.get("sort_order") or 999),
    }


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
    runtime_copy_source = src.get("runtime_copy")
    login_copy_source = runtime_copy_source.get("login") if isinstance(runtime_copy_source, dict) and isinstance(runtime_copy_source.get("login"), dict) else {}
    home_copy_source = runtime_copy_source.get("home") if isinstance(runtime_copy_source, dict) and isinstance(runtime_copy_source.get("home"), dict) else {}
    profile_copy_source = runtime_copy_source.get("profile") if isinstance(runtime_copy_source, dict) and isinstance(runtime_copy_source.get("profile"), dict) else {}
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
    payload["police_filing_no"] = _as_text(src.get("police_filing_no", payload["police_filing_no"]), default="", max_len=128)
    payload["police_filing_url"] = _as_text(src.get("police_filing_url", payload["police_filing_url"]), default="", max_len=256)
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
    payload["runtime_copy"]["login"]["brand_name"] = _as_text(
        login_copy_source.get("brand_name", payload["runtime_copy"]["login"]["brand_name"]),
        default=payload["runtime_copy"]["login"]["brand_name"],
        max_len=32,
    )
    payload["runtime_copy"]["login"]["brand_subtitle"] = _as_text(
        login_copy_source.get("brand_subtitle", payload["runtime_copy"]["login"]["brand_subtitle"]),
        default=payload["runtime_copy"]["login"]["brand_subtitle"],
        max_len=64,
    )
    payload["runtime_copy"]["login"]["agreement_text"] = _as_text(
        login_copy_source.get("agreement_text", payload["runtime_copy"]["login"]["agreement_text"]),
        default=payload["runtime_copy"]["login"]["agreement_text"],
        max_len=80,
    )
    payload["runtime_copy"]["login"]["login_unavailable_title"] = _as_text(
        login_copy_source.get("login_unavailable_title", payload["runtime_copy"]["login"]["login_unavailable_title"]),
        default=payload["runtime_copy"]["login"]["login_unavailable_title"],
        max_len=32,
    )
    payload["runtime_copy"]["login"]["login_unavailable_desc"] = _as_text(
        login_copy_source.get("login_unavailable_desc", payload["runtime_copy"]["login"]["login_unavailable_desc"]),
        default=payload["runtime_copy"]["login"]["login_unavailable_desc"],
        max_len=200,
    )
    payload["runtime_copy"]["login"]["formal_mode_label"] = _as_text(
        login_copy_source.get("formal_mode_label", payload["runtime_copy"]["login"]["formal_mode_label"]),
        default=payload["runtime_copy"]["login"]["formal_mode_label"],
        max_len=40,
    )
    payload["runtime_copy"]["login"]["internal_test_mode_label"] = _as_text(
        login_copy_source.get("internal_test_mode_label", payload["runtime_copy"]["login"]["internal_test_mode_label"]),
        default=payload["runtime_copy"]["login"]["internal_test_mode_label"],
        max_len=40,
    )
    payload["runtime_copy"]["login"]["mock_mode_label"] = _as_text(
        login_copy_source.get("mock_mode_label", payload["runtime_copy"]["login"]["mock_mode_label"]),
        default=payload["runtime_copy"]["login"]["mock_mode_label"],
        max_len=40,
    )
    payload["runtime_copy"]["login"]["prefer_phone_title"] = _as_text(
        login_copy_source.get("prefer_phone_title", payload["runtime_copy"]["login"]["prefer_phone_title"]),
        default=payload["runtime_copy"]["login"]["prefer_phone_title"],
        max_len=32,
    )
    payload["runtime_copy"]["login"]["prefer_phone_content"] = _as_text(
        login_copy_source.get("prefer_phone_content", payload["runtime_copy"]["login"]["prefer_phone_content"]),
        default=payload["runtime_copy"]["login"]["prefer_phone_content"],
        max_len=200,
    )
    payload["runtime_copy"]["login"]["policy_required_title"] = _as_text(
        login_copy_source.get("policy_required_title", payload["runtime_copy"]["login"]["policy_required_title"]),
        default=payload["runtime_copy"]["login"]["policy_required_title"],
        max_len=32,
    )
    payload["runtime_copy"]["login"]["policy_required_content"] = _as_text(
        login_copy_source.get("policy_required_content", payload["runtime_copy"]["login"]["policy_required_content"]),
        default=payload["runtime_copy"]["login"]["policy_required_content"],
        max_len=120,
    )
    payload["runtime_copy"]["login"]["phone_auth_missing_title"] = _as_text(
        login_copy_source.get("phone_auth_missing_title", payload["runtime_copy"]["login"]["phone_auth_missing_title"]),
        default=payload["runtime_copy"]["login"]["phone_auth_missing_title"],
        max_len=32,
    )
    payload["runtime_copy"]["home"]["hero_title"] = _as_text(
        home_copy_source.get("hero_title", payload["runtime_copy"]["home"]["hero_title"]),
        default=payload["runtime_copy"]["home"]["hero_title"],
        max_len=32,
    )
    payload["runtime_copy"]["home"]["hero_subtitle"] = _as_text(
        home_copy_source.get("hero_subtitle", payload["runtime_copy"]["home"]["hero_subtitle"]),
        default=payload["runtime_copy"]["home"]["hero_subtitle"],
        max_len=120,
    )
    payload["runtime_copy"]["home"]["invite_label"] = _as_text(
        home_copy_source.get("invite_label", payload["runtime_copy"]["home"]["invite_label"]),
        default=payload["runtime_copy"]["home"]["invite_label"],
        max_len=24,
    )
    payload["runtime_copy"]["home"]["invite_note"] = _as_text(
        home_copy_source.get("invite_note", payload["runtime_copy"]["home"]["invite_note"]),
        default=payload["runtime_copy"]["home"]["invite_note"],
        max_len=120,
    )
    payload["runtime_copy"]["home"]["copy_invite_button_text"] = _as_text(
        home_copy_source.get("copy_invite_button_text", payload["runtime_copy"]["home"]["copy_invite_button_text"]),
        default=payload["runtime_copy"]["home"]["copy_invite_button_text"],
        max_len=24,
    )
    payload["runtime_copy"]["home"]["share_button_text"] = _as_text(
        home_copy_source.get("share_button_text", payload["runtime_copy"]["home"]["share_button_text"]),
        default=payload["runtime_copy"]["home"]["share_button_text"],
        max_len=24,
    )
    payload["runtime_copy"]["home"]["share_title"] = _as_text(
        home_copy_source.get("share_title", payload["runtime_copy"]["home"]["share_title"]),
        default=payload["runtime_copy"]["home"]["share_title"],
        max_len=64,
    )
    payload["runtime_copy"]["profile"]["guest_subtitle"] = _as_text(
        profile_copy_source.get("guest_subtitle", payload["runtime_copy"]["profile"]["guest_subtitle"]),
        default=payload["runtime_copy"]["profile"]["guest_subtitle"],
        max_len=80,
    )
    payload["runtime_copy"]["profile"]["user_subtitle"] = _as_text(
        profile_copy_source.get("user_subtitle", payload["runtime_copy"]["profile"]["user_subtitle"]),
        default=payload["runtime_copy"]["profile"]["user_subtitle"],
        max_len=80,
    )
    payload["runtime_copy"]["profile"]["guest_section_title"] = _as_text(
        profile_copy_source.get("guest_section_title", payload["runtime_copy"]["profile"]["guest_section_title"]),
        default=payload["runtime_copy"]["profile"]["guest_section_title"],
        max_len=40,
    )
    payload["runtime_copy"]["profile"]["guest_section_desc"] = _as_text(
        profile_copy_source.get("guest_section_desc", payload["runtime_copy"]["profile"]["guest_section_desc"]),
        default=payload["runtime_copy"]["profile"]["guest_section_desc"],
        max_len=120,
    )
    payload["runtime_copy"]["profile"]["guest_login_button_text"] = _as_text(
        profile_copy_source.get("guest_login_button_text", payload["runtime_copy"]["profile"]["guest_login_button_text"]),
        default=payload["runtime_copy"]["profile"]["guest_login_button_text"],
        max_len=20,
    )
    payload["runtime_copy"]["profile"]["account_section_title"] = _as_text(
        profile_copy_source.get("account_section_title", payload["runtime_copy"]["profile"]["account_section_title"]),
        default=payload["runtime_copy"]["profile"]["account_section_title"],
        max_len=32,
    )
    payload["runtime_copy"]["profile"]["promo_section_title"] = _as_text(
        profile_copy_source.get("promo_section_title", payload["runtime_copy"]["profile"]["promo_section_title"]),
        default=payload["runtime_copy"]["profile"]["promo_section_title"],
        max_len=32,
    )
    payload["runtime_copy"]["profile"]["promo_section_desc"] = _as_text(
        profile_copy_source.get("promo_section_desc", payload["runtime_copy"]["profile"]["promo_section_desc"]),
        default=payload["runtime_copy"]["profile"]["promo_section_desc"],
        max_len=120,
    )
    payload["runtime_copy"]["profile"]["system_section_title"] = _as_text(
        profile_copy_source.get("system_section_title", payload["runtime_copy"]["profile"]["system_section_title"]),
        default=payload["runtime_copy"]["profile"]["system_section_title"],
        max_len=32,
    )
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


def _billing_package_names(value) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {
        _as_text(item.get("name"), default="", max_len=32)
        for item in value
        if isinstance(item, dict) and _as_text(item.get("name"), default="", max_len=32)
    }


def _should_upgrade_legacy_billing_packages(raw_packages, *, package_profile_version: int) -> bool:
    package_names = _billing_package_names(raw_packages)
    return bool(package_names) and package_profile_version < DEFAULT_BILLING_PACKAGE_PROFILE_VERSION and package_names.issubset(
        LEGACY_BUILTIN_BILLING_PACKAGE_NAMES
    )


def _normalize_billing_packages(value) -> list[dict]:
    packages = value if isinstance(value, list) else []
    normalized: list[dict] = []
    names: set[str] = set()
    sort_orders: set[int] = set()
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
            item.get("credits", cny_to_fen(price)),
            default=cny_to_fen(price),
            min_value=1,
            max_value=100_000_000,
            field=f"{name}.credits",
        )
        sort_order = _as_int(
            item.get("sort_order", index),
            default=index,
            min_value=1,
            max_value=999,
            field=f"{name}.sort_order",
        )
        if sort_order in sort_orders:
            raise BizError(code=4341, message=f"套餐排序重复: {sort_order}")
        sort_orders.add(sort_order)
        normalized.append(
            {
                "name": name,
                "price": price,
                "credits": credits,
                "description": _as_text(item.get("description"), default="", max_len=120),
                "badge": _as_text(item.get("badge"), default="", max_len=20),
                "audience": _as_text(item.get("audience"), default="", max_len=40),
                "discount_note": _as_text(item.get("discount_note"), default="", max_len=40),
                "sort_order": sort_order,
                "enabled": _as_bool(item.get("enabled", True), default=True),
            }
        )
    if not normalized:
        raise BizError(code=4341, message="至少需要配置 1 个套餐")
    if not any(bool(item.get("enabled", False)) for item in normalized):
        raise BizError(code=4341, message="至少需要启用 1 个套餐")
    normalized.sort(key=lambda item: (int(item.get("sort_order", 999)), item.get("name", "")))
    return normalized


def _normalize_category_payload(category: str, payload: dict) -> dict:
    base = deepcopy(CONFIG_DEFAULTS[category])
    raw = payload if isinstance(payload, dict) else {}

    if category == "rewrite_strategy":
        return normalize_rewrite_strategy_config(raw)
    if category == "dedup_strategy":
        return normalize_dedup_strategy_config(raw)

    if category == "billing":
        schema_version = _as_int(
            raw.get("schema_version", base.get("schema_version", DEFAULT_BILLING_SCHEMA_VERSION)),
            default=DEFAULT_BILLING_SCHEMA_VERSION,
            min_value=1,
            max_value=99,
            field="schema_version",
        )
        package_profile_version = _as_int(
            raw.get(
                "package_profile_version",
                raw.get("packages_version", base.get("package_profile_version", DEFAULT_BILLING_PACKAGE_PROFILE_VERSION)),
            ),
            default=DEFAULT_BILLING_PACKAGE_PROFILE_VERSION,
            min_value=1,
            max_value=99,
            field="package_profile_version",
        )
        raw_packages = raw.get("packages", base.get("packages", []))
        if _should_upgrade_legacy_billing_packages(raw_packages, package_profile_version=package_profile_version):
            raw_packages = deepcopy(DEFAULT_BILLING_PACKAGES)
            package_profile_version = DEFAULT_BILLING_PACKAGE_PROFILE_VERSION
        base["aigc_points_per_char"] = _as_int(
            raw.get("aigc_points_per_char", raw.get("aigc_rate", base["aigc_points_per_char"])),
            default=1,
            min_value=1,
            max_value=9999,
            field="aigc_points_per_char",
        )
        base["dedup_points_per_char"] = _as_int(
            raw.get("dedup_points_per_char", raw.get("dedup_rate", base["dedup_points_per_char"])),
            default=1,
            min_value=1,
            max_value=9999,
            field="dedup_points_per_char",
        )
        base["rewrite_points_per_char"] = _as_int(
            raw.get("rewrite_points_per_char", raw.get("rewrite_rate", base["rewrite_points_per_char"])),
            default=1,
            min_value=1,
            max_value=9999,
            field="rewrite_points_per_char",
        )
        base["schema_version"] = max(schema_version, DEFAULT_BILLING_SCHEMA_VERSION)
        base["package_profile_version"] = max(package_profile_version, DEFAULT_BILLING_PACKAGE_PROFILE_VERSION)
        base["packages"] = _normalize_billing_packages(raw_packages)
        return base

    if category == "user_navigation":
        return normalize_user_navigation_config(raw)

    if category == "promo_center":
        return _normalize_promo_center_config(raw, base)

    if category == "aigc_detect_strategy":
        return normalize_aigc_detect_strategy_config(raw)

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
        base["miniapp_internal_test_login_enabled"] = _as_bool(
            raw.get("miniapp_internal_test_login_enabled", base.get("miniapp_internal_test_login_enabled", False)),
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


def _normalize_promo_text_list(values, *, limit: int, max_len: int) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    for item in values:
        text = _as_text(item, default="", max_len=max_len)
        if not text:
            continue
        result.append(text)
        if len(result) >= limit:
            break
    return result


def _normalize_promo_contacts(raw_contacts) -> dict[str, list[str]]:
    contacts = raw_contacts if isinstance(raw_contacts, dict) else {}
    normalized: dict[str, list[str]] = {"phone": [], "wechat": [], "email": []}
    for key in ("phone", "wechat", "email"):
        values = contacts.get(key)
        if not isinstance(values, list):
            values = []
        bucket: list[str] = []
        seen = set()
        for item in values:
            text = _as_text(item, default="", max_len=128)
            if not text:
                continue
            dedup_key = text.lower()
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            bucket.append(text)
            if len(bucket) >= 20:
                break
        normalized[key] = bucket
    return normalized


def _normalize_promo_nav_cards(raw_cards, default_cards: list[dict]) -> list[dict]:
    source_cards = raw_cards if isinstance(raw_cards, list) else []
    source_map = {}
    for item in source_cards:
        if not isinstance(item, dict):
            continue
        key = _as_text(item.get("key"), default="", max_len=32).lower()
        if key in PROMO_CENTER_CARD_KEYS:
            source_map[key] = item
    cards: list[dict] = []
    for index, default_card in enumerate(default_cards):
        key = default_card["key"]
        current = source_map.get(key, {})
        cards.append(
            {
                "key": key,
                "title": _as_text(current.get("title", default_card.get("title", "")), default=default_card.get("title", ""), max_len=32),
                "badge": _as_text(current.get("badge", default_card.get("badge", "")), default=default_card.get("badge", ""), max_len=32),
                "description": _as_text(
                    current.get("description", default_card.get("description", "")),
                    default=default_card.get("description", ""),
                    max_len=120,
                ),
                "sort_order": _as_int(current.get("sort_order", default_card.get("sort_order", index + 1)), default=index + 1, min_value=1, max_value=99),
                "enabled": _as_bool(current.get("enabled", default_card.get("enabled", True)), default=default_card.get("enabled", True)),
            }
        )
    cards.sort(key=lambda item: (int(item.get("sort_order") or 0), item["key"]))
    return cards


def _normalize_promo_reward_tiers(raw_tiers, *, default_tiers: list[dict], threshold_max: int = 100000, reward_max: int = 1000000) -> list[dict]:
    tiers = raw_tiers if isinstance(raw_tiers, list) else []
    normalized: list[dict] = []
    for index, item in enumerate(tiers):
        if not isinstance(item, dict):
            continue
        threshold = _as_int(item.get("threshold", 0), default=0, min_value=0, max_value=threshold_max)
        reward_points = _as_int(item.get("reward_points", 0), default=0, min_value=0, max_value=reward_max)
        label = _as_text(item.get("label", ""), default="", max_len=48)
        if reward_points <= 0:
            continue
        normalized.append({"threshold": threshold, "reward_points": reward_points, "label": label})
        if len(normalized) >= 12:
            break
    if normalized:
        normalized.sort(key=lambda item: (int(item["threshold"]), int(item["reward_points"])))
        return normalized
    return deepcopy(default_tiers)


def _normalize_promo_platforms(raw_platforms, default_platforms: list[dict]) -> list[dict]:
    source_items = raw_platforms if isinstance(raw_platforms, list) else []
    source_map = {}
    for item in source_items:
        if not isinstance(item, dict):
            continue
        key = _as_text(item.get("key"), default="", max_len=32).lower()
        if key:
            source_map[key] = item
    result: list[dict] = []
    for default_item in default_platforms:
        key = default_item["key"]
        current = source_map.get(key, {})
        result.append(
            {
                "key": key,
                "label": _as_text(current.get("label", default_item.get("label", "")), default=default_item.get("label", ""), max_len=24),
                "status_text": _as_text(
                    current.get("status_text", default_item.get("status_text", "")),
                    default=default_item.get("status_text", ""),
                    max_len=32,
                ),
                "enabled": _as_bool(current.get("enabled", default_item.get("enabled", True)), default=default_item.get("enabled", True)),
            }
        )
    return result


def _normalize_promo_other_entries(raw_entries) -> list[dict]:
    if not isinstance(raw_entries, list):
        return []
    items: list[dict] = []
    for item in raw_entries:
        if not isinstance(item, dict):
            continue
        title = _as_text(item.get("title", ""), default="", max_len=32)
        description = _as_text(item.get("description", ""), default="", max_len=120)
        qrcode_url = _as_text(item.get("qrcode_url", ""), default="", max_len=256)
        if not title and not description and not qrcode_url:
            continue
        items.append(
            {
                "title": title,
                "description": description,
                "qrcode_url": qrcode_url,
                "enabled": _as_bool(item.get("enabled", True), default=True),
            }
        )
        if len(items) >= 8:
            break
    return items


def _normalize_promo_partner_cards(raw_contacts, default_contacts: list[dict]) -> list[dict]:
    source_items = raw_contacts if isinstance(raw_contacts, list) else []
    result: list[dict] = []
    for index, default_item in enumerate(default_contacts):
        current = source_items[index] if index < len(source_items) and isinstance(source_items[index], dict) else {}
        result.append(
            {
                "title": _as_text(current.get("title", default_item.get("title", "")), default=default_item.get("title", ""), max_len=32),
                "description": _as_text(
                    current.get("description", default_item.get("description", "")),
                    default=default_item.get("description", ""),
                    max_len=120,
                ),
                "wechat_id": _as_text(current.get("wechat_id", default_item.get("wechat_id", "")), default=default_item.get("wechat_id", ""), max_len=64),
                "qrcode_url": _as_text(current.get("qrcode_url", default_item.get("qrcode_url", "")), default=default_item.get("qrcode_url", ""), max_len=256),
                "enabled": _as_bool(current.get("enabled", default_item.get("enabled", True)), default=default_item.get("enabled", True)),
            }
        )
    return result


def _normalize_promo_pages(raw_pages, base_pages: dict, contacts: dict[str, list[str]], assets: dict, invite_reward_points: int) -> dict:
    pages_source = raw_pages if isinstance(raw_pages, dict) else {}
    normalized_pages: dict[str, dict] = {}

    invite_default = deepcopy(base_pages["invite"])
    invite_source = pages_source.get("invite") if isinstance(pages_source.get("invite"), dict) else {}
    invite_default["rule_lines"] = [
        f"被邀请者完成手机号与微信绑定后，可获得 {max(0, int(invite_reward_points or 0))} 点数。",
        f"邀请者每产生 1 个有效邀请，可获得 {max(0, int(invite_reward_points // 2 or 0))} 点数。",
        "支持配置里程碑加奖，全部奖励均以点数发放。",
    ]
    normalized_pages["invite"] = {
        "enabled": _as_bool(invite_source.get("enabled", invite_default.get("enabled", True)), default=invite_default.get("enabled", True)),
        "title": _as_text(invite_source.get("title", invite_default.get("title", "")), default=invite_default.get("title", ""), max_len=32),
        "subtitle": _as_text(invite_source.get("subtitle", invite_default.get("subtitle", "")), default=invite_default.get("subtitle", ""), max_len=180),
        "rule_lines": _normalize_promo_text_list(invite_source.get("rule_lines", invite_default.get("rule_lines", [])), limit=6, max_len=120),
        "quick_actions_title": _as_text(
            invite_source.get("quick_actions_title", invite_default.get("quick_actions_title", "")),
            default=invite_default.get("quick_actions_title", ""),
            max_len=32,
        ),
        "bind_code_label": _as_text(invite_source.get("bind_code_label", invite_default.get("bind_code_label", "")), default=invite_default.get("bind_code_label", ""), max_len=32),
        "bind_code_placeholder": _as_text(
            invite_source.get("bind_code_placeholder", invite_default.get("bind_code_placeholder", "")),
            default=invite_default.get("bind_code_placeholder", ""),
            max_len=64,
        ),
        "bind_code_button_text": _as_text(
            invite_source.get("bind_code_button_text", invite_default.get("bind_code_button_text", "")),
            default=invite_default.get("bind_code_button_text", ""),
            max_len=24,
        ),
        "share_copy_title": _as_text(invite_source.get("share_copy_title", invite_default.get("share_copy_title", "")), default=invite_default.get("share_copy_title", ""), max_len=32),
        "share_copy_text": _as_text(invite_source.get("share_copy_text", invite_default.get("share_copy_text", "")), default=invite_default.get("share_copy_text", ""), max_len=300),
        "miniapp_guide_title": _as_text(
            invite_source.get("miniapp_guide_title", invite_default.get("miniapp_guide_title", "")),
            default=invite_default.get("miniapp_guide_title", ""),
            max_len=40,
        ),
        "miniapp_steps": _normalize_promo_text_list(invite_source.get("miniapp_steps", invite_default.get("miniapp_steps", [])), limit=5, max_len=80),
        "bind_code_notice": _as_text(
            invite_source.get("bind_code_notice", invite_default.get("bind_code_notice", "")),
            default=invite_default.get("bind_code_notice", ""),
            max_len=120,
        ),
    }

    like_default = deepcopy(base_pages["like"])
    like_source = pages_source.get("like") if isinstance(pages_source.get("like"), dict) else {}
    normalized_pages["like"] = {
        "enabled": _as_bool(like_source.get("enabled", like_default.get("enabled", True)), default=like_default.get("enabled", True)),
        "title": _as_text(like_source.get("title", like_default.get("title", "")), default=like_default.get("title", ""), max_len=32),
        "subtitle": _as_text(like_source.get("subtitle", like_default.get("subtitle", "")), default=like_default.get("subtitle", ""), max_len=180),
        "rule_lines": _normalize_promo_text_list(like_source.get("rule_lines", like_default.get("rule_lines", [])), limit=6, max_len=120),
        "qrcode_title": _as_text(like_source.get("qrcode_title", like_default.get("qrcode_title", "")), default=like_default.get("qrcode_title", ""), max_len=32),
        "review_notice": _as_text(like_source.get("review_notice", like_default.get("review_notice", "")), default=like_default.get("review_notice", ""), max_len=180),
        "other_entries_title": _as_text(
            like_source.get("other_entries_title", like_default.get("other_entries_title", "")),
            default=like_default.get("other_entries_title", ""),
            max_len=32,
        ),
        "other_entries": _normalize_promo_other_entries(like_source.get("other_entries", like_default.get("other_entries", []))),
    }

    create_default = deepcopy(base_pages["create"])
    create_source = pages_source.get("create") if isinstance(pages_source.get("create"), dict) else {}
    normalized_pages["create"] = {
        "enabled": _as_bool(create_source.get("enabled", create_default.get("enabled", True)), default=create_default.get("enabled", True)),
        "title": _as_text(create_source.get("title", create_default.get("title", "")), default=create_default.get("title", ""), max_len=32),
        "subtitle": _as_text(create_source.get("subtitle", create_default.get("subtitle", "")), default=create_default.get("subtitle", ""), max_len=180),
        "rule_lines": _normalize_promo_text_list(create_source.get("rule_lines", create_default.get("rule_lines", [])), limit=6, max_len=120),
        "platforms": _normalize_promo_platforms(create_source.get("platforms", create_default.get("platforms", [])), create_default.get("platforms", [])),
        "template_title": _as_text(create_source.get("template_title", create_default.get("template_title", "")), default=create_default.get("template_title", ""), max_len=32),
        "templates": _normalize_promo_text_list(create_source.get("templates", create_default.get("templates", [])), limit=8, max_len=220),
        "submit_placeholder": _as_text(create_source.get("submit_placeholder", create_default.get("submit_placeholder", "")), default=create_default.get("submit_placeholder", ""), max_len=64),
        "submit_button_text": _as_text(create_source.get("submit_button_text", create_default.get("submit_button_text", "")), default=create_default.get("submit_button_text", ""), max_len=24),
        "history_button_text": _as_text(create_source.get("history_button_text", create_default.get("history_button_text", "")), default=create_default.get("history_button_text", ""), max_len=24),
    }

    partner_default = deepcopy(base_pages["partner"])
    partner_source = pages_source.get("partner") if isinstance(pages_source.get("partner"), dict) else {}
    legacy_partner_cards = [
        {
            "title": "电话联系",
            "description": "机构合作电话",
            "wechat_id": "",
            "qrcode_url": "",
            "enabled": len(contacts.get("phone", [])) > 0,
        },
        {
            "title": "微信联系",
            "description": "机构合作微信",
            "wechat_id": contacts.get("wechat", [""])[0] if contacts.get("wechat") else "",
            "qrcode_url": assets.get("partner_primary_qrcode_url", ""),
            "enabled": True,
        },
    ]
    partner_cards_source = partner_source.get("contacts")
    if not isinstance(partner_cards_source, list) and contacts.get("wechat"):
        partner_cards_source = legacy_partner_cards
    normalized_pages["partner"] = {
        "enabled": _as_bool(partner_source.get("enabled", partner_default.get("enabled", True)), default=partner_default.get("enabled", True)),
        "title": _as_text(partner_source.get("title", partner_default.get("title", "")), default=partner_default.get("title", ""), max_len=32),
        "subtitle": _as_text(partner_source.get("subtitle", partner_default.get("subtitle", "")), default=partner_default.get("subtitle", ""), max_len=180),
        "description": _as_text(partner_source.get("description", partner_default.get("description", "")), default=partner_default.get("description", ""), max_len=240),
        "benefits": _normalize_promo_text_list(partner_source.get("benefits", partner_default.get("benefits", [])), limit=6, max_len=120),
        "contacts": _normalize_promo_partner_cards(partner_cards_source, partner_default.get("contacts", [])),
    }
    return normalized_pages


def _normalize_promo_center_config(raw: dict, base: dict) -> dict:
    source = raw if isinstance(raw, dict) else {}
    normalized = deepcopy(base)
    normalized["enabled"] = _as_bool(source.get("enabled", base.get("enabled", True)), default=True)
    normalized["schema_version"] = _as_int(source.get("schema_version", base.get("schema_version", 2)), default=2, min_value=1, max_value=99)
    normalized["updated_by"] = _as_text(source.get("updated_by", base.get("updated_by", "")), default=base.get("updated_by", ""), max_len=64)
    normalized["updated_at"] = _as_text(source.get("updated_at", base.get("updated_at", "")), default=base.get("updated_at", ""), max_len=64)
    normalized["invite_reward_points"] = _as_int(
        source.get("invite_reward_points", base.get("invite_reward_points", 2000)),
        default=2000,
        min_value=0,
        max_value=100_000,
        field="invite_reward_points",
    )
    normalized["contacts"] = _normalize_promo_contacts(source.get("contacts", base.get("contacts", {})))

    assets_source = source.get("assets") if isinstance(source.get("assets"), dict) else {}
    base_assets = base.get("assets", {})
    normalized["assets"] = {
        "like_qrcode_url": _as_text(assets_source.get("like_qrcode_url", base_assets.get("like_qrcode_url", "")), default=base_assets.get("like_qrcode_url", ""), max_len=256),
        "invite_example_image_url": _as_text(
            assets_source.get("invite_example_image_url", base_assets.get("invite_example_image_url", "")),
            default=base_assets.get("invite_example_image_url", ""),
            max_len=256,
        ),
        "partner_primary_qrcode_url": _as_text(
            assets_source.get("partner_primary_qrcode_url", base_assets.get("partner_primary_qrcode_url", "")),
            default=base_assets.get("partner_primary_qrcode_url", ""),
            max_len=256,
        ),
        "partner_secondary_qrcode_url": _as_text(
            assets_source.get("partner_secondary_qrcode_url", base_assets.get("partner_secondary_qrcode_url", "")),
            default=base_assets.get("partner_secondary_qrcode_url", ""),
            max_len=256,
        ),
        "platform_douyin_qrcode_url": _as_text(
            assets_source.get("platform_douyin_qrcode_url", base_assets.get("platform_douyin_qrcode_url", "")),
            default=base_assets.get("platform_douyin_qrcode_url", ""),
            max_len=256,
        ),
        "platform_xiaohongshu_qrcode_url": _as_text(
            assets_source.get("platform_xiaohongshu_qrcode_url", base_assets.get("platform_xiaohongshu_qrcode_url", "")),
            default=base_assets.get("platform_xiaohongshu_qrcode_url", ""),
            max_len=256,
        ),
        "platform_bilibili_qrcode_url": _as_text(
            assets_source.get("platform_bilibili_qrcode_url", base_assets.get("platform_bilibili_qrcode_url", "")),
            default=base_assets.get("platform_bilibili_qrcode_url", ""),
            max_len=256,
        ),
        "platform_wechat_qrcode_url": _as_text(
            assets_source.get("platform_wechat_qrcode_url", base_assets.get("platform_wechat_qrcode_url", "")),
            default=base_assets.get("platform_wechat_qrcode_url", ""),
            max_len=256,
        ),
    }

    normalized["nav_cards"] = _normalize_promo_nav_cards(source.get("nav_cards"), base.get("nav_cards", []))

    reward_source = source.get("reward_rules") if isinstance(source.get("reward_rules"), dict) else {}
    reward_base = base.get("reward_rules", {})
    invite_rule_source = reward_source.get("invite") if isinstance(reward_source.get("invite"), dict) else {}
    like_rule_source = reward_source.get("like") if isinstance(reward_source.get("like"), dict) else {}
    create_rule_source = reward_source.get("create") if isinstance(reward_source.get("create"), dict) else {}
    legacy_inviter_points = normalized["invite_reward_points"] if ("invite_reward_points" in source and not invite_rule_source) else max(0, normalized["invite_reward_points"] // 2)
    normalized["reward_rules"] = {
        "invite": {
            "invitee_bind_reward_points": _as_int(
                invite_rule_source.get("invitee_bind_reward_points", normalized["invite_reward_points"]),
                default=normalized["invite_reward_points"],
                min_value=0,
                max_value=1_000_000,
            ),
            "inviter_valid_invite_reward_points": _as_int(
                invite_rule_source.get("inviter_valid_invite_reward_points", legacy_inviter_points),
                default=legacy_inviter_points,
                min_value=0,
                max_value=1_000_000,
            ),
            "audit_mode": _as_text(invite_rule_source.get("audit_mode", reward_base.get("invite", {}).get("audit_mode", "manual")), default="manual", max_len=32),
            "auto_grant": _as_bool(invite_rule_source.get("auto_grant", reward_base.get("invite", {}).get("auto_grant", False)), default=False),
            "milestones": _normalize_promo_reward_tiers(
                invite_rule_source.get("milestones"),
                default_tiers=reward_base.get("invite", {}).get("milestones", []),
            ),
        },
        "like": {
            "audit_mode": _as_text(like_rule_source.get("audit_mode", reward_base.get("like", {}).get("audit_mode", "manual")), default="manual", max_len=32),
            "auto_grant": _as_bool(like_rule_source.get("auto_grant", reward_base.get("like", {}).get("auto_grant", False)), default=False),
            "tiers": _normalize_promo_reward_tiers(
                like_rule_source.get("tiers"),
                default_tiers=reward_base.get("like", {}).get("tiers", []),
            ),
        },
        "create": {
            "audit_mode": _as_text(create_rule_source.get("audit_mode", reward_base.get("create", {}).get("audit_mode", "manual")), default="manual", max_len=32),
            "auto_grant": _as_bool(create_rule_source.get("auto_grant", reward_base.get("create", {}).get("auto_grant", False)), default=False),
            "tiers": _normalize_promo_reward_tiers(
                create_rule_source.get("tiers"),
                default_tiers=reward_base.get("create", {}).get("tiers", []),
            ),
        },
    }

    normalized["pages"] = _normalize_promo_pages(
        source.get("pages"),
        base.get("pages", {}),
        normalized["contacts"],
        normalized["assets"],
        normalized["reward_rules"]["invite"]["invitee_bind_reward_points"],
    )
    invite_page_source = source.get("pages", {}).get("invite") if isinstance(source.get("pages"), dict) and isinstance(source.get("pages", {}).get("invite"), dict) else {}
    if not invite_page_source.get("rule_lines"):
        normalized["pages"]["invite"]["rule_lines"] = [
            f"被邀请者完成手机号与微信绑定后，可获得 {normalized['reward_rules']['invite']['invitee_bind_reward_points']} 点数。",
            f"邀请者每产生 1 个有效邀请，可获得 {normalized['reward_rules']['invite']['inviter_valid_invite_reward_points']} 点数。",
            "支持配置里程碑加奖，全部奖励均以点数发放。",
        ]

    normalized["contacts"] = _normalize_promo_contacts(source.get("contacts", normalized["contacts"]))
    return normalized


def _store_promo_asset_upload(upload: UploadFile, *, slot: str) -> tuple[str, str]:
    filename = str(upload.filename or "").strip()
    if not filename:
        raise BizError(code=4101, message="请先选择图片文件")
    suffix = Path(filename).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise BizError(code=4104, message="图片仅支持 png、jpg、jpeg、webp")
    safe_slot = re.sub(r"[^a-z0-9_-]+", "-", str(slot or "").strip().lower()).strip("-") or "promo-asset"
    original_name, unique_name = build_storage_name(filename, f"{safe_slot}.png")
    target_path = settings.upload_dir / "promo" / "assets" / unique_name
    save_upload_to(target_path, upload, MAX_FILE_SIZE_MB * 1024 * 1024)
    return serialize_task_artifact_path(target_path) or str(target_path), original_name


def _category_readiness(category: str, value: dict) -> dict:
    if category == "billing":
        rate_ok = all(float(value.get(k, 0) or 0) > 0 for k in ("aigc_points_per_char", "dedup_points_per_char", "rewrite_points_per_char"))
        packages = value.get("packages") if isinstance(value.get("packages"), list) else []
        enabled_count = sum(1 for item in packages if isinstance(item, dict) and bool(item.get("enabled")))
        pkg_ok = enabled_count >= 1
        ok = rate_ok and pkg_ok
        if not rate_ok:
            message = "任务点数单价配置异常"
        elif not pkg_ok:
            message = "至少需启用 1 个通用点数套餐"
        else:
            message = f"点数计费与套餐已就绪（启用 {enabled_count} 个套餐）"
        return {"category": category, "status": "ready" if ok else "error", "message": message}
    if category == "user_navigation":
        navigation = normalize_user_navigation_config(value)
        items = navigation.get("items", [])
        visible_count = sum(1 for item in items if item.get("visible"))
        if visible_count <= 0:
            return {"category": category, "status": "error", "message": "前台导航至少需展示 1 个功能"}
        return {"category": category, "status": "ready", "message": f"前台导航已编排（展示 {visible_count} 个功能）"}
    if category == "promo_center":
        promo = _normalize_promo_center_config(value, deepcopy(CONFIG_DEFAULTS["promo_center"]))
        enabled = bool(promo.get("enabled", True))
        if not enabled:
            return {"category": category, "status": "warning", "message": "推广中心已关闭"}
        reward_points = int(promo.get("reward_rules", {}).get("invite", {}).get("invitee_bind_reward_points") or promo.get("invite_reward_points") or 0)
        cards = promo.get("nav_cards") if isinstance(promo.get("nav_cards"), list) else []
        enabled_cards = [item for item in cards if isinstance(item, dict) and item.get("enabled") is not False]
        if not enabled_cards:
            return {"category": category, "status": "warning", "message": "顶部活动卡片未启用，前台将无法切页"}
        partner_contacts = promo.get("pages", {}).get("partner", {}).get("contacts")
        partner_count = 0
        if isinstance(partner_contacts, list):
            partner_count = len([item for item in partner_contacts if isinstance(item, dict) and item.get("enabled") is not False and (item.get("qrcode_url") or item.get("wechat_id"))])
        if partner_count <= 0:
            return {"category": category, "status": "warning", "message": "机构合作页未配置有效二维码或微信号"}
        if reward_points <= 0:
            return {"category": category, "status": "warning", "message": "邀请页点数奖励未设置，当前仅展示活动内容"}
        return {
            "category": category,
            "status": "ready",
            "message": f"已启用 {len(enabled_cards)} 个活动入口，邀请奖励 {reward_points} 点，机构合作 {partner_count} 个联系卡片",
        }
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
    if category == "aigc_detect_strategy":
        readiness = aigc_detect_strategy_readiness(value)
        return {"category": category, "status": readiness["status"], "message": readiness["message"]}
    if category == "rewrite_strategy":
        readiness = rewrite_strategy_readiness(value)
        return {"category": category, "status": readiness["status"], "message": readiness["message"]}
    if category == "dedup_strategy":
        readiness = dedup_strategy_readiness(value)
        return {"category": category, "status": readiness["status"], "message": readiness["message"]}
    if category == "miniapp":
        miniapp = _extract_miniapp_payload(value)
        if not miniapp["enabled"]:
            return {"category": category, "status": "warning", "message": "小程序配置未启用"}
        base_app_id = str(miniapp.get("app_id") or "")
        base_app_secret = str(miniapp.get("app_secret") or "")
        if not base_app_id or not base_app_secret:
            return {"category": category, "status": "error", "message": "小程序基础配置缺少 AppID / AppSecret"}
        login_enabled = bool(miniapp.get("wechat_miniprogram_login_enabled"))
        payment_enabled = bool(miniapp.get("wechat_miniprogram_payment_enabled"))
        app_id = str(miniapp.get("wechat_miniprogram_app_id") or base_app_id or "")
        app_secret = str(miniapp.get("wechat_miniprogram_app_secret") or base_app_secret or "")
        if login_enabled and (not app_id or not app_secret):
            return {"category": category, "status": "error", "message": "小程序登录已启用但 AppID/AppSecret 未填写完整"}
        api_base_url = str(miniapp.get("api_base_url") or "")
        request_domain = str(miniapp.get("request_domain") or "")
        payment_notify_url = str(miniapp.get("payment_notify_url") or "")
        if (not api_base_url) or (not _is_http_url(api_base_url)):
            return {"category": category, "status": "error", "message": "小程序 API 地址未配置或格式错误"}
        if (not request_domain) or (not _is_https_url(request_domain)):
            return {"category": category, "status": "error", "message": "小程序 request 域名未配置或不是 HTTPS"}
        if payment_enabled and (not payment_notify_url):
            return {"category": category, "status": "error", "message": "小程序支付已启用但未填写 payment_notify_url"}
        if payment_enabled and (not _is_public_https_url(payment_notify_url)):
            return {"category": category, "status": "error", "message": "小程序 payment_notify_url 必须是公网 HTTPS 地址"}
        status_bits: list[str] = []
        status_bits.append("登录已启用" if login_enabled else "登录未启用")
        status_bits.append("支付已启用" if payment_enabled else "支付未启用")
        return {"category": category, "status": "ready", "message": f"小程序配置已就绪（{'；'.join(status_bits)}）"}
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
    if category == "aigc_detect_strategy":
        source = normalize_aigc_detect_strategy_config(source)
    if category == "rewrite_strategy":
        source = normalize_rewrite_strategy_config(source)
    if category == "dedup_strategy":
        source = normalize_dedup_strategy_config(source)
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
        merged["schema_version"] = _as_int(
            merged.get("schema_version", DEFAULT_BILLING_SCHEMA_VERSION),
            default=DEFAULT_BILLING_SCHEMA_VERSION,
            min_value=1,
            max_value=99,
            field="schema_version",
        )
        merged["package_profile_version"] = _as_int(
            merged.get("package_profile_version", merged.get("packages_version", DEFAULT_BILLING_PACKAGE_PROFILE_VERSION)),
            default=DEFAULT_BILLING_PACKAGE_PROFILE_VERSION,
            min_value=1,
            max_value=99,
            field="package_profile_version",
        )
        merged["aigc_points_per_char"] = _as_int(
            merged.get("aigc_points_per_char", merged.get("aigc_rate", 1)),
            default=1,
            min_value=1,
            max_value=9999,
            field="aigc_points_per_char",
        )
        merged["dedup_points_per_char"] = _as_int(
            merged.get("dedup_points_per_char", merged.get("dedup_rate", 1)),
            default=1,
            min_value=1,
            max_value=9999,
            field="dedup_points_per_char",
        )
        merged["rewrite_points_per_char"] = _as_int(
            merged.get("rewrite_points_per_char", merged.get("rewrite_rate", 1)),
            default=1,
            min_value=1,
            max_value=9999,
            field="rewrite_points_per_char",
        )
        merged.pop("aigc_rate", None)
        merged.pop("dedup_rate", None)
        merged.pop("rewrite_rate", None)
        merged.pop("packages_version", None)
        if _should_upgrade_legacy_billing_packages(
            merged.get("packages"),
            package_profile_version=int(merged.get("package_profile_version") or DEFAULT_BILLING_PACKAGE_PROFILE_VERSION),
        ):
            merged["packages"] = deepcopy(DEFAULT_BILLING_PACKAGES)
            merged["package_profile_version"] = DEFAULT_BILLING_PACKAGE_PROFILE_VERSION
        try:
            merged["packages"] = _normalize_billing_packages(merged.get("packages"))
        except BizError:
            merged["packages"] = deepcopy(DEFAULT_BILLING_PACKAGES)
            merged["package_profile_version"] = DEFAULT_BILLING_PACKAGE_PROFILE_VERSION
        merged["schema_version"] = max(int(merged.get("schema_version") or 1), DEFAULT_BILLING_SCHEMA_VERSION)
        merged["package_profile_version"] = max(
            int(merged.get("package_profile_version") or 1),
            DEFAULT_BILLING_PACKAGE_PROFILE_VERSION,
        )
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
    elif category == "promo_center":
        value = deepcopy(value)
        value["updated_by"] = getattr(admin, "username", "") or f"admin#{admin.id}"
        value["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")

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
    return platform_label(platform)


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
    readiness_map = {}
    for category in ("login", "payment", "billing", "llm", "miniapp", "aigc_detect_strategy"):
        readiness_map[category] = _category_readiness(category, _get_category_config(db, category, redact=False))
    strategy_rows = list_process_strategies(db).get("items", [])
    strategy_total = len(strategy_rows)
    strategy_enabled = sum(1 for item in strategy_rows if bool(item.get("is_enabled")))
    task_status_rows = db.query(Task.status, func.count(Task.id)).group_by(Task.status).all()
    task_status_map = {
        (status.value if hasattr(status, "value") else str(status)): int(count)
        for status, count in task_status_rows
    }
    refund_pending_count = int(
        db.query(Task)
        .filter(Task.status == TaskStatus.FAILED, Task.cost_credits > 0, Task.refund_done.is_(False))
        .count()
    )
    paid_not_refunded_orders = int(db.query(Order).filter(Order.status == "paid").count())
    llm_error_24h = int(
        db.query(LLMErrorLog)
        .filter(LLMErrorLog.created_at >= datetime.utcnow() - timedelta(hours=24))
        .count()
    )
    baseline_status = "ready"
    baseline_reasons: list[str] = []
    for category in ("login", "payment", "billing"):
        status = readiness_map.get(category, {}).get("status")
        if status == "error":
            baseline_status = "error"
            baseline_reasons.append(f"{CONFIG_LABELS.get(category, category)}未就绪")
        elif status == "warning" and baseline_status != "error":
            baseline_status = "warning"
            baseline_reasons.append(f"{CONFIG_LABELS.get(category, category)}待确认")
    if strategy_enabled <= 0:
        baseline_status = "error"
        baseline_reasons.append("任务策略未启用")
    operational_alerts = []
    if task_status_map.get("failed", 0) > 0:
        operational_alerts.append({"level": "warning", "key": "failed_tasks", "message": f"当前有 {task_status_map.get('failed', 0)} 个失败任务，请及时复核。"})
    if refund_pending_count > 0:
        operational_alerts.append({"level": "error", "key": "refund_pending", "message": f"当前有 {refund_pending_count} 个失败任务尚未退款。"})
    if readiness_map.get("payment", {}).get("status") == "warning":
        operational_alerts.append({"level": "warning", "key": "payment_mode", "message": str(readiness_map.get("payment", {}).get("message") or "支付配置待确认")})
    if readiness_map.get("miniapp", {}).get("status") == "error":
        operational_alerts.append({"level": "warning", "key": "miniapp_config", "message": str(readiness_map.get("miniapp", {}).get("message") or "小程序配置未就绪")})
    if llm_error_24h > 0:
        operational_alerts.append({"level": "warning", "key": "llm_errors", "message": f"最近 24 小时共有 {llm_error_24h} 条 LLM 异常日志。"})
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
            "mvp_baseline": {
                "status": baseline_status,
                "reasons": baseline_reasons,
                "items": [
                    {
                        "key": "login",
                        "label": "账户与登录",
                        "status": readiness_map["login"]["status"],
                        "message": readiness_map["login"]["message"],
                    },
                    {
                        "key": "payment",
                        "label": "支付与订单",
                        "status": readiness_map["payment"]["status"],
                        "message": readiness_map["payment"]["message"],
                    },
                    {
                        "key": "billing",
                        "label": "点数计费",
                        "status": readiness_map["billing"]["status"],
                        "message": readiness_map["billing"]["message"],
                    },
                    {
                        "key": "tasks",
                        "label": "任务处理",
                        "status": "ready" if strategy_enabled > 0 else "error",
                        "message": f"已启用 {strategy_enabled}/{strategy_total} 条任务策略",
                    },
                    {
                        "key": "llm",
                        "label": "算法与大模型",
                        "status": readiness_map["llm"]["status"],
                        "message": readiness_map["llm"]["message"],
                    },
                    {
                        "key": "miniapp",
                        "label": "小程序",
                        "status": readiness_map["miniapp"]["status"],
                        "message": readiness_map["miniapp"]["message"],
                    },
                ],
            },
            "operational_alerts": operational_alerts,
            "ops_summary": {
                "task_status": task_status_map,
                "refund_pending_count": refund_pending_count,
                "paid_order_count": paid_not_refunded_orders,
                "llm_error_24h": llm_error_24h,
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
            "balance_fen": int(u.credits or 0),
            "balance_cny": _fen_to_cny_api(u.credits or 0),
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
    delta_fen = _resolve_admin_adjust_delta_fen(req)
    if delta_fen == 0:
        raise BizError(code=4302, message="调整值不能为0")
    before_balance_fen = int(user.credits or 0)
    change_credits(
        db,
        user,
        tx_type=CreditType.ADMIN_ADJUST,
        delta=delta_fen,
        reason=f"管理员[{admin.username}]调整点数:{req.reason}",
        related_id=f"admin_adjust:{admin.id}:{datetime.utcnow().timestamp()}",
        source="admin",
    )
    db.add(
        AdminAuditLog(
            admin_id=admin.id,
            action="user_credit_adjust",
            target_type="user",
            target_id=str(user.id),
            before_json={"balance_fen": before_balance_fen, "delta_fen": delta_fen},
            after_json={"balance_fen": int(user.credits or 0), "delta_fen": delta_fen, "reason": req.reason},
        )
    )
    db.commit()
    return ok(
        data={
            "user_id": user.id,
            "balance_fen": int(user.credits or 0),
            "balance_cny": _fen_to_cny_api(user.credits or 0),
            "credits": user.credits,
        }
    )


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
    total_recharge_fen = int(sum(int(o.credits or 0) for o in orders))
    total_task_cost_fen = int(
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
                "balance_fen": int(user.credits or 0),
                "balance_cny": _fen_to_cny_api(user.credits or 0),
                "credits": user.credits,
                "is_banned": user.is_banned,
                "source": _normalize_source_bucket(user.source),
                "created_at": user.created_at,
            },
            "summary": {
                "total_paid_cny": total_paid_cny,
                "total_recharge_fen": total_recharge_fen,
                "total_recharge_cny": _fen_to_cny_api(total_recharge_fen),
                "total_task_cost_fen": total_task_cost_fen,
                "total_task_cost_points": total_task_cost_fen,
                "total_paid_credits": total_recharge_fen,
                "total_task_cost_credits": total_task_cost_fen,
            },
            "credit_transactions": [
                {
                    "id": tx.id,
                    "tx_type": tx.tx_type.value,
                    "source": _normalize_source_bucket(tx.source),
                    "delta_fen": int(tx.delta or 0),
                    "delta_cny": _fen_to_cny_api(tx.delta or 0),
                    "balance_before_fen": int(tx.balance_before or 0),
                    "balance_before_cny": _fen_to_cny_api(tx.balance_before or 0),
                    "balance_after_fen": int(tx.balance_after or 0),
                    "balance_after_cny": _fen_to_cny_api(tx.balance_after or 0),
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
                    "source": _normalize_source_bucket(t.source),
                    "char_count": t.char_count,
                    "cost_fen": int(t.cost_credits or 0),
                    "cost_points": int(t.cost_credits or 0),
                    "cost_credits": t.cost_credits,
                    "source_filename": t.source_filename,
                    "result_filename": build_task_result_filename(t.task_type, t.source_filename, t.output_path),
                    "filename_pair": build_task_filename_pair(
                        t.source_filename,
                        build_task_result_filename(t.task_type, t.source_filename, t.output_path),
                    ),
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
            "cost_fen": int(t.cost_credits or 0),
            "cost_points": int(t.cost_credits or 0),
            "cost_credits": t.cost_credits,
            "refund_done": bool(t.refund_done),
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
            "cost_fen": int(row.cost_credits or 0),
            "cost_points": int(row.cost_credits or 0),
            "cost_credits": row.cost_credits,
            "refund_done": bool(row.refund_done),
            "source_filename": row.source_filename,
            "result_filename": build_task_result_filename(row.task_type, row.source_filename, row.output_path),
            "filename_pair": build_task_filename_pair(
                row.source_filename,
                build_task_result_filename(row.task_type, row.source_filename, row.output_path),
            ),
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
    path = resolve_task_artifact_path(row.output_path)
    if path is None or not path.exists():
        raise BizError(code=4109, message="输出文件不存在")
    download_name = build_task_result_filename(row.task_type, row.source_filename, path)
    return FileResponse(path=str(path), filename=download_name)


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
            "recharge_fen": int(o.credits or 0),
            "recharge_cny": _fen_to_cny_api(o.credits or 0),
            "credits": o.credits,
            "status": o.status,
            "source": _normalize_source_bucket(o.source),
            "is_first_pay": o.is_first_pay,
            "package_snapshot": _order_package_snapshot(o),
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
            "recharge_fen": int(row.credits or 0),
            "recharge_cny": _fen_to_cny_api(row.credits or 0),
            "credits": row.credits,
            "status": row.status,
            "provider": row.provider,
            "source": _normalize_source_bucket(row.source),
            "is_first_pay": row.is_first_pay,
            "package_snapshot": _order_package_snapshot(row),
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
        raise BizError(code=4348, message="用户通用点数已不足以冲销本订单，当前订单不可直接退款")
    change_credits(
        db,
        user,
        tx_type=CreditType.ADMIN_ADJUST,
        delta=-int(order.credits),
        reason=f"管理员[{admin.username}]点数充值退款:{order.order_no}",
        related_id=f"refund:{order.order_no}",
        source="admin",
    )
    order.status = "refunded"
    record_refund_order_rebate(db, order=order, operator=f"admin:{admin.username}")
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


def _promo_status_stats(rows, allowed_statuses: list[str]) -> dict:
    stats = {key: 0 for key in allowed_statuses}
    stats["total"] = 0
    for raw_status, raw_count in rows:
        key = raw_status.value if hasattr(raw_status, "value") else str(raw_status or "").strip().lower()
        count = int(raw_count or 0)
        stats[key] = count
        stats["total"] += count
    return stats


def _promo_reward_options(scene: str, *, db: Session) -> list[dict]:
    promo = _get_category_config(db, "promo_center", redact=False)
    reward_rules = promo.get("reward_rules") if isinstance(promo.get("reward_rules"), dict) else {}
    scene_rules = reward_rules.get(scene) if isinstance(reward_rules.get(scene), dict) else {}
    raw_options = scene_rules.get("tiers") if isinstance(scene_rules.get("tiers"), list) else []
    options = []
    for index, item in enumerate(raw_options):
        if not isinstance(item, dict):
            continue
        options.append(
            {
                "key": str(item.get("key") or item.get("tier_key") or f"tier-{index + 1}"),
                "threshold": int(item.get("threshold") or 0),
                "reward_points": int(item.get("reward_points") or 0),
                "label": str(item.get("label") or f"{int(item.get('threshold') or 0)}+")[:64],
            }
        )
    return options


def _promo_benefit_code(submission_id: int) -> str:
    return f"submission:{int(submission_id)}"


def _promo_benefit_map(db: Session, *, scene: str, submission_ids: list[int]) -> dict[str, PromoBenefitRecord]:
    if not submission_ids:
        return {}
    codes = [_promo_benefit_code(submission_id) for submission_id in submission_ids]
    rows = (
        db.query(PromoBenefitRecord)
        .filter(PromoBenefitRecord.scene == scene, PromoBenefitRecord.benefit_code.in_(codes))
        .all()
    )
    return {str(row.benefit_code): row for row in rows}


def _resolve_promo_reward_option(
    *,
    options: list[dict],
    option_key: str | None = None,
    fallback_points: int | None = None,
) -> dict | None:
    normalized_key = str(option_key or "").strip()
    if normalized_key:
        for item in options:
            if str(item.get("key") or "") == normalized_key:
                return item
    points = int(fallback_points or 0)
    if points > 0:
        for item in options:
            if int(item.get("reward_points") or 0) == points:
                return item
    return None


def _promo_benefit_reward_option_key(benefit: PromoBenefitRecord | None) -> str:
    if benefit is None or not isinstance(benefit.meta_json, dict):
        return ""
    return str(benefit.meta_json.get("reward_option_key") or "").strip()


def _grant_promo_credit_reward(
    db: Session,
    *,
    user: User,
    scene: str,
    submission_id: int,
    reward_option: dict,
    title: str,
    source: str,
    meta: dict | None = None,
) -> PromoBenefitRecord:
    reward_points = int(reward_option.get("reward_points") or 0)
    benefit_code = _promo_benefit_code(submission_id)
    row = (
        db.query(PromoBenefitRecord)
        .filter(
            PromoBenefitRecord.user_id == user.id,
            PromoBenefitRecord.scene == scene,
            PromoBenefitRecord.benefit_code == benefit_code,
        )
        .with_for_update()
        .first()
    )
    if row is not None:
        return row
    if reward_points > 0:
        change_credits(
            db,
            user,
            tx_type=CreditType.SHARE_REWARD,
            delta=reward_points,
            reason=title,
            related_id=f"promo_reward:{scene}:{submission_id}",
            source=source,
        )
    row = PromoBenefitRecord(
        user_id=int(user.id),
        scene=scene,
        benefit_code=benefit_code,
        benefit_type=PromoBenefitType.CREDITS,
        status=PromoBenefitStatus.GRANTED,
        title=title[:120],
        credit_delta=reward_points,
        payout_status="paid" if reward_points > 0 else "pending",
        meta_json=meta or {},
        granted_at=datetime.utcnow(),
    )
    db.add(row)
    db.flush()
    return row


def _admin_like_submission_item(
    row: UserShareTaskSubmission,
    *,
    user_phone: str = "",
    user_nickname: str = "",
    reviewer_name: str = "",
    reward_option_key: str = "",
    benefit: PromoBenefitRecord | None = None,
) -> dict:
    status = row.status.value if hasattr(row.status, "value") else str(row.status or "pending")
    return {
        "id": int(row.id),
        "scene": "like",
        "user_id": int(row.user_id),
        "user_phone": user_phone,
        "user_nickname": user_nickname,
        "platform": str(row.platform or "").strip(),
        "status": status,
        "reward_credits": int(row.reward_credits or 0),
        "reward_option_key": reward_option_key,
        "share_text": str(row.share_text or ""),
        "original_filename": str(row.original_filename or ""),
        "screenshot_path": str(row.screenshot_path or ""),
        "review_note": row.review_note,
        "reviewed_by": int(row.reviewed_by or 0) if row.reviewed_by else None,
        "reviewed_by_username": reviewer_name or "",
        "reviewed_at": row.reviewed_at,
        "benefit_status": benefit.status.value if benefit and hasattr(benefit.status, "value") else "",
        "benefit_title": benefit.title if benefit else "",
        "benefit_payout_status": str(benefit.payout_status or "") if benefit else "",
        "benefit_granted_at": benefit.granted_at if benefit else None,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _admin_create_submission_item(
    row: PromoShareSubmission,
    *,
    user_phone: str = "",
    user_nickname: str = "",
    reviewer_name: str = "",
    benefit: PromoBenefitRecord | None = None,
) -> dict:
    status = row.status.value if hasattr(row.status, "value") else str(row.status or "submitted")
    return {
        "id": int(row.id),
        "scene": "create",
        "user_id": int(row.user_id),
        "user_phone": user_phone,
        "user_nickname": user_nickname,
        "platform": str(row.platform or "").strip(),
        "tier_key": str(row.tier_key or "").strip(),
        "share_link": str(row.share_link or "").strip(),
        "payout_account": str(row.payout_account or "").strip(),
        "payout_name": str(row.payout_name or "").strip(),
        "note": str(row.note or ""),
        "status": status,
        "reward_credits": int(row.reward_credits or 0),
        "reward_amount_cny": cny_to_api(row.reward_amount_cny or 0),
        "coupon_name": row.coupon_name,
        "coupon_count": int(row.coupon_count or 0),
        "review_note": row.review_note,
        "reviewed_by": int(row.reviewed_by or 0) if row.reviewed_by else None,
        "reviewed_by_username": reviewer_name or "",
        "reviewed_at": row.reviewed_at,
        "benefit_status": benefit.status.value if benefit and hasattr(benefit.status, "value") else "",
        "benefit_title": benefit.title if benefit else "",
        "benefit_payout_status": str(benefit.payout_status or "") if benefit else "",
        "benefit_granted_at": benefit.granted_at if benefit else None,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


@router.get("/promo/like-submissions", response_model=APIResp)
def admin_like_submissions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q_phone: str | None = Query(default=None),
    status: str | None = Query(default=None),
    platform: str | None = Query(default=None),
    _: AdminUser = Depends(require_admin_permission("users:view")),
    db: Session = Depends(db_dep),
) -> APIResp:
    reward_options = _promo_reward_options("like", db=db)
    base_query = db.query(UserShareTaskSubmission).join(User, User.id == UserShareTaskSubmission.user_id)
    if q_phone:
        base_query = _apply_phone_filter(base_query, q_phone)
    if platform:
        base_query = base_query.filter(UserShareTaskSubmission.platform == platform.strip().lower())
    normalized_status = str(status or "").strip().lower()
    if normalized_status:
        try:
            base_query = base_query.filter(UserShareTaskSubmission.status == ShareTaskStatus(normalized_status))
        except Exception:
            raise BizError(code=4350, message="status 不支持")
    status_rows = (
        base_query.with_entities(UserShareTaskSubmission.status, func.count(UserShareTaskSubmission.id))
        .group_by(UserShareTaskSubmission.status)
        .all()
    )
    total = base_query.count()
    rows = (
        base_query.outerjoin(AdminUser, AdminUser.id == UserShareTaskSubmission.reviewed_by)
        .with_entities(UserShareTaskSubmission, User.phone, User.nickname, AdminUser.username)
        .order_by(desc(UserShareTaskSubmission.updated_at), desc(UserShareTaskSubmission.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    benefit_map = _promo_benefit_map(db, scene="like", submission_ids=[int(row.id) for row, *_ in rows])
    items = [
        _admin_like_submission_item(
            row,
            user_phone=phone or "",
            user_nickname=nickname or "",
            reviewer_name=reviewer_name or "",
            reward_option_key=_promo_benefit_reward_option_key(benefit_map.get(_promo_benefit_code(int(row.id)))),
            benefit=benefit_map.get(_promo_benefit_code(int(row.id))),
        )
        for row, phone, nickname, reviewer_name in rows
    ]
    return ok(
        data={
            "items": items,
            "pagination": paginate(total, page, page_size),
            "status_stats": _promo_status_stats(status_rows, ["pending", "approved", "rejected", "todo"]),
            "reward_options": reward_options,
        }
    )


@router.post("/promo/like-submissions/{submission_id}/review", response_model=APIResp)
def review_like_submission(
    submission_id: int,
    payload: dict,
    admin: AdminUser = Depends(require_admin_permission("users:manage")),
    db: Session = Depends(db_dep),
) -> APIResp:
    decision = str(payload.get("status", "")).strip().lower()
    if decision not in {"approved", "rejected"}:
        raise BizError(code=4351, message="status 仅支持 approved / rejected")
    review_note = str(payload.get("review_note", "")).strip()[:255] or None
    reward_options = _promo_reward_options("like", db=db)
    row = db.query(UserShareTaskSubmission).filter(UserShareTaskSubmission.id == submission_id).with_for_update().first()
    if row is None:
        raise BizError(code=4046, message="截图提审记录不存在", http_status=404)
    before_status = row.status.value if hasattr(row.status, "value") else str(row.status or "")
    existing_benefit = (
        db.query(PromoBenefitRecord)
        .filter(
            PromoBenefitRecord.user_id == row.user_id,
            PromoBenefitRecord.scene == "like",
            PromoBenefitRecord.benefit_code == _promo_benefit_code(row.id),
        )
        .with_for_update()
        .first()
    )
    reward_option_key = str(payload.get("reward_option_key", "")).strip()
    selected_reward = _resolve_promo_reward_option(options=reward_options, option_key=reward_option_key, fallback_points=row.reward_credits)
    if decision == "approved" and selected_reward is None:
        raise BizError(code=4354, message="请先选择集赞奖励档位")
    if (
        decision == "approved"
        and existing_benefit is not None
        and selected_reward is not None
        and int(existing_benefit.credit_delta or 0) != int(selected_reward.get("reward_points") or 0)
    ):
        raise BizError(code=4358, message="该记录奖励已发放，不能改成新的奖励档位")
    if decision == "rejected" and existing_benefit is not None:
        raise BizError(code=4355, message="该记录奖励已发放，不能直接改为驳回")
    row.status = ShareTaskStatus.APPROVED if decision == "approved" else ShareTaskStatus.REJECTED
    row.review_note = review_note
    row.reviewed_by = int(admin.id)
    row.reviewed_at = datetime.utcnow()
    if selected_reward is not None:
        row.reward_credits = int(selected_reward.get("reward_points") or 0)
    benefit = existing_benefit
    user = db.get(User, int(row.user_id))
    if decision == "approved":
        benefit = _grant_promo_credit_reward(
            db,
            user=user,
            scene="like",
            submission_id=int(row.id),
            reward_option=selected_reward or {"reward_points": int(row.reward_credits or 0)},
            title=f"集赞活动奖励：{selected_reward.get('label') if selected_reward else '审核通过'}",
            source="promo_like_review",
            meta={
                "submission_id": int(row.id),
                "platform": str(row.platform or ""),
                "reward_option_key": str(selected_reward.get("key") or ""),
                "threshold": int(selected_reward.get("threshold") or 0),
            },
        )
    db.add(
        AdminAuditLog(
            admin_id=admin.id,
            action="promo_like_review",
            target_type="promo_like_submission",
            target_id=str(row.id),
            before_json={"status": before_status, "review_note": None},
            after_json={
                "status": decision,
                "review_note": review_note,
                "reward_option_key": str(selected_reward.get("key") or "") if selected_reward else "",
                "reward_credits": int(selected_reward.get("reward_points") or 0) if selected_reward else int(row.reward_credits or 0),
            },
        )
    )
    db.commit()
    db.refresh(row)
    return ok(
        data={
            "item": _admin_like_submission_item(
                row,
                user_phone=user.phone if user else "",
                user_nickname=user.nickname if user else "",
                reviewer_name=admin.username,
                reward_option_key=str(selected_reward.get("key") or "") if selected_reward else "",
                benefit=benefit,
            )
        }
    )


@router.get("/promo/create-submissions", response_model=APIResp)
def admin_create_submissions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q_phone: str | None = Query(default=None),
    status: str | None = Query(default=None),
    platform: str | None = Query(default=None),
    _: AdminUser = Depends(require_admin_permission("users:view")),
    db: Session = Depends(db_dep),
) -> APIResp:
    reward_options = _promo_reward_options("create", db=db)
    base_query = db.query(PromoShareSubmission).join(User, User.id == PromoShareSubmission.user_id)
    if q_phone:
        base_query = _apply_phone_filter(base_query, q_phone)
    if platform:
        base_query = base_query.filter(PromoShareSubmission.platform == platform.strip().lower())
    normalized_status = str(status or "").strip().lower()
    if normalized_status:
        try:
            base_query = base_query.filter(PromoShareSubmission.status == PromoShareSubmissionStatus(normalized_status))
        except Exception:
            raise BizError(code=4352, message="status 不支持")
    status_rows = (
        base_query.with_entities(PromoShareSubmission.status, func.count(PromoShareSubmission.id))
        .group_by(PromoShareSubmission.status)
        .all()
    )
    total = base_query.count()
    rows = (
        base_query.outerjoin(AdminUser, AdminUser.id == PromoShareSubmission.reviewed_by)
        .with_entities(PromoShareSubmission, User.phone, User.nickname, AdminUser.username)
        .order_by(desc(PromoShareSubmission.updated_at), desc(PromoShareSubmission.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    benefit_map = _promo_benefit_map(db, scene="create", submission_ids=[int(row.id) for row, *_ in rows])
    items = [
        _admin_create_submission_item(
            row,
            user_phone=phone or "",
            user_nickname=nickname or "",
            reviewer_name=reviewer_name or "",
            benefit=benefit_map.get(_promo_benefit_code(int(row.id))),
        )
        for row, phone, nickname, reviewer_name in rows
    ]
    return ok(
        data={
            "items": items,
            "pagination": paginate(total, page, page_size),
            "status_stats": _promo_status_stats(status_rows, ["submitted", "approved", "rejected"]),
            "reward_options": reward_options,
        }
    )


@router.post("/promo/create-submissions/{submission_id}/review", response_model=APIResp)
def review_create_submission(
    submission_id: int,
    payload: dict,
    admin: AdminUser = Depends(require_admin_permission("users:manage")),
    db: Session = Depends(db_dep),
) -> APIResp:
    decision = str(payload.get("status", "")).strip().lower()
    if decision not in {"approved", "rejected"}:
        raise BizError(code=4353, message="status 仅支持 approved / rejected")
    review_note = str(payload.get("review_note", "")).strip()[:255] or None
    reward_options = _promo_reward_options("create", db=db)
    row = db.query(PromoShareSubmission).filter(PromoShareSubmission.id == submission_id).with_for_update().first()
    if row is None:
        raise BizError(code=4047, message="创作提审记录不存在", http_status=404)
    before_status = row.status.value if hasattr(row.status, "value") else str(row.status or "")
    existing_benefit = (
        db.query(PromoBenefitRecord)
        .filter(
            PromoBenefitRecord.user_id == row.user_id,
            PromoBenefitRecord.scene == "create",
            PromoBenefitRecord.benefit_code == _promo_benefit_code(row.id),
        )
        .with_for_update()
        .first()
    )
    reward_option_key = str(payload.get("reward_option_key", "")).strip() or str(row.tier_key or "")
    selected_reward = _resolve_promo_reward_option(options=reward_options, option_key=reward_option_key, fallback_points=row.reward_credits)
    if decision == "approved" and selected_reward is None:
        raise BizError(code=4356, message="当前创作记录没有匹配到奖励档位")
    if (
        decision == "approved"
        and existing_benefit is not None
        and selected_reward is not None
        and int(existing_benefit.credit_delta or 0) != int(selected_reward.get("reward_points") or 0)
    ):
        raise BizError(code=4359, message="该记录奖励已发放，不能改成新的奖励档位")
    if decision == "rejected" and existing_benefit is not None:
        raise BizError(code=4357, message="该记录奖励已发放，不能直接改为驳回")
    row.status = PromoShareSubmissionStatus.APPROVED if decision == "approved" else PromoShareSubmissionStatus.REJECTED
    row.review_note = review_note
    row.reviewed_by = int(admin.id)
    row.reviewed_at = datetime.utcnow()
    if selected_reward is not None:
        row.tier_key = str(selected_reward.get("key") or row.tier_key or "")
        row.reward_credits = int(selected_reward.get("reward_points") or 0)
    benefit = existing_benefit
    user = db.get(User, int(row.user_id))
    if decision == "approved":
        benefit = _grant_promo_credit_reward(
            db,
            user=user,
            scene="create",
            submission_id=int(row.id),
            reward_option=selected_reward or {"reward_points": int(row.reward_credits or 0)},
            title=f"创作活动奖励：{selected_reward.get('label') if selected_reward else '审核通过'}",
            source="promo_create_review",
            meta={
                "submission_id": int(row.id),
                "platform": str(row.platform or ""),
                "reward_option_key": str(selected_reward.get("key") or ""),
                "threshold": int(selected_reward.get("threshold") or 0),
            },
        )
    db.add(
        AdminAuditLog(
            admin_id=admin.id,
            action="promo_create_review",
            target_type="promo_create_submission",
            target_id=str(row.id),
            before_json={"status": before_status, "review_note": None},
            after_json={
                "status": decision,
                "review_note": review_note,
                "reward_option_key": str(selected_reward.get("key") or "") if selected_reward else str(row.tier_key or ""),
                "reward_credits": int(selected_reward.get("reward_points") or 0) if selected_reward else int(row.reward_credits or 0),
            },
        )
    )
    db.commit()
    db.refresh(row)
    return ok(
        data={
            "item": _admin_create_submission_item(
                row,
                user_phone=user.phone if user else "",
                user_nickname=user.nickname if user else "",
                reviewer_name=admin.username,
                benefit=benefit,
            )
        }
    )


@router.get("/promo/like-submissions/{submission_id}/screenshot")
def download_like_submission_screenshot(
    submission_id: int,
    _: AdminUser = Depends(require_admin_permission("users:view")),
    db: Session = Depends(db_dep),
) -> FileResponse:
    row = db.get(UserShareTaskSubmission, submission_id)
    if row is None:
        raise BizError(code=4046, message="截图提审记录不存在", http_status=404)
    raw_path = str(row.screenshot_path or "").strip()
    path = resolve_task_artifact_path(raw_path)
    if path is None or not path.exists():
        raise BizError(code=4110, message="截图文件不存在", http_status=404)
    try:
        resolved = path.resolve()
        promo_root = (settings.upload_dir / "promo" / "like").resolve()
        if not (resolved == promo_root or promo_root in resolved.parents):
            raise BizError(code=4111, message="截图文件路径不可信", http_status=403)
    except BizError:
        raise
    except Exception as exc:
        raise BizError(code=4111, message="截图文件路径不可信", http_status=403) from exc
    download_name = str(row.original_filename or "").strip() or f"promo_like_{row.id}"
    return FileResponse(path=str(path), filename=download_name)


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
    for c in ("llm", "payment", "billing", "login", "notice", "miniapp", "user_navigation", "promo_center", "aigc_detect_strategy", "rewrite_strategy", "dedup_strategy"):
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


@router.post("/promo/assets/upload", response_model=APIResp)
def admin_upload_promo_asset(
    slot: str = Form(...),
    file: UploadFile = File(...),
    _: AdminUser = Depends(require_admin_permission("configs:manage")),
) -> APIResp:
    asset_key = str(slot or "").strip()
    if asset_key not in PROMO_CENTER_UPLOAD_ASSET_KEYS:
        raise BizError(code=4341, message="不支持的推广素材类型")
    asset_url, original_name = _store_promo_asset_upload(file, slot=asset_key)
    return ok(data={"slot": asset_key, "url": asset_url, "original_name": original_name})


@router.get("/strategies", response_model=APIResp)
def admin_process_strategies(
    _: AdminUser = Depends(require_admin_permission("configs:view")),
    db: Session = Depends(db_dep),
) -> APIResp:
    data = list_process_strategies(db)
    items = []
    for row in data.get("items", []):
        platform = str(row.get("platform", ""))
        task_type = str(row.get("task_type", ""))
        item = dict(row)
        item["platform_label"] = platform_label(platform, db=db)
        item["task_type_label"] = _task_type_label(task_type)
        items.append(item)
    return ok(
        data={
            "task_types": data.get("task_types", []),
            "platforms": data.get("platforms", []),
            "platform_configs": data.get("platform_configs", []),
            "items": items,
        }
    )


@router.get("/algo-config/table", response_model=APIResp)
def admin_algo_config_table(
    _: AdminUser = Depends(require_admin_permission("configs:view")),
    db: Session = Depends(db_dep),
) -> APIResp:
    platform_rows = list_platforms(db, enabled_only=False)
    execution_rows = list_process_strategies(db)
    return ok(
        data={
            "platforms": platform_rows,
            "task_types": execution_rows.get("task_types", []),
            "items": execution_rows.get("items", []),
        }
    )


@router.post("/algo-config/platforms", response_model=APIResp)
def admin_create_or_update_platform(
    payload: dict,
    admin: AdminUser = Depends(require_admin_permission("configs:manage")),
    db: Session = Depends(db_dep),
) -> APIResp:
    if not isinstance(payload, dict):
        raise BizError(code=4302, message="请求体必须为 JSON 对象")
    before = list_platforms(db, enabled_only=False)
    normalized = validate_platform_payload(payload)
    try:
        result = upsert_platform(db, payload=normalized, updated_by=admin.id)
        for task_type in normalized.get("task_types", []):
            update_process_strategy(
                db,
                task_type=task_type,
                platform=normalized["key"],
                updated_by=admin.id,
            )
        after = list_platforms(db, enabled_only=False)
        db.add(
            AdminAuditLog(
                admin_id=admin.id,
                action="platform_upsert",
                target_type="algo_platform",
                target_id=normalized["key"],
                before_json=before,
                after_json=after,
            )
        )
        db.commit()
        return ok(data=result)
    except Exception:
        db.rollback()
        raise


@router.put("/strategies/{task_type}/{platform}", response_model=APIResp)
def admin_update_process_strategy(
    task_type: str,
    platform: str,
    payload: dict,
    admin: AdminUser = Depends(require_admin_permission("configs:manage")),
    db: Session = Depends(db_dep),
) -> APIResp:
    if not isinstance(payload, dict):
        raise BizError(code=4302, message="请求体必须为 JSON 对象")
    if not any(key in payload for key in ("process_mode", "is_enabled", "timeout_sec")):
        raise BizError(code=4341, message="至少需要提供 process_mode / is_enabled / timeout_sec 其中之一")

    normalized_task_type = normalize_task_type(task_type)
    normalized_platform = normalize_platform(platform, task_type=normalized_task_type, db=db)
    before = get_process_strategy(db, task_type=normalized_task_type, platform=normalized_platform)

    process_mode = payload.get("process_mode") if "process_mode" in payload else None
    if process_mode is not None:
        process_mode = normalize_process_mode(process_mode)
    is_enabled = _as_bool(payload.get("is_enabled"), default=False) if "is_enabled" in payload else None
    timeout_sec = payload.get("timeout_sec") if "timeout_sec" in payload else None

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

    result_payload = dict(result)
    result_payload["platform_label"] = _platform_label(normalized_platform)
    result_payload["task_type_label"] = _task_type_label(normalized_task_type.value)
    if is_independent_strategy_config(normalized_task_type, normalized_platform):
        result_payload["current_version"] = None
        result_payload["latest_version"] = None
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
            "delta_fen": int(tx.delta or 0),
            "delta_cny": _fen_to_cny_api(tx.delta or 0),
            "balance_before_fen": int(tx.balance_before or 0),
            "balance_before_cny": _fen_to_cny_api(tx.balance_before or 0),
            "balance_after_fen": int(tx.balance_after or 0),
            "balance_after_cny": _fen_to_cny_api(tx.balance_after or 0),
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





