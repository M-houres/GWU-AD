from decimal import Decimal

from app.models import TaskType


TASK_POINTS_PER_CHAR_DEFAULT = Decimal("1")
TASK_POINTS_PER_CHAR: dict[TaskType, Decimal] = {
    TaskType.AIGC_DETECT: TASK_POINTS_PER_CHAR_DEFAULT,
    TaskType.DEDUP: TASK_POINTS_PER_CHAR_DEFAULT,
    TaskType.REWRITE: TASK_POINTS_PER_CHAR_DEFAULT,
}

DEFAULT_BILLING_SCHEMA_VERSION = 2
DEFAULT_BILLING_PACKAGE_PROFILE_VERSION = 2
LEGACY_BUILTIN_BILLING_PACKAGE_NAMES = {"基础包", "标准包", "大额包", "年费包"}

DEFAULT_BILLING_PACKAGES = [
    {
        "name": "体验包",
        "price": 19.9,
        "credits": 13000,
        "description": "适合短篇体验或首次充值用户，低门槛了解检测、降重、改写等处理链路。",
        "badge": "新手体验",
        "audience": "C端新人体验",
        "discount_note": "贴近原价 1.5，几乎无优惠",
        "sort_order": 1,
        "enabled": True,
    },
    {
        "name": "进阶包",
        "price": 49.9,
        "credits": 40000,
        "description": "适合个人长期自用，在多次检测、降重和改写过程中保持稳定储备。",
        "badge": "中档优选",
        "audience": "个人长期自用",
        "discount_note": "中等优惠",
        "sort_order": 2,
        "enabled": True,
    },
    {
        "name": "团队包",
        "price": 99.9,
        "credits": 100000,
        "description": "适合小团队、小代理或多篇文稿集中处理，兼顾成本与处理规模。",
        "badge": "高优惠",
        "audience": "小团队 / 小代理",
        "discount_note": "高优惠",
        "sort_order": 3,
        "enabled": True,
    },
    {
        "name": "批量包",
        "price": 199.9,
        "credits": 250000,
        "description": "适合工作室和批量处理场景，单价达到当前套餐体系的底部区间。",
        "badge": "底价档",
        "audience": "B端工作室批发",
        "discount_note": "完美达到约 0.8 元底价",
        "sort_order": 4,
        "enabled": True,
    },
]


PACKAGE_CONFIG = {
    item["name"]: {"price": float(item["price"]), "credits": int(item["credits"])}
    for item in DEFAULT_BILLING_PACKAGES
}


ALLOWED_EXTENSIONS = {".doc", ".docx", ".pdf", ".txt"}
MAX_FILE_SIZE_MB = 20
