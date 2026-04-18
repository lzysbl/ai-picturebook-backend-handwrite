"""安全工具：密码哈希与 JWT 签发/解析。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """将明文密码哈希存储。"""

    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """校验明文密码与哈希值是否匹配。"""

    return pwd_context.verify(plain_password, password_hash)


def create_access_token(data: dict[str, Any], expires_minutes: int | None = None) -> str:
    """创建 JWT 访问令牌。"""

    to_encode = data.copy()
    minutes = expires_minutes or settings.access_token_expire_minutes
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """解析 JWT 令牌，失败会抛 JWTError。"""

    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])


__all__ = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
    "JWTError",
]
