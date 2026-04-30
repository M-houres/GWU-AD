import logging
from typing import Callable, Generator
import time

import redis
from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.client_source import get_client_source
from app.config import get_settings
from app.database import get_db
from app.models import AdminUser, PartnerChannel, User
from app.security import auth_session_key, decode_token
settings = get_settings()
logger = logging.getLogger("app.deps")
redis_client = redis.Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    db=settings.redis_db,
    decode_responses=True,
)


class MemoryRedisCompat:
    def __init__(self) -> None:
        self._values: dict[str, str] = {}
        self._exp_at: dict[str, float] = {}

    def _purge_if_expired(self, key: str) -> None:
        exp = self._exp_at.get(key)
        if exp is None:
            return
        if exp <= time.time():
            self._values.pop(key, None)
            self._exp_at.pop(key, None)

    def ping(self) -> bool:
        return True

    def setex(self, key: str, seconds: int, value) -> bool:
        self._values[key] = str(value)
        self._exp_at[key] = time.time() + int(seconds)
        return True

    def set(self, key: str, value, ex: int | None = None, nx: bool = False):
        self._purge_if_expired(key)
        if nx and key in self._values:
            return False
        self._values[key] = str(value)
        if ex is not None:
            self._exp_at[key] = time.time() + int(ex)
        else:
            self._exp_at.pop(key, None)
        return True

    def get(self, key: str):
        self._purge_if_expired(key)
        return self._values.get(key)

    def ttl(self, key: str) -> int:
        self._purge_if_expired(key)
        if key not in self._values:
            return -2
        exp = self._exp_at.get(key)
        if exp is None:
            return -1
        remain = int(exp - time.time())
        if remain <= 0:
            self._values.pop(key, None)
            self._exp_at.pop(key, None)
            return -2
        return remain

    def incr(self, key: str) -> int:
        self._purge_if_expired(key)
        current = self._values.get(key, "0")
        try:
            value = int(current)
        except Exception:
            value = 0
        value += 1
        self._values[key] = str(value)
        return value

    def decr(self, key: str) -> int:
        self._purge_if_expired(key)
        current = self._values.get(key, "0")
        try:
            value = int(current)
        except Exception:
            value = 0
        value -= 1
        self._values[key] = str(value)
        return value

    def expire(self, key: str, seconds: int) -> bool:
        self._purge_if_expired(key)
        if key not in self._values:
            return False
        self._exp_at[key] = time.time() + int(seconds)
        return True

    def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            self._purge_if_expired(key)
            if key in self._values:
                removed += 1
                self._values.pop(key, None)
            self._exp_at.pop(key, None)
        return removed


memory_redis = MemoryRedisCompat()

auth_scheme = HTTPBearer(auto_error=False)
LEGACY_OPERATOR_DEFAULT_PERMISSIONS = {
    "dashboard:view",
    "users:view",
    "users:manage",
    "tasks:view",
    "orders:view",
    "orders:refund",
    "logs:view",
    "credits:view",
}


def get_redis():
    try:
        redis_client.ping()
        return redis_client
    except redis.RedisError:
        if settings.is_prod:
            logger.error("redis_unavailable_in_production")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="redis unavailable")
        return memory_redis


def _get_auth_store():
    try:
        redis_client.ping()
        return redis_client
    except redis.RedisError:
        if settings.is_prod:
            logger.error("auth_store_unavailable_in_production")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="auth store unavailable")
        return memory_redis


def redis_is_available() -> bool:
    try:
        redis_client.ping()
        return True
    except redis.RedisError:
        return False


def client_source_dep(request: Request) -> str:
    return get_client_source(request)


def db_dep() -> Generator[Session, None, None]:
    yield from get_db()


def current_user(
    cred: HTTPAuthorizationCredentials = Depends(auth_scheme),
    user_access_cookie: str | None = Cookie(default=None, alias="gw_user_access"),
    db: Session = Depends(db_dep),
    auth_store=Depends(get_redis),
) -> User:
    token = cred.credentials if cred is not None and cred.credentials else str(user_access_cookie or "").strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing token")
    try:
        payload = decode_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token") from exc
    if payload.get("scope") != "user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid scope")
    token_type = str(payload.get("typ") or "access").strip().lower()
    if token_type != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid scope")
    try:
        user_id = int(payload["sub"])
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token") from exc
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")
    if getattr(user, "is_banned", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user banned")
    session_version = str(payload.get("sv") or "").strip()
    if session_version:
        current_version = str(auth_store.get(auth_session_key("user", str(user.id))) or "").strip()
        if not current_version or current_version != session_version:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token revoked")
    elif settings.is_prod:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token upgrade required")
    return user


def current_admin(
    cred: HTTPAuthorizationCredentials = Depends(auth_scheme),
    admin_access_cookie: str | None = Cookie(default=None, alias="gw_admin_access"),
    db: Session = Depends(db_dep),
    auth_store=Depends(get_redis),
) -> AdminUser:
    token = cred.credentials if cred is not None and cred.credentials else str(admin_access_cookie or "").strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing token")
    try:
        payload = decode_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token") from exc
    if payload.get("scope") != "admin":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid scope")
    token_type = str(payload.get("typ") or "access").strip().lower()
    if token_type != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid scope")
    try:
        admin_id = int(payload["sub"])
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token") from exc
    admin = db.get(AdminUser, admin_id)
    if not admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="admin not found")
    if not getattr(admin, "is_active", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin disabled")
    session_version = str(payload.get("sv") or "").strip()
    if session_version:
        current_version = str(auth_store.get(auth_session_key("admin", str(admin.id))) or "").strip()
        if not current_version or current_version != session_version:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token revoked")
    elif settings.is_prod:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token upgrade required")
    return admin


def _resolve_partner_from_token(
    token: str | None,
    *,
    db: Session,
    auth_store,
    required: bool,
) -> PartnerChannel | None:
    normalized = str(token or "").strip()
    if not normalized:
        if required:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing token")
        return None
    try:
        payload = decode_token(normalized)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token") from exc
    if payload.get("scope") != "partner":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid scope")
    token_type = str(payload.get("typ") or "access").strip().lower()
    if token_type != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid scope")
    try:
        channel_id = int(payload["sub"])
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token") from exc
    channel = db.get(PartnerChannel, channel_id)
    if not channel:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="partner not found")
    if str(channel.status or "").strip().lower() != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="partner disabled")
    session_version = str(payload.get("sv") or "").strip()
    if session_version:
        current_version = str(auth_store.get(auth_session_key("partner", str(channel.id))) or "").strip()
        if not current_version or current_version != session_version:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token revoked")
    elif settings.is_prod:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token upgrade required")
    return channel


def current_partner(
    cred: HTTPAuthorizationCredentials = Depends(auth_scheme),
    partner_access_cookie: str | None = Cookie(default=None, alias="gw_partner_access"),
    db: Session = Depends(db_dep),
    auth_store=Depends(get_redis),
) -> PartnerChannel:
    token = cred.credentials if cred is not None and cred.credentials else str(partner_access_cookie or "").strip()
    channel = _resolve_partner_from_token(token, db=db, auth_store=auth_store, required=True)
    if channel is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing token")
    return channel


def optional_partner(
    cred: HTTPAuthorizationCredentials = Depends(auth_scheme),
    partner_access_cookie: str | None = Cookie(default=None, alias="gw_partner_access"),
    db: Session = Depends(db_dep),
    auth_store=Depends(get_redis),
) -> PartnerChannel | None:
    token = cred.credentials if cred is not None and cred.credentials else str(partner_access_cookie or "").strip()
    return _resolve_partner_from_token(token, db=db, auth_store=auth_store, required=False)


def current_super_admin(admin: AdminUser = Depends(current_admin)) -> AdminUser:
    if admin.role != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    return admin


def normalize_admin_permissions(value) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set)):
        return {str(item).strip() for item in value if str(item).strip()}
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return set()
        return {part.strip() for part in raw.split(",") if part.strip()}
    return set()


def _expand_permission_compat(permissions: set[str]) -> set[str]:
    expanded = set(permissions)
    if "configs:manage" in expanded:
        expanded.add("configs:view")
    return expanded


def admin_has_permission(admin: AdminUser, permission: str) -> bool:
    if not permission:
        return True
    if admin.role == "super_admin":
        return True
    permissions = normalize_admin_permissions(getattr(admin, "permissions_json", []))
    if not permissions:
        permissions = set(LEGACY_OPERATOR_DEFAULT_PERMISSIONS)
    permissions = _expand_permission_compat(permissions)
    if "*" in permissions:
        return True
    if permission in permissions:
        return True
    if ":" in permission:
        scope = permission.split(":", 1)[0]
        if f"{scope}:*" in permissions:
            return True
    return False


def require_admin_permission(permission: str) -> Callable[[AdminUser], AdminUser]:
    def _dep(admin: AdminUser = Depends(current_admin)) -> AdminUser:
        if admin_has_permission(admin, permission):
            return admin
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    return _dep
