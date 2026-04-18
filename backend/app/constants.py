from decimal import Decimal

from app.models import TaskType


TASK_POINTS_PER_CHAR_DEFAULT = Decimal("1")
TASK_POINTS_PER_CHAR: dict[TaskType, Decimal] = {
    TaskType.AIGC_DETECT: TASK_POINTS_PER_CHAR_DEFAULT,
    TaskType.DEDUP: TASK_POINTS_PER_CHAR_DEFAULT,
    TaskType.REWRITE: TASK_POINTS_PER_CHAR_DEFAULT,
}

DEFAULT_BILLING_PACKAGES = [
    {
        "name": "入门版",
        "price": 19.0,
        "credits": 10000,
        "description": "适合新手试用或偶尔使用，低门槛体验核心功能。",
        "badge": "新手推荐",
        "enabled": True,
    },
    {
        "name": "基础版",
        "price": 39.0,
        "credits": 20000,
        "description": "适合少量多次使用，覆盖日常降重、降AI和检测需求。",
        "badge": "日常常用",
        "enabled": True,
    },
    {
        "name": "专业版",
        "price": 79.0,
        "credits": 50000,
        "description": "适合中度使用需求，兼顾成本和可用点数储备。",
        "badge": "高性价比",
        "enabled": True,
    },
    {
        "name": "增强版",
        "price": 149.0,
        "credits": 100000,
        "description": "适合常规批量使用，适配更稳定的内容处理节奏。",
        "badge": "批量优选",
        "enabled": True,
    },
    {
        "name": "高级版",
        "price": 419.0,
        "credits": 300000,
        "description": "适合中高频长期使用，兼顾规模与长期成本。",
        "badge": "长期推荐",
        "enabled": True,
    },
    {
        "name": "旗舰版",
        "price": 1199.0,
        "credits": 1000000,
        "description": "适合高频大量使用场景，提供充足通用点数储备。",
        "badge": "旗舰首选",
        "enabled": True,
    },
]


PACKAGE_CONFIG = {
    item["name"]: {"price": float(item["price"]), "credits": int(item["credits"])}
    for item in DEFAULT_BILLING_PACKAGES
}


ALLOWED_EXTENSIONS = {".docx", ".pdf", ".txt"}
MAX_FILE_SIZE_MB = 20
