from app.exceptions import BizError

REFERRAL_MODULE_DISABLED_MESSAGE = "推广福利模块正在重构，暂不可用"


def is_referral_module_enabled() -> bool:
    return False


def raise_referral_module_disabled() -> None:
    raise BizError(code=4419, message=REFERRAL_MODULE_DISABLED_MESSAGE, http_status=410)
