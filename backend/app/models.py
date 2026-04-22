from decimal import Decimal
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from sqlalchemy.types import TypeDecorator

from app.database import Base
from app.security import decrypt_at_rest, encrypt_at_rest

ID_PK_TYPE = BigInteger().with_variant(Integer, "sqlite")


class EncryptedString(TypeDecorator):
    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        raw = str(value).strip()
        if not raw:
            return ""
        return raw if raw.startswith("enc:") else encrypt_at_rest(raw)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return decrypt_at_rest(value)


class TaskType(str, Enum):
    AIGC_DETECT = "aigc_detect"
    DEDUP = "dedup"
    REWRITE = "rewrite"


class TaskStatus(str, Enum):
    PENDING = "pending"
    PREPROCESSING = "preprocessing"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RewardType(str, Enum):
    REGISTER_INVITE = "register_invite"
    REGISTER_BONUS = "register_bonus"
    FIRST_PAY = "first_pay"
    RECURRING_PAY = "recurring_pay"


class CreditType(str, Enum):
    INIT = "init"
    TASK_CONSUME = "task_consume"
    TASK_REFUND = "task_refund"
    PACKAGE_PAY = "package_pay"
    REFERRAL_INVITE = "referral_invite"
    REFERRAL_BONUS = "referral_bonus"
    REFERRAL_FIRST_PAY = "referral_first_pay"
    REFERRAL_RECURRING = "referral_recurring"
    SHARE_REWARD = "share_reward"
    ADMIN_ADJUST = "admin_adjust"


class ShareTaskStatus(str, Enum):
    TODO = "todo"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PromoBenefitType(str, Enum):
    CREDITS = "credits"
    COUPON = "coupon"
    CASH = "cash"


class PromoBenefitStatus(str, Enum):
    GRANTED = "granted"
    REVOKED = "revoked"


class PromoShareSubmissionStatus(str, Enum):
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"


class PartnerLedgerEntryType(str, Enum):
    ACCRUAL = "accrual"
    REVERSAL = "reversal"


class PartnerLedgerStatus(str, Enum):
    PENDING = "pending"
    SETTLED = "settled"
    REVERSED = "reversed"


class PartnerStatementStatus(str, Enum):
    GENERATED = "generated"
    SETTLED = "settled"


class PartnerWithdrawStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(ID_PK_TYPE, primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(EncryptedString(128), unique=True, index=True)
    phone_last4: Mapped[str] = mapped_column(String(4), default="", index=True)
    nickname: Mapped[str] = mapped_column(String(64), default="")
    openid: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    wechat_unionid: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    wechat_openid_web: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    wechat_openid_mp: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(20), default="web", index=True)
    credits: Mapped[int] = mapped_column(Integer, default=0)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    tasks: Mapped[list["Task"]] = relationship(back_populates="user")

    @validates("phone")
    def _normalize_phone_fields(self, _key, value: str) -> str:
        raw = str(value or "").strip()
        self.phone_last4 = raw[-4:] if len(raw) >= 4 else raw
        return raw


class UserInviteCode(Base):
    __tablename__ = "user_invite_codes"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    invite_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ReferralRelation(Base):
    __tablename__ = "referral_relations"

    id: Mapped[int] = mapped_column(ID_PK_TYPE, primary_key=True, autoincrement=True)
    inviter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    invitee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    invite_code: Mapped[str] = mapped_column(String(16), index=True)
    source: Mapped[str] = mapped_column(String(20), default="web", index=True)
    status: Mapped[str] = mapped_column(String(20), default="registered")
    register_reward_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    first_pay_reward_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ReferralReward(Base):
    __tablename__ = "referral_rewards"

    id: Mapped[int] = mapped_column(ID_PK_TYPE, primary_key=True, autoincrement=True)
    inviter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    invitee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    reward_type: Mapped[RewardType] = mapped_column(SQLEnum(RewardType), index=True)
    reward_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    credits: Mapped[int] = mapped_column(Integer)
    ref_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="web", index=True)
    status: Mapped[str] = mapped_column(String(16), default="sent")
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(ID_PK_TYPE, primary_key=True, autoincrement=True)
    order_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    amount_cny: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    credits: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(20), default="web", index=True)
    status: Mapped[str] = mapped_column(String(20), default="created")
    provider: Mapped[str] = mapped_column(String(20), default="mock")
    is_first_pay: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class PartnerChannel(Base):
    __tablename__ = "partner_channels"

    id: Mapped[int] = mapped_column(ID_PK_TYPE, primary_key=True, autoincrement=True)
    channel_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    contact_name: Mapped[str] = mapped_column(String(64), default="")
    contact_phone: Mapped[str] = mapped_column(EncryptedString(128), default="")
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    order_token: Mapped[str] = mapped_column(String(96), unique=True, index=True)
    portal_token: Mapped[str] = mapped_column(String(96), unique=True, index=True)
    default_rebate_rate_bp: Mapped[int] = mapped_column(Integer, default=1500)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class PartnerPolicy(Base):
    __tablename__ = "partner_policies"

    id: Mapped[int] = mapped_column(ID_PK_TYPE, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("partner_channels.id"), index=True)
    package_name: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    rebate_rate_bp: Mapped[int] = mapped_column(Integer, default=1500)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("channel_id", "package_name", name="uk_partner_policy_channel_package"),
    )


class PartnerUserBinding(Base):
    __tablename__ = "partner_user_bindings"

    id: Mapped[int] = mapped_column(ID_PK_TYPE, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("partner_channels.id"), index=True)
    bind_source: Mapped[str] = mapped_column(String(24), default="link")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class PartnerOrderAttribution(Base):
    __tablename__ = "partner_order_attributions"

    id: Mapped[int] = mapped_column(ID_PK_TYPE, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), unique=True, index=True)
    order_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("partner_channels.id"), index=True)
    channel_code_snapshot: Mapped[str] = mapped_column(String(32), index=True)
    package_name: Mapped[str] = mapped_column(String(64), default="")
    rebate_rate_bp: Mapped[int] = mapped_column(Integer, default=0)
    attribution_source: Mapped[str] = mapped_column(String(24), default="link")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class PartnerMonthlyStatement(Base):
    __tablename__ = "partner_monthly_statements"

    id: Mapped[int] = mapped_column(ID_PK_TYPE, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("partner_channels.id"), index=True)
    statement_month: Mapped[str] = mapped_column(String(7), index=True)
    status: Mapped[PartnerStatementStatus] = mapped_column(
        SQLEnum(PartnerStatementStatus), default=PartnerStatementStatus.GENERATED, index=True
    )
    total_orders: Mapped[int] = mapped_column(Integer, default=0)
    gross_amount_fen: Mapped[int] = mapped_column(Integer, default=0)
    rebate_amount_fen: Mapped[int] = mapped_column(Integer, default=0)
    settled_by: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"), nullable=True, index=True)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("channel_id", "statement_month", name="uk_partner_statement_channel_month"),
    )


class PartnerRebateLedger(Base):
    __tablename__ = "partner_rebate_ledger"

    id: Mapped[int] = mapped_column(ID_PK_TYPE, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("partner_channels.id"), index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True, index=True)
    order_no: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    entry_type: Mapped[PartnerLedgerEntryType] = mapped_column(SQLEnum(PartnerLedgerEntryType), index=True)
    status: Mapped[PartnerLedgerStatus] = mapped_column(
        SQLEnum(PartnerLedgerStatus), default=PartnerLedgerStatus.PENDING, index=True
    )
    base_amount_fen: Mapped[int] = mapped_column(Integer, default=0)
    rebate_amount_fen: Mapped[int] = mapped_column(Integer, default=0)
    statement_month: Mapped[str] = mapped_column(String(7), index=True)
    statement_id: Mapped[int | None] = mapped_column(ForeignKey("partner_monthly_statements.id"), nullable=True, index=True)
    related_ledger_id: Mapped[int | None] = mapped_column(ForeignKey("partner_rebate_ledger.id"), nullable=True)
    note: Mapped[str] = mapped_column(String(255), default="")
    settled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("channel_id", "order_no", "entry_type", name="uk_partner_ledger_channel_order_entry"),
        Index("ix_partner_ledger_channel_month_status", "channel_id", "statement_month", "status"),
    )


class PartnerWithdrawRequest(Base):
    __tablename__ = "partner_withdraw_requests"

    id: Mapped[int] = mapped_column(ID_PK_TYPE, primary_key=True, autoincrement=True)
    request_no: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("partner_channels.id"), index=True)
    apply_amount_fen: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[PartnerWithdrawStatus] = mapped_column(
        SQLEnum(PartnerWithdrawStatus), default=PartnerWithdrawStatus.PENDING, index=True
    )
    note: Mapped[str] = mapped_column(String(255), default="")
    reject_reason: Mapped[str] = mapped_column(String(255), default="")
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"), nullable=True, index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_partner_withdraw_channel_status", "channel_id", "status"),
    )


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id: Mapped[int] = mapped_column(ID_PK_TYPE, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    tx_type: Mapped[CreditType] = mapped_column(SQLEnum(CreditType), index=True)
    delta: Mapped[int] = mapped_column(Integer)
    balance_before: Mapped[int] = mapped_column(Integer)
    balance_after: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(255), default="")
    related_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(20), default="web", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "tx_type", "related_id", name="uk_user_tx_related"),
        Index("ix_credit_transactions_user_recent", "user_id", "id"),
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(ID_PK_TYPE, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    task_type: Mapped[TaskType] = mapped_column(SQLEnum(TaskType), index=True)
    platform: Mapped[str] = mapped_column(String(20), index=True)
    processing_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="web", index=True)
    status: Mapped[TaskStatus] = mapped_column(SQLEnum(TaskStatus), default=TaskStatus.PENDING)
    source_filename: Mapped[str] = mapped_column(String(255))
    source_path: Mapped[str] = mapped_column(String(500))
    report_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    output_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    cost_credits: Mapped[int] = mapped_column(Integer, default=0)
    refund_done: Mapped[bool] = mapped_column(Boolean, default=False)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped[User] = relationship(back_populates="tasks")

    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uk_tasks_user_idempotency_key"),
        Index("ix_tasks_user_recent", "user_id", "id"),
        Index("ix_tasks_status_id", "status", "id"),
    )


class SystemSwitch(Base):
    __tablename__ = "system_switch"

    id: Mapped[int] = mapped_column(ID_PK_TYPE, primary_key=True, autoincrement=True)
    current_mode: Mapped[str] = mapped_column(String(32), default="LLM_PLUS_ALGO")
    llm_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    llm_fail_count: Mapped[int] = mapped_column(Integer, default=0)
    llm_fail_threshold: Mapped[int] = mapped_column(Integer, default=3)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class SwitchLog(Base):
    __tablename__ = "switch_logs"

    id: Mapped[int] = mapped_column(ID_PK_TYPE, primary_key=True, autoincrement=True)
    from_mode: Mapped[str] = mapped_column(String(32))
    to_mode: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class LLMErrorLog(Base):
    __tablename__ = "llm_error_logs"

    id: Mapped[int] = mapped_column(ID_PK_TYPE, primary_key=True, autoincrement=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"), nullable=True, index=True)
    error_type: Mapped[str] = mapped_column(String(60))
    error_detail: Mapped[str] = mapped_column(String(500))
    trigger_downgrade: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(ID_PK_TYPE, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="operator")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    permissions_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(ID_PK_TYPE, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    content: Mapped[str] = mapped_column(String(500))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class UserShareTaskSubmission(Base):
    __tablename__ = "user_share_task_submissions"

    id: Mapped[int] = mapped_column(ID_PK_TYPE, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    reward_credits: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[ShareTaskStatus] = mapped_column(SQLEnum(ShareTaskStatus), default=ShareTaskStatus.PENDING, index=True)
    screenshot_path: Mapped[str] = mapped_column(String(500))
    original_filename: Mapped[str] = mapped_column(String(255), default="")
    share_text: Mapped[str] = mapped_column(String(500), default="")
    review_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"), nullable=True, index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "platform", name="uk_user_share_task_platform"),
    )


class RegistrationRiskLog(Base):
    __tablename__ = "registration_risk_logs"

    id: Mapped[int] = mapped_column(ID_PK_TYPE, primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(EncryptedString(128), index=True)
    ip: Mapped[str] = mapped_column(String(64), index=True)
    user_agent: Mapped[str] = mapped_column(String(300), default="")
    reason: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PromoBenefitRecord(Base):
    __tablename__ = "promo_benefit_records"

    id: Mapped[int] = mapped_column(ID_PK_TYPE, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    scene: Mapped[str] = mapped_column(String(32), index=True)
    benefit_code: Mapped[str] = mapped_column(String(64), index=True)
    benefit_type: Mapped[PromoBenefitType] = mapped_column(SQLEnum(PromoBenefitType), index=True)
    status: Mapped[PromoBenefitStatus] = mapped_column(SQLEnum(PromoBenefitStatus), default=PromoBenefitStatus.GRANTED, index=True)
    title: Mapped[str] = mapped_column(String(120))
    credit_delta: Mapped[int] = mapped_column(Integer, default=0)
    amount_cny: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    coupon_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    coupon_count: Mapped[int] = mapped_column(Integer, default=0)
    payout_status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    paid_by: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"), nullable=True, index=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    meta_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    granted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "scene", "benefit_code", name="uk_promo_benefit_user_scene_code"),
    )


class PromoClassroom(Base):
    __tablename__ = "promo_classrooms"

    id: Mapped[int] = mapped_column(ID_PK_TYPE, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    invite_code: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    level: Mapped[str] = mapped_column(String(24), default="青铜班")
    member_count: Mapped[int] = mapped_column(Integer, default=1)
    activity_score: Mapped[int] = mapped_column(Integer, default=60)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class PromoClassroomMember(Base):
    __tablename__ = "promo_classroom_members"

    id: Mapped[int] = mapped_column(ID_PK_TYPE, primary_key=True, autoincrement=True)
    classroom_id: Mapped[int] = mapped_column(ForeignKey("promo_classrooms.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(16), default="member")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("classroom_id", "user_id", name="uk_promo_classroom_member"),
    )


class PromoShareSubmission(Base):
    __tablename__ = "promo_share_submissions"

    id: Mapped[int] = mapped_column(ID_PK_TYPE, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    tier_key: Mapped[str] = mapped_column(String(24))
    share_link: Mapped[str] = mapped_column(String(500))
    payout_account: Mapped[str] = mapped_column(String(120), default="")
    payout_name: Mapped[str] = mapped_column(String(120), default="")
    note: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[PromoShareSubmissionStatus] = mapped_column(SQLEnum(PromoShareSubmissionStatus), default=PromoShareSubmissionStatus.SUBMITTED, index=True)
    reward_credits: Mapped[int] = mapped_column(Integer, default=0)
    reward_amount_cny: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    coupon_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    coupon_count: Mapped[int] = mapped_column(Integer, default=0)
    review_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"), nullable=True, index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "platform", name="uk_promo_share_user_platform"),
    )


class SystemConfig(Base):
    __tablename__ = "system_configs"

    id: Mapped[int] = mapped_column(ID_PK_TYPE, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(60), index=True)
    config_key: Mapped[str] = mapped_column(String(60), index=True)
    config_value: Mapped[dict] = mapped_column(JSON)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("category", "config_key", name="uk_cfg_category_key"),
    )


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"

    id: Mapped[int] = mapped_column(ID_PK_TYPE, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"), index=True)
    action: Mapped[str] = mapped_column(String(80))
    target_type: Mapped[str] = mapped_column(String(80))
    target_id: Mapped[str] = mapped_column(String(120), default="")
    before_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
