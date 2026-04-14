from datetime import datetime, timedelta, timezone
import base64
import hashlib
import uuid

import bcrypt
from cryptography.hazmat.primitives.ciphers.aead import AESSIV
from jose import JWTError, jwt

from app.config import get_settings

settings = get_settings()
ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


def _normalize_password(plain: str) -> bytes:
    # 先归一化为固定长度，避免 bcrypt 72 字节限制引发问题
    text = (plain or "").encode("utf-8")
    digest = hashlib.sha256(text).hexdigest()
    return digest.encode("utf-8")


def _normalize_secret_material(raw: str) -> bytes:
    text = str(raw or "").strip()
    if not text:
        text = settings.jwt_secret
    return hashlib.sha512(text.encode("utf-8")).digest()


def _data_cipher() -> AESSIV:
    return AESSIV(_normalize_secret_material(settings.data_encryption_key))


def encrypt_at_rest(value: str) -> str:
    plain = str(value or "").strip()
    if not plain:
        return ""
    # Deterministic AEAD so equality lookups remain stable after encryption.
    ciphertext = _data_cipher().encrypt(plain.encode("utf-8"), [b"gw-academic:data"])
    return "enc:" + base64.urlsafe_b64encode(ciphertext).decode("utf-8")


def decrypt_at_rest(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if not raw.startswith("enc:"):
        return raw
    data = base64.urlsafe_b64decode(raw[4:].encode("utf-8"))
    plain = _data_cipher().decrypt(data, [b"gw-academic:data"])
    return plain.decode("utf-8")


def phone_lookup_digest(phone: str) -> str:
    return hashlib.sha256(str(phone or "").strip().encode("utf-8")).hexdigest()


def hash_password(plain: str) -> str:
    normalized = _normalize_password(plain)
    return bcrypt.hashpw(normalized, bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    normalized = _normalize_password(plain)
    try:
        encoded_hash = hashed.encode("utf-8")
        if bcrypt.checkpw(normalized, encoded_hash):
            return True
        # 兼容历史密码哈希（旧逻辑直接 bcrypt 原文）
        legacy = (plain or "")[:72].encode("utf-8")
        return bcrypt.checkpw(legacy, encoded_hash)
    except Exception:
        return False


def create_token(
    subject: str,
    scope: str,
    expire_minutes: int | None = None,
    *,
    token_type: str = ACCESS_TOKEN_TYPE,
    session_version: str | None = None,
) -> str:
    minutes = expire_minutes or settings.jwt_expire_minutes
    exp = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {
        "sub": subject,
        "scope": scope,
        "typ": token_type,
        "jti": uuid.uuid4().hex,
        "exp": exp,
    }
    if session_version:
        payload["sv"] = session_version
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def create_access_token(subject: str, scope: str, *, session_version: str | None = None) -> str:
    return create_token(
        subject,
        scope,
        expire_minutes=settings.jwt_expire_minutes,
        token_type=ACCESS_TOKEN_TYPE,
        session_version=session_version,
    )


def create_refresh_token(subject: str, scope: str, *, session_version: str | None = None) -> str:
    return create_token(
        subject,
        scope,
        expire_minutes=int(settings.refresh_token_expire_days) * 24 * 60,
        token_type=REFRESH_TOKEN_TYPE,
        session_version=session_version,
    )


def new_session_version() -> str:
    return uuid.uuid4().hex


def auth_session_key(scope: str, subject: str) -> str:
    return f"auth:session:{scope}:{subject}"


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except JWTError as exc:
        raise ValueError("invalid token") from exc
