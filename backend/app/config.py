from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "格物学术"
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    cors_allow_origins: str = "*"
    log_level: str = "INFO"
    log_file_enabled: bool = True
    log_file_max_mb: int = 20
    log_file_backup_count: int = 7
    log_dirname: str = "logs"

    jwt_secret: str = "change_me_in_prod"
    jwt_expire_minutes: int = 120
    refresh_token_expire_days: int = 30
    auth_cookie_secure: bool = True
    auth_cookie_samesite: str = "lax"
    user_refresh_cookie_name: str = "gw_user_refresh"
    admin_refresh_cookie_name: str = "gw_admin_refresh"
    data_encryption_key: str = ""

    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = "root"
    mysql_database: str = "wuhongai"
    sqlite_path: str = "wuhongai.db"
    db_fallback_sqlite: bool = True

    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_db: int = 0

    celery_broker_url: str = "redis://127.0.0.1:6379/0"
    celery_result_backend: str = "redis://127.0.0.1:6379/0"

    initial_credits: int = 5000
    aigc_daily_free_limit: int = 6
    referral_register_inviter_credits: int = 500
    referral_register_invitee_bonus: int = 500
    max_code_retry: int = 3
    phone_lock_minutes: int = 5
    auth_send_code_ip_1h_limit: int = 30
    auth_login_ip_10m_limit: int = 120
    auth_return_debug_code: bool = False
    admin_login_ip_10m_limit: int = 30
    admin_login_user_10m_limit: int = 10

    admin_init_username: str = "admin"
    admin_init_password: str = "admin123456"
    admin_login_ip_allowlist: str = ""
    payment_sign_secret: str = "change_me_payment_sign_key"
    payment_callback_ttl_seconds: int = 900
    payment_test_mode: bool = True
    frontend_base_url: str = ""
    sms_api_key: str = ""
    sms_gateway_url: str = ""

    algorithm_package_root: str = ""
    algorithm_package_max_mb: int = 200
    algorithm_package_exec_timeout_seconds: int = 8
    docx_process_table_text: bool = True

    llm_enabled_default: bool = False
    llm_api_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: int = 25
    llm_retry_attempts: int = 3
    llm_retry_backoff_base_seconds: float = 0.8

    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_pool_timeout: int = 30
    db_pool_recycle: int = 3600
    db_connect_timeout_seconds: int = 10
    db_read_timeout_seconds: int = 30
    db_write_timeout_seconds: int = 30
    db_statement_timeout_ms: int = 30000
    db_startup_retry_attempts: int = 12
    db_startup_retry_delay_seconds: float = 2.0

    task_submit_ip_1m_limit: int = 60
    task_submit_user_1m_limit: int = 20
    task_submit_user_inflight_limit: int = 5
    task_submit_queue_backlog_limit: int = 2000
    task_processing_global_concurrency: int = 8
    task_processing_user_concurrency: int = 3
    task_processing_retry_countdown_seconds: int = 5
    task_chain_guard_enabled: bool = True
    task_chain_guard_preprocessing_timeout_seconds: int = 900
    task_chain_guard_pending_timeout_seconds: int = 900
    task_chain_guard_queued_timeout_seconds: int = 1200
    task_chain_guard_running_timeout_seconds: int = 3600
    celery_local_fallback_enabled: bool = True
    local_submission_worker_concurrency: int = 4
    local_processing_worker_concurrency: int = 4
    local_maintenance_worker_concurrency: int = 2
    task_artifact_retention_days: int = 30
    backup_retention_days: int = 7

    @field_validator("app_env", mode="before")
    @classmethod
    def _normalize_app_env(cls, value):
        raw = str(value or "dev").strip().lower()
        aliases = {
            "production": "prod",
            "release": "prod",
            "online": "prod",
            "local": "dev",
            "development": "dev",
            "test": "test",
            "testing": "test",
            "staging": "staging",
        }
        return aliases.get(raw, raw or "dev")

    @property
    def is_prod(self) -> bool:
        return self.app_env == "prod"

    @property
    def cors_allow_origin_list(self) -> list[str]:
        raw = str(self.cors_allow_origins or "").strip()
        if not raw:
            return []
        if raw == "*":
            return ["*"]
        return [item.strip() for item in raw.split(",") if item.strip()]

    @property
    def auth_cookie_secure_enabled(self) -> bool:
        return bool(self.is_prod and self.auth_cookie_secure)

    @property
    def admin_login_ip_allowlist_set(self) -> set[str]:
        raw = str(self.admin_login_ip_allowlist or "").strip()
        if not raw:
            return set()
        return {item.strip() for item in raw.split(",") if item.strip()}

    @property
    def mysql_dsn(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
        )

    @property
    def sqlite_dsn(self) -> str:
        db_file = Path(__file__).resolve().parent.parent / self.sqlite_path
        return f"sqlite:///{db_file}"

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def upload_dir(self) -> Path:
        p = Path(__file__).resolve().parent.parent / "uploads"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def output_dir(self) -> Path:
        p = Path(__file__).resolve().parent.parent / "output"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def log_dir(self) -> Path:
        p = Path(__file__).resolve().parent.parent / self.log_dirname
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def algorithm_package_dir(self) -> Path:
        if self.algorithm_package_root:
            p = Path(self.algorithm_package_root)
            if not p.is_absolute():
                p = Path(__file__).resolve().parent.parent / p
        else:
            p = Path(__file__).resolve().parent.parent / "algorithm_packages"
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()
