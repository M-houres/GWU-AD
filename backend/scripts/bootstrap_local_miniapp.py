from __future__ import annotations

import os
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api.admin import CONFIG_DEFAULTS  # noqa: E402
from app.database import db_session  # noqa: E402
from app.models import SystemConfig  # noqa: E402


DEFAULT_NOTIFY_URL = "https://restin.top/api/v1/billing/notify/wechatpay"
DEFAULT_API_BASE_URL = "https://restin.top/api/v1"
DEFAULT_WEB_BASE_URL = "https://restin.top"
DEFAULT_DOMAIN = "https://restin.top"
DEFAULT_WS_DOMAIN = "wss://restin.top"
DEFAULT_CERT_KEY_PATH = Path(r"C:\Users\m\Desktop\001项目\格物学术资料\_cert_20260401\apiclient_key.pem")


def env_text(name: str, default: str = "") -> str:
    return str(os.environ.get(name, default) or "").strip()


def read_default_text(path: Path) -> str:
    try:
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""
    return ""


def merge_payload(base: dict, patch: dict) -> dict:
    merged = deepcopy(base)
    merged.update({key: value for key, value in patch.items() if value is not None})
    return merged


def upsert_config(db, *, key: str, value: dict) -> None:
    row = (
        db.query(SystemConfig)
        .filter(SystemConfig.category == "system", SystemConfig.config_key == key)
        .first()
    )
    if row is None:
        db.add(SystemConfig(category="system", config_key=key, config_value=value, updated_by=None))
        return
    row.config_value = value


def main() -> None:
    app_id = env_text("GW_MINIAPP_APP_ID", "wxf330c17322dfbd98")
    app_secret = env_text("GW_MINIAPP_APP_SECRET")
    original_id = env_text("GW_MINIAPP_ORIGINAL_ID", "gh_41c6044ce31a")
    enable_real_login = env_text("GW_MINIAPP_ENABLE_REAL_LOGIN", "true").lower() in {"1", "true", "yes", "on"}
    enable_internal_test = env_text("GW_MINIAPP_ENABLE_INTERNAL_TEST", "false").lower() in {"1", "true", "yes", "on"}

    request_domain = env_text("GW_MINIAPP_REQUEST_DOMAIN", DEFAULT_DOMAIN)
    upload_domain = env_text("GW_MINIAPP_UPLOAD_DOMAIN", request_domain)
    download_domain = env_text("GW_MINIAPP_DOWNLOAD_DOMAIN", request_domain)
    business_domain = env_text("GW_MINIAPP_BUSINESS_DOMAIN", request_domain)
    ws_domain = env_text("GW_MINIAPP_WS_DOMAIN", DEFAULT_WS_DOMAIN)
    api_base_url = env_text("GW_MINIAPP_API_BASE_URL", DEFAULT_API_BASE_URL)
    web_base_url = env_text("GW_MINIAPP_WEB_BASE_URL", DEFAULT_WEB_BASE_URL)
    icp_filing_no = env_text("GW_MINIAPP_ICP_FILING_NO")
    police_filing_no = env_text("GW_MINIAPP_POLICE_FILING_NO")
    police_filing_url = env_text("GW_MINIAPP_POLICE_FILING_URL")
    contact_phone = env_text("GW_MINIAPP_CONTACT_PHONE")
    contact_email = env_text("GW_MINIAPP_CONTACT_EMAIL")

    payment_enabled = env_text("GW_MINIAPP_PAYMENT_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    merchant_id = env_text("GW_WECHATPAY_MERCHANT_ID", "1740438525")
    merchant_serial_no = env_text("GW_WECHATPAY_MERCHANT_SERIAL_NO", "51A52F4216B6E43579BBE3161821D1B7DE6A2770")
    api_v3_key = env_text("GW_WECHATPAY_API_V3_KEY", "s5dmc2L4hN0SacZYvxaBFpO7CJosCqjM")
    public_key_id = env_text("GW_WECHATPAY_PUBLIC_KEY_ID", "PUB_KEY_ID_0117404385252026032300212317000000")
    public_key = env_text("GW_WECHATPAY_PUBLIC_KEY")
    merchant_private_key_pem = env_text("GW_WECHATPAY_MERCHANT_PRIVATE_KEY_PEM") or read_default_text(DEFAULT_CERT_KEY_PATH)
    notify_url = env_text("GW_WECHATPAY_NOTIFY_URL", DEFAULT_NOTIFY_URL)

    if enable_real_login and not app_secret:
        raise SystemExit("GW_MINIAPP_APP_SECRET 未设置，无法开启本地真实小程序登录")

    with db_session() as db:
        login_value = merge_payload(
            CONFIG_DEFAULTS["login"],
            {
                "wechat_miniprogram_login_enabled": enable_real_login,
                "wechat_miniprogram_app_id": app_id,
                "wechat_miniprogram_app_secret": app_secret,
                "miniapp_internal_test_login_enabled": enable_internal_test,
            },
        )

        miniapp_value = merge_payload(
            CONFIG_DEFAULTS["miniapp"],
            {
                "enabled": True,
                "app_id": app_id,
                "app_secret": app_secret,
                "original_id": original_id,
                "api_base_url": api_base_url,
                "web_base_url": web_base_url,
                "request_domain": request_domain,
                "upload_domain": upload_domain,
                "download_domain": download_domain,
                "ws_domain": ws_domain,
                "business_domain": business_domain,
                "icp_filing_no": icp_filing_no,
                "police_filing_no": police_filing_no,
                "police_filing_url": police_filing_url,
                "contact_phone": contact_phone,
                "contact_email": contact_email,
                "wechat_miniprogram_login_enabled": enable_real_login,
                "wechat_miniprogram_app_id": app_id,
                "wechat_miniprogram_app_secret": app_secret,
                "wechat_miniprogram_payment_enabled": payment_enabled,
                "payment_notify_url": notify_url,
            },
        )

        payment_patch = {
            "provider": "wechatpay_v3",
            "test_mode": True,
            "merchant_id": merchant_id,
            "merchant_serial_no": merchant_serial_no,
            "api_v3_key": api_v3_key,
            "wechatpay_public_key_id": public_key_id,
            "notify_url": notify_url,
        }
        if public_key:
            payment_patch["wechatpay_public_key"] = public_key
        if merchant_private_key_pem:
            payment_patch["merchant_private_key_pem"] = merchant_private_key_pem

        payment_value = merge_payload(CONFIG_DEFAULTS["payment"], payment_patch)

        upsert_config(db, key="login", value=login_value)
        upsert_config(db, key="miniapp", value=miniapp_value)
        upsert_config(db, key="payment", value=payment_value)

    print("local miniapp config bootstrapped")
    print(f"app_id={app_id}")
    print(f"request_domain={request_domain}")
    print(f"real_login={'on' if enable_real_login else 'off'}")
    print(f"internal_test={'on' if enable_internal_test else 'off'}")
    print(f"payment_public_key={'present' if bool(public_key) else 'missing'}")
    print(f"merchant_private_key={'present' if bool(merchant_private_key_pem) else 'missing'}")
    if not env_text("GW_WECHATPAY_MERCHANT_PRIVATE_KEY_PEM") and merchant_private_key_pem:
        print(f"merchant_private_key_source={DEFAULT_CERT_KEY_PATH}")


if __name__ == "__main__":
    main()
