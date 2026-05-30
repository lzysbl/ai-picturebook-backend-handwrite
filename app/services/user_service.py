"""用户账号服务。

职责：
- 管理用户注册、登录认证、用户查询和密码修改。
- 生成密码重置 token，并根据 token 完成密码重置。
- 为需要登录的业务接口提供用户身份基础数据。

前端关联：
- `/ui/login`：用户登录。
- `/ui/register`：用户注册。
- `/ui/forgot-password`：申请密码重置。
- `/ui/reset-password`：设置新密码。
- 其他业务页面会通过 `/api/users/me` 校验登录状态。

主要路由：
- `app/routers/users.py`：`/api/users/register`
- `app/routers/users.py`：`/api/users/login`
- `app/routers/users.py`：`/api/users/forgot-password`
- `app/routers/users.py`：`/api/users/reset-password`
- `app/routers/users.py`：`/api/users/me`
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.utils.security import generate_password_reset_token, hash_password, hash_reset_token, verify_password


def _pick_value(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    stmt = select(User).where(User.username == username.strip())
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    stmt = select(User).where(User.email == email.strip().lower())
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, user_in: Any) -> User:
    username = str(_pick_value(user_in, "username") or "").strip()
    email = str(_pick_value(user_in, "email") or "").strip().lower()
    password = _pick_value(user_in, "password")
    if not username or not email or not password:
        raise ValueError("用户名、邮箱和密码不能为空")

    if await get_user_by_username(db, username):
        raise ValueError("用户名已存在")
    if await get_user_by_email(db, email):
        raise ValueError("邮箱已被注册")

    user = User(username=username, email=email, password_hash=hash_password(password))
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ValueError("用户名或邮箱已存在") from exc
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, username: str, password: str) -> User | None:
    identity = username.strip()
    user = await get_user_by_username(db, identity)
    if not user and "@" in identity:
        user = await get_user_by_email(db, identity)
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


async def issue_password_reset_token(db: AsyncSession, email: str, expires_minutes: int) -> str | None:
    user = await get_user_by_email(db, email)
    if not user:
        return None

    token = generate_password_reset_token()
    user.reset_password_token_hash = hash_reset_token(token)
    user.reset_password_expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=expires_minutes)
    await db.commit()
    return token


async def reset_password_with_token(db: AsyncSession, token: str, new_password: str) -> bool:
    token_hash = hash_reset_token(token)
    stmt = select(User).where(User.reset_password_token_hash == token_hash)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user or not user.reset_password_expires_at:
        return False

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if user.reset_password_expires_at < now:
        user.reset_password_token_hash = None
        user.reset_password_expires_at = None
        await db.commit()
        return False

    user.password_hash = hash_password(new_password)
    user.reset_password_token_hash = None
    user.reset_password_expires_at = None
    await db.commit()
    return True


async def change_password(db: AsyncSession, user: User, old_password: str, new_password: str) -> None:
    if not verify_password(old_password, user.password_hash):
        raise ValueError("旧密码错误")

    user.password_hash = hash_password(new_password)
    user.reset_password_token_hash = None
    user.reset_password_expires_at = None
    await db.commit()
