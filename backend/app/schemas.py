from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class APIResp(BaseModel):
    code: int = 0
    message: str = "success"
    data: Any | None = None


class SendCodeReq(BaseModel):
    phone: str = Field(min_length=11, max_length=20)


class LoginReq(BaseModel):
    phone: str = Field(min_length=11, max_length=20)
    code: str = Field(min_length=4, max_length=8)
    device_fingerprint: str | None = Field(default=None, max_length=128)


class MiniProgramLoginReq(BaseModel):
    code: str = Field(min_length=2, max_length=256)
    device_fingerprint: str | None = Field(default=None, max_length=128)


class MiniProgramPhoneLoginReq(BaseModel):
    login_code: str = Field(min_length=2, max_length=256)
    phone_code: str = Field(min_length=2, max_length=256)
    device_fingerprint: str | None = Field(default=None, max_length=128)


class UserResp(BaseModel):
    id: int
    phone: str
    nickname: str
    credits: int
    balance_fen: int | None = None
    balance_cny: float | None = None
    created_at: datetime


class TaskCreateResp(BaseModel):
    id: int
    status: str
    cost_credits: int
    cost_fen: int | None = None
    cost_points: int | None = None


class AdminLoginReq(BaseModel):
    username: str
    password: str


class AdminAdjustCreditReq(BaseModel):
    delta: int | None = None
    delta_fen: int | None = None
    delta_cny: Decimal | None = None
    reason: str


class PaginationQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class MockPayReq(BaseModel):
    package_name: str | None = None
    amount_cny: Decimal | None = Field(default=None, gt=0)


class CreateOrderReq(BaseModel):
    package_name: str | None = None
    amount_cny: Decimal | None = Field(default=None, gt=0)
    provider: str = Field(default="wechat")
    scene: str = Field(default="web")
    channel_code: str | None = Field(default=None, max_length=32)
    channel_token: str | None = Field(default=None, max_length=128)


class PayCallbackReq(BaseModel):
    order_no: str = Field(min_length=8, max_length=64)
    user_id: int = Field(ge=1)
    package_name: str
    amount_cny: Decimal = Field(gt=0)
    paid_at: int = Field(ge=1)
    status: str = Field(default="paid")
    provider: str = Field(default="wechat")
    nonce: str = Field(min_length=4, max_length=64)
    sign: str = Field(min_length=32, max_length=128)
